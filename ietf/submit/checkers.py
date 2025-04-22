# Copyright The IETF Trust 2016-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import io
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile

from xym import xym
from django.conf import settings

import debug                            # pyflakes:ignore

from ietf.utils import tool_version
from ietf.utils.log import log, assertion
from ietf.utils.pipe import pipe
from ietf.utils.test_runner import set_coverage_checking

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
            if re.search(r"\s+Summary:\s+0\s+|No nits found", out):
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

class DraftYangChecker(object):

    name = "yang validation"
    symbol = '<i class="bi bi-yin-yang"></i>'

    def check_file_txt(self, path):
        name = os.path.basename(path)
        workdir = tempfile.mkdtemp()
        model_name_re = r'^[A-Za-z_][A-Za-z0-9_.-]*(@\d\d\d\d-\d\d-\d\d)?\.yang$'
        errors = 0
        warnings = 0
        message = ""
        results = []
        passed = True                   # Used by the submission tool.  Yang checks always pass.
        model_list = []
        info = {'checker': self.name, 'items': [], 'code': {}}

        extractor = xym.YangModuleExtractor(path, workdir, strict=True, strict_examples=False, debug_level=1)
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

        for m in model_list:
            if not re.search(model_name_re, m):
                code += 1
                err += "Error: Bad extracted model name: '%s'\n" % m
        if len(set(model_list)) != len(model_list):
            code += 1
            err += "Error: Multiple models with the same name:\n  %s\n" % ("\n  ".join(model_list))

        model_list = list(set(model_list))

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
            modpath = ':'.join([
                                workdir,
                                settings.SUBMIT_YANG_RFC_MODEL_DIR,
                                settings.SUBMIT_YANG_DRAFT_MODEL_DIR,
                                settings.SUBMIT_YANG_IANA_MODEL_DIR,
                                settings.SUBMIT_YANG_CATALOG_MODEL_DIR,
                            ])
            if os.path.exists(path):
                with io.open(path) as file:
                    text = file.readlines()
                # pyang
                cmd_template = settings.SUBMIT_PYANG_COMMAND
                command = [ w for w in cmd_template.split() if not '=' in w ][0]
                cmd = cmd_template.format(libs=modpath, model=path)
                venv_path = os.environ.get('VIRTUAL_ENV') or os.path.join(os.getcwd(), 'env')
                venv_bin = os.path.join(venv_path, 'bin')
                if not venv_bin in os.environ.get('PATH', '').split(':'):
                    os.environ['PATH'] = os.environ.get('PATH', '') + ":" + venv_bin
                code, out, err = pipe(cmd)
                out = out.decode('utf-8')
                err = err.decode('utf-8')
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
                set_coverage_checking(False) # we can't count the following as it may or may not be run, depending on setup
                if settings.SUBMIT_YANGLINT_COMMAND and os.path.exists(settings.YANGLINT_BINARY):
                    cmd_template = settings.SUBMIT_YANGLINT_COMMAND
                    command = [ w for w in cmd_template.split() if not '=' in w ][0]
                    cmd = cmd_template.format(model=path, rfclib=settings.SUBMIT_YANG_RFC_MODEL_DIR, tmplib=workdir,
                        draftlib=settings.SUBMIT_YANG_DRAFT_MODEL_DIR, ianalib=settings.SUBMIT_YANG_IANA_MODEL_DIR,
                        cataloglib=settings.SUBMIT_YANG_CATALOG_MODEL_DIR, )
                    code, out, err = pipe(cmd)
                    out = out.decode('utf-8')
                    err = err.decode('utf-8')
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
                set_coverage_checking(True)
            else:
                errors += 1
                message += "No such file: %s\nPossible mismatch between extracted xym file name and returned module name?\n" % (path)

            dest = os.path.join(settings.SUBMIT_YANG_DRAFT_MODEL_DIR, model)
            shutil.move(path, dest)
            ftp_dest = Path(settings.FTP_DIR) / "yang" / "draftmod" / model
            try:
                os.link(dest, ftp_dest)
            except IOError as ex:
                log(
                    "There was an error creating a hardlink at %s pointing to %s: %s"
                    % (ftp_dest, dest, ex)
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
