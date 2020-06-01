import asyncio
import os
import re
import shutil

import click
import pyperclip

from salmon import config
from salmon.common import commandgroup
from salmon.constants import ENCODINGS, FORMATS, SOURCES, TAG_ENCODINGS
from salmon.errors import AbortAndDeleteFolder, InvalidMetadataError

from salmon.gazelle import GazelleApi, validate_tracker, choose_tracker_first_time, choose_tracker

from salmon.tagger import (
    metadata_validator_base,
    validate_encoding,
    validate_source,
)
from salmon.tagger.audio_info import (
    check_hybrid,
    gather_audio_info,
    recompress_path,
)
from salmon.tagger.cover import download_cover_if_nonexistent
from salmon.tagger.foldername import rename_folder
from salmon.tagger.folderstructure import check_folder_structure
from salmon.tagger.metadata import get_metadata
from salmon.tagger.pre_data import construct_rls_data
from salmon.tagger.retagger import rename_files, tag_files
from salmon.tagger.review import review_metadata
from salmon.tagger.tags import check_tags, gather_tags, standardize_tags
from salmon.uploader.dupe_checker import (
    check_existing_group,
    generate_dupe_check_searchstrs,
)
from salmon.uploader.preassumptions import print_preassumptions
from salmon.uploader.spectrals import (
    check_spectrals,
    handle_spectrals_upload_and_deletion,
)
from salmon.uploader.upload import (
    concat_track_data,
    generate_lossy_approval_comment,
    prepare_and_upload,
    report_lossy_master,
)

loop = asyncio.get_event_loop()


@commandgroup.command()
@click.argument(
    "path", type=click.Path(exists=True, file_okay=False, resolve_path=True)
)
@click.option("--group-id", "-g", default=None, help="Group ID to upload torrent to")
@click.option(
    "--source",
    "-s",
    type=click.STRING,
    callback=validate_source,
    help=f'Source of files ({"/".join(SOURCES.values())})',
)
@click.option(
    "--lossy/--not-lossy",
    "-l/-L",
    default=None,
    help="Whether or not the files are lossy mastered",
)
@click.option(
    "--spectrals",
    "-sp",
    type=click.INT,
    multiple=True,
    help="Track numbers of spectrals to include in torrent description",
)
@click.option(
    "--overwrite",
    "-ow",
    is_flag=True,
    help="Whether or not to use the original metadata.",
)
@click.option(
    "--encoding",
    "-e",
    type=click.STRING,
    callback=validate_encoding,
    help=f"You must specify one of the following encodings if files aren't lossless: "
    + ", ".join(list(TAG_ENCODINGS.keys())),
)
@click.option(
    "--compress",
    "-c",
    is_flag=True,
    help="Recompress flacs to the configured compression level before uploading.",
)
@click.option("--tracker", "-t",
              callback=validate_tracker,
              help=f'Uploading Choices: ({"/".join(config.TRACKERS.keys())})')
def up(
        path,
        group_id,
        source, lossy,
        spectrals, overwrite,
        encoding, compress,
        tracker):
    """Upload an album folder to Gazelle Site"""

    if not tracker:
        tracker = choose_tracker_first_time()
    gazelle_site = GazelleApi(tracker)
    click.secho(f"Uploading to {gazelle_site.base_url}", fg="cyan")
    print_preassumptions(gazelle_site, path, group_id,
                         source, lossy, spectrals, encoding)
    upload(
        gazelle_site,
        path,
        group_id,
        source,
        lossy,
        spectrals,
        encoding,
        overwrite_meta=overwrite,
        recompress=compress,
    )


