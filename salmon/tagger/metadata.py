import asyncio
import json
from copy import copy
from itertools import islice

import click

from salmon import config
from salmon.common import handle_scrape_errors, make_searchstrs, re_strip
from salmon.search import SEARCHSOURCES, run_metasearch
from salmon.tagger.combine import combine_metadatas
from salmon.tagger.sources import METASOURCES
from salmon.tagger.sources.base import generate_artists

loop = asyncio.get_event_loop()


def get_metadata(path, tags, rls_data=None):
    """
    Get metadata pertaining to a release from various metadata sources. Have the user
    decide which sources to use, and then combine their information.
    """
    click.secho("\nChecking metadata...", fg="cyan", bold=True)
    searchstrs = make_searchstrs(rls_data["artists"], rls_data["title"])
    kwargs = (
        dict(artists=[a for a, _ in rls_data["artists"]], album=rls_data["title"])
        if rls_data
        else {}
    )
    search_results = run_metasearch(
        searchstrs, filter=False, track_count=len(tags), **kwargs
    )
    choices = _print_search_results(search_results, rls_data)
    metadata = _select_choice(choices, rls_data)
    remove_various_artists(metadata["tracks"])
    return metadata


def _print_search_results(results, rls_data=None):
    """Print the results from the metadata source."""
    if rls_data:
        _print_metadata(rls_data, metadata_name="Previous")

    choices = {}
    choice_id = 1
    not_found = list(SEARCHSOURCES.keys())
    for source, releases in results.items():
        if releases:
            click.secho(f"\nResults for {source}:", fg="yellow", bold=True)
            not_found.remove(source)
            results = dict(islice(releases.items(), config.SEARCH_LIMIT))
            for rls_id, release in results.items():
                choices[choice_id] = (source, rls_id)
                url = SEARCHSOURCES[source].Searcher.format_url(rls_id)
                click.secho(f"> {choice_id:02d} {release[1]} | {url}")
                choice_id += 1

    if not_found:
        click.echo()
        for source in not_found:
            click.echo(f"No results found from {source}.")

    return choices


def _select_choice(choices, rls_data):
    """
    Allow the user to select a metadata choice. Then, if the metadata came from a scraper,
    run the scrape(s) and return combined metadata.
    """
    while True:
        if choices:
            res = click.prompt(
                click.style(
                    "\nWhich metadata results would you like to use? Other "
                    "options: paste URLs, [m]anual, [a]bort",
                    fg="magenta",
                    bold=True,
                ),
                type=click.STRING,
            )
        else:
            res = click.prompt(
                click.style(
                    "\nNo metadata results were found. Options: paste URLs, "
                    "[m]anual, [a]bort",
                    fg="magenta",
                    bold=True,
                ),
                type=click.STRING,
            )

        if res.lower().startswith("m"):
            return _get_manual_metadata(rls_data)
        elif res.lower().startswith("a"):
            raise click.Abort

        sources, tasks = [], []
        for r in res.split():
            if r.lower().startswith("http"):
                for name, source in METASOURCES.items():
                    if source.Scraper.regex.match(r.strip()):
                        sources.append(name)
                        tasks.append(source.Scraper().scrape_release(r.strip()))
                        break
            elif r.strip().isdigit() and int(r) in choices:
                scraper = METASOURCES[choices[int(r)][0]].Scraper()
                sources.append(choices[int(r)][0])
                tasks.append(
                    handle_scrape_errors(
                        scraper.scrape_release_from_id(choices[int(r)][1])
                    )
                )
        if not tasks:
            continue

        metadatas = loop.run_until_complete(asyncio.gather(*tasks))
        meta = combine_metadatas(
            *((s, m) for s, m in zip(sources, metadatas) if m), base=rls_data
        )
        meta = clean_metadata(meta)
        meta["artists"], meta["tracks"] = generate_artists(meta["tracks"])
        return meta


def _get_manual_metadata(rls_data):
    """
    Use the metadata built from the file tags as a base, then allow the user to edit
    that dictionary.
    """
    metadata = json.dumps(rls_data, indent=2)
    while True:
        try:
            metadata = click.edit(metadata, extension=".json") or metadata
            metadata_dict = json.loads(metadata)
            if isinstance(metadata_dict["genres"], str):
                metadata_dict["genres"] = [metadata_dict["genres"]]
            return metadata_dict
        except (TypeError, json.decoder.JSONDecodeError):
            click.confirm(
                click.style(
                    "Metadata is not a valid JSON file, retry?", fg="magenta", bold=True
                ),
                default=True,
                abort=True,
            )


def _print_metadata(metadata, metadata_name="Pending"):
    """Print the metadata that is a part of the new metadata."""
    click.secho(f"\n{metadata_name} metadata:", fg="yellow", bold=True)
    click.echo(
        f"> TRACK COUNT   : {sum(len(d.values()) for d in metadata['tracks'].values())}"
    )
    click.echo("> ARTISTS:")
    for artist in metadata["artists"]:
        click.echo(f">>>  {artist[0]} [{artist[1]}]")
    click.echo(f"> TITLE         : {metadata['title']}")
    click.echo(f"> GROUP YEAR    : {metadata['group_year']}")
    click.echo(f"> YEAR          : {metadata['year']}")
    click.echo(f"> EDITION TITLE : {metadata['edition_title']}")
    click.echo(f"> LABEL         : {metadata['label']}")
    click.echo(f"> CATNO         : {metadata['catno']}")
    click.echo(f"> UPC           : {metadata['upc']}")
    click.echo(f"> GENRES        : {'; '.join(metadata['genres'])}")
    click.echo(f"> RELEASE TYPE  : {metadata['rls_type']}")
    click.echo(f"> COMMENT       : {metadata['comment']}")
    click.echo("> URLS:")
    for url in metadata["urls"]:
        click.echo(f">>> {url}")


def remove_various_artists(tracks):
    for dnum, disc in tracks.items():
        for tnum, track in disc.items():
            artists = []
            for artist, importance in track["artists"]:
                if (
                    "various artists" not in artist.lower()
                    or artist.lower().strip() != "various"
                ):
                    artists.append((artist, importance))
            track["artists"] = artists


def clean_metadata(metadata):
    for disc, tracks in metadata["tracks"].items():
        for num, track in tracks.items():
            for artist, importance in copy(track["artists"]):
                guest_artists = {
                    re_strip(a)
                    for a, i in track["artists"]
                    if i in {"guest", "remixer"}
                }
                if re_strip(artist) in guest_artists and importance == "main":
                    if (
                        sum(
                            'main' in item
                            for item in metadata["tracks"][disc][num]["artists"]
                        )
                        == 1
                    ):
                        pass
                    else:
                        metadata["tracks"][disc][num]["artists"].remove(
                            (artist, importance)
                        )

    if metadata["catno"] and metadata["catno"].replace(" ", "") == str(metadata["upc"]):
        metadata["catno"] = None
    return metadata
