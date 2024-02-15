import asyncio
import re
from itertools import chain

import click

from salmon import config
from salmon.common import (
    commandgroup,
    handle_scrape_errors,
    normalize_accents,
    re_split,
    re_strip,
)
from salmon.search import (
    bandcamp,
    beatport,
    deezer,
    discogs,
    itunes,
    junodownload,
    musicbrainz,
#    tidal,
)

SEARCHSOURCES = {
    "Bandcamp": bandcamp,
    "MusicBrainz": musicbrainz,
    "iTunes": itunes,
    "Junodownload": junodownload,
    "Discogs": discogs,
    "Beatport": beatport,
#    "Tidal": tidal,
    "Deezer": deezer,
}

loop = asyncio.get_event_loop()


@commandgroup.command()
@click.argument("searchstr", nargs=-1, required=True)
@click.option("--track-count", "-t", type=click.INT)
@click.option("--limit", "-l", type=click.INT, default=config.SEARCH_LIMIT)
def metas(searchstr, track_count, limit):
    """Search for releases from metadata providers"""
    searchstr = " ".join(searchstr)
    click.secho(f'Searching {", ".join(SEARCHSOURCES)}', fg="cyan", bold=True)
    results = run_metasearch([searchstr], limit=limit, track_count=track_count)
    not_found = []
    source_errors = SEARCHSOURCES.keys() - [r for r in results]
    for source, releases in results.items():
        if releases:
            click.secho(f"\nResults from {source}:", fg="yellow", bold=True)
            for rls_id, release in releases.items():
                rls_name = release[0][1]
                url = SEARCHSOURCES[source].Searcher.format_url(rls_id, rls_name)
                click.echo(f"> {release[1]} {url}")
        elif source:
            not_found.append(source)

    click.echo()
    for source in not_found:
        click.secho(f"No results found from {source}.", fg="red")
    if source_errors:
        click.secho(f'Failed to scrape {", ".join(source_errors)}.', fg="red")


def run_metasearch(
    searchstrs,
    limit=config.SEARCH_LIMIT,
    sources=None,
    track_count=None,
    artists=None,
    album=None,
    filter=True,
):
    """
    Run a search for releases matching the searchstr. Specify the artists and albums
    kwargs to have stronger filtering of results.
    """
    sources = (
        SEARCHSOURCES
        if not sources
        else {k: m for k, m in SEARCHSOURCES.items() if k in sources}
    )
    results = {}
    tasks = [
        handle_scrape_errors(s.Searcher().search_releases(search, limit))
        for search in searchstrs
        for s in sources.values()
    ]
    task_responses = loop.run_until_complete(asyncio.gather(*tasks))
    for source, result in [r or (None, None) for r in task_responses]:
        if result:
            if filter:
                result = filter_results(result, artists, album)
            if track_count:
                result = filter_by_track_count(result, track_count)
        results[source] = result
    return results


def filter_results(results, artists, album):
    filtered = {}
    for rls_id, result in (results or {}).items():
        if artists:
            split_artists = []
            for a in artists:
                split_artists += re_split(re_strip(normalize_accents(a)))
            stripped_rls_artist = re_strip(normalize_accents(result[0].artist))

            if "Various" in result[0].artist:
                if len(artists) == 1:
                    continue
            elif not any(a in stripped_rls_artist for a in split_artists):
                continue
            elif not any(
                a in stripped_rls_artist.split()
                for a in chain.from_iterable([a.split() for a in split_artists])
            ):
                continue
        if album:
            if not _compare_albums(album, result[0].album):
                continue
        filtered[rls_id] = result
    return filtered


def filter_by_track_count(results, track_count):
    filtered = {}
    for rls_id, (ident_data, res_str) in results.items():
        if not ident_data.track_count or abs(ident_data.track_count - track_count) <= 1:
            filtered[rls_id] = (ident_data, res_str)
    return filtered


def _compare_albums(one, two):
    one, two = normalize_accents(one, two)
    if re_strip(one) == re_strip(two):
        return True
    elif re_strip(
        re.sub(r" \(?(mix|feat|with|incl|prod).+", "", one, flags=re.IGNORECASE)
    ) == re_strip(
        re.sub(r" \(?(mix|feat|with|incl|prod).+", "", two, flags=re.IGNORECASE)
    ):
        return True
    return False
