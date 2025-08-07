"""YANG usage guidelines plugin
See RFC 8407
Other plugins can derive from this and make it more specific, e.g.,
ietf.py derives from this and sets the namespace and module name prefixes
to IETF-specific values.
"""

import optparse

from pyang import plugin
from pyang import statements
from pyang import error
from pyang import grammar
from pyang.error import err_add

def pyang_plugin_init():
    plugin.register_plugin(LintPlugin())

class LintPlugin(plugin.PyangPlugin):
    def __init__(self):
        plugin.PyangPlugin.__init__(self)
        ## Other plugins (e.g., ietf.py) can derive from this plugin
        ## and override these variables.

        # Set this to a list of allowed namespace prefixes.
        # The code checks that the namespace is on the form:
        #   <prefix><modulename>
        # If some other convention is used, the derived plugin can
        # define its own checks.
        self.namespace_prefixes = []

        # Set this to a list of allowed module name prefixes.
        # The code checks that the module name is on the form:
        #   <prefix>-...
        # If some other convention is used, the derived plugin can
        # define its own checks.
        self.modulename_prefixes = []

        # Set this to control whether to check that names are hyphenated
        # and don't contain any upper-case characters
        self.ensure_hyphenated_names = None

    def add_opts(self, optparser):
        optlist = [
            optparse.make_option("--lint",
                                 dest="lint",
                                 action="store_true",
                                 help="Validate the module(s) according to " \
                                 "RFC 8407rules."),
            optparse.make_option("--lint-namespace-prefix",
                                 dest="lint_namespace_prefixes",
                                 default=[],
                                 action="append",
                                 help="Validate that the module's namespace " \
                                     "matches one of the given prefixes."),
            optparse.make_option("--lint-modulename-prefix",
                                 dest="lint_modulename_prefixes",
                                 default=[],
                                 action="append",
                                 help="Validate that the module's name " \
                                     "matches one of the given prefixes."),
            optparse.make_option("--lint-ensure-hyphenated-names",
                                 dest="lint_ensure_hyphenated_names",
                                 action="store_true",
                                 help="No upper case and underscore in names."),
            ]
        optparser.add_options(optlist)

    def setup_ctx(self, ctx):
        if not ctx.opts.lint:
            return
        self._setup_ctx(ctx)

    def _setup_ctx(self, ctx):
        "Should be called by any derived plugin's setup_ctx() function."

        ctx.strict = True
        ctx.canonical = True
        ctx.max_identifier_len = 64
        ctx.implicit_errors = False

        # always add additional prefixes given on the command line
        self.namespace_prefixes.extend(ctx.opts.lint_namespace_prefixes)
        self.modulename_prefixes.extend(ctx.opts.lint_modulename_prefixes)

        # copy other lint options to instance variables, taking care not to
        # overwrite any settings from derived class constructors
        if ctx.opts.lint_ensure_hyphenated_names:
            self.ensure_hyphenated_names = True

        # register our grammar validation funs

        statements.add_validation_var(
            '$chk_default',
            lambda keyword: keyword in _keyword_with_default)
        statements.add_validation_var(
            '$chk_required',
            lambda keyword: keyword in _required_substatements)

        statements.add_validation_var(
            '$chk_recommended',
            lambda keyword: keyword in _recommended_substatements)

        statements.add_validation_fun(
            'grammar', ['$chk_default'],
            lambda ctx, s: v_chk_default(ctx, s))
        statements.add_validation_fun(
            'grammar', ['$chk_required'],
            lambda ctx, s: v_chk_required_substmt(ctx, s))
        statements.add_validation_fun(
            'grammar', ['$chk_recommended'],
            lambda ctx, s: v_chk_recommended_substmt(ctx, s))

        if self.ensure_hyphenated_names:
            statements.add_validation_fun(
                'grammar', ['*'],
                lambda ctx, s: v_chk_hyphenated_names(ctx, s))

        statements.add_validation_fun(
            'grammar', ['namespace'],
            lambda ctx, s: v_chk_namespace(ctx, s, self.namespace_prefixes))

        statements.add_validation_fun(
            'grammar', ['module', 'submodule'],
            lambda ctx, s: v_chk_module_name(ctx, s, self.modulename_prefixes))

        statements.add_validation_fun(
            'strict', ['include'],
            lambda ctx, s: v_chk_include(ctx, s))

        statements.add_validation_fun(
            'strict', ['module'],
            lambda ctx, s: v_chk_mandatory_top_level(ctx, s))

        # register our error codes
        error.add_error_code(
            'LINT_EXPLICIT_DEFAULT', 4,
            'RFC 8407: 4.4: '
            + 'statement "%s" is given with its default value "%s"')
        error.add_error_code(
            'LINT_MISSING_REQUIRED_SUBSTMT', 3,
            '%s: '
            + 'statement "%s" must have a "%s" substatement')
        error.add_error_code(
            'LINT_MISSING_RECOMMENDED_SUBSTMT', 4,
            '%s: '
            + 'statement "%s" should have a "%s" substatement')
        error.add_error_code(
            'LINT_BAD_NAMESPACE_VALUE', 4,
            'RFC 8407: 4.9: namespace value should be "%s"')
        error.add_error_code(
            'LINT_BAD_MODULENAME_PREFIX_1', 4,
            'RFC 8407: 4.1: '
            + 'the module name should start with the string %s')
        error.add_error_code(
            'LINT_BAD_MODULENAME_PREFIX_N', 4,
            'RFC 8407: 4.1: '
            + 'the module name should start with one of the strings %s')
        error.add_error_code(
            'LINT_NO_MODULENAME_PREFIX', 4,
            'RFC 8407: 4.1: '
            + 'no module name prefix string used')
        error.add_error_code(
            'LINT_BAD_REVISION', 3,
            'RFC 8407: 4.7: '
            + 'the module\'s revision %s is older than '
            + 'submodule %s\'s revision %s')
        error.add_error_code(
            'LINT_TOP_MANDATORY', 3,
            'RFC 8407: 4.10: '
            + 'top-level node %s must not be mandatory')
        error.add_error_code(
            'LINT_NOT_HYPHENATED', 4,
            '%s is not hyphenated, e.g., using upper-case or underscore')

        # override std error string
        error.add_error_code(
            'LONG_IDENTIFIER', 3,
            'RFC 8407: 4.3: identifier %s exceeds %s characters')

