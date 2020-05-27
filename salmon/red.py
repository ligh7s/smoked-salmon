from collections import namedtuple

from salmon.gazelle import GazelleApi
from salmon import config
from salmon.constants import RELEASE_TYPES
from salmon.errors import (
    LoginError,
    RateLimitError,
    RequestError,
    RequestFailedError,
)



ARTIST_TYPES = [
    "main",
    "guest",
    "remixer",
    "composer",
    "conductor",
    "djcompiler",
    "producer",
]

INVERTED_RELEASE_TYPES = {
    **dict(zip(RELEASE_TYPES.values(), RELEASE_TYPES.keys())),
    1024: "Guest Appearance",
    1023: "Remixed By",
    1022: "Composition",
    1021: "Produced By",
}


SearchReleaseData = namedtuple(
    "SearchReleaseData",
    ["lossless", "lossless_web", "year", "artist", "album", "release_type", "url"],
)
#This is for plugins that have not been updated.
RED_API = GazelleApi('RED')