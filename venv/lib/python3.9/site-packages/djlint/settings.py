"""Settings for reformater."""

from __future__ import annotations

import json
import logging
import sys
from itertools import chain
from pathlib import Path
from typing import TYPE_CHECKING

import yaml
from click import echo
from colorama import Fore
from pathspec import PathSpec
from pathspec.patterns.gitwildmatch import GitWildMatchPatternError

from djlint.const import HTML_TAG_NAMES, HTML_VOID_ELEMENTS

if sys.version_info >= (3, 11):
    try:
        import tomllib
    except ImportError:
        # Help users on older alphas
        if not TYPE_CHECKING:
            import tomli as tomllib
else:
    import tomli as tomllib

if sys.version_info >= (3, 11):
    from typing import final
else:
    from typing_extensions import final

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Mapping

    from typing_extensions import Any, TypeVar

    _TMappingStrAny = TypeVar("_TMappingStrAny", bound=Mapping[str, Any])


logger = logging.getLogger(__name__)


def find_project_root(src: Path) -> Path:
    """Attempt to get the project root."""
    for directory in (src, *src.parents):
        if (directory / ".git").exists():
            return directory

        if (directory / ".hg").is_dir():
            return directory

        if (directory / "pyproject.toml").is_file():
            return directory

        if (directory / "djlint.toml").is_file():
            return directory

        if (directory / ".djlintrc").is_file():
            return directory

    return directory


def load_gitignore(root: Path) -> PathSpec:
    """Search upstream for a .gitignore file."""
    gitignore = root / ".gitignore"
    if gitignore.is_file():
        with gitignore.open(encoding="utf-8") as this_file:
            git_lines = this_file.readlines()
    else:
        git_lines = []

    try:
        return PathSpec.from_lines("gitwildmatch", git_lines)

    except GitWildMatchPatternError as e:
        echo(f"Could not parse {gitignore}: {e}", err=True)
        raise


def find_pyproject(root: Path) -> Path | None:
    """Search upstream for a pyproject.toml file."""
    pyproject = root / "pyproject.toml"

    if pyproject.is_file():
        return pyproject

    return None


def find_djlint_toml(root: Path) -> Path | None:
    """Search upstream for a djlint.toml file."""
    djlint_toml = root / "djlint.toml"

    if djlint_toml.is_file():
        return djlint_toml

    return None


def find_djlintrc(root: Path) -> Path | None:
    """Search upstream for a .djlintrc file."""
    djlintrc = root / ".djlintrc"

    if djlintrc.is_file():
        return djlintrc

    return None


def find_djlint_rules(root: Path) -> Path | None:
    """Search upstream for a .djlint_rules.yaml file."""
    rules = root / ".djlint_rules.yaml"

    if rules.is_file():
        return rules

    return None


def load_pyproject_config(filepath: Path) -> Any:
    """Load djlint config from pyproject.toml."""
    data = tomllib.loads(filepath.read_text(encoding="utf-8"))
    return data.get("tool", {}).get("djlint", {})


def load_djlint_toml_config(filepath: Path) -> dict[str, Any]:
    """Load djlint config from djlint.toml."""
    return tomllib.loads(filepath.read_text(encoding="utf-8"))


def load_djlintrc_config(filepath: Path) -> Any:
    """Load djlint config from .djlintrc."""
    return json.loads(filepath.read_bytes())


def load_project_settings(src: Path, config: Path | None) -> dict[str, Any]:
    """Load djlint config."""
    djlint_content: dict[str, Any] = {}

    if config:
        try:
            if config.name == "pyproject.toml":
                djlint_content.update(load_pyproject_config(config))
            elif config.suffix == ".toml":
                djlint_content.update(load_djlint_toml_config(config))
            else:
                djlint_content.update(load_djlintrc_config(config))
        except Exception as error:
            logger.error(
                "%sFailed to load config file %s. %s", Fore.RED, config, error
            )

    if pyproject_file := find_pyproject(src):
        try:
            content = load_pyproject_config(pyproject_file)
        except Exception as error:
            logger.error(
                "%sFailed to load pyproject.toml file. %s", Fore.RED, error
            )
        else:
            if content:
                djlint_content.update(content)
                return djlint_content

    if djlint_toml_file := find_djlint_toml(src):
        try:
            djlint_content.update(load_djlint_toml_config(djlint_toml_file))
        except Exception as error:
            logger.error(
                "%sFailed to load djlint.toml file. %s", Fore.RED, error
            )

    elif djlintrc_file := find_djlintrc(src):
        try:
            djlint_content.update(load_djlintrc_config(djlintrc_file))
        except Exception as error:
            logger.error("%sFailed to load .djlintrc file. %s", Fore.RED, error)

    return djlint_content


