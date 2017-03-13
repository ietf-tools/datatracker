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

def build_traceback(stack):
    """
    Build something that looks sufficiently like a traceback to be passed to a
    logging.logger as the exc_info argument.
    """
    class Traceback():
        pass
    next = None
    for frame_record in stack:
        fr_frame, fr_filename, fr_lineno, fr_funcname, fr_context, fr_context_this = frame_record
        tb = Traceback()
        tb.tb_frame = fr_frame
        tb.tb_lasti = fr_frame.f_lasti
        tb.tb_lineno = fr_lineno
        tb.tb_next = next
        next = tb
        # Stop traceback at _get_response() -- we don't want to see the
        # middleware, debug server, or wsgi internals when the exception
        # occurs in our app code, below _get_response():
        if fr_funcname == '_get_response' and fr_filename.endswith('django/core/handlers/base.py'):
            break
    return tb

def assertion(statement):
    """
    This acts like an assertion.  It uses the django logger in order to send
    the failed assertion and a backtrace as for an internal server error.

    """
    stack = inspect.stack()[1:]
    frame = stack[0][0]
    value = eval(statement, frame.f_globals, frame.f_locals)
    if not value:
        if settings.DEBUG is True or settings.SERVER_MODE == 'test':
            raise AssertionError("Assertion '%s' failed." % (statement,))
        else:
            # build a simulated traceback object
            tb = build_traceback(stack)
            # provide extra info if available
            extra = {}
            for key in [ 'request', 'status_code', ]:
                if key in frame.f_locals:
                    extra[key] = frame.f_locals[key]
            logger.error("Assertion '%s' failed.", statement, exc_info=(AssertionError, statement, tb), extra=extra)

def unreachable():
    "Raises an assertion or sends traceback to admins if executed."
    stack = inspect.stack()[1:]
    frame = stack[0][0]
    if settings.DEBUG is True or settings.SERVER_MODE == 'test':
        raise AssertionError("Arrived at code in %s() which was marked unreachable." % frame.f_code.co_name)
    else:
        # build a simulated traceback object
        tb = build_traceback(stack)
        # provide extra info if available
        extra = {}
        for key in [ 'request', 'status_code', ]:
            if key in frame.f_locals:
                extra[key] = frame.f_locals[key]
        logger.error("Arrived at code in %s() which was marked unreachable.", frame.f_code.co_name, exc_info=(AssertionError, frame.f_code.co_name, tb), extra=extra)
    
