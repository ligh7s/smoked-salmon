from salmon.trackers.base import BaseGazelleApi

from salmon import config
import click
import requests
from requests.exceptions import ConnectTimeout, ReadTimeout


class OpsApi(BaseGazelleApi):
    def __init__(self):
        site_code='OPS'
        tracker_details = config.TRACKERS[site_code]
        self.headers = {
            "Connection": "keep-alive",
            "Cache-Control": "max-age=0",
            "User-Agent": config.USER_AGENT,

        }
        self.site_code = site_code
        self.base_url = 'https://orpheus.network'
        self.tracker_url = 'https://home.opsfet.ch'
        self.site_string = 'OPS'
        
        self.cookie = tracker_details['SITE_SESSION']

        self.session = requests.Session()
        self.session.headers.update(self.headers)

        self.authkey = None
        self.passkey = None
        self.authenticate()