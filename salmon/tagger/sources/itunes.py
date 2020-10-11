import re
from collections import defaultdict
from datetime import datetime

import json

from salmon.common import RE_FEAT, parse_copyright
from salmon.errors import ScrapeError
from salmon.sources import iTunesBase
from salmon.tagger.sources.base import MetadataMixin

ALIAS_GENRE = {
    "Hip-Hop/Rap": {"Hip Hop", "Rap"},
    "R&B/Soul": {"Rhythm & Blues", "Soul"},
    "Music": {},
}


class Scraper(iTunesBase, MetadataMixin):
    def parse_release_title(self, soup):
        try:
            title = soup.select(".product-name")[0].text.strip()
            return RE_FEAT.sub("", title)
        except (TypeError, IndexError) as e:
            raise ScrapeError("Failed to parse scraped title.") from e

    def parse_cover_url(self, soup):
        try:
            # Just choosing the last artwork url here.
            art = (
                soup.select(".product-lockup__artwork-for-product")[0]
                .img['srcset']
                .split(",")
            )
            return art[-1].split()[0]
        except (TypeError, IndexError) as e:
            raise ScrapeError("Could not parse cover URL.") from e

    def parse_genres(self, soup):
        try:
            info = json.loads(soup.find(attrs={"name": "schema:music-album"}).text)
            genres = {g for gs in info['genre'] for g in ALIAS_GENRE.get(gs, [gs])}
            # either replace with alias (which can be more than one tag) or return untouched.
            return genres
        except (TypeError, IndexError) as e:
            raise ScrapeError("Could not parse genres.") from e

    def parse_release_year(self, soup):
        try:
            return int(re.search(r"(\d{4})", self.parse_release_date(soup))[1])
        except TypeError as e:
            raise ScrapeError("Could not parse release year.") from e

    def parse_release_date(self, soup):
        # This can't be enough. Can it?
        try:
            date_string = soup.find(attrs={"property": "music:release_date"})[
                'content'
            ].split("T")[0]
            return date_string
        except:
            return None

    def parse_release_label(self, soup):
        try:
            return parse_copyright(
                soup.select(".song-copyright")[0].string.lower().title()
            )
        except IndexError as e:
            raise ScrapeError("Could not parse record label.") from e

    def parse_comment(self, soup):
        try:
            return soup.select(".product-hero-desc .product-hero-desc__section > p")[0][
                "aria-label"
            ].strip()
        except IndexError:
            return None

    def parse_tracks(self, soup):

        tracks = defaultdict(dict)
        cur_disc = 1

        for track in soup.select(".web-preview"):
            try:
                try:
                    num = (
                        track.select(".song-index")[0]
                        .select(".column-data")[0]
                        .string.strip()
                    )
                except IndexError:
                    continue
                raw_title = track.select(".song-name")[0].text.strip()
                title = RE_FEAT.sub("", raw_title)
                explicit = bool(track.select(".badge.explicit.default"))
                # Itunes silently increments disc number.
                if int(num) == 1 and num in tracks[str(cur_disc)]:
                    cur_disc += 1

                tracks[str(cur_disc)][num] = self.generate_track(
                    trackno=int(num),
                    discno=cur_disc,
                    artists=parse_artists(soup, track, raw_title),
                    title=title,
                    explicit=explicit,
                )
            except (ValueError, IndexError) as e:
                raise e
                raise ScrapeError("Could not parse tracks.") from e

        return dict(tracks)


def parse_artists(soup, track, title):
    """
    Parse all the artists from various locations and compile a split
    list of all of them.  This is not foolproof, but better than the
    alternative. Artists such as Vintage & Morelli will fuck this up,
    but that is why we have manual confirmation for metadata.
    """
    header_artists = parse_artists_header(soup)
    track_artists = parse_artists_track(track)
    title_artists = parse_artists_title(title)
    return reconcile_artists(header_artists, track_artists, title_artists)


def parse_artists_header(soup):
    """Parse the artists listed in the header as artists of the release."""
    artists = []
    try:
        release_artists = soup.select(".product-creator")[0].a.string.strip()
    except (TypeError, IndexError):
        return artists

    if re.match(r"[^,]+, [^&]+ (& [^&]+)+", release_artists):
        first_artist, rest = release_artists.split(",", 1)
        artists.append(first_artist)
        for a in rest.split("&"):
            a = a.strip()
            if a not in artists:
                artists.append(a)
    elif "&" in release_artists:
        for a in release_artists.split("&"):
            a = a.strip()
            if a not in artists:
                artists.append(a)
    else:
        artists.append(release_artists.strip())
    return artists


def parse_artists_track(track):
    """Parse the artists listed per-track, below the track title."""
    track_block = track.select(".by-line.typography-caption")
    if len(track_block) == 1:
        biline = track_block[0].text.strip().replace("\n", ", ")
        if biline[0:3] == "By ":
            return _parse_artists_commas(biline[2:])
        else:
            return _parse_artists_commas(biline)
    return []


def parse_artists_title(title):
    """Parse the guest artists from the track title."""
    feat = RE_FEAT.search(title)
    if feat:
        return _parse_artists_commas(feat[1])
    return set()


def _parse_artists_commas(artiststr):
    """
    Parse the artist names when they begin with commas and end with one
    ampersand. Split and strip them.
    """
    artists = []
    res = re.match(r"([^,]+)((?:, [^,&]+)+) & (.+)$", artiststr)
    if res:
        artists = [res[1].strip()] + [r.strip() for r in res[2].split(",") if r.strip()]
        for a in artists:
            if a not in artists:
                artists.append(a)
        artists.append(res[3].strip())
    elif "&" in artiststr:
        for a in artiststr.split("&"):
            a = a.strip()
            if a not in artists:
                artists.append(a)
    else:
        artists.append(artiststr.strip())
    return artists


def reconcile_artists(headers, tracks, titles):
    """De-duplicate the scraped artists and return a completed list."""
    artists = []
    for artist in tracks if tracks else headers:
        if (artist, "main") not in artists:
            artists.append((artist, "main"))
    for artist in titles:
        if (artist, "guest") not in artists:
            artists.append((artist, "guest"))
    return artists