def validate_rules(
    rules: Iterable[_TMappingStrAny],
) -> Iterator[_TMappingStrAny]:
    """Validate a list of linter rules. Returns valid rules."""
    for rule in rules:
        warning = False
        name = rule["rule"].get("name", "undefined")
        if "name" not in rule["rule"]:
            warning = True
            echo(Fore.RED + "Warning: A rule is missing a name! 😢")
        if (
            "patterns" not in rule["rule"]
            and "python_module" not in rule["rule"]
        ):
            warning = True
            echo(
                Fore.RED
                + f"Warning: Rule {name} is missing a pattern or a python_module! 😢"
            )
        if "message" not in rule["rule"]:
            warning = True
            echo(Fore.RED + f"Warning: Rule {name} is missing a message! 😢")

        if not warning:
            yield rule


def load_custom_rules(src: Path) -> Any:
    """Load djlint config from pyproject.toml."""
    djlint_rules_file = find_djlint_rules(src)

    if djlint_rules_file:
        return yaml.load(
            djlint_rules_file.read_text(encoding="utf-8"),
            Loader=yaml.SafeLoader,
        )

    return ()


def build_custom_blocks(custom_blocks: str | None) -> str | None:
    """Build regex string for custom template blocks."""
    if custom_blocks:
        open_tags = {x.strip() + r"\b" for x in custom_blocks.split(",")}
        close_tags = {f"end{x}" for x in open_tags}
        return "|" + "|".join(sorted(open_tags | close_tags))
    return None


def build_ignore_blocks(ignore_blocks: str | None) -> str | None:
    """Build regex string for template blocks to not format."""
    if ignore_blocks:
        open_tags = {x.strip() + r"\b" for x in ignore_blocks.split(",")}
        close_tags = {f"end{x}" for x in open_tags}
        return "|".join(sorted(open_tags | close_tags))
    return None


def build_custom_html(custom_html: str | None) -> str | None:
    """Build regex string for custom HTML blocks."""
    if custom_html:
        return "|" + "|".join(x.strip() for x in custom_html.split(","))
    return None


