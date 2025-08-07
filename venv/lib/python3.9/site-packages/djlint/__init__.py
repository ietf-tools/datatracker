"""djLint · lint and reformat HTML templates."""

from __future__ import annotations

import os
import sys
import tempfile
from concurrent.futures import (
    ProcessPoolExecutor,
    ThreadPoolExecutor,
    as_completed,
)
from pathlib import Path
from typing import TYPE_CHECKING

import click
from click import echo
from colorama import Fore, Style, colorama_text
from tqdm import tqdm

from djlint.lint import lint_file
from djlint.output import print_output
from djlint.reformat import reformat_file
from djlint.settings import Config
from djlint.src import get_src

if TYPE_CHECKING:
    from djlint.types import ProcessResult


@click.command(  # type: ignore[operator]
    context_settings={"help_option_names": ["-h", "--help"]},
    help="djLint · HTML template linter and formatter.",
)
@click.argument(
    "src",
    type=click.Path(
        exists=True,
        file_okay=True,
        dir_okay=True,
        readable=True,
        allow_dash=True,
    ),
    nargs=-1,
    required=True,
    metavar="SRC ...",
)
@click.version_option(package_name="djlint")
@click.option(
    "-e",
    "--extension",
    type=str,
    default="",
    help="File extension to check [default: html]",
    show_default=False,
)
@click.option(
    "-i",
    "--ignore",
    type=str,
    default="",
    help='Codes to ignore. ex: "H014,H017"',
    show_default=False,
)
@click.option("--reformat", is_flag=True, help="Reformat the file(s).")
@click.option("--check", is_flag=True, help="Check formatting on the file(s).")
@click.option(
    "--indent",
    type=int,
    help="Indent spacing. [default: 4]",
    show_default=False,
)
@click.option(
    "--quiet", is_flag=True, help="Do not print diff when reformatting."
)
@click.option(
    "--profile",
    type=str,
    help="Enable defaults by template language. ops: django, jinja, nunjucks, handlebars, golang, angular, html [default: html]",
)
@click.option(
    "--require-pragma",
    is_flag=True,
    help="Only format or lint files that starts with a comment with the text 'djlint:on'",
)
@click.option(
    "--lint", is_flag=True, help="Lint for common issues. [default option]"
)
@click.option(
    "--use-gitignore",
    is_flag=True,
    help="Use .gitignore file to extend excludes.",
)
@click.option("--warn", is_flag=True, help="Return errors as warnings.")
@click.option(
    "--preserve-leading-space",
    is_flag=True,
    help="Attempt to preserve leading space on text.",
)
@click.option(
    "--preserve-blank-lines",
    is_flag=True,
    help="Attempt to preserve blank lines.",
)
@click.option(
    "--format-css", is_flag=True, help="Also format contents of <style> tags."
)
@click.option(
    "--format-js", is_flag=True, help="Also format contents of <script> tags."
)
@click.option(
    "--configuration",
    type=click.Path(
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        resolve_path=True,
        allow_dash=True,
        path_type=Path,
    ),
    help="Path to global configuration file in djlint.toml or .djlintrc format",
)
@click.option(
    "--statistics",
    is_flag=True,
    help="Count the number of occurrences of each error/warning code.",
)
@click.option(
    "--include",
    type=str,
    default="",
    help='Codes to include. ex: "H014,H017"',
    show_default=False,
)
@click.option(
    "--ignore-case", is_flag=True, help="Do not fix case on known html tags."
)
@click.option(
    "--ignore-blocks",
    type=str,
    default="",
    help="Comma list of template blocks to not indent.",
)
@click.option(
    "--blank-line-after-tag",
    type=str,
    default="",
    help="Add an additional blank line after {% <tag> ... %} tag groups.",
)
@click.option(
    "--blank-line-before-tag",
    type=str,
    default="",
    help="Add an additional blank line before {% <tag> ... %} tag groups.",
)
@click.option(
    "--line-break-after-multiline-tag",
    is_flag=True,
    help="Do not condense the content of multi-line tags into the line of the last attribute.",
)
@click.option(
    "--custom-blocks",
    type=str,
    default="",
    help="Indent custom template blocks. For example {% toc %}...{% endtoc %}",
)
@click.option(
    "--custom-html",
    type=str,
    default="",
    help="Indent custom HTML tags. For example <mjml>",
)
@click.option(
    "--exclude",
    type=str,
    default="",
    help="Override the default exclude paths.",
)
@click.option(
    "--extend-exclude",
    type=str,
    default="",
    help="Add additional paths to the default exclude.",
)
@click.option(
    "--linter-output-format",
    type=str,
    default="",
    help="Customize order of linter output message.",
)
@click.option(
    "--max-line-length",
    type=int,
    help="Max line length. [default: 120]",
    show_default=False,
)
@click.option(
    "--max-attribute-length",
    type=int,
    help="Max attribute length. [default: 70]",
    show_default=False,
)
@click.option(
    "--format-attribute-template-tags",
    is_flag=True,
    help="Attempt to format template syntax inside of tag attributes.",
)
@click.option(
    "--per-file-ignores",
    type=(str, str),
    multiple=True,
    help="Ignore linter rules on a per-file basis.",
)
@click.option(
    "--indent-css", type=int, help="Set CSS indent level.", show_default=False
)
@click.option(
    "--indent-js", type=int, help="Set JS indent level.", show_default=False
)
@click.option(
    "--close-void-tags",
    is_flag=True,
    help="Add closing mark on known void tags. Ex: <img> becomse <img />",
)
@click.option(
    "--no-line-after-yaml",
    is_flag=True,
    help="Do not add a blank line after yaml front matter.",
)
@click.option(
    "--no-function-formatting",
    is_flag=True,
    help="Do not attempt to format function contents.",
)
@click.option(
    "--no-set-formatting",
    is_flag=True,
    help="Do not attempt to format set contents.",
)
@click.option(
    "--max-blank-lines",
    type=int,
    help="Consolidate blank lines down to x lines. [default: 0]",
    show_default=False,
)
@colorama_text(autoreset=True)
def main(
    *,
    src: tuple[str, ...],
    extension: str,
    ignore: str,
    reformat: bool,
    indent: int | None,
    check: bool,
    quiet: bool,
    profile: str | None,
    require_pragma: bool,
    lint: bool,
    use_gitignore: bool,
    warn: bool,
    preserve_leading_space: bool,
    preserve_blank_lines: bool,
    format_css: bool,
    format_js: bool,
    configuration: Path | None,
    statistics: bool,
    include: str,
    ignore_case: bool,
    ignore_blocks: str,
    blank_line_after_tag: str,
    blank_line_before_tag: str,
    line_break_after_multiline_tag: bool,
    custom_blocks: str,
    custom_html: str,
    exclude: str,
    extend_exclude: str,
    linter_output_format: str,
    max_line_length: int | None,
    max_attribute_length: int | None,
    format_attribute_template_tags: bool,
    per_file_ignores: tuple[tuple[str, str], ...],
    indent_css: int | None,
    indent_js: int | None,
    close_void_tags: bool,
    no_line_after_yaml: bool,
    no_function_formatting: bool,
    no_set_formatting: bool,
    max_blank_lines: int | None,
) -> None:
    """djLint · HTML template linter and formatter."""
    config = Config(
        src[0],
        extension=extension,
        ignore=ignore,
        indent=indent,
        quiet=quiet,
        profile=profile,
        require_pragma=require_pragma,
        lint=lint or not (reformat or check),
        reformat=reformat,
        check=check,
        use_gitignore=use_gitignore,
        warn=warn,
        preserve_leading_space=preserve_leading_space,
        preserve_blank_lines=preserve_blank_lines,
        format_css=format_css,
        format_js=format_js,
        configuration=configuration,
        statistics=statistics,
        include=include,
        ignore_case=ignore_case,
        ignore_blocks=ignore_blocks,
        blank_line_after_tag=blank_line_after_tag,
        blank_line_before_tag=blank_line_before_tag,
        line_break_after_multiline_tag=line_break_after_multiline_tag,
        custom_blocks=custom_blocks,
        custom_html=custom_html,
        exclude=exclude,
        extend_exclude=extend_exclude,
        linter_output_format=linter_output_format,
        max_line_length=max_line_length,
        max_attribute_length=max_attribute_length,
        format_attribute_template_tags=format_attribute_template_tags,
        per_file_ignores=per_file_ignores,
        indent_css=indent_css,
        indent_js=indent_js,
        close_void_tags=close_void_tags,
        no_line_after_yaml=no_line_after_yaml,
        no_function_formatting=no_function_formatting,
        no_set_formatting=no_set_formatting,
        max_blank_lines=max_blank_lines,
    )

    temp_file = None

    try:
        if "-" in src:
            if config.files:
                file_list = get_src((Path(x) for x in config.files), config)

            else:
                config.stdin = True
                stdin_stream = click.get_text_stream("stdin", encoding="utf-8")
                stdin_text = stdin_stream.read()
                temp_file = tempfile.NamedTemporaryFile(  # noqa: SIM115
                    mode="w", encoding="utf-8", delete=False
                )
                temp_file.write(stdin_text)
                temp_file.seek(0)

                # cannot use gitignore for stdin paths.
                config.use_gitignore = False

                file_list = get_src((Path(temp_file.name),), config)

        else:
            file_list = get_src((Path(x) for x in src), config)

        if not file_list:
            return

        message = ""

        if config.check:
            message = "Checking"
        elif config.reformat:
            message = "Reformatting"

        if config.lint:
            if message:
                message += " and "
            message += "Linting"

        bar_message = "{}{}{} {}{{n_fmt}}/{{total_fmt}}{} {}files{} {{bar}} {}{{elapsed}}{}".format(
            Fore.BLUE + Style.BRIGHT,
            message,
            Style.RESET_ALL,
            Fore.RED + Style.BRIGHT,
            Style.RESET_ALL,
            Fore.BLUE + Style.BRIGHT,
            Style.RESET_ALL,
            Fore.GREEN + Style.BRIGHT,
            Style.RESET_ALL + "    ",
        )
        if not config.stdin and not config.quiet:
            echo()

        progress_char = " »" if sys.platform == "win32" else "┈━"

        executor_cls = (
            ThreadPoolExecutor
            if min(os.cpu_count() or 1, len(file_list)) == 1
            else ProcessPoolExecutor
        )

        with executor_cls() as exe:
            futures = {
                exe.submit(process, config, this_file): this_file
                for this_file in file_list
            }

            if temp_file is None:
                file_errors = []
                elapsed = "00:00"
                with tqdm(
                    total=len(file_list),
                    bar_format=bar_message,
                    colour="BLUE",
                    ascii=progress_char,
                    leave=False,
                ) as pbar:
                    for future in as_completed(futures):
                        file_errors.append(future.result())
                        pbar.update()
                        elapsed = pbar.format_interval(
                            pbar.format_dict["elapsed"]
                        )

                finished_bar_message = f"{Fore.BLUE + Style.BRIGHT}{message}{Style.RESET_ALL} {Fore.GREEN + Style.BRIGHT}{{n_fmt}}/{{total_fmt}}{Style.RESET_ALL} {Fore.BLUE + Style.BRIGHT}files{Style.RESET_ALL} {{bar}} {Fore.GREEN + Style.BRIGHT}{elapsed}{Style.RESET_ALL}    "

                with tqdm(
                    total=len(file_list),
                    initial=len(file_list),
                    bar_format=finished_bar_message,
                    colour="GREEN",
                    ascii=progress_char,
                    leave=True,
                ):
                    pass
            else:
                file_errors = [
                    future.result() for future in as_completed(futures)
                ]

        if temp_file and (config.reformat or config.check):
            # if using stdin, only give back formatted code.
            echo(
                Path(temp_file.name)
                .read_text(encoding="utf-8")
                .rstrip()
                .encode("utf-8")
            )
    finally:
        if temp_file:
            try:
                temp_file.close()
            finally:
                Path(temp_file.name).unlink(missing_ok=True)

    if print_output(config, file_errors, len(file_list)) and not config.warn:
        sys.exit(1)


def process(config: Config, this_file: Path) -> ProcessResult:
    """Run linter or formatter."""
    output: ProcessResult = {}
    if config.reformat or config.check:
        output["format_message"] = reformat_file(config, this_file)

    if config.lint:
        output["lint_message"] = lint_file(config, this_file)

    return output
