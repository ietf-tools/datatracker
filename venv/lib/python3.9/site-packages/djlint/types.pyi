from typing_extensions import TypedDict

class LintError(TypedDict):
    code: str
    line: str
    match: str
    message: str

class ProcessResult(TypedDict, total=False):
    format_message: dict[str, tuple[str, ...]]
    lint_message: dict[str, list[LintError]]
