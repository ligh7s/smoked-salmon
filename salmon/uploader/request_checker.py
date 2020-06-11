import asyncio
import re
from urllib import parse

import click


from salmon.common import RE_FEAT, make_searchstrs
from salmon.errors import AbortAndDeleteFolder

from salmon.errors import RequestError
import rich

loop = asyncio.get_event_loop()
#import bbcode

#parser = bbcode.Parser()

def check_requests(gazelle_site, searchstrs,metadata):
    """
    Make a request to the API with a dupe-check searchstr,
    then have the user validate that the torrent does not match
    anything on site.
    """
    results = get_request_results(gazelle_site, searchstrs)
    print_request_results(gazelle_site, results, " / ".join(searchstrs))
    request_id = _prompt_for_request_id(gazelle_site, results)
    if request_id:
        confirmation = _confirm_request_id(gazelle_site, request_id)
        if confirmation is True:
            return request_id
        return None
    return request_id


def get_request_results(gazelle_site, searchstrs):
    results = []
    for searchstr in searchstrs:
        for release in loop.run_until_complete(
            gazelle_site.request("requests", search=searchstr)
        )["results"]:
            if release not in results:
                results.append(release)
    return results

def print_request_results(gazelle_site, results, searchstr):
    """Print all the request search results."""
    if not results:
        click.secho(
            f'\nNo requests found on {gazelle_site.site_string} matching this release.',
            fg="green",
            nl=False
        )
        click.secho(f" (searchstrs: {searchstr})", bold=True)
    else:
        click.secho(
            f'\nRequests matching this release were found on {gazelle_site.site_string}: ',
            fg="red",
            nl=False
        )
        click.secho(f" (searchstrs: {searchstr})", bold=True)
        for r_index, r in enumerate(results):
            try:
                url = f'{gazelle_site.base_url}/requests.php?id={r["requestId"]}'
                # User doesn't get to pick a zero index
                click.echo(f" {r_index+1:02d} >> {r['requestId']} | ", nl=False)
                if len(r['artists'][0])>3:
                    r['artist'] = "Various Artists"
                else:
                    r['artist'] = ""
                    for a in r['artists'][0]:
                        r['artist'] += a['name'] + " "
                click.secho(f"{r['artist']}", fg="cyan", nl=False)
                click.secho(f" - {r['title']} ", fg="cyan", nl=False)
                click.secho(
                    f"({r['year']}) [{r['releaseType']}] ", fg="yellow")
                click.secho(f"Requirements: {' or '.join(r['bitrateList'])} / ",nl=False)
                click.secho(f"{' or '.join(r['formatList'])} / ",nl=False)
                click.secho(f"{' or '.join(r['mediaList'])} / ")
                

            except (KeyError, TypeError) as e:
                continue

def _print_request_details(gazelle_site, req):
    """Print request details."""
    group_info = {}
    click.secho("\nSelected Request:")
    click.secho(f"{gazelle_site.base_url}/requests.php?id={req['requestId']} ")
    click.secho(f" {req['artist']}", fg="cyan", nl=False)
    click.secho(f" - {req['title']} ", fg="cyan", nl=False)
    click.secho(f"({req['year']})", fg="yellow")
    click.secho(f" - {req['requestorName']} ", fg="cyan", nl=False)

    if 'totalBounty' in req.keys():
        bounty=req['totalBounty']
    elif 'bounty' in req.keys():
        bounty=req['bounty']
    bounty = int(bounty)/1048576
    click.secho(f" - {bounty}MB", fg="cyan")

    click.secho(f"Allowed Bitrate: {' | '.join(req['bitrateList'])}")
    click.secho(f"Allowed Formats: {' | '.join(req['formatList'])}")
    if 'CD' in req['mediaList']:
        req['mediaList'].remove('CD')
        req['mediaList'].append(str('CD '+req['logCue']))
    click.secho(f"Allowed   Media: {' | '.join(req['mediaList'])}")
    click.secho('Description:',fg="cyan",)
    description=req['bbDescription'].splitlines(True)
    
    #Should probably be refactored out and a setting.
    line_limit=5
    num_lines=len(description)
    if num_lines>line_limit:
        description="".join(description[:line_limit])+f"...{num_lines-line_limit} more lines..."
    else:
        description="".join(description)
    rich.print(description)


def _prompt_for_request_id(gazelle_site, results):
    """Have the user choose a group ID"""
    while True:
        request_id = click.prompt(
            click.style(
                "\nWould you like to fill a request?\n"
                "Choose from above, paste a url, or do[n]t."
                ,fg="magenta",
                bold=True,
            ),
            default="N",
        )
        if request_id.strip().isdigit():
            request_id = int(request_id) - 1  # User doesn't type zero index
            if request_id < 1:
                request_id = 0  # If the user types 0 give them the first choice.
            if request_id < len(results):
                request_id = results[request_id]['requestId']
                return int(request_id)
            else:
                request_id = int(request_id) + 1
                click.echo(f"Interpreting {request_id} as a request id")
                return request_id

        elif request_id.strip().lower().startswith(gazelle_site.base_url + "/requests.php"):
            request_id = parse.parse_qs(parse.urlparse(request_id).query)['id'][0]
            return int(request_id)
        elif request_id.lower().startswith("n"):
            click.echo(f"Not filling a request")
            return None
        elif not request_id.strip():
            click.echo(f"Not filling a request")
            return None

def _confirm_request_id(gazelle_site, request_id):
    """Have the user decide whether or not they want to fill request"""
    try:
        req=loop.run_until_complete(gazelle_site.request("request", id=request_id))
        req['artist'] = ""
        if len(req['musicInfo']['artists'])>3:
            req['artist'] = "Various Artists"
        else:
            for a in req['musicInfo']['artists']:
                req['artist'] += a['name'] + " "
    except RequestError:
        click.secho(f"{request_id} does not exist.", fg="red")
        raise click.Abort
    _print_request_details(gazelle_site, req)
    while True:
        resp = click.prompt(
            click.style(
                "\nAre you sure you would you like to fill this request [Y]es, "
                "[n]o",
                fg="magenta",
                bold=True,
            ),
            default="Y",
        )[0].lower()
        if resp == "y":
            return True
        elif resp == "n":
            click.secho(f"Not filling the request", fg="red")
            return False
