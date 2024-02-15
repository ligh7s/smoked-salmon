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
        self.site_code = 'RED'
        self.base_url = 'https://redacted.ch'
        self.tracker_url = 'https://flacsfor.me'
        self.site_string = 'RED'
        self.cookie = config.RED_SESSION
        if config.RED_API_KEY:
            self.api_key = config.RED_API_KEY

        if config.RED_DOTTORRENTS_DIR:
            self.dot_torrents_dir = config.RED_DOTTORRENTS_DIR
        else:
            self.dot_torrents_dir = config.DOTTORRENTS_DIR

        super().__init__()

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
