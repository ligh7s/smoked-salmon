import config as user_config

DEFAULT_VALUES = {
    "IMGUR_CLIENT_ID": None,
    "IMGUR_CLIENT_SECRET": None,
    "IMGUR_REFRESH_TOKEN": None,
    "SIMULTANEOUS_DOWNLOADS": 2,
    "SIMULTANEOUS_SPECTRALS": 3,
    "SIMULTANEOUS_CONVERSIONS": 2,
    "USER_AGENT": "salmon uploading tools",
    "FOLDER_TEMPLATE": "{artists} - {title} ({year}) [{source} {format}] {{{label}}}",
    "FILE_TEMPLATE": "{tracknumber}. {artist} - {title}",
    "SEARCH_LIMIT": 3,
    "SEARCH_EXCLUDED_LABELS": {"edm comps"},
    "BLACKLISTED_GENRES": {"Soundtrack", "Asian Music"},
    "FLAC_COMPRESSION_LEVEL": 8,
    "TIDAL_TOKEN": "CzET4vdadNUFQ5JU",
    "TIDAL_SEARCH_REGIONS": ["DE", "NZ", "US", "GB"],
    "TIDAL_FETCH_REGIONS": ["DE", "NZ", "US", "GB"],
    "LOWERCASE_COVER": False,
    "VARIOUS_ARTIST_THRESHOLD": 4,
    "BLACKLISTED_SUBSTITUTION": "_",
    "GUESTS_IN_TRACK_TITLE": False,
    "NO_ARTIST_IN_FILENAME_IF_ONLY_ONE_ALBUM_ARTIST": True,
    "ONE_ALBUM_ARTIST_FILE_TEMPLATE": "{tracknumber}. {title}",
    "VARIOUS_ARTIST_WORD": "Various",
    "BITRATES_IN_T_DESC": False,
    "INCLUDE_TRACKLIST_IN_T_DESC": False,
    "COPY_UPLOADED_URL_TO_CLIPBOARD": False,
    "REVIEW_AS_COMMENT_TAG": True,
    "FEH_FULLSCREEN": True,
    "STRIP_USELESS_VERSIONS": True,
    "IMAGE_UPLOADER": "ptpimg",
    "COVER_UPLOADER": "ptpimg",
    "SPECS_UPLOADER": "emp",
    "ICONS_IN_DESCRIPTIONS": False,
    "FULLWIDTH_REPLACEMENTS": False,
    "NATIVE_SPECTRALS_VIEWER": False,
    "PROMPT_PUDDLETAG": False,
    "ADD_EDITION_TITLE_TO_ALBUM_TAG": True,
    "WEB_HOST": "http://127.0.0.1:55110",
    "WEB_PORT": 55110,
    "WEB_STATIC_ROOT_URL": "/static",
    "COMPRESS_SPECTRALS": False,
    "LMA_COMMENT_IN_T_DESC": False,
    "USE_UPC_AS_CATNO": True,
    "DEFAULT_TRACKER": False,
    "MULTI_TRACKER_UPLOAD": True,
    "RED_SESSION": False,
    "OPS_SESSION": False,
    "RED_API_KEY": False,
    "ALWAYS_ASK_FOR_REQUEST_FILL": False,
    "CHECK_RECENT_UPLOADS": True,
    "LOG_DUPE_TOLERANCE": 0.5,
    "CHECK_REQUESTS": True,
    "LAST_MINUTE_DUPE_CHECK": False,
    "RED_DOTTORRENTS_DIR": False,
    "OPS_DOTTORRENTS_DIR": False,
    "TRACKER_LIST": [],
}


class ConfigError(Exception):
    pass


class Config:
    def __getattr__(self, name):
        try:
            return getattr(user_config, name)
        except AttributeError:
            try:
                return DEFAULT_VALUES[name]
            except KeyError:
                raise ConfigError(
                    f"You are missing {name} in your config. Read UPGRADING.md."
                )


config = Config()
