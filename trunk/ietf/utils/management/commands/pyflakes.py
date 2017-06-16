from __future__ import absolute_import
import ast
import os
from pyflakes import checker, messages
import sys

from django.conf import settings
from django.core.management.base import BaseCommand

# BlackHole, PySyntaxError and checking based on 
# https://github.com/patrys/gedit-pyflakes-plugin.git
class BlackHole(object):
    write = flush = lambda *args, **kwargs: None

    def __enter__(self):
        self.stderr, sys.stderr = sys.stderr, self

    def __exit__(self, *args, **kwargs):
        sys.stderr = self.stderr


class PySyntaxError(messages.Message):
    message = 'syntax error in line %d: %s'

    def __init__(self, filename, lineno, col, message):
        try:
            super(PySyntaxError, self).__init__(filename, lineno)
        except Exception:
            sys.stderr.write("\nAn exception occurred while processing file %s\n"+
                "The file could contain syntax errors.\n\n" % filename)

        self.message_args = (col, message)


def check(codeString, filename, verbosity=1):
    """
    Check the Python source given by C{codeString} for flakes.

    @param codeString: The Python source to check.
    @type codeString: C{str}

    @param filename: The name of the file the source came from, used to report
        errors.
    @type filename: C{str}

    @return: The number of warnings emitted.
    @rtype: C{int}
    """

    try:
        with BlackHole():
            tree = ast.parse(codeString, filename)
    except SyntaxError, e:
        return [PySyntaxError(filename, e.lineno, e.offset, e.text)]
    else:
        # Okay, it's syntactically valid.  Now parse it into an ast and check
        # it.
        w = checker.Checker(tree, filename)

        lines = codeString.split('\n')
        # honour pyflakes:ignore comments
        messages = [message for message in w.messages
                    if lines[message.lineno-1].find('pyflakes:ignore') < 0]
        # honour pyflakes:

        messages.sort(lambda a, b: cmp(a.lineno, b.lineno))
        if verbosity > 0:
            if len(messages):
                sys.stderr.write('F')
            else:
                sys.stderr.write('.')
        if verbosity > 1:
            sys.stderr.write("  %s\n" % filename)
        return messages


def checkPath(filename, verbosity):
    """
    Check the given path, printing out any warnings detected.

    @return: the number of warnings printed
    """
    try:
        return check(file(filename, 'U').read() + '\n', filename, verbosity)
    except IOError, msg:
        return ["%s: %s" % (filename, msg.args[1])]
    except TypeError:
        pass

def checkPaths(filenames, verbosity):
    warnings = []
    for arg in filenames:
        if os.path.isdir(arg):
            for dirpath, dirnames, filenames in os.walk(arg):
                for filename in filenames:
                    if filename.endswith('.py'):
                        try:
                            warnings.extend(checkPath(os.path.join(dirpath, filename), verbosity))
                        except TypeError as e:
                            print("Exception while processing dirpath=%s, filename=%s: %s" % (dirpath, filename,e ))
                            raise
        else:
            warnings.extend(checkPath(arg, verbosity))
    return warnings
#### pyflakes.scripts.pyflakes ends.


class Command(BaseCommand):
    help = "Run pyflakes syntax checks."
    args = '[path [path [...]]]'

    def handle(self, *filenames, **options):
        if not filenames:
            filenames = getattr(settings, 'PYFLAKES_DEFAULT_ARGS', ['.'])
        verbosity = int(options.get('verbosity'))
        warnings = checkPaths(filenames, verbosity=verbosity)
        print ""
        for warning in warnings:
            print warning

        if warnings:
            print 'Total warnings: %d' % len(warnings)
            raise SystemExit(1)
            
