
import sys
import inspect
import syslog
from pprint import pformat

# A debug decorator, written by Paul Butler, taken from
# http://paulbutler.org/archives/python-debugging-with-decorators/
# Additional functions and decorator functionality added by
# Henrik Levkowetz

# Number of times to indent output
# A list is used to force access by reference
__report_indent = [4]
increment = 2
debug = True
#syslog.openlog("debug", syslog.LOG_PID, syslog.LOG_USER)

def set_indent(i):
    __report_indent[0] = i

def trace(fn):                 # renamed from 'report' by henrik 16 Jun 2011
    """Decorator to print information about a function
    call for use while debugging.
    Prints function name, arguments, and call number
    when the function is called. Prints this information
    again along with the return value when the function
    returns.
    """
    def fix(s,n=32):    
        if len(s) > n+3:
            s = s[:n]+"..."
        s = s.replace('\n',' ')
        return s
    def wrap(*params,**kwargs):
        call = wrap.callcount = wrap.callcount + 1

        indent = ' ' * __report_indent[0]
        fc = "%s(%s)" % (fn.__name__, ', '.join(
            [fix(repr(a)) for a in params] +
            ["%s = %s" % (a, fix(repr(b))) for a,b in kwargs.items()]
        ))

        print "%s* %s [#%s]" % (indent, fc, call)
        __report_indent[0] += increment
        ret = fn(*params,**kwargs)
        __report_indent[0] -= increment
        sys.stderr.write( "%s  %s [#%s] ==> %s\n" % (indent, fc, call, repr(ret)))

        return ret
    wrap.callcount = 0
    if debug:
        return wrap
    else:
        return fn

def show(name):
    if debug:
        frame = inspect.stack()[1][0]
        value = eval(name, frame.f_globals, frame.f_locals)
        indent = ' ' * (__report_indent[0])
        sys.stderr.write("%s%s: %s\n" % (indent, name, value))

def log(name):
    if debug:
        frame = inspect.stack()[1][0]
        value = eval(name, frame.f_globals, frame.f_locals)
        indent = ' ' * (__report_indent[0])
        syslog.syslog("%s%s: %s" % (indent, name, value))

def pprint(name):
    if debug:
        frame = inspect.stack()[1][0]
        value = eval(name, frame.f_globals, frame.f_locals)
        indent = ' ' * (__report_indent[0])
        sys.stdout.write("%s%s:\n" % (indent, name))
        lines = pformat(value).split('\n')
        for line in lines:
            sys.stdout.write("%s %s\n"%(indent, line))

def say(s):
    if debug:
        indent = ' ' * (__report_indent[0])
        sys.stderr.write("%s%s\n" % (indent, s))