def upload(
    gazelle_site,
    path,
    group_id,
    source,
    lossy,
    spectrals,
    encoding,
    existing=None,
    overwrite_meta=False,
    recompress=False,
    source_url=None,
    searchstrs=None,
):
    """Upload an album folder to Gazelle Site"""
    path = os.path.abspath(path)
    if not source:
        source = _prompt_source()
    audio_info = gather_audio_info(path)
    hybrid = check_hybrid(audio_info)
    standardize_tags(path)
    tags = gather_tags(path)
    rls_data = construct_rls_data(
        tags,
        audio_info,
        source,
        encoding,
        existing=existing,
        overwrite=overwrite_meta,
        prompt_encoding=True,
    )

    try:
        if group_id is None:
            searchstrs = generate_dupe_check_searchstrs(
                rls_data["artists"], rls_data["title"], rls_data["catno"]
            )
            group_id = check_existing_group(gazelle_site, searchstrs)
        lossy_master, spectral_ids = check_spectrals(path, audio_info, lossy, spectrals)
        metadata = get_metadata(path, tags, rls_data)
        download_cover_if_nonexistent(path, metadata["cover"])
        path, metadata, tags, audio_info = edit_metadata(
            path, tags, metadata, source, rls_data, recompress
        )
        if not group_id:
            group_id = recheck_dupe(gazelle_site, searchstrs, metadata)
            click.echo()
        track_data = concat_track_data(tags, audio_info)
    except click.Abort:
        return click.secho(f"\nAborting upload...", fg="red")
    except AbortAndDeleteFolder:
        shutil.rmtree(path)
        return click.secho(f"\nDeleted folder, aborting upload...", fg="red")

    lossy_comment = None
    if lossy_master:
        lossy_comment = generate_lossy_approval_comment(
            source_url, list(track_data.keys())
        )
        click.echo()

    spectrals_path = os.path.join(path, "Spectrals")
    spectral_urls = handle_spectrals_upload_and_deletion(spectrals_path, spectral_ids)

    remaining_gazelle_sites = list(config.TRACKERS.keys())
    tracker = gazelle_site.site_code
    while True:
        # Loop until we don't want to upload to any more sites.
        if not tracker:
            click.secho("Would you like to upload to another tracker? ",
                        fg="magenta", nl=False)
            tracker = choose_tracker(remaining_gazelle_sites)
            click.secho(
                f"Uploading to {config.TRACKERS[tracker]['SITE_URL']}", fg="cyan")
            gazelle_site = GazelleApi(tracker)
            searchstrs = generate_dupe_check_searchstrs(
                rls_data["artists"], rls_data["title"], rls_data["catno"]
            )
            group_id = check_existing_group(gazelle_site, searchstrs, metadata)

        remaining_gazelle_sites.remove(tracker)

        torrent_id, group_id = prepare_and_upload(
            gazelle_site,
            path,
            group_id,
            metadata,
            track_data,
            hybrid,
            lossy_master,
            spectral_urls,
            lossy_comment,
        )
        if lossy_master:
            report_lossy_master(
                gazelle_site,
                torrent_id,
                spectral_urls,
                track_data,
                source,
                lossy_comment,
                source_url=source_url,
            )

        url = "{}/torrents.php?id={}&torrentid={}".format(
            gazelle_site.base_url, group_id, torrent_id)
        click.secho(
            f"\nSuccessfully uploaded {url} ({os.path.basename(path)}).",
            fg="green",
            bold=True,
        )
        if config.COPY_UPLOADED_URL_TO_CLIPBOARD:
            pyperclip.copy(url)
        tracker = None
        if not remaining_gazelle_sites:
            return click.secho(f"\nDone uploading this release.", fg="red")


def edit_metadata(path, tags, metadata, source, rls_data, recompress):
    """
    The metadata editing portion of the uploading process. This sticks the user
    into an infinite loop where the metadata process is repeated until the user
    decides it is ready for upload.
    """
    while True:
        metadata = review_metadata(metadata, metadata_validator)
        tag_files(path, tags, metadata)

        tags = check_tags(path)
        if recompress:
            recompress_path(path)
        path = rename_folder(path, metadata)
        rename_files(path, tags, metadata, source)
        check_folder_structure(path)

        if click.confirm(
            click.style(
                "\nWould you like to upload the torrent? (No to re-run metadata "
                "section)",
                fg="magenta",
                bold=True,
            ),
            default=True,
        ):
            metadata["tags"] = convert_genres(metadata["genres"])
            break

        # Refresh tags to accomodate differences in file structure.
        tags = gather_tags(path)

    tags = gather_tags(path)
    audio_info = gather_audio_info(path)
    return path, metadata, tags, audio_info


def recheck_dupe(gazelle_site, searchstrs, metadata):
    new_searchstrs = generate_dupe_check_searchstrs(
        metadata["artists"], metadata["title"], metadata["catno"]
    )
    if (
        searchstrs
        and any(n not in searchstrs for n in new_searchstrs)
        or not searchstrs
        and new_searchstrs
    ):
        click.secho('\nRechecking for dupes on', fg="cyan", bold=True, nl=False)
        click.secho(gazelle_site.site_string, bold=True, nl=False)
        click.secho('due to metadata changes...', bold=True)
        return check_existing_group(gazelle_site, new_searchstrs)


def metadata_validator(metadata):
    """Validate that the provided metadata is not an issue."""
    metadata = metadata_validator_base(metadata)
    if metadata["format"] not in FORMATS.values():
        raise InvalidMetadataError(f'{metadata["format"]} is not a valid format.')
    if metadata["encoding"] not in ENCODINGS:
        raise InvalidMetadataError(f'{metadata["encoding"]} is not a valid encoding.')

    return metadata


def convert_genres(genres):
    """Convert the weirdly spaced genres to RED-compliant genres."""
    return ",".join(re.sub("[-_ ]", ".", g).strip() for g in genres)


def _prompt_source():
    click.echo(f'\nValid sources: {", ".join(SOURCES.values())}')
    while True:
        sauce = click.prompt(
            click.style(
                f"What is the source of this release? [a]bort", fg="magenta", bold=True
            ),
            default="",
        )
        try:
            return SOURCES[sauce.lower()]
        except KeyError:
            if sauce.lower().startswith("a"):
                raise click.Abort
            click.secho(f"{sauce} is not a valid source.", fg="red")
