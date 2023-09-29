import requests

from salmon import config
from salmon.errors import ImageUploadFailed
from salmon.images.base import BaseImageUploader


HEADERS = {"referer": "https://ptpimg.me/index.php", "User-Agent": config.USER_AGENT}


class ImageUploader(BaseImageUploader):
    def _perform(self, file_, ext):
        data = {"api_key": config.PTPIMG_KEY}
        url = "https://ptpimg.me/upload.php"
        files = {"file-upload[0]": file_}
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
