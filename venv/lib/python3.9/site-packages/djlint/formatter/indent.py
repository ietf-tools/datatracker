"""djLint add indentation to html."""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

import json5 as json
import regex as re

from djlint.formatter.attributes import format_attributes
from djlint.helpers import (
    RE_FLAGS_IMSX,
    RE_FLAGS_IMX,
    RE_FLAGS_IX,
    inside_ignored_block,
    is_ignored_block_closing,
    is_ignored_block_opening,
    is_safe_closing_tag,
    is_script_style_block_closing,
    is_script_style_block_opening,
)

if TYPE_CHECKING:
    from djlint.settings import Config


def indent_html(rawcode: str, config: Config) -> str:
    """Indent raw code."""
    if config.profile not in {"handlebars", "golang"}:
        # we can try to fix template tags. ignore handlebars
        # this should be done before indenting to line length
        # calc is preserved.

        def fix_tag_spacing(html: str, match: re.Match[str]) -> str:
            if inside_ignored_block(config, html, match):
                return match.group()

            return f"{match.group(1)} {match.group(2)} {match.group(3)}"

        """
        We should have tags like this:
        {{ tag }}
        {%- tag atrib -%}
        """
        func = partial(fix_tag_spacing, rawcode)

        rawcode = re.sub(
            r"({%-?\+?)[ ]*?(\w(?:(?!%}).)*?)[ ]*?(\+?-?%})", func, rawcode
        )

        rawcode = re.sub(
            r"({{)[ ]*?(\w(?:(?!}}).)*?)[ ]*?(\+?-?}})", func, rawcode
        )

    elif config.profile == "handlebars":

        def fix_handlebars_template_tags(
            html: str, match: re.Match[str]
        ) -> str:
            if inside_ignored_block(config, html, match):
                return match.group()

            return f"{match.group(1)} {match.group(2)}"

        func = partial(fix_handlebars_template_tags, rawcode)
        # handlebars templates
        rawcode = re.sub(r"({{#(?:each|if).+?[^ ])(}})", func, rawcode)

    rawcode_flat_list = re.split(r"\n", rawcode)

    indent = config.indent

    beautified_code = ""
    indent_level = 0
    in_set_tag = False
    is_raw_first_line = False
    in_script_style_tag = False
    is_block_raw = False
    jinja_replace_list = []

    slt_html = config.indent_html_tags

    # here using all tags cause we allow empty tags on one line
    always_self_closing_html = config.always_self_closing_html_tags

    # here using all tags cause we allow empty tags on one line
    slt_template = config.optional_single_line_template_tags

    # nested ignored blocks..
    ignored_level = 0

    for item in rawcode_flat_list:
        is_safe_closing_tag_ = is_safe_closing_tag(config, item)
        is_ignored_block_opening_ = is_ignored_block_opening(config, item)

        # if a raw tag first line
        if not is_block_raw and is_ignored_block_opening_:
            is_raw_first_line = True

        # if a raw tag then start ignoring
        if is_ignored_block_opening_:
            is_block_raw = True
            ignored_level += 1

        if is_script_style_block_opening(config, item):
            in_script_style_tag = True

        if is_safe_closing_tag_:
            ignored_level -= 1
            ignored_level = max(ignored_level, 0)
            if is_block_raw and ignored_level == 0:
                is_block_raw = False

        if (
            not is_block_raw
            and re.search(
                rf"^\s*?(?:{config.ignored_inline_blocks})",
                item,
                flags=RE_FLAGS_IMX,
            )
        ) or (
            not is_block_raw
            and (
                re.search(
                    rf"""^(?:[^<\s].*?)? # start of a line, optionally with some text
                    (?:
                        <({slt_html})(?:(?:>|\b[^>]+?>)(?:.*?)(?:</(?:\1)>)|\b[^>]*?/>) # <span stuff-or-not>stuff</span> or <img stuff /> >>> match 1
                        |(?:<(?:{always_self_closing_html})\b[^>]*?/?>) # <img stuff />
                        |(?:{{%[ ]*?({slt_template})[ ]+?.*?%}})(?:.*?)(?:{{%[ ]+?end(?:\2)[ ]+?.*?%}}) # >>> match 2
                        |{config.ignored_inline_blocks}
                    )[ \t]*?
                    (?:
                    .*? # anything
                    (?: # followed by another slt
                        <({slt_html})(?:(?:>|\b[^>]+?>)(?:.*?)(?:</(?:\3)>)|\b[^>]*?/>) # <span stuff-or-not>stuff</span> or <img stuff /> >>> match 3
                       |(?:<(?:{always_self_closing_html})\b[^>]*?/?>) # <img stuff />
                       |(?:{{%[ ]*?({slt_template})[ ]+?.*?%}})(?:.*?)(?:{{%[ ]+?end(?:\4)[ ]+?.*?%}}) # >>> match 4
                       |{config.ignored_inline_blocks}
                    )[ \t]*?
                    )*? # optional of course
                    [^<]*?$ # with no other tags following until end of line
                """,
                    item,
                    flags=RE_FLAGS_IMX,
                )
            )
        ):
            tmp = (indent * indent_level) + item + "\n"

        # closing set tag
        elif (
            not config.no_set_formatting
            and not is_block_raw
            and in_set_tag
            and re.search(r"^(?!.*\{\%).*%\}.*$", item, flags=RE_FLAGS_IMX)
        ):
            indent_level = max(indent_level - 1, 0)
            in_set_tag = False
            tmp = (indent * indent_level) + item + "\n"

        # closing curly brace inside a set tag
        elif (
            not config.no_set_formatting
            and not is_block_raw
            and in_set_tag
            and re.search(r"^[ ]*}|^[ ]*]", item, flags=RE_FLAGS_IMX)
        ):
            indent_level = max(indent_level - 1, 0)
            tmp = (indent * indent_level) + item + "\n"

        # if unindent, move left
        elif (
            not is_block_raw
            and not is_safe_closing_tag_
            and re.search(config.tag_unindent, item, flags=RE_FLAGS_IMX)
            # and not ending in a slt like <span><strong></strong>.
            and not re.search(
                rf"(<({slt_html})>)(.*?)(</(\2)>[^<]*?$)",
                item,
                flags=RE_FLAGS_IMX,
            )
            and not re.search(
                rf"(<({slt_html})\\b[^>]+?>)(.*?)(</(\2)>[^<]*?$)",
                item,
                flags=RE_FLAGS_IMX,
            )
        ):
            # block to catch inline block followed by a non-break tag
            if re.search(
                rf"(^<({slt_html})>)(.*?)(</(\2)>)", item, flags=RE_FLAGS_IMX
            ) or re.search(
                rf"(^<({slt_html})\b[^>]+?>)(.*?)(</(\2)>)",
                item,
                flags=RE_FLAGS_IMX,
            ):
                # unindent after instead of before
                tmp = (indent * indent_level) + item + "\n"
                indent_level = max(indent_level - 1, 0)
            else:
                indent_level = max(indent_level - 1, 0)
                tmp = (indent * indent_level) + item + "\n"

        elif not is_block_raw and re.search(
            r"^" + str(config.tag_unindent_line), item, flags=RE_FLAGS_IMX
        ):
            tmp = (indent * (indent_level - 1)) + item + "\n"

        # if indent, move right

        # opening set tag
        elif (
            not config.no_set_formatting
            and not is_block_raw
            and not in_set_tag
            and re.search(
                r"^([ ]*{%[ ]*?set)(?!.*%}).*$", item, flags=RE_FLAGS_IMX
            )
        ):
            tmp = (indent * indent_level) + item + "\n"
            indent_level += 1
            in_set_tag = True

        # opening curly brace inside a set tag
        elif (
            not config.no_set_formatting
            and not is_block_raw
            and in_set_tag
            and re.search(
                r"(\{(?![^{}]*%[}\s])(?=[^{}]*$)|\[(?=[^\]]*$))",
                item,
                flags=RE_FLAGS_IMX,
            )
        ) or (
            re.search(
                r"^(?:" + str(config.tag_indent) + r")",
                item,
                flags=RE_FLAGS_IMX,
            )
            and not is_block_raw
        ):
            tmp = (indent * indent_level) + item + "\n"
            indent_level += 1

        elif is_raw_first_line or (is_safe_closing_tag_ and not is_block_raw):
            tmp = (indent * indent_level) + item + "\n"

        elif is_block_raw or not item.strip():
            tmp = item + "\n"

        # otherwise, just leave same level
        elif not config.preserve_leading_space:
            # if we are not trying to preserve indenting
            # on text, the add it now.
            tmp = (indent * indent_level) + item + "\n"
        else:
            tmp = item + "\n"

        # if a opening raw tag then start ignoring.. only if there is no closing tag
        # on the same line
        if is_ignored_block_opening_:
            is_block_raw = True
            is_raw_first_line = False

        # if a normal tag, we can try to expand attributes
        elif not is_block_raw:
            # get leading space, and attributes

            func = partial(format_attributes, config, item)

            tmp = re.sub(
                config.indent_html_tags_regex, func, tmp, flags=RE_FLAGS_IX
            )

        # turn off raw block if we hit end - for one line raw blocks, but not an inline raw
        if (
            not in_script_style_tag
            or is_script_style_block_closing(config, item)
        ) and is_ignored_block_closing(config, item):
            in_script_style_tag = False
            if not is_safe_closing_tag_:
                ignored_level -= 1
                ignored_level = max(ignored_level, 0)
            if ignored_level == 0:
                is_block_raw = False

        # detect the outer quotes for jinja
        if config.profile == "jinja":
            for match in re.finditer(
                r"=([\"'])(\{\{[\s\S]*?\}\})\1", tmp, flags=re.M
            ):
                outer_quotes = match.group(1)
                inner_content = match.group(2)
                jinja_replace_list.append({
                    "outer_quote": outer_quotes,
                    "content": inner_content,
                })

        beautified_code += tmp

    # try to fix internal formatting of set tag
    def format_data(
        config: Config, contents: str, tag_size: int, leading_space: str
    ) -> str:
        try:
            # try to format the contents as json
            data = json.loads(contents)
            contents = json.dumps(
                data, trailing_commas=False, ensure_ascii=False, quote_keys=True
            )

            if tag_size + len(contents) >= config.max_line_length:
                # if the line is too long we can indent the json
                contents = json.dumps(
                    data,
                    indent=config.indent_size,
                    trailing_commas=False,
                    ensure_ascii=False,
                    quote_keys=True,
                )

        except Exception:
            # was not json.. try to eval as set
            try:
                # if contents is a python keyword, do not evaluate it.
                evaluated = (
                    str(eval(contents))  # noqa: S307
                    if contents != "object"
                    else contents
                )
                # need to unwrap the eval
                contents = (
                    evaluated[1:-1]
                    if contents[:1] != "(" and evaluated[:1] == "("
                    else evaluated
                )
            except Exception:
                contents = contents.strip()

        return (f"\n{leading_space}").join(contents.splitlines())

    def format_set(config: Config, html: str, match: re.Match[str]) -> str:
        if inside_ignored_block(config, html, match):
            return match.group()

        leading_space = match.group(1)
        open_bracket = match.group(2)
        tag = match.group(3)
        close_bracket = match.group(5)
        contents = match.group(4).strip()
        contents_split = contents.split("=", 1)

        if len(contents_split) > 1:
            contents = (
                contents_split[0].strip()
                + " = "
                + format_data(
                    config,
                    contents_split[-1],
                    len(f"{open_bracket} {tag}  {close_bracket}"),
                    leading_space,
                )
            )

        return f"{leading_space}{open_bracket} {tag} {contents} {close_bracket}"

    def format_function(config: Config, html: str, match: re.Match[str]) -> str:
        if inside_ignored_block(config, html, match):
            return match.group()

        leading_space = match.group(1)
        open_bracket = match.group(2)
        tag = match.group(3).strip()
        index = (match.group(5) or "").strip()
        close_bracket = match.group(6)
        contents = format_data(
            config,
            match.group(4).strip()[1:-1],
            len(f"{open_bracket} {tag}() {close_bracket}"),
            leading_space,
        )

        # # define cleaned match with both quote styles
        cleaned_match = f"{leading_space}{open_bracket} {tag}({contents}){index} {close_bracket}"

        if config.profile == "jinja":
            outer_quotes = None
            inner_quotes = None

            # Determine user quote type
            for jinja_content in jinja_replace_list:
                content = cleaned_match.replace(
                    '"', "'"
                )  # Replace double quotes
                if content == jinja_content.get("content"):
                    outer_quotes = jinja_content.get("outer_quote")
                    inner_quotes = "'" if outer_quotes == '"' else '"'
                    break
                content = cleaned_match.replace(
                    "'", '"'
                )  # Replace single quotes
                if content == jinja_content.get("content"):
                    outer_quotes = jinja_content.get("outer_quote")
                    inner_quotes = '"' if outer_quotes == "'" else "'"
                    break

            if outer_quotes is not None and inner_quotes is not None:
                # Replace all content inner quotes and remove trailing/leading spaces
                cleaned_contents = re.sub(
                    rf"(?<=\{re.escape(outer_quotes)})\s+|\s+(?=\{re.escape(outer_quotes)})",
                    "",
                    contents.replace(outer_quotes, inner_quotes),
                )

                # Update cleaned match
                cleaned_match = f"{leading_space}{open_bracket} {tag}({cleaned_contents}){index} {close_bracket}"
                cleaned_match = cleaned_match.strip()

        return cleaned_match

    if not config.no_set_formatting:
        func = partial(format_set, config, beautified_code)
        # format set contents
        beautified_code = re.sub(
            r"([ ]*)({%-?)[ ]*(set)[ ]+?((?:(?!%}).)*?)(-?%})",
            func,
            beautified_code,
            flags=RE_FLAGS_IMSX,
        )

    if not config.no_function_formatting:
        func = partial(format_function, config, beautified_code)
        # format function contents
        beautified_code = re.sub(
            r"([ ]*)({{-?\+?)[ ]*?((?:(?!}}).)*?\w)(\((?:\"[^\"]*\"|'[^']*'|[^\)])*?\)[ ]*)((?:\[[^\]]*?\]|\.[^\s]+)[ ]*)?((?:(?!}}).)*?-?\+?}})",
            func,
            beautified_code,
            flags=RE_FLAGS_IMSX,
        )

    if not config.preserve_blank_lines:
        beautified_code = beautified_code.lstrip()

    return beautified_code.rstrip() + "\n"
