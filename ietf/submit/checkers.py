# Copyright The IETF Trust 2016-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import io
import itertools
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

from xym import xym
from django.conf import settings

import debug                            # pyflakes:ignore

from ietf.utils import tool_version
from ietf.utils.log import log, assertion
from ietf.utils.pipe import pipe
from ietf.utils.test_runner import disable_coverage

class DraftSubmissionChecker(object):
    name = ""

    def check_file_txt(self, text):
        "Run checks on a text file"
        raise NotImplementedError

    def check_file_xml(self, xml):
        "Run checks on an xml file"
        raise NotImplementedError

    def check_fragment_txt(self, text):
        "Run checks on a fragment from a text file"
        raise NotImplementedError

    def check_fragment_xml(self, xml):
        "Run checks on a fragment from an xml file"
        raise NotImplementedError


class DraftIdnitsChecker(object):
    """
    Draft checker class for idnits.  Idnits can only handle whole text files,
    so only check_file_txt() is defined; check_file_xml and check_fragment_*
    methods are undefined.

    Furthermore, idnits doesn't provide an error code or line-by-line errors,
    so a bit of massage is needed in order to return the expected failure flag.
    """
    name = "idnits check"

    # start using this when we provide more in the way of warnings during
    # submission checking:
    # symbol = '<span class="bi bi-check-square"></span>'
    # symbol = u'<span class="large">\ua17d</span>' # Yi syllable 'nit'
    # symbol = u'<span class="large">\ub2e1</span>' # Hangul syllable 'nit'

    symbol = ""

    def __init__(self, options=["--submitcheck", "--nitcount", ]):
        assert isinstance(options, list)
        if not "--nitcount" in options:
            options.append("--nitcount")
        self.options = ' '.join(options)

    def check_file_txt(self, path):
        """
        Run an idnits check, and return a passed/failed indication, a message,
        and error and warning messages.

        Error and warning list items are tuples:
            (line_number, line_text, message)
        """
        items = []
        errors = 0
        warnings = 0
        errstart = ['  ** ', '  ~~ ']
        warnstart = ['  == ', '  -- ']
        

        cmd = "%s %s %s" % (settings.IDSUBMIT_IDNITS_BINARY, self.options, path)
        code, out, err = pipe(cmd)
        out = out.decode('utf-8')
        err = err.decode('utf-8')
        if code != 0 or out == "":
            message = "idnits error: %s:\n  Error %s: %s" %( cmd, code, err)
            log(message)
            passed = False
            
        else:
            message = out
            if re.search(r"(?<!\s)\s+Summary:\s+0\s+|No nits found", out):  # lookbehind keeps this linear
                passed  = True
            else:
                passed  = False

        item = ""
        for line in message.splitlines():
            if   line[:5] in (errstart + warnstart):
                item = line.rstrip()
            elif line.strip() == "" and item:
                tuple = (None, None, item)
                items.append(tuple)
                if item[:5] in errstart:
                    errors += 1
                elif item[:5] in warnstart:
                    warnings += 1
                else:
                    raise RuntimeError("Unexpected state in idnits checker: item: %s, line: %s" % (item, line))
                item = ""
            elif item and line.strip() != "":
                item += " " + line.strip()
            else:
                pass
        info = {'checker': self.name, 'items': [], 'code': {}}

        return passed, message, errors, warnings, info

# The only file names that are accepted for extracted yang models
MODEL_NAME_RE = r'[A-Za-z_][A-Za-z0-9_.-]*(@\d\d\d\d-\d\d-\d\d)?\.yang'


def is_model_file_name(name):
    return isinstance(name, str) and re.fullmatch(MODEL_NAME_RE, name) is not None


class ModelExtractor(xym.YangModuleExtractor):
    """YangModuleExtractor that chooses the names of the files it writes

    A document names the file each of its models should be extracted to, and xym
    writes the model to that name inside the destination directory before anything
    else has looked at it. Here that name is only used when it is a plain model
    file name. Otherwise the model is written to a placeholder name in the
    destination directory, and the name the document asked for is kept in
    placeholders so that it can be reported.

    get_extracted_models() will still rename a placeholder to match the module name
    and revision found in the model when it can determine them.
    """

    PLACEHOLDER = "unnamed-model-%d.yang"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.placeholders = {}

    def write_model_to_file(self, mdl, fn):
        if fn and not is_model_file_name(fn):
            placeholder = self.PLACEHOLDER % (len(self.placeholders) + 1)
            self.placeholders[placeholder] = fn
            fn = placeholder
        super().write_model_to_file(mdl, fn)


