"""djLint function to call cssbeautifier."""

from __future__ import annotations

from functools import partial
from io import StringIO
from typing import TYPE_CHECKING

import cssbeautifier
import regex as re
from cssbeautifier.css.options import BeautifierOptions

from djlint.helpers import RE_FLAGS_IS, child_of_unformatted_block

if TYPE_CHECKING:
    from djlint.settings import Config


def format_css(html: str, config: Config) -> str:
    """Format css inside <style> tags."""

    def launch_formatter(
        config: Config, html: str, match: re.Match[str]
    ) -> str:
        """Add break after if not in ignored block."""
        if child_of_unformatted_block(config, html, match):
            return match.group()

        if not match.group(3).strip():
            return match.group()

        indent = len(match.group(1)) * " "

        # because of the param options for css-beautifier we cannot pass
        # in a fixed space leading.
        # so, call formatter twice, once with a fake indent.
        # check which lines changed (these are the formattable lines)
        # and add the leading space to them.

        config.css_config["indent_level"] = 1
        opts = BeautifierOptions(config.css_config)
        beautified_lines = cssbeautifier.beautify(
            match.group(3), opts
        ).splitlines()

        config.css_config["indent_level"] = 2
        opts = BeautifierOptions(config.css_config)
        beautified_lines_test = cssbeautifier.beautify(
            match.group(3), opts
        ).splitlines()

        with StringIO() as buf:
            for line, test in zip(beautified_lines, beautified_lines_test):
                buf.write("\n")
                if line != test:
                    buf.write(indent)
                buf.write(line)
            beautified = buf.getvalue()

        return match.group(1) + match.group(2) + beautified + "\n" + indent

    func = partial(launch_formatter, config, html)

    return re.sub(
        r"([ ]*?)(<(?:style)\b(?:\"[^\"]*\"|'[^']*'|{[^}]*}|[^'\">{}])*>)(.*?)(?=</style>)",
        func,
        html,
        flags=RE_FLAGS_IS,
    )
