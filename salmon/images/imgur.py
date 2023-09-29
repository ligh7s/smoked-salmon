from pyimgurapi import ImgurAPI

from salmon import config
from salmon.errors import ImageUploadFailed

CLIENT = ImgurAPI(
    refresh_token=config.IMGUR_REFRESH_TOKEN,
    client_id=config.IMGUR_CLIENT_ID,
    client_secret=config.IMGUR_CLIENT_SECRET,
)


class ImageUploader:
    def upload_file(self, filename):
        try:
            CLIENT.auth()
            with open(filename, "rb") as f:
                url = CLIENT.image.upload(
                    f,
                    filename
                ).data
            return url.link, f"https://imgur.com/delete/{url.deletehash}"
        except Exception as e:
            raise ImageUploadFailed from e
