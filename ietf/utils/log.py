# Copyright The IETF Trust 2007, All Rights Reserved

import logging
import inspect
import os.path

try:
    import syslog
    logfunc = syslog.syslog
except ImportError:                     # import syslog will fail on Windows boxes
    logging.basicConfig(filename='tracker.log',level=logging.INFO)
    logfunc = logging.info
    pass

from django.conf import settings

import debug                            # pyflakes:ignore

def getclass(frame):
    cls = None
    argnames, varargs, varkw, defaults  = inspect.getargvalues(frame)
    if len(argnames) > 0:
        selfname = argnames[0]
        cls = defaults[selfname].__class__
    return cls

def getcaller():
    parent, pfile, pline, pfunction, lines, index = inspect.stack()[2]
    moduleinfo = inspect.getmoduleinfo(pfile)
    pmodule = moduleinfo[0] if moduleinfo else None
    pclass = getclass(parent)
    return (pmodule, pclass, pfunction, pfile, pline)

def log(msg):
    "Uses syslog by preference.  Logs the given calling point and message."
    if settings.SERVER_MODE == 'test':
        return
    if isinstance(msg, unicode):
        msg = msg.encode('unicode_escape')
    try:
        mod, cls, func, file, line = getcaller()
        file = os.path.abspath(file)
        file = file.replace(settings.BASE_DIR, "")
        if func == "<module>":
            where = ""
        else:
            where = " in " + func + "()"
    except IndexError:
        file, line, where = "/<UNKNOWN>", 0, ""
    logfunc("ietf%s(%d)%s: %s" % (file, line, where, msg))



logger = logging.getLogger('django')

def affirm(statement):
    """
    This acts like an assertion.  It uses the django logger in order to send
    the failed assertion and a backtrace as for an internal server error.

    """
    class Traceback():
        pass
    frame = inspect.stack()[1][0]
    value = eval(statement, frame.f_globals, frame.f_locals)
    if not value:
        if settings.DEBUG is True:
            raise AssertionError(statement)
        else:
            # build a simulated traceback object
            tb = Traceback()
            tb.tb_frame = frame
            tb.tb_lasti = None
            tb.tb_lineno = frame.f_lineno
            tb.tb_next = None
            logger.error("AssertionError: '%s'", statement, exc_info=(AssertionError, statement, tb), extra=frame.f_locals)