class DraftYangChecker(object):

    name = "yang validation"
    symbol = '<i class="bi bi-yin-yang"></i>'

    @staticmethod
    def _build_pyang_command(model: str, workdir: str) -> list[str]:
        modpath = ":".join(
            [
                workdir,
                settings.SUBMIT_YANG_RFC_MODEL_DIR,
                settings.SUBMIT_YANG_DRAFT_MODEL_DIR,
                settings.SUBMIT_YANG_IANA_MODEL_DIR,
                settings.SUBMIT_YANG_CATALOG_MODEL_DIR,
            ]
        )
        return ["pyang", "--verbose", "--ietf", "-p", modpath, model]

    @staticmethod
    def _build_yanglint_command(model: str, workdir: str) -> list[str]:
        import_paths = [
            settings.SUBMIT_YANG_RFC_MODEL_DIR,
            workdir,
            settings.SUBMIT_YANG_DRAFT_MODEL_DIR,
            settings.SUBMIT_YANG_IANA_MODEL_DIR,
            settings.SUBMIT_YANG_CATALOG_MODEL_DIR,
        ]
        path_args = [("-p", path) for path in import_paths]
        return (
            [
                settings.YANGLINT_BINARY,
                "--verbose",
                "-D",
            ]
            + list(itertools.chain(*path_args))
            + [model, "-i"]
        )

    def check_file_txt(self, path):
        name = os.path.basename(path)
        workdir = tempfile.mkdtemp()
        errors = 0
        warnings = 0
        message = ""
        results = []
        passed = True                   # Used by the submission tool.  Yang checks always pass.
        model_list = []
        info = {'checker': self.name, 'items': [], 'code': {}}

        extractor = ModelExtractor(path, workdir, strict=True, strict_examples=False, debug_level=1)
        if not os.path.exists(path):
            return None, "%s: No such file or directory: '%s'"%(name.capitalize(), path), errors, warnings, info
        with open(path) as file:
            out = ""
            err = ""
            code = 0
            try:
                # This places the yang models as files in workdir
                saved_stdout = sys.stdout
                saved_stderr = sys.stderr
                sys.stdout = io.StringIO()
                sys.stderr = io.StringIO()
                extractor.extract_yang_model_text(file.read())
                model_list = extractor.get_extracted_models(False, True)
                out = sys.stdout.getvalue()
                err = sys.stderr.getvalue()
                # signature change in xym:
            except Exception as exc:
                sys.stdout = saved_stdout
                sys.stderr = saved_stderr
                msg = "Exception when running xym on %s: %s" % (name, exc)
                log(msg)
                raise
                return None, msg, 0, 0, info
            finally:
                sys.stdout = saved_stdout
                sys.stderr = saved_stderr
        if not model_list:
            # Found no yang models, don't deliver any YangChecker result
            return None, "", 0, 0, info

        # A model that is still on a placeholder had an unusable name in the draft
        # and could not be renamed from its own module name. Report the name the
        # draft gave it.
        bad_names = {
            m for m in model_list
            if m in extractor.placeholders or not is_model_file_name(m)
        }
        for m in sorted(bad_names):
            code += 1
            err += "Error: Bad extracted model name: '%s'\n" % extractor.placeholders.get(m, m)
        if len(set(model_list)) != len(model_list):
            code += 1
            err += "Error: Multiple models with the same name:\n  %s\n" % ("\n  ".join(model_list))

        # Names come from the draft text. Only names that passed validation may
        # be used to build commands or file paths below.
        model_list = [m for m in set(model_list) if m not in bad_names]

        command = "xym"
        message = "{version}:\n{output}\n\n".format(
            version=tool_version[command], 
            output=out.replace('\n\n', '\n').strip() if code == 0 else err,
        )

        results.append({
            "name": name,
            "passed":  passed,
            "message": message,
            "warnings": 0,
            "errors":  code,
            "items": [],
        })

        for model in model_list:
            path = os.path.join(workdir, model)
            message = ""
            passed = True
            errors = 0
            warnings = 0
            items = []
            if os.path.exists(path):
                with io.open(path) as file:
                    text = file.readlines()
                # pyang
                cmd_template = settings.SUBMIT_PYANG_COMMAND
                command = [ w for w in cmd_template.split() if not '=' in w ][0]
                cmd = self._build_pyang_command(path, workdir)
                venv_path = os.environ.get('VIRTUAL_ENV') or os.path.join(os.getcwd(), 'env')
                venv_bin = os.path.join(venv_path, 'bin')
                if not venv_bin in os.environ.get('PATH', '').split(':'):
                    os.environ['PATH'] = os.environ.get('PATH', '') + ":" + venv_bin
                try:
                    result = subprocess.run(cmd, capture_output=True)
                    code = result.returncode
                    out = result.stdout.decode('utf-8', errors='replace')
                    err = result.stderr.decode('utf-8', errors='replace')
                except (OSError, subprocess.SubprocessError) as exc:
                    log("pyang error: %s:\n  %s" % (" ".join(cmd), exc))
                    code, out, err = 1, "", "%s\n" % exc
                if code > 0 or len(err.strip()) > 0 :
                    error_lines = err.splitlines()
                    assertion('len(error_lines) > 0')
                    for line in error_lines:
                        if line.strip():
                            try:
                                fn, lnum, msg = line.split(':', 2)
                                lnum = int(lnum)
                                if fn == model and (lnum-1) in range(len(text)):
                                    line = text[lnum-1].rstrip()
                                else:
                                    line = None
                                items.append((lnum, line, msg))
                                if 'error: ' in msg:
                                    errors += 1
                                if 'warning: ' in msg:
                                    warnings += 1
                            except ValueError:
                                pass
                #passed = passed and code == 0 # For the submission tool.  Yang checks always pass
                message += "{version}: {template}:\n{output}\n".format(
                    version=tool_version[command],
                    template=cmd_template,
                    output=out + "No validation errors\n" if (code == 0 and len(err) == 0) else out + err,
                )

                # yanglint
                with disable_coverage():  # pragma: no cover
                    if settings.SUBMIT_YANGLINT_COMMAND and os.path.exists(settings.YANGLINT_BINARY):
                        cmd_template = settings.SUBMIT_YANGLINT_COMMAND
                        command = [ w for w in cmd_template.split() if not '=' in w ][0]
                        cmd = self._build_yanglint_command(path, workdir)
                        try:
                            result = subprocess.run(cmd, capture_output=True)
                            code = result.returncode
                            out = result.stdout.decode('utf-8', errors='replace')
                            err = result.stderr.decode('utf-8', errors='replace')
                        except (OSError, subprocess.SubprocessError) as exc:
                            log("yanglint error: %s:\n  %s" % (" ".join(cmd), exc))
                            code, out, err = 1, "", "%s\n" % exc
                        if code > 0 or len(err.strip()) > 0:
                            err_lines = err.splitlines()
                            for line in err_lines:
                                if line.strip():
                                    try:
                                        if 'err : ' in line:
                                            errors += 1
                                        if 'warn: ' in line:
                                            warnings += 1
                                    except ValueError:
                                        pass
                        #passed = passed and code == 0 # For the submission tool.  Yang checks always pass
                        message += "{version}: {template}:\n{output}\n".format(
                            version=tool_version[command],
                            template=cmd_template,
                            output=out + "No validation errors\n" if (code == 0 and len(err) == 0) else out + err,
                        )
            else:
                errors += 1
                message += "No such file: %s\nPossible mismatch between extracted xym file name and returned module name?\n" % (path)

            # Move model file into place
            dest = os.path.join(settings.SUBMIT_YANG_DRAFT_MODEL_DIR, model)
            shutil.move(path, dest)

            # Create a hard link in FTP_DIR, removing a file in the way. This happens
            # e.g., on the periodic re-run of Yang checks on active documents, when
            # the "file in the way" is the previous model file.
            ftp_dest = Path(settings.FTP_DIR) / "yang" / "draftmod" / model
            ftp_dest.unlink(missing_ok=True)
            try:
                os.link(dest, ftp_dest)
            except IOError as err:
                log(
                    f"There was an error creating a hardlink at {ftp_dest} "
                    f"pointing to {dest}: {err}"
                )

            # summary result
            results.append({
                "name": model,
                "passed":  passed,
                "message": message,
                "warnings": warnings,
                "errors":  errors,
                "items": items,
            })


        shutil.rmtree(workdir)

        passed  = all( res["passed"] for res in results )
        message = "\n".join([ "\n".join([res['name']+':', res["message"]]) for res in results ])
        errors  = sum(res["errors"] for res in results )
        warnings  = sum(res["warnings"] for res in results )
        items  = [ e for res in results for e in res["items"] ]
        info['items'] = items
        info['code']['yang'] = model_list
        return passed, message, errors, warnings, info


