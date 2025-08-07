"""rule H025: Check for orphans html tags."""

from __future__ import annotations

import copy
from itertools import chain
from typing import TYPE_CHECKING

import regex as re

from djlint.helpers import (
    RE_FLAGS_IX,
    inside_ignored_linter_block,
    inside_ignored_rule,
    overlaps_ignored_block,
)
from djlint.lint import get_line

if TYPE_CHECKING:
    from typing_extensions import Any

    from djlint.settings import Config
    from djlint.types import LintError


def run(
    rule: dict[str, Any],
    config: Config,
    html: str,
    filepath: str,
    line_ends: list[dict[str, int]],
    *args: Any,
    **kwargs: Any,
) -> tuple[LintError, ...]:
    """Check for orphans html tags."""
    open_tags: list[re.Match[str]] = []
    orphan_tags: list[re.Match[str]] = []

    for match in re.finditer(
        r"<(/?(\w+))\s*(" + config.attribute_pattern + r"|\s*)*\s*?>",
        html,
        flags=re.X,
    ):
        if match.group(1) and not re.search(
            rf"^/?{config.always_self_closing_html_tags}\b",
            match.group(1),
            flags=RE_FLAGS_IX,
        ):
            # close tags should equal open tags
            if match.group(1)[0] != "/":
                open_tags.insert(0, match)
            else:
                for i, tag in enumerate(copy.deepcopy(open_tags)):
                    if tag.group(2) == match.group(1)[1:]:
                        open_tags.pop(i)
                        break
                else:
                    # there was no open tag matching the close tag
                    orphan_tags.append(match)

    return tuple(
        {
            "code": rule["name"],
            "line": get_line(match.start(), line_ends),
            "match": match.group().strip()[:20],
            "message": rule["message"],
        }
        for match in chain(open_tags, orphan_tags)
        if (
            not overlaps_ignored_block(config, html, match)
            and not inside_ignored_rule(config, html, match, rule["name"])
            and not inside_ignored_linter_block(config, html, match)
        )
    )
