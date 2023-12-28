import asyncio
from os.path import dirname, join

import aiohttp
import aiohttp_jinja2
import click
import jinja2
from aiohttp_jinja2 import render_template

from salmon import config
from salmon.common import commandgroup
from salmon.errors import WebServerIsAlreadyRunning
from salmon.web import spectrals

loop = asyncio.get_event_loop()


@commandgroup.command()
def web():
    """Start the salmon web server"""
    app = create_app()  # noqa: F841
    click.secho(f"Running webserver on http://127.0.0.1:{config.WEB_PORT}", fg="cyan")
    loop.run_forever()


def create_app():
    app = aiohttp.web.Application()
    add_routes(app)
    aiohttp_jinja2.setup(
        app, loader=jinja2.FileSystemLoader(join(dirname(__file__), "templates"))
    )
    return loop.run_until_complete(
        loop.create_server(app.make_handler(), host=config.WEB_BIND, port=config.WEB_PORT)
    )


async def create_app_async():
    app = aiohttp.web.Application()
    add_routes(app)
    aiohttp_jinja2.setup(
        app, loader=jinja2.FileSystemLoader(join(dirname(__file__), "templates"))
    )
    runner = aiohttp.web.AppRunner(app)
    await runner.setup()
    site = aiohttp.web.TCPSite(runner, config.WEB_BIND, config.WEB_PORT)
    try:
        await site.start()
    except OSError:
        raise WebServerIsAlreadyRunning
    return runner


def add_routes(app):
    app.router.add_static(
        "/static", join(dirname(__file__), "static"), follow_symlinks=True
    )
    app.router.add_route("GET", "/", handle_index)
    app.router.add_route("GET", "/spectrals", spectrals.handle_spectrals)
    app["static_root_url"] = config.WEB_STATIC_ROOT_URL


def handle_index(request, **kwargs):
    return render_template("index.html", request, {})
