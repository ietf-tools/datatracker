"""Collection of shared djLint functions."""
# ruff: noqa: ERA001

from __future__ import annotations

import itertools
from functools import cache
from typing import TYPE_CHECKING

import regex as re

if TYPE_CHECKING:
    from collections.abc import Iterable
    from typing import Final

    from typing_extensions import TypeVar

    from djlint.settings import Config

    T = TypeVar("T")

RE_FLAGS_IS: Final = re.I | re.S
RE_FLAGS_IX: Final = re.I | re.X
RE_FLAGS_MS: Final = re.M | re.S
RE_FLAGS_MX: Final = re.M | re.X
RE_FLAGS_IMS: Final = re.I | re.M | re.S
RE_FLAGS_IMX: Final = re.I | re.M | re.X
RE_FLAGS_ISX: Final = re.I | re.S | re.X
RE_FLAGS_IMSX: Final = re.I | re.M | re.S | re.X


def _last_item(iterable: Iterable[T], /) -> T | None:
    last = None
    for item in iterable:
        last = item
    return last


def is_ignored_block_opening(config: Config, item: str) -> bool:
    """Find ignored group opening.

    A valid ignored group opening tag will not be part of a
    single line block.
    """
    inline = _last_item(
        re.finditer(config.ignored_blocks_inline, item, flags=RE_FLAGS_IMSX)
    )
    last_index = (
        inline.end()  # get the last index. The ignored opening should start after this.
        if inline
        else 0
    )
    return bool(
        re.search(
            config.ignored_block_opening, item[last_index:], flags=RE_FLAGS_IX
        )
    )


def is_script_style_block_opening(config: Config, item: str) -> bool:
    """Find ignored group opening.

    A valid ignored group opening tag will not be part of a
    single line block.
    """
    inline = _last_item(
        re.finditer(config.script_style_inline, item, flags=RE_FLAGS_IMSX)
    )
    last_index = (
        inline.end()  # get the last index. The ignored opening should start after this.
        if inline
        else 0
    )
    return bool(
        re.search(
            config.script_style_opening, item[last_index:], flags=RE_FLAGS_IX
        )
    )


def inside_protected_trans_block(
    config: Config, html: str, match: re.Match[str]
) -> bool:
    """Find ignored group closing.

    A valid ignored group closing tag will not be part of a
    single line block.

    True = non indentable > inside ignored trans block
    False = indentable > either inside a trans trimmed block, or somewhere else, but not a trans non trimmed :)
    """
    close_block = re.search(
        config.ignored_trans_blocks_closing, match.group(), flags=RE_FLAGS_IX
    )

    if not close_block:
        return False

    non_trimmed = _last_item(
        re.finditer(config.ignored_trans_blocks, html, flags=RE_FLAGS_ISX)
    )

    trimmed = _last_item(
        re.finditer(config.trans_trimmed_blocks, html, flags=RE_FLAGS_ISX)
    )

    # who is max?
    if non_trimmed and (not trimmed or non_trimmed.end() > trimmed.end()):
        # non trimmed!
        # check that this is not an inline block.
        non_trimmed_inline = bool(
            re.search(
                config.ignored_trans_blocks, match.group(), flags=RE_FLAGS_ISX
            )
        )

        if non_trimmed_inline:
            last_index = non_trimmed.end()  # get the last index. The ignored opening should start after this.

            return bool(
                re.search(
                    config.ignored_trans_blocks_closing,
                    html[last_index:],
                    flags=RE_FLAGS_IX,
                )
            )

        return close_block.end() <= non_trimmed.end()

    if trimmed:
        # inside a trimmed block, we can return true to continue as if
        # this is a indentable block
        return close_block.end() > trimmed.end()
    return False

    # print(close_block)
    # if non_trimmed:
    #     last_index = (
    #         non_trimmed[-1].end()
    #     )  # get the last index. The ignored opening should start after this.

    # return re.search(
    #     config.ignored_trans_blocks_closing,
    #     html[last_index:],
    #     flags=RE_FLAGS_IX,
    # )


