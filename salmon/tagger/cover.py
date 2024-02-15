import os
import re

import click
import requests

from salmon import config


def download_cover_if_nonexistent(path, cover_url):
    for filename in os.listdir(path):
        if re.match(r"^(cover|folder)\.(jpe?g|png)$", filename, flags=re.IGNORECASE):
            return
    if cover_url:
        click.secho("\nDownloading cover image...", fg="yellow")
        _download_cover(path, cover_url)


def _download_cover(path, cover_url):
    ext = os.path.splitext(cover_url)[1]
    c = "c" if config.LOWERCASE_COVER else "C"
    headers = {'User-Agent': 'smoked-salmon-v1'}
    stream = requests.get(cover_url, stream=True, headers=headers)
    if stream.status_code < 400:
        with open(os.path.join(path, f"{c}over{ext}"), "wb") as f:
            for chunk in stream.iter_content(chunk_size=5096):
                if chunk:
                    f.write(chunk)
    else:
        click.secho(f"\nFailed to download cover image (ERROR {stream.status_code})", fg="red")
