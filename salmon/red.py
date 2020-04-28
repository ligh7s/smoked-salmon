import asyncio
import html
import re
import sys
import time
from ratelimit import limits, sleep_and_retry
from collections import namedtuple
from json.decoder import JSONDecodeError

import click
import requests
from bs4 import BeautifulSoup
from requests.exceptions import ConnectTimeout, ReadTimeout

from salmon import config
from salmon.constants import RELEASE_TYPES
from salmon.errors import (
    LoginError,
    RateLimitError,
    RequestError,
    RequestFailedError,
)

loop = asyncio.get_event_loop()

ARTIST_TYPES = [
    "main",
    "guest",
    "remixer",
    "composer",
    "conductor",
    "djcompiler",
    "producer",
]

INVERTED_RELEASE_TYPES = {
    **dict(zip(RELEASE_TYPES.values(), RELEASE_TYPES.keys())),
    1024: "Guest Appearance",
    1023: "Remixed By",
    1022: "Composition",
    1021: "Produced By",
}


SearchReleaseData = namedtuple(
    "SearchReleaseData",
    ["lossless", "lossless_web", "year", "artist", "album", "release_type", "url"],
)


class RedApi:
    headers = {
        "Connection": "keep-alive",
        "Cache-Control": "max-age=0",
        "User-Agent": config.USER_AGENT,
        "Authorization": config.RED_API_KEY,
    }

    def __init__(self):
        self.base_url = "https://redacted.ch/"
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        self.last_rate_limit_expiry = time.time() - 10
        self.cur_req_count = 0
        self.cookie = config.RED_SESSION
        self.authkey = None
        self.passkey = None

    @property
    def announce(self):
        return f"https://flacsfor.me/{self.passkey}/announce"

    def authenticate(self):
        """Make a request to the RED API with the saved cookie and get our authkey."""
        self.session.cookies.clear()
        self.session.cookies["session"] = self.cookie
        try:
            acctinfo = loop.run_until_complete(self.request("index"))
        except RequestError:
            raise LoginError
        self.authkey = acctinfo["authkey"]
        self.passkey = acctinfo["passkey"]

    @sleep_and_retry
    @limits(5,10)
    async def request(self, action, **kwargs):
        """
        Make a request to the Redacted API, accomodating the rate limit.
        This method will create a counter and a timestamp, and ensure that
        the 5 requests / 10 seconds rate limit isn't violated, while allowing
        short bursts of requests without a 2 second wait after each one
        (at the expense of a potentially longer wait later).
        """

        url = self.base_url + "ajax.php"
        params = {"action": action, **kwargs}

        self.cur_req_count += 1
        try:
            resp = await loop.run_in_executor(
                None,
                lambda: self.session.get(
                    url, params=params, timeout=5, allow_redirects=False
                ),
            )
            # print(resp)  # debug
            resp = resp.json()
        except JSONDecodeError:
            raise RateLimitError
        except (ConnectTimeout, ReadTimeout):
            click.secho(
                f"Connection to RED API timed out, try script again later. Gomen!",
                fg="red",
            )
            sys.exit(1)

        if resp["status"] != "success":
            raise RequestFailedError
        return resp["response"]

    async def torrentgroup(self, group_id):
        """Get information about a torrent group."""
        return await self.request("torrentgroup", id=group_id)

    async def get_request(self, id):
        data = {"id": id}
        return await self.request("request", **data)

    async def artist_rls(self, artist):
        """
        Get all the torrent groups belonging to an artist on RED.
        All groups without a FLAC will be highlighted.
        """
        resp = await self.request("artist", artistname=artist)
        releases = []
        for group in resp["torrentgroup"]:
            # We do not put compilations or guest appearances in this list.
            if not group["artists"]:
                continue
            if group["releaseType"] == 7:
                if not group["extendedArtists"]["6"] or artist.lower() not in {
                    a["name"].lower() for a in group["extendedArtists"]["6"]
                }:
                    continue
            if group["releaseType"] in {1023, 1021, 1022, 1024}:
                continue

            releases.append(
                SearchReleaseData(
                    lossless=any(t["format"] == "FLAC" for t in group["torrent"]),
                    lossless_web=any(
                        t["format"] == "FLAC" and t["media"] == "WEB"
                        for t in group["torrent"]
                    ),
                    year=group["groupYear"],
                    artist=html.unescape(
                        compile_artists(group["artists"], group["releaseType"])
                    ),
                    album=html.unescape(group["groupName"]),
                    release_type=INVERTED_RELEASE_TYPES[group["releaseType"]],
                    url=f'https://redacted.ch/torrents.php?id={group["groupId"]}',
                )
            )

        releases = list({r.url: r for r in releases}.values())  # Dedupe

        return resp["id"], releases

    async def upload(self, data, files):
        """Attempt to upload a torrent to RED."""
        url = self.base_url + "ajax.php?action=upload"
        data["auth"] = self.authkey
        resp = await loop.run_in_executor(
            None,
            lambda: self.session.post(
                url, data=data, files=files, headers=self.headers
            ),
        )
        resp = resp.json()
        # print(resp) debug
        if resp["status"] != "success":
            raise RequestError(f"Upload failed: {resp['error']}")
        elif resp["status"] == "success":
            print(resp)
            return resp["response"]["torrentid"], resp["response"]["groupid"]

    async def report_lossy_master(self, torrent_id, comment, type_="lossywebapproval"):
        """Automagically report a torrent for lossy master/web approval."""
        url = self.base_url + "reportsv2.php"
        params = {"action": "takereport"}
        data = {
            "auth": self.authkey,
            "torrentid": torrent_id,
            "categoryid": 1,
            "type": type_,
            "extra": comment,
            "submit": True,
        }
        r = await loop.run_in_executor(
            None,
            lambda: self.session.post(
                url, params=params, data=data, headers=self.headers
            ),
        )
        if "torrents.php" in r.url:
            return True
        raise RequestError(
            f"Failed to report the torrent for lossy master, code {r.status_code}."
        )


def compile_artists(artists, release_type):
    """Generate a string to represent the artists."""
    if release_type == 7 or len(artists) > 3:
        return config.VARIOUS_ARTIST_WORD
    return " & ".join([a["name"] for a in artists])


RED_API = RedApi()
