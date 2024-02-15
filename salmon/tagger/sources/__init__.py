import asyncio

import click

from salmon.errors import ScrapeError
from salmon.tagger.sources import (
    bandcamp,
    beatport,
    deezer,
    discogs,
    itunes,
    junodownload,
    musicbrainz,
#    tidal,
)

METASOURCES = {
    "MusicBrainz": musicbrainz,
    "iTunes": itunes,
    "Junodownload": junodownload,
#    "Tidal": tidal,
    "Deezer": deezer,
    "Discogs": discogs,
    "Beatport": beatport,
    "Bandcamp": bandcamp,  # Must be last due to the catch-all nature of its URLs.
}

loop = asyncio.get_event_loop()


async def run_metadata(url, sources=None, return_source_name=False):
    """Run a scrape for the metadata of a URL"""
    sources = (
        METASOURCES
        if not sources
        else {name: source for name, source in METASOURCES.items() if name in sources}
    )
    for name, source in sources.items():
        if source.Scraper.regex.match(url):
            click.secho(f"Getting metadata from {name}.", fg="cyan")
            if return_source_name:
                return await source.Scraper().scrape_release(url), name
            return await source.Scraper().scrape_release(url)
    raise ScrapeError("URL did not match a scraper.")