def is_ignored_block_closing(config: Config, item: str) -> bool:
    """Find ignored group closing.

    A valid ignored group closing tag will not be part of a
    single line block.
    """
    inline = _last_item(
        re.finditer(config.ignored_inline_blocks, item, flags=RE_FLAGS_IX)
    )
    last_index = (
        inline.end()  # get the last index. The ignored opening should start after this.
        if inline
        else 0
    )
    return bool(
        re.search(
            config.ignored_block_closing, item[last_index:], flags=RE_FLAGS_IX
        )
    )


def is_script_style_block_closing(config: Config, item: str) -> bool:
    """Find ignored group closing.

    A valid ignored group closing tag will not be part of a
    single line block.
    """
    inline = _last_item(
        re.finditer(config.script_style_inline, item, flags=RE_FLAGS_IX)
    )
    last_index = (
        inline.end()  # get the last index. The ignored opening should start after this.
        if inline
        else 0
    )
    return bool(
        re.search(
            config.script_style_closing, item[last_index:], flags=RE_FLAGS_IX
        )
    )


def is_safe_closing_tag(config: Config, item: str) -> bool:
    """Find ignored group opening.

    A valid ignored group opening tag will not be part of a
    single line block.
    """
    inline = _last_item(
        re.finditer(
            config.ignored_inline_blocks + r" | " + config.ignored_blocks,
            item,
            flags=RE_FLAGS_IMSX,
        )
    )
    last_index = (
        inline.end()  # get the last index. The ignored opening should start after this.
        if inline
        else 0
    )
    return bool(
        re.search(config.safe_closing_tag, item[last_index:], flags=RE_FLAGS_IX)
    )


def inside_template_block(
    config: Config, html: str, match: re.Match[str]
) -> bool:
    """Check if a re.Match is inside of a template block."""
    match_start, match_end = match.span()
    for ignored_match in re.finditer(
        config.template_blocks, html, flags=RE_FLAGS_IMSX
    ):
        ignored_match_start, ignored_match_end = ignored_match.span()
        if (
            ignored_match_start <= match_start
            and match_end <= ignored_match_end
        ):
            return True
    return False


@cache
def _inside_html_attribute(
    html: str, /, *, html_tag_regex: str
) -> tuple[tuple[int, int], ...]:
    return tuple(
        # group 3 are the attributes
        x.span(3)
        for x in re.finditer(html_tag_regex, html, flags=RE_FLAGS_IMSX)
    )


def inside_html_attribute(
    config: Config, html: str, match: re.Match[str]
) -> bool:
    """Check if a re.Match is inside of an html attribute."""
    match_start, match_end = match.span()
    for ignored_match_start, ignored_match_end in _inside_html_attribute(
        html, html_tag_regex=config.html_tag_regex
    ):
        # span = (-1, -1) if no attributes are present
        if (
            ignored_match_start <= match_start
            and match_end <= ignored_match_end
        ):
            return True
    return False


def inside_ignored_linter_block(
    config: Config, html: str, match: re.Match[str]
) -> bool:
    """Check if a re.Match is inside of a ignored linter block."""
    match_start, match_end = match.span()
    for ignored_match in re.finditer(
        config.ignored_linter_blocks, html, flags=RE_FLAGS_IMSX
    ):
        ignored_match_start, ignored_match_end = ignored_match.span()
        if (
            ignored_match_start <= match_start
            and match_end <= ignored_match_end
        ):
            return True
    return False


@cache
def _inside_ignored_block(
    html: str, /, *, ignored_blocks: str, ignored_inline_blocks: str
) -> tuple[tuple[int, int], ...]:
    return tuple(
        x.span()
        for x in itertools.chain(
            re.finditer(ignored_blocks, html, flags=RE_FLAGS_IMSX),
            re.finditer(ignored_inline_blocks, html, flags=RE_FLAGS_IX),
        )
    )


