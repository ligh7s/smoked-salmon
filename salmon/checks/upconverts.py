import math
import os
import re
import subprocess

import click
import mutagen

from salmon.errors import NotAValidInputFile


def _upconvert_check_handler(filepath):
    try:
        upconv, wasted_bits, bitdepth = check_upconvert(filepath)
    except NotAValidInputFile as e:
        click.secho(str(e), fg="yellow")
    else:
        if upconv:
            click.secho(
                "This file is likely upconverted from a file of a lesser bitdepth. "
                f"Wasted bits: {wasted_bits}/{bitdepth}",
                fg="red",
                bold=True,
            )
        else:
            click.secho(
                f"This file does not have a high number of wasted bits. "
                f"Wasted bits: {wasted_bits}/{bitdepth}",
                fg="green",
            )


def check_upconvert(filepath):
    try:
        mut = mutagen.File(filepath)
        bitdepth = mut.info.bits_per_sample
    except AttributeError:
        raise NotAValidInputFile("This is not a FLAC file.")

    if bitdepth == 16:
        raise NotAValidInputFile("This is a 16bit FLAC file.")

    with open(os.devnull, "w") as devnull:
        response = subprocess.check_output(
            ["flac", "-ac", filepath], stderr=devnull
        ).decode("utf-8")

    wasted_bits_list = []
    for line in response.split("\n"):
        r = re.search(r"wasted_bits=(\d+)", line)
        if r:
            wasted_bits_list.append(int(r[1]))

    wasted_bits = math.ceil(sum(wasted_bits_list) / len(wasted_bits_list))
    if wasted_bits >= 8:
        return True, wasted_bits, bitdepth
    else:
        return False, wasted_bits, bitdepth
