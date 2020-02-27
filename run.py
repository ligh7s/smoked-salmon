#!/usr/bin/env python3

# flake8: noqa

import click

import salmon.commands
from salmon.common import commandgroup
from salmon.errors import FilterError, LoginError, UploadError

if __name__ == '__main__':
    try:
        commandgroup(obj={})
    except (UploadError, FilterError) as e:
        click.secho(str(e), fg='red', bold=True)
    except LoginError:
        click.secho(f'Failed to log into RED', fg='red')
    except ImportError as e:
        click.secho(f'You are missing required dependencies: {e}', fg='red')
