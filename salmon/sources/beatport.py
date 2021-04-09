import re

from salmon.sources.base import BaseScraper


class BeatportBase(BaseScraper):

    url = site_url = "https://beatport.com"
    search_url = "https://beatport.com/search/releases"
    release_format = "/release/{rls_name}/{rls_id}"
    regex = re.compile(
        r"^https?://(?:(?:www|classic)\.)?beatport\.com/release/.+?/(\d+)/?$"
    )
