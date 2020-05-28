import asyncio
import os
import re
import shutil
import tempfile

import click
from dottorrent import Torrent

from salmon import config
from salmon.common import str_to_int_if_int
from salmon.constants import ARTIST_IMPORTANCES, RELEASE_TYPES
from salmon.images import upload_cover

from salmon.gazelle import RequestError


from salmon.sources import SOURCE_ICONS
from salmon.tagger.sources import METASOURCES

loop = asyncio.get_event_loop()


def prepare_and_upload(
    gazelle_site,
    path,
    group_id,
    metadata,
    track_data,
    hybrid,
    lossy_master,
    spectral_urls,
    lossy_comment,
):
    """Wrapper function for all the data compiling and processing."""
    if not group_id:
        cover_url = upload_cover(path)
        data = compile_data(
            path, metadata, track_data, hybrid, cover_url, spectral_urls, lossy_comment
        )
    else:
        data = compile_data_for_group(
            path, group_id, metadata, track_data, hybrid, spectral_urls, lossy_comment
        )
    torrent_path, torrent_file = generate_torrent(gazelle_site, path)
    files = compile_files(path, torrent_file, metadata)

    click.secho(f"Uploading torrent...", fg="yellow")
    try:
        torrent_id, group_id = loop.run_until_complete(gazelle_site.upload(data, files))
        shutil.move(
            torrent_path,
            os.path.join(config.DOTTORRENTS_DIR, f"{os.path.basename(path)}.torrent"),
        )
        return torrent_id, group_id
    except RequestError as e:
        click.secho(str(e), fg="red", bold=True)
        exit()


def report_lossy_master(
    gazelle_site,
    torrent_id,
    spectral_urls,
    track_data,
    source,
    comment,
    source_url=None
):
    """
    Generate the report description and call the function to report the torrent
    for lossy master approval. Use LWA if the torrent is web, otherwise LMA.
    """
    type_ = "lossywebapproval" if source == "WEB" else "lossyapproval"
    filenames = list(track_data.keys())
    comment = _add_spectral_links_to_lossy_comment(
        comment, source_url, spectral_urls, filenames
    )
    loop.run_until_complete(
        gazelle_site.report_lossy_master(torrent_id, comment, type_))
    click.secho("\nReported upload for Lossy Master/WEB Approval Request.", fg="cyan")


def generate_lossy_approval_comment(source_url, filenames):
    comment = click.prompt(
        click.style(
            "Do you have a comment for the lossy approval report? It is appropriate to "
            "make a note about the source here. Source information from go, gos, and the "
            "queue will be included automatically.",
            fg="cyan",
            bold=True,
        ),
        default="",
    )
    if not (comment or source_url):
        click.secho(
            f"This release was not uploaded with go, gos, or the queue, "
            "so you must add a comment about the source.",
            fg="red",
        )
        return generate_lossy_approval_comment(source_url, filenames)
    return comment


def _add_spectral_links_to_lossy_comment(comment, source_url, spectral_urls, filenames):
    if comment:
        comment += "\n\n"
    if source_url:
        comment += f"Sourced from: {source_url}\n\n"
    comment += "[u]Spectrals:[/u]"
    for spec_id, urls in spectral_urls.items():
        filename = re.sub(r"[\[\]]", "_", filenames[spec_id])
        comment += f'\n[hide={filename}][img={"][img=".join(urls)}][/hide]'
    return comment


def concat_track_data(tags, audio_info):
    """Combine the tag and audio data into one dictionary per track."""
    track_data = {}
    for k, v in audio_info.items():
        track_data[k] = {**v, "t": tags[k]}
    return track_data


def compile_data(
    path, metadata, track_data, hybrid, cover_url, spectral_urls, lossy_comment
):
    """
    Compile the data dictionary that needs to be submitted with a brand new
    torrent group upload POST.
    """
    return {
        "submit": True,
        "type": 0,
        "title": metadata["title"],
        "artists[]": [a[0] for a in metadata["artists"]],
        "importance[]": [ARTIST_IMPORTANCES[a[1]] for a in metadata["artists"]],
        "year": metadata["group_year"],
        "record_label": metadata["label"],
        "catalogue_number": metadata["catno"],
        "releasetype": RELEASE_TYPES[metadata["rls_type"]],
        "remaster": True,
        "remaster_year": metadata["year"],
        "remaster_title": metadata["edition_title"],
        "remaster_record_label": metadata["label"],
        "remaster_catalogue_number": metadata["catno"],
        "format": metadata["format"],
        "bitrate": metadata["encoding"],
        "other_bitrate": None,
        "vbr": metadata["encoding_vbr"],
        "media": metadata["source"],
        "tags": metadata["tags"],
        "image": cover_url,
        "album_desc": generate_description(track_data, metadata),
        "release_desc": generate_t_description(
            metadata, track_data, hybrid, metadata["urls"], spectral_urls, lossy_comment
        ),
    }


def compile_data_for_group(
    path, group_id, metadata, track_data, hybrid, spectral_urls, lossy_comment
):
    """Compile the data that needs to be submitted
     with an upload to an existing group."""
    return {
        "submit": True,
        "type": 0,
        "groupid": group_id,
        "remaster": True,
        "remaster_year": metadata["year"],
        "remaster_title": metadata["edition_title"],
        "remaster_record_label": metadata["label"],
        "remaster_catalogue_number": metadata["catno"],
        "format": metadata["format"],
        "bitrate": metadata["encoding"],
        "other_bitrate": None,
        "vbr": metadata["encoding_vbr"],
        "media": metadata["source"],
        "release_desc": generate_t_description(
            metadata, track_data, hybrid, metadata["urls"], spectral_urls, lossy_comment
        ),
    }


