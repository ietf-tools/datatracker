# Copyright The IETF Trust 2016, All Rights Reserved

import os
import re
from xym import xym
import shutil
import tempfile

from django.conf import settings

import debug                            # pyflakes:ignore

from ietf.utils.pipe import pipe
from ietf.utils.log import log

class DraftSubmissionChecker():
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
    # symbol = '<span class="fa fa-check-square"></span>'
    symbol = ""

    def check_file_txt(self, path):
        """
        Run an idnits check, and return a passed/failed indication, a message,
        and error and warning messages.

        Error and warning list items are tuples:
            (line_number, line_text, message)
        """
        filename = os.path.basename(path)
        result = {}
        items = []
        errors = 0
        warnings = 0
        errstart = ['  ** ', '  ~~ ']
        warnstart = ['  == ', '  -- ']
        

        cmd = "%s --submitcheck --nitcount %s" % (settings.IDSUBMIT_IDNITS_BINARY, path)
        code, out, err = pipe(cmd)
        if code != 0 or out == "":
            message = "idnits error: %s:\n  Error %s: %s" %( cmd, code, err)
            log(message)
            passed = False
            
        else:
            message = out
            if re.search("\s+Summary:\s+0\s+|No nits found", out):
                passed  = True
            else:
                passed  = False

        item = None
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
                item = None
            elif item and line.strip() != "":
                item += " " + line.strip()
            else:
                pass
            result[filename] = {
                    "passed":  passed,
                    "message": message,
                    "errors":  errors,
                    "warnings":warnings,
                    "items": items,
                }


        return passed, message, errors, warnings, result

class DraftYangChecker(object):

    name = "yang validation"
    symbol = u'<span class="large">\u262f</span>'

    def check_file_txt(self, path):
        name = os.path.basename(path)
        workdir = tempfile.mkdtemp()
        errors = []
        warnings = []
        results = {}

        extractor = xym.YangModuleExtractor(path, workdir, strict=True, debug_level = 0)
        if not os.path.exists(path):
            return None, "%s: No such file or directory: '%s'"%(name.capitalize(), path), errors, warnings, results
        with open(path) as file:
            try:
                # This places the yang models as files in workdir
                extractor.extract_yang_model(file.readlines())
                model_list = extractor.get_extracted_models()
            except Exception as exc:
                passed  = False
                message = exc
                errors  = [ (name, None, None, exc) ]
                warnings = []
                return passed, message, errors, warnings

        for model in model_list:
            path = os.path.join(workdir, model)
            modpath = ':'.join([
                                workdir,
                                settings.YANG_RFC_MODEL_DIR,
                                settings.YANG_DRAFT_MODEL_DIR,
                                settings.YANG_INVAL_MODEL_DIR,
                            ])
            with open(path) as file:
                text = file.readlines()
            cmd = settings.IDSUBMIT_PYANG_COMMAND % {"modpath": modpath, "model": path, }
            code, out, err = pipe(cmd)
            errors = 0
            warnings = 0
            items = []
            if code > 0:
                error_lines = err.splitlines()
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
            results[model] = {
                "passed":  code == 0,
                "message": out+"No validation errors\n" if code == 0 else err,
                "warnings": warnings,
                "errors":  errors,
                "items": items,
            }

        shutil.rmtree(workdir)

        ## For now, never fail because of failed yang validation.
        if len(model_list):
            passed = True
        else:
            passed = None
        #passed  = all( res["passed"] for res in results.values() )
        message = "\n\n".join([ "\n".join([model+':', res["message"]]) for model, res in results.items() ])
        errors  = sum(res["errors"] for res in results.values() )
        warnings  = sum(res["warnings"] for res in results.values() )
        items  = [ e for res in results.values() for e in res["items"] ]

        return passed, message, errors, warnings, items

