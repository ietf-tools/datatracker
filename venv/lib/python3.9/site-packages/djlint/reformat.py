"""Djlint reformat html files.

Much code is borrowed from https://github.com/rareyman/HTMLBeautify, many thanks!
"""

from __future__ import annotations

import difflib
from typing import TYPE_CHECKING

from djlint.formatter.compress import compress_html
from djlint.formatter.condense import clean_whitespace, condense_html
from djlint.formatter.css import format_css
from djlint.formatter.expand import expand_html
from djlint.formatter.indent import indent_html
from djlint.formatter.js import format_js

if TYPE_CHECKING:
    from pathlib import Path

    from djlint.settings import Config


def formatter(config: Config, rawcode: str) -> str:
    """Format a html string."""
    if not rawcode:
        return rawcode

    # naturalize the line breaks
    compressed = compress_html("\n".join(rawcode.splitlines()), config)

    expanded = expand_html(compressed, config)

    condensed = clean_whitespace(expanded, config)

    indented_code = indent_html(condensed, config)

    beautified_code = condense_html(indented_code, config)

    if config.format_css:
        beautified_code = format_css(beautified_code, config)

    if config.format_js:
        beautified_code = format_js(beautified_code, config)

    # preserve original line endings
    line_ending = rawcode.find("\n")
    if line_ending > -1 and rawcode[max(line_ending - 1, 0)] == "\r":
        # convert \r?\n to \r\n
        beautified_code = beautified_code.replace("\r", "").replace(
            "\n", "\r\n"
        )

    return beautified_code


def reformat_file(
    config: Config, this_file: Path
) -> dict[str, tuple[str, ...]]:
    """Reformat html file."""
    with this_file.open(encoding="utf-8", newline="") as f:
        rawcode = f.read()

    beautified_code = formatter(config, rawcode)

    if (
        config.check is not True and beautified_code != rawcode
    ) or config.stdin:
        with this_file.open("w", encoding="utf-8", newline="") as f:
            f.write(beautified_code)

    return {
        str(this_file): tuple(
            difflib.unified_diff(
                rawcode.splitlines(), beautified_code.splitlines()
            )
        )
    }