_keyword_with_default = {
    'status': 'current',
    'mandatory': 'false',
    'min-elements': '0',
    'max-elements': 'unbounded',
    'config': 'true',
    'yin-element': 'false',
    }

_required_substatements = {
    'module': (('contact', 'organization', 'description', 'revision'),
               "RFC 8407: 4.8"),
    'submodule': (('contact', 'organization', 'description', 'revision'),
                  "RFC 8407: 4.8"),
    'revision':(('reference',), "RFC 8407: 4.8"),
    'extension':(('description',), "RFC 8407: 4.14"),
    'feature':(('description',), "RFC 8407: 4.14"),
    'identity':(('description',), "RFC 8407: 4.14"),
    'typedef':(('description',), "RFC 8407: 4.13,4.14"),
    'grouping':(('description',), "RFC 8407: 4.14"),
    'augment':(('description',), "RFC 8407: 4.14"),
    'rpc':(('description',), "RFC 8407: 4.14"),
    'notification':(('description',), "RFC 8407: 4.14,4.16"),
    'container':(('description',), "RFC 8407: 4.14"),
    'leaf':(('description',), "RFC 8407: 4.14"),
    'leaf-list':(('description',), "RFC 8407: 4.14"),
    'list':(('description',), "RFC 8407: 4.14"),
    'choice':(('description',), "RFC 8407: 4.14"),
    'anyxml':(('description',), "RFC 8407: 4.14"),
    }

_recommended_substatements = {
    'enum':(('description',), "RFC 8407: 4.11.3,4.14"),
    'bit':(('description',), "RFC 8407: 4.11.3,4.14"),
    }

