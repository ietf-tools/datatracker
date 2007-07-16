# Copyright The IETF Trust 2007, All Rights Reserved

import syslog
import inspect
import os.path
import ietf
from django.conf import settings

def getclass(frame):
    cls = None
    argnames, varargs, varkw, defaults  = inspect.getargvalues(frame)
    if len(argnames) > 0:
        selfname = argnames[0]
        cls = defaults[selfname].__class__
    return cls

def getcaller():
    parent, pfile, pline, pfunction, lines, index = inspect.stack()[2]
    pmodule = inspect.getmoduleinfo(pfile)[0]
    pclass = getclass(parent)
    return (pmodule, pclass, pfunction, pfile, pline)

def log(msg):
    mod, cls, func, file, line = getcaller()
    file = os.path.abspath(file)
    file = file.replace(settings.BASE_DIR, "")
    if func == "<module>":
        where = ""
    else:
        where = " in " + func + "()"
    syslog.syslog("ietf%s(%d)%s: %s" % (file, line, where, msg))

log("IETFdb v%s started" % ietf.__version__)
