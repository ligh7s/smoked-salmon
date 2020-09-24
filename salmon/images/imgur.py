import pyimgur

from salmon import config
from salmon.errors import ImageUploadFailed

CLIENT = pyimgur.Imgur(config.IMGUR_CLIENT_ID)

class ImageUploader:
    def upload_file(self, filename):
        try:
            url = CLIENT.upload_image(filename)
            return url.link, f"https://imgur.com/delete/{url.deletehash}"
        except Exception as e:
            raise ImageUploadFailed from e