@final
class Config:
    """Djlint Config."""

    def __init__(
        self,
        src: str = ".",
        *,
        ignore: str = "",
        extension: str = "",
        indent: int | None = None,
        quiet: bool = False,
        profile: str | None = None,
        require_pragma: bool = False,
        reformat: bool = False,
        check: bool = False,
        lint: bool = False,
        use_gitignore: bool = False,
        warn: bool = False,
        preserve_leading_space: bool = False,
        preserve_blank_lines: bool = False,
        format_css: bool = False,
        format_js: bool = False,
        configuration: Path | None = None,
        statistics: bool = False,
        include: str = "",
        ignore_case: bool = False,
        ignore_blocks: str = "",
        custom_blocks: str = "",
        blank_line_after_tag: str = "",
        blank_line_before_tag: str = "",
        line_break_after_multiline_tag: bool = False,
        custom_html: str = "",
        exclude: str = "",
        extend_exclude: str = "",
        linter_output_format: str = "",
        max_line_length: int | None = None,
        max_attribute_length: int | None = None,
        format_attribute_template_tags: bool = False,
        per_file_ignores: tuple[tuple[str, str], ...] = (),
        indent_css: int | None = None,
        indent_js: int | None = None,
        close_void_tags: bool = False,
        no_line_after_yaml: bool = False,
        no_function_formatting: bool = False,
        no_set_formatting: bool = False,
        max_blank_lines: int | None = None,
    ) -> None:
        self.reformat = reformat
        self.check = check
        self.lint = lint
        self.warn = warn

        if src == "-":
            self.project_root = find_project_root(Path.cwd())
        else:
            self.project_root = find_project_root(Path(src).resolve())

        djlint_settings = load_project_settings(
            self.project_root, configuration
        )

        self.gitignore = load_gitignore(self.project_root)
        # custom configuration options

        self.use_gitignore: bool = use_gitignore or djlint_settings.get(
            "use_gitignore", False
        )
        self.extension: str = str(
            extension or djlint_settings.get("extension", "html")
        )
        self.quiet: bool = quiet or djlint_settings.get("quiet", False)
        self.require_pragma: bool = (
            require_pragma
            or str(djlint_settings.get("require_pragma", "false")).lower()
            == "true"
        )

        self.custom_blocks: str = str(
            build_custom_blocks(
                custom_blocks or djlint_settings.get("custom_blocks")
            )
            or ""
        )

        self.custom_html: str = str(
            build_custom_html(custom_html or djlint_settings.get("custom_html"))
            or ""
        )

        self.format_attribute_template_tags: bool = (
            format_attribute_template_tags
            or djlint_settings.get("format_attribute_template_tags", False)
        )

        self.preserve_leading_space: bool = (
            preserve_leading_space
            or djlint_settings.get("preserve_leading_space", False)
        )
        self.ignore_blocks: str | None = build_ignore_blocks(
            ignore_blocks or djlint_settings.get("ignore_blocks", "")
        )

        self.preserve_blank_lines: bool = (
            preserve_blank_lines
            or djlint_settings.get("preserve_blank_lines", False)
        )

        self.format_js: bool = format_js or djlint_settings.get(
            "format_js", False
        )

        self.js_config = (
            {"indent_size": indent_js}
            if indent_js
            else djlint_settings.get("js")
        ) or {}

        self.css_config = (
            {"indent_size": indent_css}
            if indent_css
            else djlint_settings.get("css")
        ) or {}

        self.format_css: bool = format_css or djlint_settings.get(
            "format_css", False
        )

        self.ignore_case: bool = ignore_case or djlint_settings.get(
            "ignore_case", False
        )

        self.close_void_tags: bool = close_void_tags or djlint_settings.get(
            "close_void_tags", False
        )
        self.no_line_after_yaml: bool = (
            no_line_after_yaml
            or djlint_settings.get("no_line_after_yaml", False)
        )
        self.no_set_formatting: bool = no_set_formatting or djlint_settings.get(
            "no_set_formatting", False
        )
        self.no_function_formatting: bool = (
            no_function_formatting
            or djlint_settings.get("no_function_formatting", False)
        )

        # ignore is based on input and also profile
        self.ignore: str = str(ignore or djlint_settings.get("ignore", ""))
        self.include: str = str(include or djlint_settings.get("include", ""))

        self.files: list[str] | None = djlint_settings.get("files", None)
        self.stdin = False

        # codes to exclude
        profile_dict: dict[str, tuple[str, ...]] = {
            "html": ("D", "J", "T", "N", "M"),
            "django": ("J", "N", "M"),
            "jinja": ("D", "N", "M"),
            "nunjucks": ("D", "J", "M"),
            "handlebars": ("D", "J", "N"),
            "golang": ("D", "J", "N", "M"),
            "angular": ("D", "J", "H012", "H026", "H028"),
        }

        self.profile_code: tuple[str, ...] = profile_dict.get(
            str(profile or djlint_settings.get("profile", "html")).lower(), ()
        )
        self.profile: str = str(
            profile or djlint_settings.get("profile", "all")
        ).lower()

        self.linter_output_format: str = (
            linter_output_format
            or djlint_settings.get(
                "linter_output_format", "{code} {line} {message} {match}"
            )
        )

        # load linter rules
        rule_set = validate_rules(
            chain(
                yaml.safe_load(
                    (Path(__file__).parent / "rules.yaml").read_text(
                        encoding="utf-8"
                    )
                ),
                load_custom_rules(self.project_root),
            )
        )

        self.linter_rules = tuple(
            x
            for x in rule_set
            if x["rule"]["name"] not in self.ignore.split(",")
            and not any(
                x["rule"]["name"].startswith(code) for code in self.profile_code
            )
            and self.profile not in x["rule"].get("exclude", set())
            and (
                x["rule"].get("default", True)
                or x["rule"]["name"] in self.include.split(",")
            )
        )

        self.statistics = statistics

        # base options
        default_indent = 4
        if not indent:
            try:
                indent = int(djlint_settings.get("indent", default_indent))
            except ValueError:
                echo(
                    Fore.RED
                    + f"Error: Invalid pyproject.toml indent value {djlint_settings['indent']}"
                )
                indent = default_indent
        self.indent_size = indent
        self.indent: str = indent * " "

        try:
            self.max_blank_lines = int(
                djlint_settings.get("max_blank_lines", max_blank_lines or 0)
            )
        except ValueError:
            echo(
                Fore.RED
                + f"Error: Invalid pyproject.toml indent value {djlint_settings['max_blank_lines']}"
            )
            self.max_blank_lines = max_blank_lines or 0

        # From ruff and black
        default_exclude: str = r"""
            __pypackages__
            | _build
            | \.bzr
            | \.direnv
            | \.eggs
            | \.git
            | \.git-rewrite
            | \.hg
            | \.ipynb_checkpoints
            | \.mypy_cache
            | \.nox
            | \.pants\.d
            | \.pytest_cache
            | \.pytype
            | \.ruff_cache
            | \.svn
            | \.tox
            | \.venv
            | \.vscode
            | buck-out
            | build
            | dist
            | node_modules
            | venv
        """

        self.exclude: str = exclude or djlint_settings.get(
            "exclude", default_exclude
        )

        extend_exclude = extend_exclude or djlint_settings.get(
            "extend_exclude", ""
        )

        if extend_exclude:
            self.exclude += r" | " + r" | ".join(
                x.strip() for x in extend_exclude.split(",")
            )

        self.per_file_ignores = (
            (dict(per_file_ignores))
            if per_file_ignores
            else djlint_settings.get("per-file-ignores", {})
        )

        # add blank line after load tags
        self.blank_line_after_tag: str | None = (
            blank_line_after_tag
            or djlint_settings.get("blank_line_after_tag", None)
        )

        # add blank line before load tags
        self.blank_line_before_tag: str | None = (
            blank_line_before_tag
            or djlint_settings.get("blank_line_before_tag", None)
        )

        # add line break after multi-line tags
        self.line_break_after_multiline_tag: bool = (
            line_break_after_multiline_tag
            or djlint_settings.get("line_break_after_multiline_tag", False)
        )

        # contents of tags will not be formatted
        self.script_style_opening: str = r"""
           <style
         | <script
        """
        self.ignored_block_opening: str = r"""
              <style
            | {\*
            | <\?php
            | <script
            | <!--
            | [^\{]{\#(?!\s*djlint\:\s*(?:on|off))
            | ^{\#(?!\s*djlint\:\s*(?:on|off))
            | <pre
            | <textarea
            | {%[ ]*?blocktrans(?:late)?(?:(?!%}|\btrimmed\b).)*?%}
            | {\#\s*djlint\:\s*off\s*\#}
            | {%[ ]+?comment[ ]+?(?:(?!%}).)*?%}
            | {{!--\s*djlint\:off\s*--}}
            | {{-?\s*/\*\s*djlint\:off\s*\*/\s*-?}}
        """
        self.script_style_closing: str = r"""
              </style
            | </script
        """
        self.ignored_block_closing: str = r"""
              </style
            | \*}
            | \?>
            | </script
            |  -->
            | ^(?:(?!{\#).)*\#} # lines that have a #}, but not a {#
            | </pre
            | </textarea
            | {\#\s*djlint\:\s*on\s*\#}
            | (?<!djlint:off\s*?){%[ ]+?endcomment[ ]+?%}
            | {{!--\s*djlint\:on\s*--}}
            | {{-?\s*/\*\s*djlint\:on\s*\*/\s*-?}}
            | {%[ ]*?endblocktrans(?:late)?(?:(?!%}).)*?%}
        """

        # ignored block closing tags that
        # we can safely indent.
        self.safe_closing_tag: str = r"""
              </script
            | </style
            | {\#\s*djlint\:\s*on\s*\#}
            | {%[ ]+?endcomment[ ]+?%}
            | {{!--\s*djlint\:on\s*--}}
            | {{-?\s*/\*\s*djlint\:on\s*\*/\s*-?}}
        """

        # all html tags possible
        self.indent_html_tags: str = "|".join(HTML_TAG_NAMES) + self.custom_html

        self.indent_template_tags: str = (
            (rf"(?!{self.ignore_blocks})" if self.ignore_blocks else "")
            + r""" (?:if
                | ifchanged
                | for
                | asyncEach
                | asyncAll
                | block(?!trans|translate)
                | spaceless
                | compress
                | addto
                | language
                | with
                | assets
                | verbatim
                | autoescape
                | filter
                | each
                | macro
                | call
                | raw
                | blocktrans(?!late)
                | blocktranslate
                | thumbnail
                | set(?!(?:(?!%}).)*=)
            """
            + self.custom_blocks
            + r")\b"
        )

        self.template_indent: str = (
            r"""
            (?:\{\{\#|\{%-?)[ ]*?
                ("""
            + self.indent_template_tags
            + r"""
            ) | \{{-?[ ]*?form_start
            """
        )

        self.template_unindent: str = r"""
                (?:
                  (?:\{\{\/)
                | (?:\{%-?[ ]*?end(?!comment))
                | (?:\{{-?[ ]*?form_end)
              )
            """

        # these tags should be unindented and next line will be indented
        self.tag_unindent_line: str = r"""
              (?:\{%-?[ ]*?(?:elif|else|empty|plural))
            | (?:
                \{\{[ ]*?
                (
                    (?:else|\^)
                    [ ]*?\}\}
                )
              )
        """

        self.break_before = r"(?<!\n[ \t]*?)"

        # if lines are longer than x
        self.max_line_length = 120

        try:
            self.max_line_length = max_line_length or int(
                djlint_settings.get("max_line_length", self.max_line_length)
            )
        except ValueError:
            echo(
                Fore.RED
                + f"Error: Invalid pyproject.toml max_line_length value {djlint_settings['max_line_length']}"
            )

        self.max_attribute_length = 70

        try:
            self.max_attribute_length = max_attribute_length or int(
                djlint_settings.get(
                    "max_attribute_length", self.max_attribute_length
                )
            )
        except ValueError:
            echo(
                Fore.RED
                + f"Error: Invalid pyproject.toml max_attribute_length value {djlint_settings['max_attribute_length']}"
            )

        self.template_if_for_pattern = r"(?:{%-?\s?(?:if|for|asyncAll|asyncEach)[^}]*?%}(?:.*?{%\s?end(?:if|for|each|all)[^}]*?-?%})+?)"

        self.attribute_pattern: str = (
            rf"""
            (?:
                (
                    (?:\w|-|\.|\:|@|/(?!>))+ | required | checked
                )? # attribute name
                (?:  [ ]*?=[ ]*? # followed by "="
                    (
                        \"[^\"]*? # double quoted attribute
                        (?:
                            {self.template_if_for_pattern} # if or for loop
                           | {{{{.*?}}}} # template stuff
                           | {{%[^}}]*?%}}
                           | [^\"] # anything else
                        )*?
                        \" # closing quote
                      | '[^']*? # single quoted attribute
                        (?:
                            {self.template_if_for_pattern} # if or for loop
                           | {{{{.*?}}}} # template stuff
                           | {{%[^}}]*?%}}
                           | [^'] # anything else
                        )*?
                        \' # closing quote
                      | (?:\w|-)+ # or a non-quoted string value
                      | {{{{.*?}}}} # a non-quoted template var
                      | {{%[^}}]*?%}} # a non-quoted template tag
                      | {self.template_if_for_pattern} # a non-quoted if statement

                    )
                )? # attribute value
            )
            | ({self.template_if_for_pattern}
            """
            r"""
            | (?:\'|\") # allow random trailing quotes
            | {{.*?}}
            | {\#.*?\#}
            | {%.*?%})
        """
        )

        self.template_tags = r"""
        {{(?:(?!}}).)*}}|{%(?:(?!%}).)*%}
        """

        self.html_tag_attribute_regex = rf"""
            ((?:\s*?(?:
                \"(?>{self.template_tags}|\\\"|[^\"])*\"
                |'(?>{self.template_tags}|\\'|[^'])*'
                |{self.template_tags}
                |[^'\">{{}}/\s]|/(?!>)
            ))+)?
        """

        self.html_tag_regex = rf"""
            (</?(?:!(?!--))?) # an opening bracket (< or </ or <!), but not a comment
            ([^\s>!\[]+\b) # a tag name
            {self.html_tag_attribute_regex} # any attributes
            \s*? # potentially some whitespace
            (/?>) # a closing bracket (/> or >)
        """

        self.indent_html_tags_attribute_regex = rf"""
            \s((?:
                (?<!\\)\"(?>{self.template_tags}|\\\"|[^\"])*\"
                |(?<!\\)'(?>{self.template_tags}|\\'|[^'])*'
                |{self.template_tags}
                |[^'\">{{}}\/]
            )+?)
        """

        self.indent_html_tags_regex: str = rf"""
            (\s*?)
            (<(?:{self.indent_html_tags}))
            {self.indent_html_tags_attribute_regex}
            (\s*?/?>)
        """

        self.attribute_style_pattern: str = (
            r"^(.*?)(style=)([\"|'])(([^\"']+?;)+?)\3"
        )

        self.ignored_attributes = frozenset({
            "href",
            "action",
            "data-url",
            "src",
            "url",
            "srcset",
            "data-src",
        })

        self.start_template_tags: str = (
            (rf"(?!{self.ignore_blocks})" if self.ignore_blocks else "")
            + r"""
              (?:if
            | for
            | asyncEach
            | asyncAll
            | block(?!trans)
            | spaceless
            | compress
            | load
            | assets
            | addto
            | language
            | with
            | assets
            | autoescape
            | filter
            | verbatim
            | each
            | macro
            | call
            | raw
            | blocktrans(?!late)
            | blocktranslate
            | thumbnail
            | set(?!(?:(?!%}).)*=)

            """
            + self.custom_blocks
            + r""")
        """
        )

        self.break_template_tags: str = (
            (rf"(?!{self.ignore_blocks})" if self.ignore_blocks else "")
            + r"""
              (?:if
            | endif
            | for
            | endfor
            | asyncEach
            | endeach
            | asyncAll
            | endall
            | block(?!trans)
            | endblock(?!trans)
            | else
            | plural
            | spaceless
            | endspaceless
            | compress
            | endcompress
            | load
            | include
            | assets
            | endassets
            | addto
            | language
            | with
            | endwith
            | autoescape
            | endautoescape
            | filter
            | endfilter
            | elif
            | resetcycle
            | verbatim
            | endverbatim
            | each
            | macro
            | endmacro
            | raw
            | endraw
            | call
            | endcall
            | image
            | blocktrans(?!late)
            | endblocktrans(?!late)
            | blocktranslate
            | endblocktranslate
            | set(?!(?:(?!%}).)*=)
            | endset
            | thumbnail
            | endthumbnail
            """
            + self.custom_blocks
            + r""")
        """
        )
        self.template_blocks: str = r"""
        {%((?!%}).)+%}|{{((?!}}).)+}}
        """

        self.ignored_linter_blocks: str = r"""
           {%-?[ ]*?raw\b(?:(?!%}).)*?-?%}.*?(?={%-?[ ]*?endraw[ ]*?-?%})
        """

        self.unformatted_blocks_coarse: str = r"djlint\:\s*off"

        self.unformatted_blocks: str = r"""
            # html comment
            | <!--\s*djlint\:off\s*-->.(?:(?!<!--\s*djlint\:on\s*-->).)*
            # django/jinja/nunjucks
            | {\#\s*djlint\:\s*off\s*\#}(?:(?!{\#\s*djlint\:\s*on\s*\#}).)*
            | {%\s*comment\s*%\}\s*djlint\:off\s*\{%\s*endcomment\s*%\}(?:(?!{%\s*comment\s*%\}\s*djlint\:on\s*\{%\s*endcomment\s*%\}).)*
            # inline jinja comments
            | {\#(?!\s*djlint\:\s*(?:off|on)).*?\#}
            # handlebars
            | {{!--\s*djlint\:off\s*--}}(?:(?!{{!--\s*djlint\:on\s*--}}).)*
            # golang
            | {{-?\s*/\*\s*djlint\:off\s*\*/\s*-?}}(?:(?!{{-?\s*/\*\s*djlint\:on\s*\*/\s*-?}}).)*
            | ^---[\s\S]+?---
        """

        self.ignored_blocks: str = r"""
              <(pre|textarea).*?</(\1)>
            | <(script|style).*?(?=(\</(?:\3)>))
            # html comment
            | <!--\s*djlint\:off\s*-->.(?:(?!<!--\s*djlint\:on\s*-->).)*
            # django/jinja/nunjucks
            | {\#\s*djlint\:\s*off\s*\#}(?:(?!{\#\s*djlint\:\s*on\s*\#}).)*
            | {%\s*comment\s*%\}\s*djlint\:off\s*\{%\s*endcomment\s*%\}(?:(?!{%\s*comment\s*%\}\s*djlint\:on\s*\{%\s*endcomment\s*%\}).)*
            # inline jinja comments
            | {\#(?!\s*djlint\:\s*(?:off|on)).*?\#}
            # handlebars
            | {{!--\s*djlint\:off\s*--}}(?:(?!{{!--\s*djlint\:on\s*--}}).)*
            # golang
            | {{-?\s*/\*\s*djlint\:off\s*\*/\s*-?}}(?:(?!{{-?\s*/\*\s*djlint\:on\s*\*/\s*-?}}).)*
            # inline golang comments
            | {{-?\s*/\*(?!\s*djlint\:\s*(?:off|on)).*?\*/\s*-?}}
            | <!--.*?-->
            | <\?php.*?\?>
            | {%[ ]*?blocktranslate\b(?:(?!%}|\btrimmed\b).)*?%}.*?{%[ ]*?endblocktranslate[ ]*?%}
            | {%[ ]*?blocktrans\b(?:(?!%}|\btrimmed\b).)*?%}.*?{%[ ]*?endblocktrans[ ]*?%}
            | {%[ ]*?comment\b(?:(?!%}).)*?%}(?:(?!djlint:(?:off|on)).)*?(?={%[ ]*?endcomment[ ]*?%})
            | ^---[\s\S]+?---
        """
        self.script_style_inline: str = r"""
        <(script|style).*?(?=(\</(?:\1)>))
        """
        self.ignored_blocks_inline: str = r"""
              <(pre|textarea).*?</(\1)>
            | <(script|style).*?(?=(\</(?:\3)>))
            # html comment
            | <!--\s*djlint\:off\s*-->.*?(?=<!--\s*djlint\:on\s*-->)
            # django/jinja/nunjucks
            | {\#\s*djlint\:\s*off\s*\#}.*?(?={\#\s*djlint\:\s*on\s*\#})
            | {%\s*comment\s*%\}\s*djlint\:off\s*\{%\s*endcomment\s*%\}.*?(?={%\s*comment\s*%\}\s*djlint\:on\s*\{%\s*endcomment\s*%\})
            # inline jinja comments
            | {\#(?!\s*djlint\:\s*(?:off|on)).*?\#}
            # handlebars
            | {{!--\s*djlint\:off\s*--}}.*?(?={{!--\s*djlint\:on\s*--}})
            # golang
            | {{-?\s*/\*\s*djlint\:off\s*\*/\s*-?}}.*?(?={{-?\s*/\*\s*djlint\:on\s*\*/\s*-?}})
            # inline golang comments
            | {{-?\s*/\*(?!\s*djlint\:\s*(?:off|on)).*?\*/\s*-?}}
            | <!--.*?-->
            | <\?php.*?\?>
            | {%[ ]*?blocktranslate\b(?:(?!%}|\btrimmed\b).)*?%}.*?{%[ ]*?endblocktranslate[ ]*?%}
            | {%[ ]*?blocktrans\b(?:(?!%}|\btrimmed\b).)*?%}.*?{%[ ]*?endblocktrans[ ]*?%}
            | {%[ ]*?comment\b(?:(?!%}).)*?%}(?:(?!djlint:(?:off|on)).)*?(?={%[ ]*?endcomment[ ]*?%})
            | ^---[\s\S]+?---
        """

        self.ignored_rules = (
            # html comment
            r"<!--\s*djlint\:off(.+?)-->(?:(?!<!--\s*djlint\:on\s*-->).)*",
            # django/jinja/nunjucks
            r"{\#\s*djlint\:\s*off(.+?)\#}(?:(?!{\#\s*djlint\:\s*on\s*\#}).)*",
            r"{%\s*comment\s*%\}\s*djlint\:off(.*?)\{%\s*endcomment\s*%\}(?:(?!{%\s*comment\s*%\}\s*djlint\:on\s*\{%\s*endcomment\s*%\}).)*",
            # handlebars
            r"{{!--\s*djlint\:off(.*?)--}}(?:(?!{{!--\s*djlint\:on\s*--}}).)*",
            # golang
            r"{{-?\s*/\*\s*djlint\:off(.*?)\*/\s*-?}}(?:(?!{{-?\s*/\*\s*djlint\:on\s*\*/\s*-?}}).)*",
        )

        self.ignored_trans_blocks: str = r"""
              {%[ ]*?blocktranslate?\b(?:(?!%}|\btrimmed\b).)*?%}.*?{%[ ]*?endblocktranslate?[ ]*?%}
            | {%[ ]*?blocktrans\b(?:(?!%}|\btrimmed\b).)*?%}.*?{%[ ]*?endblocktrans[ ]*?%}
        """
        self.trans_trimmed_blocks: str = r"""
              {%[ ]*?blocktranslate\b(?:(?!%}).)*?\btrimmed\b(?:(?!%}).)*?%}.*?{%[ ]*?endblocktranslate[ ]*?%}
            | {%[ ]*?blocktrans\b(?:(?!%}).)*?\btrimmed\b(?:(?!%}).)*?%}.*?{%[ ]*?endblocktrans[ ]*?%}
        """
        self.ignored_trans_blocks_closing: str = r"""
         {%[ ]*?endblocktrans(?:late)?(?:(?!%}).)*?%}
        """

        self.ignored_inline_blocks: str = r"""
              <!--.*?-->
            | <script.*?\</script>
            | <style.*?\</style>
            | {\*.*?\*}
            | {\#(?!.*djlint:[ ]*?(?:off|on)\b).*\#}
            | <\?php.*?\?>
            | {%[ ]*?comment\b(?:(?!%}).)*?%}(?:(?!djlint:(?:off|on)).)*?{%[ ]*?endcomment[ ]*?%}
            | {%[ ]*?blocktrans(?:late)?\b(?:(?!%}|\btrimmed\b).)*?%}.*?{%[ ]*?endblocktrans(?:late)?[ ]*?%}
        """

        self.optional_single_line_html_tags: str = r"""
              button
            | a
            | h1
            | h2
            | h3
            | h4
            | h5
            | h6
            | td
            | th
            | strong
            | small
            | em
            | icon
            | span
            | title
            | link
            | path
            | label
            | div
            | li
            | script
            | style
            | head
            | body
            | p
            | select
            | article
            | option
            | legend
            | summary
            | dt
            | figcaption
            | tr
            | li
        """

        self.always_self_closing_html_tags: str = "|".join(HTML_VOID_ELEMENTS)

        self.optional_single_line_template_tags: str = r"""
              if
            | for
            | block
            | with
            | asyncEach
            | asyncAll
        """

        self.break_html_tags: str = (
            r"""
              html
            | head
            | body
            | div
         #   | a # a gets no breaks #177
            | nav
            | ul
            | ol
            | dl
            | dd
            | dt
            | li
            | table
            | thead
            | tbody
            | tr
            | th
            | td
            | blockquote
            | select
            | form
            | option
            | optgroup
            | fieldset
            | legend
            | label
            | header
            | cache
            | main
            | section
            | aside
            | footer
            | figure
            | figcaption
            | video
         #   | span # span gets no breaks #171
            | p
            | g
            | svg
            | h\d
            | button
            | path
            | picture
            | script
            | style
            | details
            | summary
            | """
            + self.always_self_closing_html_tags
            + self.custom_html
            + """
        """
        )

        # the contents of these tag blocks will be indented, then unindented
        self.tag_indent: str = (
            self.template_indent
            + """
            | (?:<
                (?:
                    """
            + self.indent_html_tags
            + """
                )\\b
              )
        """
        )

        # either a template tag at the start of a line,
        # a html tag at the start of a line,
        # or an html tag as the end of a line.
        # Nothing in between!
        self.tag_unindent: str = (
            r"""
                ^
                """
            + self.template_unindent
            + """
            | (?:^</
                (?:
                    """
            + self.indent_html_tags
            + """
                )\\b
              )
            | (?:</
                (?:
                    """
            + self.indent_html_tags
            + """
                )>$
              )
        """
        )
