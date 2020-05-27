import asyncio
import re
from urllib import parse

import click


from salmon.common import RE_FEAT, make_searchstrs
from salmon.errors import AbortAndDeleteFolder

from salmon.gazelle import RequestError

loop = asyncio.get_event_loop()


def check_existing_group(gazelle_site, searchstrs, offer_deletion=True):
    """
    Make a request to the API with a dupe-check searchstr,
    then have the user validate that the torrent does not match
    anything on site.
    """
    results = get_search_results(gazelle_site, searchstrs)
    print_search_results(gazelle_site, results, " / ".join(searchstrs))
    group_id = _prompt_for_group_id(gazelle_site, results, offer_deletion)
    if group_id:
        confirmation = _confirm_group_id(gazelle_site, group_id, results)
        if confirmation is True:
            return group_id
        return None
    return group_id


def get_search_results(gazelle_site, searchstrs):
    results = []
    for searchstr in searchstrs:
        for release in loop.run_until_complete(
            gazelle_site.request("browse", searchstr=searchstr)
        )["results"]:
            if release not in results:
                results.append(release)
    return results


def generate_dupe_check_searchstrs(artists, album, catno=None):
    searchstrs = []
    album = _sanitize_album_for_dupe_check(album)
    searchstrs += make_searchstrs(artists, album, normalize=True)
    if album is not None and re.search(r"vol[^u]", album.lower()):
        extra_alb_search = re.sub(r"vol[^ ]+", "volume", album, flags=re.IGNORECASE)
        searchstrs += make_searchstrs(artists, extra_alb_search, normalize=True)
    if album is not None and "untitled" in album.lower():  # Filthy catno untitled rlses
        searchstrs += make_searchstrs(artists, catno or "", normalize=True)
    if album is not None and "/" in album:  # Filthy singles
        searchstrs += make_searchstrs(artists, album.split("/")[0], normalize=True)
    elif catno and album is not None and catno.lower() in album.lower():
        searchstrs += make_searchstrs(artists, "untitled", normalize=True)
    return filter_unnecessary_searchstrs(searchstrs)


def _sanitize_album_for_dupe_check(album):
    album = RE_FEAT.sub("", album)
    album = re.sub(
        r"[\(\[][^\)\]]*(Edition|Version|Deluxe|Original|Reissue|Remaster|Vol|Mix|Edit)"
        r"[^\)\]]*[\)\]]",
        "",
        album,
        flags=re.IGNORECASE,
    )
    album = re.sub(
        r"[\(\[][^\)\]]*Remixes[^\)\]]*[\)\]]", "remixes", album, flags=re.IGNORECASE
    )
    album = re.sub(
        r"[\(\[][^\)\]]*Remix[^\)\]]*[\)\]]", "remix", album, flags=re.IGNORECASE
    )
    return album


def filter_unnecessary_searchstrs(searchstrs):
    past_strs = []
    new_strs = []
    for stri in sorted(searchstrs, key=len):
        word_set = set(stri.split())
        for prev_word_set in past_strs:
            if all(p in word_set for p in prev_word_set):
                break
        else:
            new_strs.append(stri)
            past_strs.append(word_set)
    return new_strs


def print_search_results(gazelle_site, results, searchstr):
    """Print all the site search results."""
    if not results:
        click.secho(
            f'\nNo groups found on {gazelle_site.site_string} matching this release.',
            fg="green",
            nl=False
        )
        click.secho(f" (searchstrs: {searchstr})", bold=True)
    else:
        click.secho(
            f'\nResults matching this release were found on {gazelle_site.site_string}: ',
            fg="red",
            nl=False
        )
        click.secho(f" (searchstrs: {searchstr})", bold=True)
        for r_index, r in enumerate(results):
            try:
                url = f'{gazelle_site.base_url}/torrents.php?id={r["groupId"]}'
                # User doesn't get to pick a zero index
                click.echo(f" {r_index+1:02d} >> {r['groupId']} | ", nl=False)
                click.secho(f"{r['artist']} - {r['groupName']} ", fg="cyan", nl=False)
                click.secho(
                    f"({r['groupYear']}) [{r['releaseType']}] ", fg="yellow", nl=False
                )
                click.echo(f"[Tags: {', '.join(r['tags'])}] | {url}")
            except (KeyError, TypeError) as e:
                continue


