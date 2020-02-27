import asyncio
import contextlib
import mimetypes
import os
from random import choice

import requests

from salmon.constants import UAGENTS
from salmon.errors import ImageUploadFailed

mimetypes.init()
loop = asyncio.get_event_loop()
HEADERS = {
    "User-Agent": choice(UAGENTS),
    "Accept": "application/json",
    "Linx-Expiry": "0",
}


def upload_file(filename):
    # The ExitStack closes files for us when the with block exits
    with contextlib.ExitStack() as stack:
        open_file = stack.enter_context(open(filename, "rb"))
        mime_type, _ = mimetypes.guess_type(filename)
        if not mime_type or mime_type.split("/")[0] != "image":
            raise ValueError("Unknown image file type {}".format(mime_type))
        ext = os.path.splitext(filename)[1]
        return _perform((f"filename{ext}", open_file, mime_type), ext)


def _perform(file_, ext):
    url = "https://vgy.me/upload"
    files = {"file": file_}

    resp = requests.post(url, headers=HEADERS, files=files)
    if resp.status_code == requests.codes.ok:
        try:
            resp_data = resp.json()
            return resp_data["image"], resp_data["delete"]
        except ValueError as e:
            raise ImageUploadFailed from e
    else:
        raise ImageUploadFailed