def inside_ignored_block(
    config: Config, html: str, match: re.Match[str]
) -> bool:
    """Do not add whitespace if the tag is in a non indent block."""
    match_start, match_end = match.span()
    for ignored_match_start, ignored_match_end in _inside_ignored_block(
        html,
        ignored_blocks=config.ignored_blocks,
        ignored_inline_blocks=config.ignored_inline_blocks,
    ):
        if (
            ignored_match_start <= match_start
            and match_end <= ignored_match_end
        ):
            return True
    return False


@cache
def _child_of_unformatted_block(
    html: str, /, *, unformatted_blocks: str, unformatted_blocks_coarse: str
) -> tuple[tuple[int, int], ...]:
    if not re.search(unformatted_blocks_coarse, html, flags=RE_FLAGS_IMSX):
        return ()
    return tuple(
        x.span()
        for x in re.finditer(unformatted_blocks, html, flags=RE_FLAGS_IMSX)
    )


def child_of_unformatted_block(
    config: Config, html: str, match: re.Match[str]
) -> bool:
    """Do not add whitespace if the tag is in a non indent block."""
    match_start, match_end = match.span()
    for ignored_match_start, ignored_match_end in _child_of_unformatted_block(
        html,
        unformatted_blocks=config.unformatted_blocks,
        unformatted_blocks_coarse=config.unformatted_blocks_coarse,
    ):
        if ignored_match_start < match_start and match_end <= ignored_match_end:
            return True
    return False


def child_of_ignored_block(
    config: Config, html: str, match: re.Match[str]
) -> bool:
    """Do not add whitespace if the tag is in a non indent block."""
    match_start, match_end = match.span()
    for ignored_match in itertools.chain(
        re.finditer(config.ignored_blocks, html, flags=RE_FLAGS_IMSX),
        re.finditer(config.ignored_inline_blocks, html, flags=RE_FLAGS_IX),
    ):
        ignored_match_start, ignored_match_end = ignored_match.span()
        if ignored_match_start < match_start and match_end <= ignored_match_end:
            return True
    return False


@cache
def _overlaps_ignored_block(
    html: str, /, *, ignored_blocks: str, ignored_inline_blocks: str
) -> tuple[tuple[int, int], ...]:
    return tuple(
        x.span()
        for x in itertools.chain(
            re.finditer(ignored_blocks, html, flags=RE_FLAGS_IMSX),
            re.finditer(ignored_inline_blocks, html, flags=RE_FLAGS_IX),
        )
    )


def overlaps_ignored_block(
    config: Config, html: str, match: re.Match[str]
) -> bool:
    """Do not add whitespace if the tag is in a non indent block."""
    match_start, match_end = match.span()
    for ignored_match_start, ignored_match_end in _overlaps_ignored_block(
        html,
        ignored_blocks=config.ignored_blocks,
        ignored_inline_blocks=config.ignored_inline_blocks,
    ):
        # don't require the match to be fully inside the ignored block.
        # poorly build html will probably span ignored blocks and should be ignored.
        if (ignored_match_start <= match_start <= ignored_match_end) or (
            ignored_match_start <= match_end <= ignored_match_end
        ):
            return True
    return False


def inside_ignored_rule(
    config: Config, html: str, match: re.Match[str], rule: str
) -> bool:
    """Check if match is inside an ignored pattern."""
    match_start, match_end = match.span()
    for rule_regex in config.ignored_rules:
        for ignored_match in re.finditer(rule_regex, html, flags=RE_FLAGS_ISX):
            ignored_match_start, ignored_match_end = ignored_match.span()
            if (
                (ignored_match_start <= match_start <= ignored_match_end)
                and rule in re.split(r"\s|,", ignored_match.group(1).strip())
            ) or (
                (ignored_match_start <= match_end <= ignored_match_end)
                and not ignored_match.group(1).strip()
            ):
                return True
    return False
