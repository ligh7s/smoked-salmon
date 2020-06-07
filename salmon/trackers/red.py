from salmon.trackers.base import BaseGazelleApi


from salmon import config
import click
import requests
from requests.exceptions import ConnectTimeout, ReadTimeout
from salmon.errors import (
    LoginError,
    RateLimitError,
    RequestError,
    RequestFailedError,
)#Do I understand imports?

class RedApi(BaseGazelleApi):
    def __init__(self):
        site_code='RED'
        tracker_details = config.TRACKERS[site_code]
        self.headers = {
            "Connection": "keep-alive",
            "Cache-Control": "max-age=0",
            "User-Agent": config.USER_AGENT,

        }
        self.site_code = site_code
        self.base_url = 'https://redacted.ch'
        self.tracker_url = 'https://flacsfor.me'
        self.site_string = 'RED'
        self.cookie = tracker_details['SITE_SESSION']
        if 'SITE_API_KEY' in tracker_details.keys():
            self.api_key = tracker_details['SITE_API_KEY']

        self.session = requests.Session()
        self.session.headers.update(self.headers)

        self.authkey = None
        self.passkey = None
        self.authenticate()

    async def report_lossy_master(self, torrent_id, comment, type_="lossywebapproval"):
        """Automagically report a torrent for lossy master/web approval."""
        url = self.base_url + "/reportsv2.php"
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