class DraftIdnits3Checker(object):
    """
    Draft checker class for idnits3, run in "submission" mode.

    idnits3 understands both text and XML Internet-Drafts, so both
    check_file_xml() and check_file_txt() are defined; the XML is preferred
    when the submission includes it, since that is the form the author wrote.

    This checker is advisory: it never fails a submission, even when idnits3
    reports errors that would block it once idnits3 becomes a required check.
    It records whether it would have blocked in the check's `items` so that the
    submitter can be warned.  A run that could not be completed at all (missing
    or broken binary, unparsable output) returns None for `passed`, which marks
    the check as "did not apply" and hides it from the submitter.
    """

    name = "idnits3 check"

    symbol = ""

    _severities = (
        ("ValidationError", "Errors"),
        ("ValidationWarning", "Warnings"),
        ("ValidationComment", "Comments"),
    )

    def __init__(self, options=None):
        if options is None:
            # --mode submission limits the checks to those relevant when a
            # draft is submitted; --output json gives us reliable per-severity
            # counts and structured nits to render ourselves.
            options = ["--mode", "submission", "--output", "json", "--no-color"]
            if settings.IDSUBMIT_IDNITS3_OFFLINE:
                options.append("--offline")
        assert isinstance(options, list)
        self.options = options

    def _version(self):
        try:
            result = subprocess.run(
                [settings.IDSUBMIT_IDNITS3_BINARY, "--version"],
                capture_output=True,
                timeout=settings.IDSUBMIT_IDNITS3_TIMEOUT,
            )
        except (OSError, subprocess.SubprocessError):
            return "unknown version"
        if result.returncode != 0:
            return "unknown version"
        return result.stdout.decode("utf-8", errors="replace").strip()

    def _render(self, nits, counts):
        """Render the idnits3 nits as the text shown to the submitter"""
        lines = [
            "idnits %s (submission mode): %d error%s, %d warning%s, %d comment%s"
            % (
                self._version(),
                counts["error"], "" if counts["error"] == 1 else "s",
                counts["warning"], "" if counts["warning"] == 1 else "s",
                counts["comment"], "" if counts["comment"] == 1 else "s",
            ),
            "",
            "These results do not affect this submission.  Errors reported here are",
            "expected to prevent submission once idnits3 becomes a required check.",
            "",
        ]
        if not nits:
            lines.append("No nits found.")
            return "\n".join(lines) + "\n"
        index = 0
        for severity, heading in self._severities:
            of_severity = [n for n in nits if n.get("severity") == severity]
            if not of_severity:
                continue
            lines.append("%s:" % heading)
            lines.append("")
            for nit in of_severity:
                index += 1
                indent = " " * 6
                lines.append("%4d. %s" % (index, nit.get("code", "UNKNOWN")))
                lines.append("%s%s" % (indent, nit.get("desc", "")))
                if nit.get("text"):
                    lines.append("%sText: %s" % (indent, nit["text"]))
                if nit.get("path"):
                    lines.append("%sPath: %s" % (indent, nit["path"]))
                if nit.get("line"):
                    lines.append(
                        "%sAt: %s"
                        % (
                            indent,
                            ", ".join(
                                "line %s column %s" % (loc.get("line"), loc.get("pos"))
                                for loc in nit["line"]
                            ),
                        )
                    )
                if nit.get("ref"):
                    lines.append("%sSee %s" % (indent, nit["ref"]))
                lines.append("")
        return "\n".join(lines) + "\n"

    def _check_file(self, path):
        info = {
            "checker": self.name,
            "items": [],
            "code": {},
            "advisory": True,
            "would_block_in_future": False,
            "comments": 0,
        }
        cmd = [settings.IDSUBMIT_IDNITS3_BINARY] + self.options + [str(path)]
        try:
            result = subprocess.run(
                cmd, capture_output=True, timeout=settings.IDSUBMIT_IDNITS3_TIMEOUT
            )
        except (OSError, subprocess.SubprocessError) as err:
            message = "idnits3 error: %s:\n  %s" % (" ".join(cmd), err)
            log(message)
            return None, message, 0, 0, info
        if result.returncode != 0:
            message = "idnits3 error: %s:\n  Error %s: %s" % (
                " ".join(cmd),
                result.returncode,
                result.stderr.decode("utf-8", errors="replace"),
            )
            log(message)
            return None, message, 0, 0, info
        try:
            output = json.loads(result.stdout.decode("utf-8", errors="replace"))
            counts = {
                severity: int(output["nitsBySeverity"].get(severity, 0))
                for severity in ("error", "warning", "comment")
            }
            nits = output.get("nits", [])
            if not isinstance(nits, list) or not all(
                isinstance(nit, dict) for nit in nits
            ):
                raise ValueError("'nits' is not a list of nits")
        except (AttributeError, KeyError, TypeError, ValueError) as err:
            message = "idnits3 error: %s:\n  Could not parse the idnits3 output: %s" % (
                " ".join(cmd),
                err,
            )
            log(message)
            return None, message, 0, 0, info

        info["items"] = [
            (
                nit["line"][0]["line"] if nit.get("line") else None,
                None,
                "%s: %s" % (nit.get("code", "UNKNOWN"), nit.get("desc", "")),
            )
            for nit in nits
        ]
        info["would_block_in_future"] = counts["error"] > 0
        # SubmissionCheck has no field for comments, so they travel in items
        info["comments"] = counts["comment"]
        # Always passes -- idnits3 does not block submission yet.
        return True, self._render(nits, counts), counts["error"], counts["warning"], info

    def check_file_txt(self, path):
        return self._check_file(path)

    def check_file_xml(self, path):
        return self._check_file(path)
