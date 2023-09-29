import asyncio
import contextlib
import mimetypes
import os
from random import choice

import requests
from bs4 import BeautifulSoup
from salmon.constants import UAGENTS
from salmon.errors import ImageUploadFailed

mimetypes.init()
loop = asyncio.get_event_loop()


class BaseImageUploader:
    def upload_file(self, filename):
        # The ExitStack closes files for us when the with block exits
        with contextlib.ExitStack() as stack:
            open_file = stack.enter_context(open(filename, "rb"))
            mime_type, _ = mimetypes.guess_type(filename)
            if not mime_type or mime_type.split("/")[0] != "image":
                raise ValueError("Unknown image file type {}".format(mime_type))
            ext = os.path.splitext(filename)[1]
            return self._perform((filename, open_file, mime_type), ext)
            # Do we need to strip filenames?
            # return self._perform((f"filename{ext}", open_file, mime_type), ext)
