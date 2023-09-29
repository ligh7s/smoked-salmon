import re
from collections import defaultdict

import click

from salmon.constants import RELEASE_TYPES
from salmon.errors import InvalidMetadataError
from salmon.tagger.metadata import _print_metadata
from salmon.tagger.sources.base import generate_artists


def review_metadata(metadata, validator):
    """
    Validate that the metadata is per the user's wishes and then offer the user
    the ability to edit it.
    """
    _check_for_empty_release_type(metadata)
    _check_for_empty_genre_list(metadata)

    break_ = False
    edit_functions = {
        "a": _edit_artists,
        "l": _alias_artists,
        "t": _edit_title,
        "g": _edit_genres,
        "r": _edit_release_type,
        "y": _edit_years,
        "e": _edit_edition_info,
        "c": _edit_comment,
        "k": _edit_tracks,
        "u": _edit_urls,
    }
    while True:
        _print_metadata(metadata)
        r = click.prompt(
            click.style(
                "\nAre there any metadata fields you would like to edit? [a]rtists, "
                "artist a[l]iases, [t]itle, [g]enres, [r]elease type, [y]ears, "
                "[e]dition info, [c]omment, trac[k]s, [u]rls, [n]othing",
                fg="magenta",
                bold=True,
            )
        )
        r_let = r[0].lower()
        try:
            edit_functions[r_let](metadata)
        except KeyError:
            if r_let == "n":
                break_ = True
            else:
                click.secho(f"{r_let} is not a valid editing option.", fg="red")
                continue
        try:
            validator(metadata)
        except InvalidMetadataError as e:
            click.confirm(
                click.style(
                    str(e) + " Revisit metadata step?", fg="magenta", bold=True
                ),
                default=True,
                abort=True,
            )
            continue
        if break_:
            break
    return metadata


def _check_for_empty_release_type(metadata):
    if not metadata["rls_type"]:
        _edit_release_type(metadata)


def _check_for_empty_genre_list(metadata):
    if not metadata["genres"]:
        click.prompt(
            click.style(
                "\nNo genres were found for this release, but one must be added. "
                "Press enter to open the genre editor.",
                fg="magenta",
                bold=True,
            ),
            default="",
        )
        _edit_genres(metadata)


def _edit_artists(metadata):
    artist_text = "\n".join(f"{a} ({i})" for a, i in metadata["artists"])
    while True:
        artist_text = click.edit(artist_text)
        if not artist_text:
            return
        try:
            artists_li = [t.strip() for t in artist_text.split("\n") if t.strip()]
            tuples_artists_list = []
            for artist_line in artists_li:
                name, role = artist_line.rsplit(" ", 1)
                role = re.search(r"\((.+)\)", role)[1].lower()
                tuples_artists_list.append((name, role))
            metadata["artists"] = tuples_artists_list
            return
        except (ValueError, KeyError, TypeError) as e:
            click.confirm(
                click.style(
                    f"The tracks file is invalid ({type(e)}: {e}), retry?", fg="red"
                ),
                default=True,
                abort=True,
            )


def _alias_artists(metadata):  # noqa: C901
    existing_artists = {a for a, _ in metadata["artists"]}
    while True:
        artist_aliases = defaultdict(list)
        artists_to_delete = []
        artist_list = (
            "\n".join({a for a, _ in metadata["artists"]})
            + "\n\nEnter the artist alias list below. Refer to README for syntax.\n\n"
        )
        artist_list = click.edit(artist_list)
        try:
            artist_text = artist_list.split("Refer to README for syntax.")[1].strip()
            for line in artist_text.split("\n"):
                if line:
                    existing, new = [a.strip() for a in line.split("-->", 1)]
                    if existing not in existing_artists:
                        raise ValueError  # Too lazy to create new exception.
                    if new:
                        artist_aliases[existing.lower()].append(new)
                    else:
                        artists_to_delete.append(existing.lower())
            break
        except (IndexError, ValueError):
            click.confirm(
                click.style("Invalid artist list. Retry?", fg="red"),
                default=True,
                abort=True,
            )
        except AttributeError:
            return

    for i, (artist, importa) in enumerate(metadata["artists"]):
        if artist.lower() in artist_aliases:
            metadata["artists"].pop(i)
            for artist_name in artist_aliases[artist.lower()]:
                if artist_name:
                    metadata["artists"].append((artist_name, importa))
    for i, (artist, importa) in enumerate(metadata["artists"]):
        if artist.lower() in artists_to_delete:
            metadata["artists"].pop(i)

    for dnum, disc in metadata["tracks"].items():
        for tnum, track in disc.items():
            for i, (artist, importa) in enumerate(track["artists"]):
                if artist.lower() in artist_aliases:
                    metadata["tracks"][dnum][tnum]["artists"].pop(i)
                    for artist_name in artist_aliases[artist.lower()]:
                        if artist_name:
                            metadata["tracks"][dnum][tnum]["artists"].append(
                                (artist_name, importa)
                            )
    for dnum, disc in metadata["tracks"].items():
        for tnum, track in disc.items():
            for i, (artist, importa) in enumerate(track["artists"]):
                if artist.lower() in artists_to_delete:
                    metadata["tracks"][dnum][tnum]["artists"].pop(i)


