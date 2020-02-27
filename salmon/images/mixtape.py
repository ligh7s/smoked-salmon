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
    with contextlib.ExitStack() as stack:
        open_file = stack.enter_context(open(filename, "rb"))
        mime_type, _ = mimetypes.guess_type(filename)
        if not mime_type or mime_type.split("/")[0] != "image":
            raise ValueError("Unknown image file type {}".format(mime_type))
        ext = os.path.splitext(filename)[1]
        return _perform((f"filename{ext}", open_file, mime_type), ext)


def _perform(file_, ext):
    url = "https://mixtape.moe/upload.php"
    files = {"files[0]": file_}

    resp = requests.post(url, headers=HEADERS, files=files)
    if resp.status_code == requests.codes.ok:
        try:
            resp_data = resp.json()
            return resp_data["files"][0]["url"], None
        except ValueError as e:
            raise ImageUploadFailed(
                f"Failed decoding body:\n{e}\n{resp.content}"
            ) from e
    else:
        raise ImageUploadFailed(f"Failed. Status {resp.status_code}:\n{resp.content}")
