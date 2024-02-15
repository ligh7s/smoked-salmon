import asyncio
import os
import shutil
import tempfile
import re

import click
from dottorrent import Torrent

from salmon import config
from salmon.common import str_to_int_if_int
from salmon.constants import ARTIST_IMPORTANCES, RELEASE_TYPES
from salmon.errors import RequestError

from salmon.images import upload_cover
from salmon.sources import SOURCE_ICONS
from salmon.tagger.sources import METASOURCES
from salmon.uploader.spectrals import (
    generate_lossy_approval_comment,
    make_spectral_bbcode,
    report_lossy_master,
)

loop = asyncio.get_event_loop()


def prepare_and_upload(
    gazelle_site,
    path,
    group_id,
    metadata,
    cover_url,
    track_data,
    hybrid,
    lossy_master,
    spectral_urls,
    lossy_comment,
    request_id,
    source_url
):
    """Wrapper function for all the data compiling and processing."""
    if not group_id:
        if not cover_url:
            cover_url = upload_cover(path, scene=metadata['scene'])
        data = compile_data_new_group(
            path,
            metadata,
            track_data,
            hybrid,
            cover_url,
            spectral_urls,
            lossy_comment,
            request_id,
            source_url=source_url
        )
    else:
        data = compile_data_existing_group(
            path,
            group_id,
            metadata,
            track_data,
            hybrid,
            spectral_urls,
            lossy_comment,
            request_id,
            source_url=source_url
        )
    if not data['scene']:
        del data['scene']
    torrent_path, torrent_file = generate_torrent(gazelle_site, path)
    files = compile_files(path, torrent_file, metadata)

    click.secho("Uploading torrent...", fg="yellow")
    try:
        torrent_id = loop.run_until_complete(gazelle_site.upload(data, files))
        return torrent_id, torrent_path, torrent_file
    except RequestError as e:
        click.secho(str(e), fg="red", bold=True)
        exit()


def concat_track_data(tags, audio_info):
    """Combine the tag and audio data into one dictionary per track."""
    track_data = {}
    for k, v in audio_info.items():
        track_data[k] = {**v, "t": tags[k]}
    return track_data


def compile_data_new_group(
    path,
    metadata,
    track_data,
    hybrid,
    cover_url,
    spectral_urls,
    lossy_comment,
    request_id=None,
    source_url=None
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
        "catalogue_number": generate_catno(metadata),
        "releasetype": RELEASE_TYPES[metadata["rls_type"]],
        "remaster": True,
        "remaster_year": metadata["year"],
        "remaster_title": metadata["edition_title"],
        "remaster_record_label": metadata["label"],
        "remaster_catalogue_number": generate_catno(metadata),
        "format": metadata["format"],
        "bitrate": metadata["encoding"],
        "other_bitrate": None,
        "scene": metadata["scene"],
        "vbr": metadata["encoding_vbr"],
        "media": metadata["source"],
        "tags": metadata["tags"],
        "image": cover_url,
        "album_desc": generate_description(track_data, metadata),
        "release_desc": generate_t_description(
            metadata, track_data, hybrid, metadata["urls"], spectral_urls, lossy_comment, source_url
        ),
        'requestid': request_id,
    }


def compile_data_existing_group(
    path,
    group_id,
    metadata,
    track_data,
    hybrid,
    spectral_urls,
    lossy_comment,
    request_id,
    source_url=None
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
        "remaster_catalogue_number": generate_catno(metadata),
        "format": metadata["format"],
        "bitrate": metadata["encoding"],
        "scene": metadata["scene"],
        "other_bitrate": None,
        "vbr": metadata["encoding_vbr"],
        "media": metadata["source"],
        "release_desc": generate_t_description(
            metadata, track_data, hybrid, metadata["urls"], spectral_urls, lossy_comment, source_url
        ),
        'requestid': request_id,
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


def generate_catno(metadata):
    if config.USE_UPC_AS_CATNO:
        return ' / '.join(x for x in [metadata["catno"], metadata["upc"]] if x)
    else:
        return metadata["catno"]


def generate_torrent(gazelle_site, path):
    """Call the dottorrent function to generate a torrent."""
    click.secho("Generating torrent file...", fg="yellow", nl=False)
    t = Torrent(
        path,
        trackers=[gazelle_site.announce],
        private=True,
        source=gazelle_site.site_string,
    )
    t.generate()
    tpath = os.path.join(
        #tempfile.gettempdir(),
        gazelle_site.dot_torrents_dir,
        f"{os.path.basename(path)} - {gazelle_site.site_string}.torrent",
    )
    with open(tpath, "wb") as tf:
        t.save(tf)
    click.secho(" done!", fg="yellow")
    return tpath, open(tpath, "rb")


def generate_description(track_data, metadata):
    """Generate the group description with the tracklist and metadata source links."""
    description = "[b][size=4]Tracklist[/b]\n"
    multi_disc = any(
        t["t"].discnumber and (t["t"].discnumber.startswith('1/') or int(t["t"].discnumber) > 1) for t in track_data.values()
    )
    total_duration = 0
    for track in track_data.values():
        length = "{}:{:02d}".format(track["duration"] // 60, track["duration"] % 60)
        total_duration += track["duration"]
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

    if len(track_data.values()) > 1:
        description += "\n[b]Total length: [/b]{}:{:02d}\n".format(
            total_duration // 60, total_duration % 60
        )

    if metadata["comment"]:
        description += f"\n{metadata['comment']}\n"

    if metadata["urls"]:
        description += "\n[b]More info:[/b] " + generate_source_links(metadata["urls"])

    return description


def generate_t_description(
    metadata, track_data, hybrid, metadata_urls, spectral_urls, lossy_comment, source_url
):
    """
    Generate the torrent description. Add information about each file, and
    add the specrals URLs if any were specified.
    """
    description = ""
    if spectral_urls:
        description += make_spectral_bbcode(list(track_data.keys()), spectral_urls)

    if not hybrid:
        track = next(iter(track_data.values()))
        if track["precision"]:
            description += "Encode Specifics: {} bit {:.01f} kHz\n".format(
                track["precision"], track["sample rate"] / 1000
            )
        else:
            description += "Encode Specifics: {:.01f} kHz\n".format(
                track["sample rate"] / 1000
            )

    if metadata["date"]:
        description += f'Released on {metadata["date"]}\n'

    if config.INCLUDE_TRACKLIST_IN_T_DESC or hybrid:
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

    if source_url is not None:
        description += f"[b]Source:[/b]\n[url]{source_url}[/url]\n\n"

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
