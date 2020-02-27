import re
from collections import defaultdict

from salmon.errors import ScrapeError
from salmon.sources import BeatportBase
from salmon.tagger.sources.base import MetadataMixin

SPLIT_GENRES = {
    "Leftfield House & Techno": {"Leftfield House", "Techno"},
    "Melodic House & Techno": {"Melodic House", "Techno"},
    "Electronica / Downtempo": {"Electronic", "Downtempo"},
    "Funk / Soul / Disco": {"Funk", "Soul", "Disco"},
    "Trap / Future Bass": {"Trap", "Future Bass"},
    "Indie Dance / Nu Disco": {"Indie Dance", "Nu Disco"},
    "Hardcore / Hard Techno": {"Hard Techno"},
    "Funky / Groove / Jackin' House": {"Funky", "Groove", "Jackin' House"},
    "Hip-Hop / R&B": {"Hip-Hop", "Rhythm & Blues"},
    "Minimal / Deep Tech": {"Minimal", "Deep Tech"},
    "Garage / Bassline / Grime": {"Garage", "Bassline", "Grime"},
    "Reggae / Dancehall / Dub": {"Reggae", "Dancehall", "Dub"},
}


class Scraper(BeatportBase, MetadataMixin):
    def parse_release_title(self, soup):
        return soup.h1.string

    def parse_cover_url(self, soup):
        res = soup.select("img.interior-release-chart-artwork")
        try:
            return res[0]["src"]
        except IndexError as e:
            raise ScrapeError("Could not parse cover self.url.") from e

    def parse_genres(self, soup):
        genres = {"Electronic"}
        tracks_sc = soup.select(
            ".bucket.tracks.interior-release-tracks .bucket-item.ec-item.track"
        )
        for track in tracks_sc:
            for a in track.select(".buk-track-genre a"):
                try:
                    genres |= SPLIT_GENRES[a.string]
                except KeyError:
                    genres.add(a.string)
        return genres

    def parse_release_year(self, soup):
        date = self.parse_release_date(soup)
        try:
            return int(re.search(r"(\d{4})", date)[1])
        except (TypeError, IndexError) as e:
            raise ScrapeError("Could not parse release year.") from e

    def parse_release_date(self, soup):
        ul = soup.select(".interior-release-chart-content-item--desktop li")
        try:
            return ul[0].select("span.value")[0].string
        except IndexError as e:
            raise ScrapeError("Could not parse release date.") from e

    def parse_release_label(self, soup):
        ul = soup.select(".interior-release-chart-content-item--desktop li")
        try:
            return ul[1].select("a")[0].string
        except IndexError as e:
            raise ScrapeError("Could not parse record label.") from e

    def parse_release_catno(self, soup):
        ul = soup.select(".interior-release-chart-content-item--desktop li")
        try:
            return ul[2].select("span.value")[0].string
        except IndexError as e:
            raise ScrapeError("Could not parse catalog number.") from e

    def parse_comment(self, soup):
        try:
            return soup.select(".interior-expandable-wrapper .interior-expandable")[
                0
            ].text.strip()
        except IndexError:
            return None  # Comment does not exist.

    def parse_tracks(self, soup):
        tracks = defaultdict(dict)
        cur_disc = 1
        tracks_sc = soup.select(
            ".bucket.tracks.interior-release-tracks " ".bucket-item.ec-item.track"
        )
        for track in tracks_sc:
            try:
                track_num = track.select(".buk-track-num")[0].string
                tracks[str(cur_disc)][track_num] = self.generate_track(
                    trackno=track_num,
                    discno=cur_disc,
                    artists=parse_artists(track),
                    title=parse_title(track),
                )
            except (ValueError, IndexError) as e:
                raise ScrapeError("Could not parse tracks.") from e
        return dict(tracks)


def parse_title(track):
    """Add the remix string to the track title, as long as it's not OM."""
    title = track.select(".buk-track-primary-title")[0].string
    remix = track.select(".buk-track-remixed")
    if remix and remix[0].string != "Original Mix":  # yw pootsu
        title += (
            f" ({remix[0].string})"  # TODO: Move this into base class along with Tidal
        )
    return title


def parse_artists(track):
    """Parse remixers and main artists; return a list of them."""
    artists, remixers = [], []
    for artist in [e.string for e in track.select(".buk-track-artists a")]:
        for split in re.split(" & |; | / ", artist):
            artists.append(split)
    for remixer in [e.string for e in track.select(".buk-track-remixers a")]:
        for split in re.split(" & |; | / ", remixer):
            remixers.append(split)

    return [
        *((name, "main") for name in artists),
        *((name, "remixer") for name in remixers),
    ]
