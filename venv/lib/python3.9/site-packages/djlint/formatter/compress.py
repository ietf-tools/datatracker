"""Compress html.

1. flatten attributes
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import regex as re

from djlint.const import HTML_TAG_NAMES, HTML_VOID_ELEMENTS
from djlint.helpers import RE_FLAGS_IMX, child_of_unformatted_block

if TYPE_CHECKING:
    from djlint.settings import Config


def compress_html(html: str, config: Config) -> str:
    """Compress html."""

    def _fix_case(tag: str) -> str:
        if not config.ignore_case and tag.lower() in HTML_TAG_NAMES:
            return tag.lower()

        if not config.ignore_case and tag.lower() == "doctype":
            return "DOCTYPE"
        return tag

    def _clean_tag(match: re.Match[str]) -> str:
        """Flatten multiline attributes back to one line.

        Skip when attribute is ignored.
        Attribute name can be in group one or group 2.
        for now, skipping if they are anywhere

        tags starting ignored blocks can have their attributes formatted,
        for example <textarea class="..." id="..."> can be formatted.
        """
        if child_of_unformatted_block(config, html, match):
            return match.group()

        open_bracket = match.group(1)
        tag = _fix_case(match.group(2))

        attributes = (
            (
                " "
                + " ".join(
                    x.strip() for x in match.group(3).strip().splitlines()
                )
            )
            if match.group(3)
            else ""
        )
        if tag.lower() in HTML_VOID_ELEMENTS and config.close_void_tags:
            close_bracket = " />"
        else:
            close_bracket = (
                match.group(4)
                if "/" not in match.group(4)
                else f" {match.group(4)}"
            )

        return f"{open_bracket}{tag}{attributes}{close_bracket}"

    return re.sub(config.html_tag_regex, _clean_tag, html, flags=RE_FLAGS_IMX)
