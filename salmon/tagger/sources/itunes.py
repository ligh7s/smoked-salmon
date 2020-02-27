import re
from collections import defaultdict
from datetime import datetime

from salmon.common import RE_FEAT, parse_copyright
from salmon.errors import ScrapeError
from salmon.sources import iTunesBase
from salmon.tagger.sources.base import MetadataMixin

ALIAS_GENRE = {
    "Hip-Hop/Rap": {"Hip Hop", "Rap"},
    "R&B/Soul": {"Rhythm & Blues", "Soul"},
}


class Scraper(iTunesBase, MetadataMixin):
    def parse_release_title(self, soup):
        try:
            title = soup.select(".product-header__title")[0].string
            return RE_FEAT.sub("", title)
        except (TypeError, IndexError) as e:
            raise ScrapeError("Failed to parse scraped title.") from e

    def parse_cover_url(self, soup):
        try:
            art = soup.select(
                "picture.product-artwork.product-artwork--captioned"
                ".we-artwork--fullwidth.we-artwork.ember-view source"
            )[0]["srcset"]
            return re.search(r",(https://[^,]+\.jpg) 3x", art)[1]
        except (TypeError, IndexError) as e:
            raise ScrapeError("Could not parse cover URL.") from e

    def parse_genres(self, soup):
        try:
            genre = soup.select(
                ".product-header__list .inline-list "
                "li.inline-list__item.inline-list__item--bulleted a"
            )[0].string
            try:
                return ALIAS_GENRE[genre]
            except KeyError:
                return {genre.strip()}
        except (TypeError, IndexError) as e:
            raise ScrapeError("Could not parse genres.") from e

    def parse_release_year(self, soup):
        try:
            return int(re.search(r"(\d{4})", self.parse_release_date(soup))[1])
        except TypeError as e:
            raise ScrapeError("Could not parse release year.") from e

    def parse_release_date(self, soup):
        for selector in [
            ".inline-list__item.inline-list__item--preorder-media",
            ".product-header__list__item.product-header__list__item--preorder-media",
            ".product-hero__tracks .link-list__item__date",
        ]:
            try:
                date_string = soup.select(selector)[0].string
                try:
                    date = re.search(r"([A-Z][a-z]+ \d{1,2}, \d{4})", date_string)[1]
                except TypeError:
                    date = date_string
                for f in ["%b %d, %Y", "%d %b %Y", "%d de %b de %Y"]:
                    try:
                        return datetime.strptime(date, f).strftime("%Y-%m-%d")
                    except ValueError:
                        pass
            except (TypeError, IndexError):
                pass
        # raise ScrapeError('Could not parse release date.')
        # Apparently iTunes is returning releases without the date now.
        return None

    def parse_release_label(self, soup):
        try:
            return parse_copyright(
                soup.select(".product-hero__tracks .link-list__item--copyright")[
                    0
                ].string
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
        for track in soup.select(".product-hero__tracks tr.table__row"):
            try:
                if track.select(".icon-musicvideo"):
                    continue

                try:
                    num = track.select(".table__row__track span.table__row__number")[
                        0
                    ].string.strip()
                except IndexError:
                    continue

                raw_title = track.select(
                    ".table__row__name .table__row__titles .table__row__headline"
                )[0].text.strip()
                title = RE_FEAT.sub("", raw_title)
                explicit = bool(
                    track.select(".table__row__name .table__row__titles .icon-explicit")
                )

                # iTunes silently increments disc.
                if int(num) == 1 and int(num) in tracks[str(cur_disc)]:
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
        header_scr = soup.select(".product-header .product-header__identity a")[
            0
        ].string
    except (TypeError, IndexError):
        return artists

    if re.match(r"[^,]+, [^&]+ (& [^&]+)+", header_scr):
        first_artist, rest = header_scr.split(",", 1)
        artists.append(first_artist)
        for a in rest.split("&"):
            a = a.strip()
            if a not in artists:
                artists.append(a)
    elif "&" in header_scr:
        for a in header_scr.split("&"):
            a = a.strip()
            if a not in artists:
                artists.append(a)
    else:
        artists.append(header_scr.strip())
    return artists


def parse_artists_track(track):
    """Parse the artists listed per-track, below the track title."""
    track_block = track.select(".table__row__name .table__row__titles > div")
    if len(track_block) == 2:
        return _parse_artists_commas(track_block[1].text)
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
