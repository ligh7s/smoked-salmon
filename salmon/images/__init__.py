import asyncio
import os
import re
import sqlite3

import click
import pyperclip

from salmon import config
from salmon.common import AliasedCommands, commandgroup
from salmon.database import DB_PATH
from salmon.errors import ImageUploadFailed
from salmon.images import catbox, emp, imgur, ptpimg

loop = asyncio.get_event_loop()

HOSTS = {
    "ptpimg": ptpimg,
    "imgur": imgur,
    "emp": emp,
    "catbox": catbox,
}


def validate_image_host(ctx, param, value):
    try:
        return HOSTS[value]
    except KeyError:
        raise click.BadParameter(f"{value} is not a valid image host")


@commandgroup.group(cls=AliasedCommands)
def images():
    """Create and manage uploads to image hosts"""
    pass


@images.command()
@click.argument(
    "filepaths",
    type=click.Path(exists=True, dir_okay=False, resolve_path=True),
    nargs=-1,
)
@click.option(
    "--image-host",
    "-i",
    help="The name of the image host to upload to",
    default=config.IMAGE_UPLOADER,
    callback=validate_image_host,
)
def up(filepaths, image_host):
    """Upload images to an image host"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        urls = []
        upload_function = image_host.ImageUploader().upload_file
        try:
            tasks = [
                loop.run_in_executor(None, lambda f=f: upload_function(f))
                for f in filepaths
            ]
            for url, deletion_url in loop.run_until_complete(asyncio.gather(*tasks)):
                cursor.execute(
                    "INSERT INTO image_uploads (url, deletion_url) VALUES (?, ?)",
                    (url, deletion_url),
                )
                click.secho(url)
                urls.append(url)
            conn.commit()
            if config.COPY_UPLOADED_URL_TO_CLIPBOARD:
                pyperclip.copy("\n".join(urls))
        except (ImageUploadFailed, ValueError) as error:
            click.secho(f"Image Upload Failed. {error}", fg="red")
            raise ImageUploadFailed("Failed to upload image") from error


@images.command()
@click.option(
    "--limit", "-l", type=click.INT, default=20, help="The number of images to show"
)
@click.option(
    "--offset",
    "-o",
    type=click.INT,
    default=0,
    help="The number of images to offset by",
)
def ls(limit, offset):
    """View previously uploaded images"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, url, deletion_url, time FROM image_uploads "
            "ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        for row in cursor.fetchall():
            click.secho("")
            click.secho(f"{row['id']:04d}. ", fg="yellow", nl=False)
            click.secho(f"{row['time']} ", fg="green", nl=False)
            click.secho(f"{row['url']} ", fg="cyan", nl=False)
            if row["deletion_url"]:
                click.secho(f"Delete: {row['deletion_url']}", fg="red")


def chunker(seq, size=4):
    for pos in range(0, len(seq), size):
        yield seq[pos : pos + size]


def upload_cover(path, scene=False):
    """
    Search a folder for a cover image, and if found, upload it.
    The image url is returned, otherwise None.
    """
    for filename in os.listdir(path):
        if re.match(r"^(cover|folder)\.(jpe?g|png)$", filename, flags=re.IGNORECASE) or (scene and re.match(r"^.*\.(jpe?g|png)$", filename, flags=re.IGNORECASE)):
            click.secho(
                f"Uploading cover to {config.COVER_UPLOADER}...", fg="yellow", nl=False
            )
            try:
                fpath = os.path.join(path, filename)
                try:
                    url = loop.run_until_complete(
                        loop.run_in_executor(
                            None,
                            lambda: HOSTS[config.COVER_UPLOADER]
                            .ImageUploader()
                            .upload_file(fpath)[0],
                        )
                    )
                except (ImageUploadFailed, ValueError) as error:
                    click.secho(f"Image Upload Failed. {error}", fg="red")
                    raise ImageUploadFailed("Failed to upload image") from error
            except ImageUploadFailed:
                return click.secho(" failed :(", fg="red")
            click.secho(f" done! {url}", fg="yellow")
            return url
    click.secho(
        f"Did not find a cover to upload to {config.IMAGE_UPLOADER}...", fg="red"
    )


def upload_spectrals(spectrals, uploader=HOSTS[config.SPECS_UPLOADER], successful=None):
    """
    Given the spectrals list of (filename, [spectral_url, ..]), send them
    to the coroutine upload handller and return a dictionary of filenames
    and spectral urls.
    """
    response = {}
    successful = successful or set()
    one_failed = False
    upload_function = uploader.ImageUploader().upload_file
    for specs_block in chunker(spectrals):
        tasks = [
            _spectrals_handler(sid, filename, sp, upload_function)
            for sid, filename, sp in specs_block
            if sid not in successful
        ]
        for sid, urls in loop.run_until_complete(asyncio.gather(*tasks)):
            if urls:
                response = {**response, sid: urls}
                successful.add(sid)
            else:
                one_failed = True
        if one_failed:
            return {**response, **_handle_failed_spectrals(spectrals, successful)}
    return response


def _handle_failed_spectrals(spectrals, successful):
    while True:
        host = click.prompt(
            click.style(
                "Some spectrals failed to upload. Which image host would you like to retry "
                f'with? (Options: {", ".join(HOSTS.keys())})',
                fg="magenta",
                bold=True,
            ),
            default="ptpimg",
        ).lower()
        if host not in HOSTS:
            click.secho(
                f"{host} is an invalid image host. Please choose another one.", fg="red"
            )
        else:
            return upload_spectrals(
                spectrals, uploader=HOSTS[host], successful=successful
            )


async def _spectrals_handler(spec_id, filename, spectral_paths, uploader):
    try:
        click.secho(f"Uploading spectrals for {filename}...", fg="yellow")
        tasks = [
            loop.run_in_executor(None, lambda f=f: uploader(f)[0])
            for f in spectral_paths
        ]
        return spec_id, await asyncio.gather(*tasks)
    except ImageUploadFailed as e:
        click.secho(f"Failed to upload spectrals for {filename}: {e}", fg="red")
        return spec_id, None
