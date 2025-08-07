"""Djlint html linter."""

from __future__ import annotations

import importlib
from collections.abc import Sequence
from typing import TYPE_CHECKING

import regex as re

from djlint.helpers import (
    inside_ignored_linter_block,
    inside_ignored_rule,
    overlaps_ignored_block,
)

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

    from djlint.settings import Config
    from djlint.types import LintError


flags = {
    "re.A": re.A,
    "re.ASCII": re.ASCII,
    "re.I": re.I,
    "re.IGNORECASE": re.IGNORECASE,
    "re.M": re.M,
    "re.MULTILINE": re.MULTILINE,
    "re.S": re.S,
    "re.DOTALL": re.DOTALL,
    "re.X": re.X,
    "re.VERBOSE": re.VERBOSE,
    "re.L": re.L,
    "re.LOCALE": re.LOCALE,
}


def build_flags(flag_list: str | int) -> int:
    """Build list of regex flags."""
    if isinstance(flag_list, int):
        return flag_list
    split_flags = flag_list.split("|")
    combined_flags = 0
    for flag in split_flags:
        combined_flags |= flags[flag.strip()]
    return combined_flags


def get_line(start: int, line_ends: Sequence[Mapping[str, int]]) -> str:
    """Get the line number and index of match."""
    line = next(pair for pair in line_ends if pair["end"] > start)

    return "{}:{}".format(line_ends.index(line) + 1, start - line["start"])


def linter(
    config: Config, html: str, filename: str, filepath: str
) -> dict[str, list[LintError]]:
    """Lint a html string."""
    errors: dict[str, list[LintError]] = {filename: []}
    # build list of line ends for file
    line_ends = [
        {"start": m.start(), "end": m.end()}
        for m in re.finditer(r"(?:.*\n)|(?:[^\n]+$)", html)
    ]

    ignored_rules: set[str] = set()

    # remove ignored rules for file
    for pattern, rules in config.per_file_ignores.items():
        if re.search(pattern, filepath, flags=re.X):
            ignored_rules.update(x.strip() for x in rules.split(","))

    for rule in config.linter_rules:
        rule = rule["rule"]  # noqa: PLW2901

        # skip ignored rules
        if rule["name"] in ignored_rules:
            continue

        # rule based on python module
        if "python_module" in rule:
            rule_module = importlib.import_module(rule["python_module"])
            module_errors = rule_module.run(
                rule=rule,
                config=config,
                html=html,
                filepath=filepath,
                line_ends=line_ends,
            )
            if not isinstance(module_errors, Sequence):
                msg = (
                    f"Error: {rule['name']} python_module run() should return"
                    " a sequence of dict with keys: code, line, match, message."
                )
                raise AssertionError(msg)
            errors[filename].extend(module_errors)

        # rule based on patterns
        else:
            for pattern in rule["patterns"]:
                for match in re.finditer(
                    pattern, html, flags=build_flags(rule.get("flags", "re.S"))
                ):
                    if (
                        not overlaps_ignored_block(config, html, match)
                        and not inside_ignored_rule(
                            config, html, match, rule["name"]
                        )
                        and not inside_ignored_linter_block(config, html, match)
                    ):
                        errors[filename].append({
                            "code": rule["name"],
                            "line": get_line(match.start(), line_ends),
                            "match": match.group().strip()[:20],
                            "message": rule["message"],
                        })

    # remove duplicate matches
    for filename, error_dict in errors.items():  # noqa: PLR1704
        unique_errors = []
        for dict_ in error_dict:
            if dict_ not in unique_errors:
                unique_errors.append(dict_)
        errors[filename] = unique_errors
    return errors


def lint_file(config: Config, this_file: Path) -> dict[str, list[LintError]]:
    """Check file for formatting errors."""
    filename = str(this_file)

    html = this_file.read_text(encoding="utf-8")

    return linter(config, html, filename, this_file.as_posix())
