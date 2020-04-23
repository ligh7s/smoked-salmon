import re

from salmon import config
from salmon.errors import ScrapeError
from salmon.search.base import IdentData, SearchMixin
from salmon.sources import JunodownloadBase


class Searcher(JunodownloadBase, SearchMixin):
    async def search_releases(self, searchstr, limit):
        releases = {}
        soup = await self.create_soup(
            self.search_url,
            params={
                "submit-search": "SEARCH",
                "solrorder": "relevancy",
                "q[all][]": [searchstr],
            },
            allow_redirects=False,
        )
        for meta in soup.find_all('div', attrs = { 'class': 'row gutters-sm jd-listing-item', 'data-ua_location': 'release' } ):
            try:
                su_title = meta.find( 'a', attrs = { 'class': 'juno-title' } )
                rls_id = re.search(r"/products/[^/]+/([\d-]+)", su_title["href"])[1]
                title = su_title.string

                right_blob = meta.find('div', attrs = { 'class': 'text-sm mb-3 mb-lg-4' } )
                date = right_blob.find('br').next_sibling.strip()
                year = 2000 + int(date[-2:])
                catno = right_blob.find('br').previous_sibling.strip().replace(' ', '')

                ar_blob = meta.find('div', attrs = { 'class': 'col juno-artist'})

                ar_li = [
                    a.string.title()
                    for a in ar_blob.find_all('a')
                    if a.string
                ]
                artists = (
                    ", ".join(ar_li)
                    if ar_li and len(ar_li) < 5
                    else config.VARIOUS_ARTIST_WORD
                )

                label_blob = meta.find( 'a', attrs = { 'class': 'juno-label' } )
                label = label_blob.text.strip()

                if label.lower() not in config.SEARCH_EXCLUDED_LABELS:
                    releases[rls_id] = (
                        IdentData(artists, title, year, None, "WEB"),
                        self.format_result(artists, title, f"{year} {label} {catno}"),
                    )
            except (TypeError, IndexError) as e:
                raise ScrapeError("Failed to parse scraped search results.") from e
            if len(releases) == limit:
                break
        return "Junodownload", releases
