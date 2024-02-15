import asyncio
import html
import importlib
import os
from urllib import parse

import click
import pyperclip

import salmon.checks
import salmon.converter
import salmon.database
import salmon.play
import salmon.search
import salmon.sources
import salmon.tagger
import salmon.uploader
import salmon.web  # noqa F401
from salmon import config
from salmon.common import commandgroup
from salmon.common import compress as recompress
from salmon.common import str_to_int_if_int
from salmon.tagger.audio_info import gather_audio_info
from salmon.tagger.combine import combine_metadatas
from salmon.tagger.metadata import clean_metadata, remove_various_artists
from salmon.tagger.retagger import create_artist_str
from salmon.tagger.sources import run_metadata
from salmon.uploader.spectrals import (
    check_spectrals,
    handle_spectrals_upload_and_deletion,
    post_upload_spectral_check,
)
from salmon.uploader.upload import generate_source_links

for name in os.listdir(
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "plugins")
):
    if not name.startswith(".") and not name.startswith("_"):
        if name.endswith(".py"):
            name = name[:-3]
        try:
            importlib.import_module(f"plugins.{name}")
        except ImportError as e:
            click.secho(
                f"The plugin {name} could not be imported.", fg="red", bold=True
            )
            raise e


loop = asyncio.get_event_loop()


@commandgroup.command()
@click.argument(
    "path", type=click.Path(exists=True, file_okay=False, resolve_path=True), nargs=1
)
@click.option("--no-delete-specs", "-nd", is_flag=True)
@click.option("--format-output", "-f", is_flag=True)
def specs(path, no_delete_specs, format_output):
    """Generate and open spectrals for a folder"""
    audio_info = gather_audio_info(path)
    _, sids = check_spectrals(path, audio_info, check_lma=False)
    spath = os.path.join(path, "Spectrals")
    spectral_urls = handle_spectrals_upload_and_deletion(
        spath, sids, delete_spectrals=not no_delete_specs
    )

    filenames = list(audio_info.keys())
    if spectral_urls:
        output = []
        for spec_id, urls in spectral_urls.items():
            if format_output:
                output.append(
                    f'[hide={filenames[spec_id]}][img={"][img=".join(urls)}][/hide]'
                )
            else:
                output.append(f'{filenames[spec_id]}: {" ".join(urls)}')
        output = "\n".join(output)
        click.secho(output)
        if config.COPY_UPLOADED_URL_TO_CLIPBOARD:
            pyperclip.copy(output)

    if no_delete_specs:
        click.secho(f'Spectrals saved to {os.path.join(path, "Spectrals")}', fg="green")


@commandgroup.command()
@click.argument("urls", type=click.STRING, nargs=-1)
def descgen(urls):
    """Generate a description from metadata sources"""
    if not urls:
        return click.secho("You must specify at least one URL", fg="red")
    tasks = [run_metadata(url, return_source_name=True) for url in urls]
    metadatas = loop.run_until_complete(asyncio.gather(*tasks))
    metadata = clean_metadata(combine_metadatas(*((s, m) for m, s in metadatas)))
    remove_various_artists(metadata["tracks"])

    description = "[b][size=4]Tracklist[/b]\n\n"
    multi_disc = len(metadata["tracks"]) > 1
    for dnum, disc in metadata["tracks"].items():
        for tnum, track in disc.items():
            if multi_disc:
                description += (
                    f"[b]{str_to_int_if_int(str(dnum), zpad=True)}-"
                    f"{str_to_int_if_int(str(tnum), zpad=True)}.[/b] "
                )
            else:
                description += f"[b]{str_to_int_if_int(str(tnum), zpad=True)}.[/b] "

            description += f'{create_artist_str(track["artists"])} - {track["title"]}\n'
    if metadata["comment"]:
        description += f"\n{metadata['comment']}\n"
    if metadata["urls"]:
        description += "\n[b]More info:[/b] " + generate_source_links(metadata["urls"])
    click.secho("\nDescription:\n", fg="yellow", bold=True)
    click.echo(description)
    if config.COPY_UPLOADED_URL_TO_CLIPBOARD:
        pyperclip.copy(description)


@commandgroup.command()
@click.argument(
    "path", type=click.Path(exists=True, file_okay=False, resolve_path=True)
)
def compress(path):
    """Recompress a directory of FLACs to level 8"""
    for root, _, figles in os.walk(path):
        for f in sorted(figles):
            if os.path.splitext(f)[1].lower() == ".flac":
                filepath = os.path.join(root, f)
                click.secho(f"Recompressing {filepath[len(path) + 1:]}...")
                recompress(filepath)


@commandgroup.command()
@click.option(
    "--torrent-id",
    "-i",
    default=None,
    help="Torrent id or URL, tracker from URL will overule -t flag.",
)
@click.option(
    "--tracker",
    "-t",
    help=f'Tracker choices: ({"/".join(salmon.trackers.tracker_list)})',
)
@click.argument(
    "path",
    type=click.Path(exists=True, file_okay=False, resolve_path=True),
    nargs=1,
    default=".",
)
def checkspecs(tracker, torrent_id, path):
    """Will check the spectrals of a given torrent based on local files.\n
    By default checks the folder the script is run from.
    Can add spectrals to a torrent description and report a torrent as lossy web.
    """
    if not torrent_id:
        click.secho("No torrent id provided.", fg="red")
        torrent_id = click.prompt(
            click.style(
                """Input a torrent id or a URL containing one.
                Tracker in a URL will override -t flag.""",
                fg="magenta",
                bold=True,
            ),
        )
    if "/torrents.php" in torrent_id:
        base_url = parse.urlparse(torrent_id).netloc
        if base_url in salmon.trackers.tracker_url_code_map.keys():
            # this will overide -t tracker
            tracker = salmon.trackers.tracker_url_code_map[base_url]
        else:
            click.echo('Unrecognised tracker!')
            raise click.Abort
        torrent_id = int(
            parse.parse_qs(parse.urlparse(torrent_id).query)['torrentid'][0]
        )
    elif torrent_id.strip().isdigit():
        torrent_id = int(torrent_id)
    else:
        click.echo('Not a valid torrent!')
        raise click.Abort
    tracker = salmon.trackers.validate_tracker(None, 'tracker', tracker)
    gazelle_site = salmon.trackers.get_class(tracker)()
    req = loop.run_until_complete(gazelle_site.request("torrent", id=torrent_id))
    path = os.path.join(path, html.unescape(req['torrent']['filePath']))
    source_url = None
    source = req['torrent']['media']
    click.echo(f"Generating spectrals for {source} sourced: {path}")
    track_data = gather_audio_info(path)
    post_upload_spectral_check(
        gazelle_site, path, torrent_id, None, track_data, source, source_url
    )
