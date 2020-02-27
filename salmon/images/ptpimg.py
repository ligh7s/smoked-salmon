import contextlib
import mimetypes
import os

import requests

from salmon import config
from salmon.errors import ImageUploadFailed

mimetypes.init()
HEADERS = {"referer": "https://ptpimg.me/index.php", "User-Agent": config.USER_AGENT}


def upload_file(filename):
    with contextlib.ExitStack() as stack:
        files = {}
        open_file = stack.enter_context(open(filename, "rb"))
        mime_type, _ = mimetypes.guess_type(filename)
        if not mime_type or mime_type.split("/")[0] != "image":
            raise ValueError("Unknown image file type {}".format(mime_type))
        ext = os.path.splitext(filename)[1]
        files["file-upload[0]"] = (f"filename{ext}", open_file, mime_type)
        return _perform(files=files)


def _perform(files=None):
    data = {"api_key": config.PTPIMG_KEY}
    url = "https://ptpimg.me/upload.php"

    resp = requests.post(url, headers=HEADERS, data=data, files=files)
    if resp.status_code == requests.codes.ok:
        try:
            r = resp.json()[0]
            return f"https://ptpimg.me/{r['code']}.{r['ext']}", None
        except ValueError as e:
            raise ImageUploadFailed(
                f"Failed decoding body:\n{e}\n{resp.content}"
            ) from e
    else:
        raise ImageUploadFailed(f"Failed. Status {resp.status_code}:\n{resp.content}")