def v_chk_default(ctx, stmt):
    if (stmt.arg == _keyword_with_default[stmt.keyword] and
        stmt.parent.keyword != 'refine'):
        err_add(ctx.errors, stmt.pos, 'LINT_EXPLICIT_DEFAULT',
                (stmt.keyword, stmt.arg))

def v_chk_required_substmt(ctx, stmt):
    if stmt.keyword in _required_substatements:
        (required, s) = _required_substatements[stmt.keyword]
        for r in required:
            if stmt.search_one(r) is None:
                err_add(ctx.errors, stmt.pos,
                        'LINT_MISSING_REQUIRED_SUBSTMT',
                        (s, stmt.keyword, r))

def v_chk_recommended_substmt(ctx, stmt):
    if stmt.keyword in _recommended_substatements:
        (recommended, s) = _recommended_substatements[stmt.keyword]
        for r in recommended:
            if stmt.search_one(r) is None:
                err_add(ctx.errors, stmt.pos,
                        'LINT_MISSING_RECOMMENDED_SUBSTMT',
                        (s, stmt.keyword, r))

def v_chk_namespace(ctx, stmt, namespace_prefixes):
    if namespace_prefixes:
        for prefix in namespace_prefixes:
            if stmt.arg == prefix + stmt.i_module.arg:
                return
        err_add(ctx.errors, stmt.pos, 'LINT_BAD_NAMESPACE_VALUE',
                namespace_prefixes[0] + stmt.i_module.arg)

def v_chk_module_name(ctx, stmt, modulename_prefixes):
    if modulename_prefixes:
        for prefix in modulename_prefixes:
            if stmt.arg.startswith(prefix + '-'):
                return
        if len(modulename_prefixes) == 1:
            err_add(ctx.errors, stmt.pos, 'LINT_BAD_MODULENAME_PREFIX_1',
                    '"' + modulename_prefixes[0] + '-"')
        elif len(modulename_prefixes) == 2:
            s = " or ".join(['"' + p + '-"' for p in modulename_prefixes])
            err_add(ctx.errors, stmt.pos, 'LINT_BAD_MODULENAME_PREFIX_N', s)
        else:
            s = ", ".join(['"' + p + '-"' for p in modulename_prefixes[:-1]]) +\
            ', or "' + modulename_prefixes[-1] + '-"'
            err_add(ctx.errors, stmt.pos, 'LINT_BAD_MODULENAME_PREFIX_N', s)
    elif '-' not in stmt.arg:
        # can't check much, but we can check that a prefix is used
        err_add(ctx.errors, stmt.pos, 'LINT_NO_MODULENAME_PREFIX', ())

def v_chk_include(ctx, stmt):
    if stmt.i_orig_module.keyword != 'module':
        # the rule applies only to modules
        return
    latest = stmt.i_orig_module.i_latest_revision
    if latest is None:
        return
    submodulename = stmt.arg
    r = stmt.search_one('revision-date')
    if r is not None:
        rev = r.arg
    else:
        rev = None
    subm = ctx.get_module(submodulename, rev)
    if (subm is not None and
        subm.i_latest_revision is not None and
        subm.i_latest_revision > latest):
        err_add(ctx.errors, stmt.pos, 'LINT_BAD_REVISION',
                (latest, submodulename, subm.i_latest_revision))

def v_chk_mandatory_top_level(ctx, stmt):
    for s in stmt.i_children:
        if statements.is_mandatory_node(s):
            err_add(ctx.errors, s.pos, 'LINT_TOP_MANDATORY', s.arg)

def v_chk_hyphenated_names(ctx, stmt):
    if stmt.keyword in grammar.stmt_map:
        arg_type, subspec = grammar.stmt_map[stmt.keyword]
        if arg_type in ('identifier', 'enum-arg') and not_hyphenated(stmt.arg):
            error.err_add(ctx.errors, stmt.pos, 'LINT_NOT_HYPHENATED', stmt.arg)

def not_hyphenated(name):
    ''' Returns True if name is not hyphenated '''
    if name is None:
        return False
    # Check for upper-case and underscore
    return name != name.lower() or "_" in name
