import re
import subprocess

import click

FLAC_IMPORTANT_REGEXES = [
    re.compile(".+\\.flac: testing,.*\x08ok"),
]

MP3_IMPORTANT_REGEXES = [
    re.compile(r"WARNING: .*"),
    re.compile(r"INFO: .*"),
]


def check_integrity(path):
    if path.lower().endswith(".flac"):
        return _check_flac_integrity(path)
    elif path.lower().endswith(".mp3"):
        return _check_mp3_integrity(path)
    raise click.Abort


def format_integrity(arg):
    return arg


def _check_flac_integrity(path):
    resp = subprocess.check_output(["flac", "-wt", path], stderr=subprocess.STDOUT)
    important_lines = []
    for line in resp.decode("utf-8").split("\n"):
        for important_line_re in FLAC_IMPORTANT_REGEXES:
            if important_line_re.match(line):
                important_lines.append(line)
    return "\n".join(important_lines)


def _check_mp3_integrity(path):
    resp = subprocess.check_output(["mp3val", path])
    important_lines = []
    for line in resp.decode("utf-8").split("\n"):
        for important_line_re in MP3_IMPORTANT_REGEXES:
            if important_line_re.match(line):
                important_lines.append(line)
    return "\n".join(important_lines)
