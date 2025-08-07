"""Build src file list."""

from __future__ import annotations

from typing import TYPE_CHECKING

import regex as re
from click import echo
from colorama import Fore

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

    from djlint.settings import Config


def get_src(src: Iterable[Path], config: Config) -> list[Path]:
    """Get source files."""
    paths = []
    for item in src:
        # normalize path

        normalized_item = item.resolve()

        if normalized_item.is_file():
            if no_pragma(config, normalized_item) and (
                not config.use_gitignore
                or not config.gitignore.match_file(normalized_item)
            ):
                paths.append(normalized_item)
            continue

        # remove leading . from extension
        extension = config.extension.removeprefix(".")

        paths.extend(
            x
            for x in normalized_item.glob(f"**/*.{extension}")
            if (
                not re.search(config.exclude, x.as_posix(), flags=re.X)
                and no_pragma(config, x)
                and (
                    not config.use_gitignore
                    or not config.gitignore.match_file(x)
                )
            )
        )

    if not paths:
        echo(Fore.BLUE + "No files to check! 😢")

    return paths


html_patterns = (r"<!--\s*djlint\:on\s*-->",)
django_jinja_patterns = (
    r"\{#\s*djlint\:on\s*#\}",
    r"\{%\s*comment\s*%\}\s*djlint\:on\s*\{%\s*endcomment\s*%\}",
)
nunjucks_patterns = (r"\{#\s*djlint\:on\s*#\}",)
handlebars_patterns = (r"\{\{!--\s*djlint\:on\s*--\}\}",)
golang_patterns = (r"\{\{-?\s*/\*\s*djlint\:on\s*\*/\s*-?\}\}",)


def no_pragma(config: Config, this_file: Path) -> bool:
    """Verify there is no pragma present."""
    if not config.require_pragma:
        return True

    with this_file.open(encoding="utf-8") as open_file:
        first_line = open_file.readline()

    pragma_patterns = {
        "html": html_patterns,
        "django": django_jinja_patterns + html_patterns,
        "jinja": django_jinja_patterns + html_patterns,
        "nunjucks": nunjucks_patterns + html_patterns,
        "handlebars": handlebars_patterns + html_patterns,
        "golang": golang_patterns + html_patterns,
        "angular": html_patterns,
        "all": django_jinja_patterns
        + nunjucks_patterns
        + handlebars_patterns
        + golang_patterns
        + html_patterns,
    }

    for pattern in pragma_patterns[config.profile]:
        if re.match(pattern, first_line):
            return True
    return False
