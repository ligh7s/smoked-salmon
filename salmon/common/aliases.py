import click

COMMAND_ALIASES = {
    "list": "ls",
    "upl": "up",
    "upload": "up",
    "down": "dl",
    "download": "dl",
    "delete": "rm",
    "del": "rm",
    "remove": "rm",
}


class AliasedCommands(click.Group):
    def get_command(self, ctx, cmd_name):
        rv = click.Group.get_command(self, ctx, cmd_name)
        if rv is not None:
            return rv
        try:
            return click.Group.get_command(self, ctx, COMMAND_ALIASES[cmd_name])
        except KeyError:
            return None