def _edit_release_type(metadata):
    _print_release_types()
    types = {r.lower(): r for r in RELEASE_TYPES}
    while True:
        rtype = (
            click.prompt(
                click.style(
                    "\nWhich release type corresponds to this release? (case insensitive)",
                    fg="magenta",
                    bold=True,
                ),
                type=click.STRING,
            )
            .strip()
            .lower()
        )
        if rtype in types:
            metadata["rls_type"] = types[rtype]
            return
        click.secho(f"{rtype} is not a valid release type.", fg="red")


def _print_release_types():
    types = RELEASE_TYPES.keys()
    longest = max(len(r) for i, r in enumerate(types) if i % 2 == 0)
    click.secho("\nRelease Types:", fg="yellow", bold=True)
    for i, rtype in enumerate(types):
        click.echo(f"  {rtype.ljust(longest)}", nl=False)
        if i % 2 == 1:
            click.echo()
    click.echo()


def _edit_title(metadata):
    while True:
        title = click.edit(metadata["title"])
        if title:
            metadata["title"] = title.strip()
            return
        click.confirm(
            click.style("The release must have a title. Retry?", fg="magenta"),
            default=True,
            abort=True,
        )


def _edit_years(metadata):
    while True:
        text = (
            f'Year      : {metadata["year"]}\n' f'Group Year: {metadata["group_year"]}'
        )
        text = click.edit(text)
        try:
            year_line, group_year_line = (
                l.strip() for l in text.strip().split("\n", 1)
            )
            metadata["year"] = re.match(r"Year *: *(\d{4})", year_line)[1]
            metadata["group_year"] = re.match(
                r"Group Year *: *(\d{4})", group_year_line
            )[1]
            return
        except (TypeError, KeyError, ValueError):
            click.confirm(
                click.style(
                    "Invalid values or formatting in the years file. Retry?",
                    fg="magenta",
                ),
                default=True,
                abort=True,
            )


def _edit_genres(metadata):
    while True:
        genres = click.edit("\n".join(metadata["genres"]))
        if genres:
            metadata["genres"] = [g for g in genres.split("\n") if g.strip()]
            return
        click.confirm(
            click.style("You must input at least one genre. Retry?", fg="magenta"),
            default=True,
            abort=True,
        )


def _edit_urls(metadata):
    while True:
        urls = click.edit("\n".join(metadata["urls"]))
        metadata["urls"] = [g for g in urls.split("\n") if g.strip()]
        return


def _edit_edition_info(metadata):
    while True:
        text = (
            f'Label         : {metadata["label"] or ""}\n'
            f'Catalog Number: {metadata["catno"] or ""}\n'
            f'Edition Title : {metadata["edition_title"] or ""}'
        )
        text = click.edit(text)
        try:
            label_line, cat_line, title_line = (
                l.strip() for l in text.strip().split("\n", 2)
            )
            metadata["label"] = re.match(r"Label *: *(.*)", label_line)[1] or None
            metadata["catno"] = (
                re.match(r"Catalog Number *: *(.*)", cat_line)[1] or None
            )
            metadata["edition_title"] = (
                re.match(r"Edition Title *: *(.*)", title_line)[1] or None
            )
            return
        except (TypeError, KeyError, ValueError):
            click.confirm(
                click.style(
                    "Invalid values or formatting in the editions file. Retry?",
                    fg="magenta",
                ),
                default=True,
                abort=True,
            )


def _edit_comment(metadata):
    review = click.edit(metadata["comment"])
    metadata["comment"] = review.strip() if review else None


def _edit_tracks(metadata):
    text_tracks_li = []
    for dnum, disc in metadata["tracks"].items():
        for tnum, track in disc.items():
            text_tracks_li.append(
                f"Disc {dnum} Track {tnum}\n"
                f'Title: {track["title"]}\n'
                f"Artists:\n" + "\n".join(f"> {a} ({i})" for a, i in track["artists"])
            )

    text_tracks = "\n\n-----\n\n".join(text_tracks_li)
    while True:
        text_tracks = click.edit(text_tracks)
        if not text_tracks:
            return
        try:
            tracks_li = [tr for tr in re.split("\n-+\n", text_tracks) if tr.strip()]
            for track_tx in tracks_li:
                ident, title, _, *artists_li = [
                    t.strip() for t in track_tx.split("\n") if t.strip()
                ]
                r_ident = re.search(r"Disc ([^ ]+) Track ([^ ]+)", ident)
                discnum, tracknum = r_ident[1], r_ident[2]
                metadata["tracks"][discnum][tracknum]["title"] = re.search(
                    r"Title *: *(.+)", title
                )[1]

                tuples_artists_list = []
                for artist_line in artists_li:
                    artist_line_name, artist_line_role = artist_line.rsplit(" ", 1)
                    artist_line_role = re.search(r"\((.+)\)", artist_line_role)[
                        1
                    ].lower()
                    tuples_artists_list.append(
                        (re.search(r"> *(.+)", artist_line_name)[1], artist_line_role)
                    )
                metadata["tracks"][discnum][tracknum]["artists"] = tuples_artists_list
            metadata["artists"], metadata["tracks"] = generate_artists(
                metadata["tracks"]
            )
            return
        except (TypeError, ValueError, KeyError) as e:
            click.confirm(
                click.style(
                    f"The tracks file is invalid ({type(e)}: {e}), retry?", fg="red"
                ),
                default=True,
                abort=True,
            )
