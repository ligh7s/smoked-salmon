import click
import requests
import asyncio
from requests.exceptions import ConnectTimeout, ReadTimeout

from salmon.trackers.base import BaseGazelleApi
from salmon import config
from salmon.errors import (
    LoginError,
    RateLimitError,
    RequestError,
    RequestFailedError,
)

loop = asyncio.get_event_loop()


class RedApi(BaseGazelleApi):
    def __init__(self):
        self.headers = {
            "Connection": "keep-alive",
            "Cache-Control": "max-age=0",
            "User-Agent": config.USER_AGENT,

        }
        self.site_code = 'RED'
        self.base_url = 'https://redacted.ch'
        self.tracker_url = 'https://flacsfor.me'
        self.site_string = 'RED'
        self.cookie = config.RED_SESSION
        if config.RED_API_KEY:
            self.api_key = config.RED_API_KEY

        self.session = requests.Session()
        self.session.headers.update(self.headers)

        self.authkey = None
        self.passkey = None
        self.authenticate()

    async def report_lossy_master(self, torrent_id, comment, source):
        """Automagically report a torrent for lossy master/web approval.
         Use LWA if the torrent is web, otherwise LMA."""

        url = self.base_url + "/reportsv2.php"
        params = {"action": "takereport"}
        type_ = "lossywebapproval" if source == "WEB" else "lossyapproval"
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
