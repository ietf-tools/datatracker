"""Expand html.

1. put html tags on individual lines, if needed.
2. put template tags on individual lines, if needed.
"""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

import regex as re

from djlint.helpers import (
    RE_FLAGS_IMX,
    RE_FLAGS_IX,
    RE_FLAGS_MX,
    inside_html_attribute,
    inside_ignored_block,
    inside_template_block,
)

if TYPE_CHECKING:
    from djlint.settings import Config


def expand_html(html: str, config: Config) -> str:
    """Split single line html into many lines based on tags."""

    def add_html_line(out_format: str, match: re.Match[str]) -> str:
        """Add whitespace.

        Do not add whitespace if the tag is in a non indent block.

        Do not add whitespace if the tag is a in a template block.

        Do not add whitespace if the tag is in an html attribute string.
        """
        if inside_ignored_block(config, html, match):
            return match.group(1)

        if inside_template_block(config, html, match):
            return match.group(1)

        if inside_html_attribute(config, html, match):
            return match.group(1)

        if out_format == "\n%s" and match.start() == 0:
            return match.group(1)

        return out_format % match.group(1)

    html_tags = config.break_html_tags

    add_left = partial(add_html_line, "\n%s")
    add_right = partial(add_html_line, "%s\n")

    break_char = config.break_before

    # html tags - break before
    html = re.sub(
        rf"{break_char}\K(</?(?:{html_tags})\b(\"[^\"]*\"|'[^']*'|{{[^}}]*}}|[^'\">{{}}])*>)",
        add_left,
        html,
        flags=RE_FLAGS_IX,
    )

    # html tags - break after
    html = re.sub(
        rf"(</?(?:{html_tags})\b(\"[^\"]*\"|'[^']*'|{{[^}}]*}}|[^'\">{{}}])*>)(?!\s*?\n)(?=[^\n])",
        add_right,
        html,
        flags=RE_FLAGS_IX,
    )

    # template tag breaks
    def should_i_move_template_tag(
        out_format: str, match: re.Match[str]
    ) -> str:
        # ensure template tag is not inside an html tag and also not the first line of the file
        if inside_ignored_block(config, html, match):
            return match.group(1)
        match_start, match_end = match.span()
        if not re.search(
            r"\<(?:"
            + str(config.indent_html_tags)
            # added > as not allowed inside a "" or '' to prevent invalid wild html matches
            # for issue #640
            + r")\b(?:\"[^\">]*\"|'[^'>]*'|{{[^}]*}}|{%[^%]*%}|{\#[^\#]*\#}|[^>{}])*?"
            + re.escape(match.group(1))
            + "$",
            html[:match_end],
            flags=RE_FLAGS_MX,
        ):
            if out_format == "\n%s" and match_start == 0:
                return match.group(1)
            return out_format % match.group(1)

        return match.group(1)

    # template tags
    # break before
    html = re.sub(
        break_char
        + r"\K((?:{%|{{\#)[ ]*?(?:"
        + config.break_template_tags
        + ")[^}]+?[%}]})",
        partial(should_i_move_template_tag, "\n%s"),
        html,
        flags=RE_FLAGS_IMX,
    )

    # break after
    return re.sub(
        rf"((?:{{%|{{{{\#)[ ]*?(?:{config.break_template_tags})(?>{config.template_tags}|[^}}])+?[%}}]}})(?=[^\n])",
        partial(should_i_move_template_tag, "%s\n"),
        html,
        flags=RE_FLAGS_IMX,
    )
