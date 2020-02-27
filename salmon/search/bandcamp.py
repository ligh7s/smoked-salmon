import re

from salmon.errors import ScrapeError
from salmon.search.base import IdentData, SearchMixin
from salmon.sources import BandcampBase


class Searcher(BandcampBase, SearchMixin):
    async def search_releases(self, searchstr, limit):
        releases = {}
        soup = await self.create_soup(
            self.search_url, params={"q": searchstr}, allow_redirects=False
        )
        for meta in soup.select(".result-items .searchresult.album .result-info"):
            try:
                re_url = self.regex.search(meta.select(".itemurl a")[0].string)
                rls_url = re.sub(r"\?.+", "", re_url[1])
                rls_id = re_url[2]
                title = meta.select(".heading a")[0].string.strip()
                title = title if len(title) < 100 else f"{title[:98]}.."
                artists = re.search("by (.+)", meta.select(".subhead")[0].text)[
                    1
                ].strip()
                track_count = int(
                    re.search(r"(\d+) tracks?", meta.select(".length")[0].text)[1]
                )

                releaser = rls_url.split(".bandcamp.com")[0]

                date = meta.select(".released")[0].text.strip()
                year = re.search(r"(\d{4})", date)[1]

                releases[(rls_url, rls_id)] = (
                    IdentData(artists, title, year, track_count, "WEB"),
                    self.format_result(
                        artists, title, f"{year} {releaser}", track_count=track_count
                    ),
                )
            except (TypeError, IndexError) as e:
                raise ScrapeError("Failed to parse scraped search results.") from e
            if len(releases) == limit:
                break
        return "Bandcamp", releases