def _prompt_for_group_id(gazelle_site, results, offer_deletion):
    """Have the user choose a group ID"""
    while True:
        group_id = click.prompt(
            click.style(
                "\nWould you like to upload to an existing group?\n"
                "Either pick from releases found, paste a release group URL, leave blank for a new group,\n"
                f'or [a]bort {", [d]elete folder " if offer_deletion else ""}',
                fg="magenta",
                bold=True,
            ),
            default="",
        )
        if group_id.strip().isdigit():
            group_id = int(group_id) - 1  # User doesn't type zero index
            if group_id < 1:
                group_id = 0  # If the user types 0 give them the first choice.
            if group_id < len(results):
                group_id = results[group_id]['groupId']
                return int(group_id)
            else:
                group_id = int(group_id) + 1
                click.echo(f"Interpreting {group_id} as a group Id")
                return group_id

        elif group_id.strip().lower().startswith(gazelle_site.base_url + "/torrents.php"):
            group_id = parse.parse_qs(parse.urlparse(group_id).query)['id'][0]
            return int(group_id)
        elif group_id.lower().startswith("a"):
            raise click.Abort
        elif group_id.lower().startswith("d") and offer_deletion:
            raise AbortAndDeleteFolder
        elif not group_id.strip():
            click.echo(f"Uploading to a new torrent group.")
            return None


def _print_torrents(gazelle_site, group_id, rset):
    """Print the torrents that are a part of the torrent group."""
    group_info = {}
    # Be nice to show the artist(s) here but it isn't the same format if they came from a URL
    click.secho(f"\nSelected ID: {rset['groupId']} ", nl=False)
    click.secho(f" - {rset['groupName']} ", fg="cyan", nl=False)
    click.secho(f" - {rset['artist']} ", fg="cyan", nl=False)
    click.secho(f"({rset['groupYear']})", fg="yellow")
    click.secho("Torrents in this group:", fg="yellow", bold=True)
    for t in rset["torrents"]:
        if t["remastered"]:
            click.echo(
                f"> {t['remasterYear']} / {t['remasterCatalogueNumber']} / "
                f"{t['media']} / {t['format']} / {t['encoding']}"
            )
        if not t["remastered"]:
            if not group_info:
                group_info = loop.run_until_complete(gazelle_site.torrentgroup(group_id))[
                    "group"
                ]
            click.echo(
                f"> OR / {group_info['recordLabel']} / "
                f"{group_info['catalogueNumber']} / {t['media']} / "
                f"{t['format']} / {t['encoding']}"
            )


def _confirm_group_id(gazelle_site, group_id, results):
    """Have the user decide whether or not to upload to a torrent group."""
    for r in results:
        if group_id == r["groupId"]:
            rset = r
            break
    else:
        try:
            rset = loop.run_until_complete(gazelle_site.torrentgroup(group_id))
            # account for differences between search result and group result json
            rset['groupName'] = rset['group']['name']
            rset['artist'] = ""
            for a in rset['group']['musicInfo']['artists']:
                rset['artist'] += a['name'] + " "
            rset['groupId'] = rset['group']['id']
            rset['groupYear'] = rset['group']['year']
        except RequestError:
            click.secho(f"{group_id} does not exist.", fg="red")
            raise click.Abort
    _print_torrents(gazelle_site, group_id, rset)
    while True:
        resp = click.prompt(
            click.style(
                "\nAre you sure you would you like to upload this torrent to this group? [Y]es, "
                "[n]ew group, [a]bort, [d]elete folder",
                fg="magenta",
                bold=True,
            ),
            default="Y",
        )[0].lower()
        if resp == "a":
            raise click.Abort
        elif resp == "d":
            raise AbortAndDeleteFolder
        elif resp == "y":
            return True
        elif resp == "n":
            return False
