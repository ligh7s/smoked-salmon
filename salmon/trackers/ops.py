from salmon.trackers.base import BaseGazelleApi

from salmon import config
import click
import requests
from requests.exceptions import ConnectTimeout, ReadTimeout


class OpsApi(BaseGazelleApi):
    def __init__(self):
        self.headers = {
            "Connection": "keep-alive",
            "Cache-Control": "max-age=0",
            "User-Agent": config.USER_AGENT,
        }
        self.site_code = 'OPS'
        self.base_url = 'https://orpheus.network'
        self.tracker_url = 'https://home.opsfet.ch'
        self.site_string = 'OPS'
        if config.OPS_TORRENTS_DIR:
            self.torrent_directory=config.OPS_TORRENTS_DIR
        else:
            self.torrent_directory=config.DOTTORRENTS_DIR

        self.cookie = config.OPS_SESSION

        self.session = requests.Session()
        self.session.headers.update(self.headers)

        self.authkey = None
        self.passkey = None
        self.authenticate()
