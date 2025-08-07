"""A repository for searching and holding loaded pyang modules"""

import os
import sys
import io

from pathlib import Path

from . import util
from . import syntax

class Repository(object):
    """Abstract base class that represents a module repository"""

    def get_modules_and_revisions(self, ctx):
        """Return a list of all modules and their revisons

        Returns a tuple (`modulename`, `revision`, `handle`), where
        `handle' is used in the call to get_module_from_handle() to
        retrieve the module.
        """

    def get_module_from_handle(self, handle):
        """Return the raw module text from the repository

        Returns (`ref`, `in_format`, `text`) if found, or None if not found.
        `ref` is a string which is used to identify the source of
              the text for the user.  used in error messages
        `in_format` is one of 'yang' or 'yin' or None.
        `text` is the raw text data

        Raises `ReadError`
        """

    class ReadError(Exception):
        """Signals that an error occured during module retrieval"""


class FileRepository(Repository):
    def __init__(self, path="", use_env=True, no_path_recurse=False,
                 verbose=False):
        """Create a Repository which searches the filesystem for modules

        `path` is a `os.pathsep`-separated string of directories
        """

        Repository.__init__(self)
        self.dirs = []
        self.no_path_recurse = no_path_recurse
        self.modules = None
        self.verbose = verbose

        for directory in path.split(os.pathsep):
            self._add_directory(directory)

        while use_env:
            use_env = False
            modpath = os.getenv('YANG_MODPATH')
            if modpath is not None:
                for directory in modpath.split(os.pathsep):
                    self._add_directory(directory)

            home = os.getenv('HOME')
            if home is not None:
                self._add_directory(os.path.join(home, 'yang', 'modules'))

            inst = os.getenv('YANG_INSTALL')
            if inst is not None:
                self._add_directory(os.path.join(inst, 'yang', 'modules'))
                break  # skip search if install location is indicated

            default_install = os.path.join(
                sys.prefix, 'share', 'yang', 'modules')
            if os.path.exists(default_install):
                self._add_directory(default_install)
                break  # end search if default location exists

            # for some systems, sys.prefix returns `/usr`
            # but the real location is `/usr/local`
            # if the package is installed with pip
            # this information can be easily retrieved
            import pkgutil
            if not pkgutil.find_loader('pip'):
                break  # abort search if pip is not installed

            # hack below to handle pip 10 internals
            # if someone knows pip and how to fix this, it would be great!
            location = None
            try:
                import pip.locations as locations
                location = locations.distutils_scheme('pyang')
            except:
                try:
                    import pip._internal.locations as locations
                    location = locations.distutils_scheme('pyang')
                except:
                    pass
            if location is not None:
                self._add_directory(
                    os.path.join(location['data'], 'share', 'yang', 'modules'))

        if verbose:
            sys.stderr.write('# module search path: %s\n'
                             % os.pathsep.join(self.dirs))

    def _add_directory(self, directory):
        if (not directory
            or directory in self.dirs
            or not os.path.isdir(directory)):
            return False
        self.dirs.append(directory)
        return True

    def _setup(self, ctx):
        # check all dirs for yang and yin files
        self.modules = []
        def add_files_from_dir(d):
            base = Path(d)
            try:
                files = base.iterdir()
            except OSError:
                files = []
            for file_path in files:
                if file_path.is_file():
                    m = syntax.re_filename.search(file_path.name)
                    if m is not None:
                        name, rev, in_format = m.groups()
                        if not os.access(str(file_path), os.R_OK):
                            continue
                        handle = in_format, str(file_path)
                        self.modules.append((name, rev, handle))
                elif (not self.no_path_recurse
                      and d != '.' and file_path.is_dir()):
                    add_files_from_dir(file_path)
        for d in self.dirs:
            add_files_from_dir(d)

    def get_modules_and_revisions(self, ctx):
        if self.modules is None:
            self._setup(ctx)
        return self.modules

    def get_module_from_handle(self, handle):
        in_format, absfilename = handle
        fd = None
        try:
            fd = io.open(absfilename, "r", encoding="utf-8")
            text = fd.read()
            if self.verbose:
                util.report_file_read(absfilename)
        except IOError as ex:
            raise self.ReadError("%s: %s" % (absfilename, ex))
        except UnicodeDecodeError as ex:
            s = str(ex).replace('utf-8', 'utf8')
            raise self.ReadError("%s: unicode error: %s" % (absfilename, s))
        finally:
            if fd is not None:
                fd.close()

        if in_format is None:
            in_format = util.guess_format(text)
        return absfilename, in_format, text
