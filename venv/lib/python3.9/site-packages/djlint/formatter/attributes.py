"""Format attributes."""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

import regex as re

from djlint.helpers import RE_FLAGS_IMX, RE_FLAGS_IX, child_of_ignored_block

if TYPE_CHECKING:
    from djlint.settings import Config


def format_template_tags(config: Config, attributes: str, spacing: int) -> str:
    """Format template tags in attributes."""
    # find break tags, add breaks + indent
    # find unindent lines and move back
    # put short stuff back on one line

    def add_indentation(config: Config, attributes: str, spacing: int) -> str:
        """Indent template tags.

        |    <form class="this"
        |    ----- attribute name
        |
        |    <form class="this"
        |---^ leading space
        |
        |    <form class="this"
        |    ^----^ base indent
        |
        """
        indent = 0
        indented = ""
        indent_adder = spacing or 0

        for line_number, line in enumerate(attributes.splitlines()):
            # when checking for template tag, use "match" to force start of line check.
            if re.match(
                config.template_unindent, line.strip(), flags=RE_FLAGS_IX
            ):
                indent -= 1
                tmp = (
                    (indent * config.indent)
                    + (indent_adder * " ")
                    + line.strip()
                )

            elif re.match(
                config.tag_unindent_line, line.strip(), flags=RE_FLAGS_IX
            ):
                # if we are leaving an indented group, then remove the indent_adder
                tmp = (
                    max(indent - 1, 0) * config.indent
                    + indent_adder * " "
                    + line.strip()
                )

            elif re.search(
                config.template_indent, line.strip(), flags=RE_FLAGS_IX
            ) and not re.search(
                config.template_unindent, line.strip(), flags=RE_FLAGS_IX
            ):
                # for open tags, search, but then check that they are not closed.
                tmp = (
                    (indent * config.indent)
                    + (indent_adder * " ")
                    + line.strip()
                )
                indent += 1

            else:
                tmp = (
                    (indent * config.indent)
                    + (indent_adder * " ")
                    + line.strip()
                )

            if line_number == 0:
                # don't touch first line
                indented += line.strip()
            elif tmp.strip():
                indented += f"\n{tmp}"

        return indented

    def add_break(pattern: str, match: re.Match[str]) -> str:
        """Make a decision if a break should be added."""
        if pattern == "before":
            return f"\n{match.group()}"

        return f"{match.group(1)}\n{match.group(2).strip()}"

    break_char = config.break_before

    func = partial(add_break, "before")

    attributes = re.sub(
        break_char
        + r".\K((?:{%|{{\#)[ ]*?(?:"
        + config.break_template_tags
        + ")[^}]+?[%|}]})",
        func,
        attributes,
        flags=RE_FLAGS_IMX,
    )

    func = partial(add_break, "after")
    # break after
    attributes = re.sub(
        r"((?:{%|{{\#)[ ]*?(?:"
        + config.break_template_tags
        + ")[^}]+?[%|}]})([^\n]+)$",
        func,
        attributes,
        flags=RE_FLAGS_IMX,
    )
    return add_indentation(config, attributes, spacing)


def format_attributes(config: Config, html: str, match: re.Match[str]) -> str:
    """Spread long attributes over multiple lines."""
    # check that we are not inside an ignored block
    if len(
        match.group(3).strip()
    ) < config.max_attribute_length or child_of_ignored_block(
        config, html, match
    ):
        return match.group()

    leading_space = match.group(1)

    tag = match.group(2) + " "

    spacing = leading_space + len(tag) * " "

    attributes = []

    # format attributes as groups
    for attr_grp in re.finditer(
        config.attribute_pattern, match.group(3).strip(), flags=re.X
    ):
        attrib_name = attr_grp.group(1)
        is_quoted = attr_grp.group(2) and attr_grp.group(2)[0] in {"'", '"'}
        quote = attr_grp.group(2)[0] if is_quoted else '"'

        attrib_value = None

        if attr_grp.group(2) and attr_grp.group(2)[0] == attr_grp.group(2)[-1]:
            if attr_grp.group(2)[0] == "'":
                attrib_value = attr_grp.group(2).strip("'")

            elif attr_grp.group(2)[0] == '"':
                attrib_value = attr_grp.group(2).strip('"')

            else:
                attrib_value = attr_grp.group(2)
        else:
            attrib_value = attr_grp.group(2)

        standalone = attr_grp.group(3)

        quote_length = 1

        if attrib_name and attrib_value:
            # for the equals sign
            quote_length += 1

        join_space = (
            f"\n{spacing}"
            if config.format_attribute_template_tags
            else (
                f"\n{spacing}" + (quote_length + len(attrib_name or "")) * " "
            )
        )

        # format style attribute
        if attrib_name and attrib_name.lower() == "style":
            attrib_value = f";{join_space}".join(
                stripped
                for value in attrib_value.split(";")
                if (stripped := value.strip())
            )

        elif attrib_name and attrib_name.lower() in {
            "srcset",
            "data-srcset",
            "sizes",
        }:
            # vw
            attrib_value = f"w,{join_space}".join(
                stripped
                for value in attrib_value.split("w,")
                if (stripped := value.strip())
            )
            # px
            attrib_value = f"x,{join_space}".join(
                stripped
                for value in attrib_value.split("x,")
                if (stripped := value.strip())
            )

        # format template stuff
        if config.format_attribute_template_tags:
            if attrib_value and attrib_name not in config.ignored_attributes:
                attrib_value = format_template_tags(
                    config,
                    attrib_value,
                    len(spacing) + len(attrib_name or "") + quote_length,
                )

            if standalone:
                standalone = format_template_tags(
                    config, standalone, len(spacing) + len(attrib_name or "")
                )

        if (attrib_name and attrib_value) or is_quoted:
            attrib_value = attrib_value or ""
            attributes.append(f"{attrib_name}={quote}{attrib_value}{quote}")
        else:
            attributes.append(
                (attrib_name or "") + (attrib_value or "") + (standalone or "")
            )
    attribute_string = f"\n{spacing}".join(x for x in attributes if x)

    close = match.group(4)

    attribute_string = f"{leading_space}{tag}{attribute_string}{close}"

    # clean trailing spaces added by breaks
    attribute_string = "\n".join(
        x.rstrip() for x in attribute_string.splitlines()
    )

    return f"{attribute_string}"
