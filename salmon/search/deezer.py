import asyncio
import re
from itertools import chain

from salmon.search.base import ArtistRlsData, IdentData, SearchMixin
from salmon.sources import DeezerBase
from ratelimit import limits, sleep_and_retry

class Searcher(DeezerBase, SearchMixin):
    #@sleep_and_retry
    #@limits(49,5)
    async def search_releases(self, searchstr, limit):
        releases = {}
        resp = await self.get_json("/search/album", params={"q": searchstr})
        #print(resp)
        for rls in resp["data"]:
            releases[rls["id"]] = (
                IdentData(
                    rls["artist"]["name"], rls["title"], None, rls["nb_tracks"], "WEB"
                ),
                self.format_result(
                    rls["artist"]["name"],
                    rls["title"],
                    None,
                    track_count=rls["nb_tracks"],
                ),
            )
            if len(releases) == limit:
                break
        return "Deezer", releases

    async def get_artist_releases(self, artiststr):
        """
        Get the releases of an artist on Deezer. Find their artist page and request
        all their releases.
        """
        artist_ids = await self._get_artist_ids(artiststr)
        tasks = [
            self._get_artist_albums(artist_id, artiststr) for artist_id in artist_ids
        ]
        return "Deezer", list(chain.from_iterable(await asyncio.gather(*tasks)))

    async def _get_artist_ids(self, artiststr):
        resp = await self.get_json("/search/artist", params={"q": artiststr})
        return [a["id"] for a in resp["data"] if a["name"].lower() == artiststr.lower()]

    async def _get_artist_albums(self, artist_id, artist_name):
        resp = await self.get_json(f"/artist/{artist_id}/albums")
        return [
            ArtistRlsData(
                url=rls["link"],
                quality="LOSSLESS",  # Cannot determine.
                year=self._parse_year(rls["release_date"]),
                artist=artist_name,
                album=rls["title"],
                label="",
                explicit=rls["explicit_lyrics"],
            )
            for rls in resp["data"]
        ]

    @staticmethod
    def _parse_year(date):
        try:
            return int(re.search(r"(\d{4})", date)[0])
        except (ValueError, IndexError, TypeError):
            return None
