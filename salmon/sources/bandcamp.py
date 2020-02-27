import re

from salmon.sources.base import BaseScraper


class BandcampBase(BaseScraper):

    search_url = "https://bandcamp.com/search/"
    regex = re.compile(r"^https?://([^/]+)/album/([^/]+)/?")
    release_format = "https://{rls_url}/album/{rls_id}"

    @classmethod
    def format_url(cls, rls_id, rls_name=None):
        return cls.release_format.format(rls_url=rls_id[0], rls_id=rls_id[1])