def compile_files(path, torrent_file, metadata):
    """
    Compile a list of file tuples that should be uploaded. This consists
    of the .torrent and any log files.
    """
    files = []
    files.append(
        ("file_input", ("meowmeow.torrent", torrent_file, "application/octet-stream"))
    )
    if metadata["source"] == "CD":
        files += attach_logfiles(path)
    return files


def attach_logfiles(path):
    """Attach all the log files that should be uploaded."""
    logfiles = []
    for root, _, files in os.walk(path):
        for filename in files:
            if filename.lower().endswith(".log"):
                filepath = os.path.abspath(os.path.join(root, filename))
                logfiles.append(
                    (filename, open(filepath, "rb"), "application/octet-stream")
                )
    return [("logfiles[]", lf) for lf in logfiles]


def generate_torrent(gazelle_site, path):
    """Call the dottorrent function to generate a torrent."""
    click.secho("Generating torrent file...", fg="yellow", nl=False)
    t = Torrent(path, trackers=[gazelle_site.announce],
                private=True, source=gazelle_site.site_string)
    t.generate()
    tpath = os.path.join(tempfile.gettempdir(),
                         f"{os.path.basename(path)} - {gazelle_site.site_string}.torrent")
    with open(tpath, "wb") as tf:
        t.save(tf)
    click.secho(" done!", fg="yellow")
    return tpath, open(tpath, "rb")


def generate_description(track_data, metadata):
    """Generate the group description with the tracklist and metadata source links."""
    description = "[b][size=4]Tracklist[/b]\n"
    multi_disc = any(
        t["t"].discnumber and int(t["t"].discnumber) > 1 for t in track_data.values()
    )

    for track in track_data.values():
        length = "{}:{:02d}".format(track["duration"] // 60, track["duration"] % 60)
        if multi_disc:
            description += (
                f'[b]{str_to_int_if_int(track["t"].discnumber, zpad=True)}-'
                f'{str_to_int_if_int(track["t"].tracknumber, zpad=True)}.[/b] '
            )
        else:
            description += (
                f'[b]{str_to_int_if_int(track["t"].tracknumber, zpad=True)}.[/b] '
            )

        description += (
            f'{", ".join(track["t"].artist)} - {track["t"].title} [i]({length})[/i]\n'
        )

    if metadata["comment"]:
        description += f"\n{metadata['comment']}\n"

    if metadata["urls"]:
        description += "\n[b]More info:[/b] " + generate_source_links(metadata["urls"])

    return description


def generate_t_description(
    metadata, track_data, hybrid, metadata_urls, spectral_urls, lossy_comment
):
    """
    Generate the torrent description. Add information about each file, and
    add the specrals URLs if any were specified.
    """
    description = ""

    if not hybrid:
        track = next(iter(track_data.values()))
        if track["precision"]:
            description += "Encode Specifics: {} bit {:.01f} kHz\n\n".format(
                track["precision"], track["sample rate"] / 1000
            )
        else:
            description += "Encode Specifics: {:.01f} kHz\n\n".format(
                track["sample rate"] / 1000
            )

    if metadata["date"]:
        description += f'Released on {metadata["date"]}\n\n'

    if config.INCLUDE_TRACKLIST_IN_T_DESC:
        for filename, track in track_data.items():
            description += os.path.splitext(filename)[0]
            description += " [i]({})[/i]".format(
                f'{track["duration"] // 60}:{track["duration"] % 60:02d}'
            )
            if config.BITRATES_IN_T_DESC:
                description += " [{:.01f}kbps]".format(track["bit rate"] / 1000)

            if hybrid:
                description += " [{} bit / {} kHz]".format(
                    track["precision"], track["sample rate"] / 1000
                )

            description += "\n"
        description += "\n"

    if lossy_comment and config.LMA_COMMENT_IN_T_DESC:
        description += f"[u]Lossy Notes:[/u]\n{lossy_comment}\n\n"

    if spectral_urls:
        filenames = list(track_data.keys())
        description += "[u]Spectrals:[/u]"
        for spec_id, urls in spectral_urls.items():
            filename = re.sub(r"[\[\]]", "_", filenames[spec_id])
            description += f'\n[hide={filename}][img={"][img=".join(urls)}][/hide]'
        description += "\n\n"

    if metadata_urls:
        description += "[b]More info:[/b] " + generate_source_links(metadata_urls)
        description += "\n"

    return description


def generate_source_links(metadata_urls):
    links = []
    for url in metadata_urls:
        for name, source in METASOURCES.items():
            if source.Scraper.regex.match(url):
                if config.ICONS_IN_DESCRIPTIONS:
                    links.append(
                        f"[pad=0|3][url={url}][img=18]{SOURCE_ICONS[name]}[/img] "
                        f"{name}[/url][/pad]"
                    )
                else:
                    links.append(f"[url={url}]{name}[/url]")
                break
    if config.ICONS_IN_DESCRIPTIONS:
        return " ".join(links)
    return " | ".join(links)
