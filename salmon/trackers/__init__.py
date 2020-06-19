

import click
from urllib import parse

from salmon import config
from salmon.trackers import  red, ops
#hard coded as it needs to reflect the imports anyway.
tracker_classes={
    'RED':red.RedApi,
    'OPS':ops.OpsApi
}

def get_class(site_code):
    "Returns the api class from the tracker string."
    return tracker_classes[site_code]


def choose_tracker(choices):
    """Allows the user to choose a tracker from choices.
    this function will only really work if they are a subset of the choices in config"""
    while True:
        # Loop until we have chosen a tracker or aborted.
        tracker_input = click.prompt(
            click.style(f'Your choices are {" , ".join(choices)} '
                        'or [a]bort.',
                        fg="magenta", bold=True
                        ),
            default=choices[0],
        )
        tracker_input = tracker_input.strip().upper()
        if tracker_input in choices:
            click.secho(f"Using tracker: {tracker_input}",fg="magenta")
            return tracker_input
        # this part allows input of the first letter of the tracker code.
        elif tracker_input in [choice[0] for choice in choices]:
            for choice in choices:
                if tracker_input == choice[0]:
                    click.secho(f"Using tracker: {choice}",fg="magenta")
                    return choice
        elif tracker_input.lower().startswith("a"):
            click.secho(f"\nDone with this release.", fg="red")
            raise click.Abort



def choose_tracker_first_time(question="Which tracker would you like to upload to?"):
    """Specific logic for the first time a tracker choice is offered.
    Uses default if there is one and uses only tracker if there is only one."""
    choices=config.TRACKER_LIST
    if len(choices) == 1:
                click.secho(f"Using tracker: {choices[0]}")
                return choices[0]
    if config.DEFAULT_TRACKER:
        click.secho(f"Using tracker: {config.DEFAULT_TRACKER}",fg="magenta")
        return config.DEFAULT_TRACKER
    click.secho(question, fg="magenta",bold=True)
    tracker = choose_tracker(choices)
    return tracker

def validate_tracker(ctx, param, value):
    """Only allow trackers in the config tracker dict.
    If it isn't there. Prompt to choose.
    """
    try:
        if value is None:
            return choose_tracker_first_time()
        if value.upper() in config.TRACKER_LIST:
            click.secho(f"Using tracker: {value.upper()}",fg="magenta")
            return value.upper() 
        else:
            click.secho(f"{value} is not a tracker in your config.")
            return choose_tracker(config.TRACKER_LIST)
    except AttributeError:
        raise click.BadParameter(
            "This flag requires a tracker. Possible sources are: "
            + ", ".join(config.TRACKER_LIST)
        )
    
def validate_request(gazelle_site, request):
    """Check the request id is a url or number.
    Should it check more?
    """
    try:
        if request is None:
            return None
        if request.strip().isdigit():
            pass
        elif request.strip().lower().startswith(gazelle_site.base_url + "/requests.php"):
            request=parse.parse_qs(parse.urlparse(request).query)['id'][0]
        click.secho(
            f"Attempting to fill {gazelle_site.base_url}/requests.php?action=view&id={request}"
            ,fg="green")
        return request
    except (KeyError, AttributeError):
        raise click.BadParameter(
            "This flag requires a request, either as a url or ID"
        )