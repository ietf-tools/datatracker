"""A parse session context"""

import re

from . import error
from . import yang_parser
from . import yin_parser
from . import util
from . import statements
from . import syntax

class Context(object):
    """Class which encapsulates a parse session"""

    def __init__(self, repository):
        """`repository` is a `Repository` instance"""

        self.modules = {}
        """dict of (modulename,revision):<class Statement>
        contains all modules and submodule found"""

        self.revs = {}
        """dict of modulename:[(revision,handle)]
        contains all modulenames and revisions found in the repository"""

        self.strict = False
        self.repository = repository
        self.errors = []
        self.canonical = False
        self.verify_revision_history = False
        self.max_line_len = None
        self.max_identifier_len = None
        self.implicit_errors = True
        self.lax_quote_checks = False
        self.lax_xpath_checks = False
        self.deviation_modules = []
        self.features = {}
        self.exclude_features = {}
        self.max_status = None
        self.keep_comments = False
        self.keep_arg_substrings = False

        for mod, rev, handle in self.repository.get_modules_and_revisions(self):
            if mod not in self.revs:
                self.revs[mod] = []
            revs = self.revs[mod]
            revs.append((rev, handle))

    def internal_reset(self):
        self.modules = {}
        self.revs = {}
        self.errors = []
        for mod, rev, handle in self.repository.get_modules_and_revisions(
                self):
            if mod not in self.revs:
                self.revs[mod] = []
            revs = self.revs[mod]
            revs.append((rev, handle))

    def add_module(self, ref, text, in_format=None,
                   expect_modulename=None, expect_revision=None,
                   expect_failure_error=True,
                   primary_module=False):
        """Parse a module text and add the module data to the context

        `ref` is a string which is used to identify the source of
              the text for the user.  used in error messages
        `text` is the raw text data
        `in_format` is one of 'yang' or 'yin'.

        Returns the parsed and validated module on success, and None on error.
        """
        if in_format is None:
            in_format = util.guess_format(text)

        if in_format == 'yin':
            p = yin_parser.YinParser()
        else:
            p = yang_parser.YangParser()

        module = p.parse(self, ref, text)
        if module is None:
            return None

        module.i_is_primary_module = primary_module
        if expect_modulename is not None:
            if not re.match(syntax.re_identifier, expect_modulename):
                error.err_add(self.errors, module.pos,
                              'FILENAME_BAD_MODULE_NAME',
                              (ref, expect_modulename, syntax.identifier))
            elif expect_modulename != module.arg:
                if expect_failure_error:
                    error.err_add(self.errors, module.pos, 'BAD_MODULE_NAME',
                                  (module.arg, ref, expect_modulename))
                    return None
                else:
                    error.err_add(self.errors, module.pos, 'WBAD_MODULE_NAME',
                                  (module.arg, ref, expect_modulename))

        latest_rev = util.get_latest_revision(module)
        if expect_revision is not None:
            if not re.match(syntax.re_date, expect_revision):
                error.err_add(self.errors, module.pos, 'FILENAME_BAD_REVISION',
                              (ref, expect_revision, 'YYYY-MM-DD'))
            elif expect_revision != latest_rev:
                if expect_failure_error:
                    error.err_add(self.errors, module.pos, 'BAD_REVISION',
                                  (latest_rev, ref, expect_revision))
                    return None
                else:
                    error.err_add(self.errors, module.pos, 'WBAD_REVISION',
                                  (latest_rev, ref, expect_revision))

        if module.arg not in self.revs:
            self.revs[module.arg] = []
            revs = self.revs[module.arg]
            revs.append((latest_rev, None))

        return self.add_parsed_module(module)

    def add_parsed_module(self, module):
        if module is None:
            return None
        if module.arg is None:
            error.err_add(self.errors, module.pos,
                          'EXPECTED_ARGUMENT', module.keyword)
            return None
        top_keywords = ['module', 'submodule']
        if module.keyword not in top_keywords:
            error.err_add(self.errors, module.pos,
                          'UNEXPECTED_KEYWORD_N',
                          (module.keyword, top_keywords))
            return None

        rev = util.get_latest_revision(module)
        if (module.arg, rev) in self.modules:
            other = self.modules[(module.arg, rev)]
            return other

        self.modules[(module.arg, rev)] = module

        return module

    def del_module(self, module):
        """Remove a module from the context"""
        rev = util.get_latest_revision(module)
        del self.modules[(module.arg, rev)]

    def get_module(self, modulename, revision=None):
        """Return the module if it exists in the context"""
        if revision is None and modulename in self.revs:
            (revision, _handle) = self._get_latest_rev(self.revs[modulename])
        if revision is not None:
            if (modulename,revision) in self.modules:
                return self.modules[(modulename, revision)]
        else:
            return None

    def _get_latest_rev(self, revs):
        self._ensure_revs(revs)
        latest = None
        lhandle = None
        for rev, handle in revs:
            if rev is not None and (latest is None or rev > latest):
                latest = rev
                lhandle = handle
        return latest, lhandle

    def _ensure_revs(self, revs):
        i = 0
        length = len(revs)
        repository = self.repository
        while i < length:
            rev, handle = revs[i]
            if rev is None:
                # now we must read the revision from the module
                try:
                    ref, in_format, text = repository.get_module_from_handle(
                        handle)
                except repository.ReadError as ex:
                    i += 1
                    continue

                if in_format is None:
                    in_format = util.guess_format(text)

                if in_format == 'yin':
                    yintext = text
                    p = yin_parser.YinParser(
                        {'no_include': True, 'no_extensions': True})
                else:
                    yintext = None
                    p = yang_parser.YangParser()

                module = p.parse(self, ref, text)
                if module is not None:
                    rev = util.get_latest_revision(module)
                    revs[i] = (rev, ('parsed', module, ref, yintext))
            i += 1

    def search_module(self, pos, modulename, revision=None,
                      primary_module=False):
        """Searches for a module named `modulename` in the repository

        If the module is found, it is added to the context.
        Returns the module if found, and None otherwise"""

        if modulename not in self.revs:
            # this module doesn't exist in the repos at all
            error.err_add(self.errors, pos, 'MODULE_NOT_FOUND', modulename)
            # keep track of this to avoid multiple errors
            self.revs[modulename] = []
            return None
        elif not self.revs[modulename]:
            # this module doesn't exist in the repos at all, error reported
            return None

        if revision is not None:
            if (modulename,revision) in self.modules:
                return self.modules[(modulename, revision)]
            self._ensure_revs(self.revs[modulename])
            x = util.keysearch(revision, 0, self.revs[modulename])
            if x is not None:
                (_revision, handle) = x
                if handle is None:
                    # this revision doesn't exist in the repos, error reported
                    return None
            else:
                # this revision doesn't exist in the repos
                error.err_add(self.errors, pos, 'MODULE_NOT_FOUND_REV',
                              (modulename, revision))
                # keep track of this to avoid multiple errors
                self.revs[modulename].append((revision, None))
                return None
        else:
            # get the latest revision
            (revision, handle) = self._get_latest_rev(self.revs[modulename])
            if (modulename, revision) in self.modules:
                return self.modules[(modulename, revision)]

        if handle is None:
            module = None
        elif handle[0] == 'parsed':
            module = handle[1]
            ref = handle[2]
            yintext = handle[3]
            if modulename != module.arg:
                error.err_add(self.errors, module.pos, 'BAD_MODULE_NAME',
                              (module.arg, ref, modulename))
                module = None
            elif yintext is None:
                module = self.add_parsed_module(handle[1])
            else:
                p = yin_parser.YinParser()
                self.yin_module_map[module.arg] = []
                module = p.parse(self, ref, yintext)
                if module is not None:
                    module = self.add_parsed_module(module)
        else:
            # get it from the repo
            try:
                ref, in_format, text = self.repository.get_module_from_handle(
                    handle)
                module = self.add_module(
                    ref, text, in_format, modulename, revision,
                    True, primary_module)
            except self.repository.ReadError as ex:
                error.err_add(self.errors, pos, 'READ_ERROR', str(ex))
                module = None

        if module is None:
            return None
        # if modulename != module.arg:
        #     error.err_add(self.errors, module.pos, 'BAD_MODULE_FILENAME',
        #                   (module.arg, ref, modulename))
        #     latest_rev = util.get_latest_revision(module)

        #     if revision is not None and revision != latest_rev:
        #         error.err_add(self.errors, module.pos, 'BAD_REVISION',
        #                       (latest_rev, ref, revision))

        #     self.del_module(module)
        #     self.modules[(modulename, latest_rev)] = None
        #     return None
        return module

    def read_module(self, modulename, revision=None, extra=None):
        """Searches for a module named `modulename` in the repository

        The module is just read, and not compiled at all.
        Returns the module if found, and None otherwise"""

        if modulename not in self.revs:
            # this module doesn't exist in the repos at all
            return None
        elif not self.revs[modulename]:
            # this module doesn't exist in the repos at all, error reported
            return None

        if revision is not None:
            if (modulename,revision) in self.modules:
                return self.modules[(modulename, revision)]
            self._ensure_revs(self.revs[modulename])
            x = util.keysearch(revision, 1, self.revs[modulename])
            if x is not None:
                _revision, handle = x
                if handle is None:
                    # this revision doesn't exist in the repos, error reported
                    return None
            else:
                # this revision doesn't exist in the repos
                return None
        else:
            # get the latest revision
            (revision, handle) = self._get_latest_rev(self.revs[modulename])
            if (modulename, revision) in self.modules:
                return self.modules[(modulename, revision)]

        if handle[0] == 'parsed':
            module = handle[1]
            return module
        else:
            # get it from the repos
            try:
                ref, in_format, text = self.repository.get_module_from_handle(
                    handle)

                if in_format is None:
                    in_format = util.guess_format(text)

                if in_format == 'yin':
                    p = yin_parser.YinParser(extra)
                else:
                    p = yang_parser.YangParser(extra)

                return p.parse(self, ref, text)
            except self.repository.ReadError as ex:
                return None

    def validate(self):
        modules = []
        for k in self.modules:
            m = self.modules[k]
            if m is not None:
                modules.append(m)
        for m in modules:
            # may add new modules by import
            statements.validate_module(self, m)

        # check for duplicate namespaces across all loaded modules
        uri_map = {}
        for k in self.modules:
            m = self.modules[k]
            namespace = None if m is None else m.search_one('namespace')
            if namespace is not None:
                uri = namespace.arg
                uses = uri_map.get(uri)
                if uses is None:
                    uri_map[uri] = uses = [], set()
                uses[0].append(namespace.pos)
                uses[1].add(m.arg)

        for uri in uri_map:
            uses = uri_map[uri]
            if len(uses[1]) == 1:
                continue
            module_names = ' '.join(sorted(uses[1]))
            for pos in uses[0]:
                error.err_add(self.errors, pos,
                              'DUPLICATE_NAMESPACE',
                              (uri, module_names))
