import copy
import re

from . import util
from . import types
from . import syntax
from . import grammar
from . import xpath
from .error import err_add

### Functions that plugins can use

def add_validation_phase(phase, before=None, after=None):
    """Add a validation phase to the framework.

    Can be used by plugins to do special validation of extensions."""
    idx = 0
    for x in _validation_phases:
        if x == before:
            _validation_phases.insert(idx, phase)
            return
        elif x == after:
            _validation_phases.insert(idx+1, phase)
            return
        idx = idx + 1
    # otherwise append at the end
    _validation_phases.append(phase)

def _sequence(one, two):
    """Return function calling two functions in order"""
    if one is None:
        return two
    elif two is None:
        return one
    return lambda *args, **kargs: (one(*args, **kargs), two(*args, **kargs))[1]

def add_validation_fun(phase, keywords, fun):
    """Add a validation function to some phase in the framework.

    Function `fun` is called for each valid occurence of each keyword in
    `keywords`.
    Can be used by plugins to do special validation of extensions."""
    for keyword in keywords:
        _validation_map[phase, keyword] = _sequence(
            _validation_map.get((phase, keyword)), fun)

def add_validation_var(var_name, var_fun):
    """Add a validation variable to the framework.

    Can be used by plugins to do special validation of extensions."""
    _validation_variables.append((var_name, var_fun))

def set_phase_i_children(phase):
    """Marks that the phase is run over the expanded i_children.

    Default is to run over substmts."""
    _v_i_children[phase] = True

def add_keyword_phase_i_children(phase, keyword):
    """Marks that the stmt is run in the expanded i_children phase."""
    _v_i_children_keywords[(phase, keyword)] = True

def add_data_keyword(keyword):
    """Can be used by plugins to register extensions as data keywords."""
    data_keywords.append(keyword)

def add_keyword_with_children(keyword):
    _keyword_with_children[keyword] = True

def is_keyword_with_children(keyword):
    return keyword in _keyword_with_children

def add_keywords_with_no_explicit_config(keyword):
    _keywords_with_no_explicit_config.append(keyword)

def add_copy_uses_keyword(keyword):
    _copy_uses_keywords.append(keyword)

def add_copy_augment_keyword(keyword):
    _copy_augment_keywords.append(keyword)

def add_xpath_function(name, input_params, output_param):
    xpath.add_extra_xpath_function(name, input_params, output_param)

def add_refinement_element(keyword, element, merge=False, v_fun=None):
    """Add an element to the <keyword>'s list of refinements"""
    for key, valid_keywords, _, _ in _refinements:
        if key == keyword:
            valid_keywords.append(element)
            return
    _refinements.append((keyword, [element], merge, v_fun))

def add_deviation_element(keyword, element):
    """Add an element to the <keyword>'s list of deviations.

    Can be used by plugins that add support for specific extension
    statements."""
    if keyword in _valid_deviations:
        _valid_deviations[keyword].append(element)
    else:
        _valid_deviations[keyword] = [element]

### Exceptions

class NotFound(Exception):
    """used when a referenced item is not found"""
    pass

class Abort(Exception):
    """used to abort an iteration"""
    pass

### Constants

re_path = re.compile('(.*)/(.*)')
re_deref = re.compile(r'deref\s*\(\s*(.*)\s*\)/\.\./(.*)')
re_and_or = re.compile(r'\band\b|\bor\b')

data_definition_keywords = ['container', 'leaf', 'leaf-list', 'list', 'case',
                            'choice', 'anyxml', 'anydata', 'uses', 'augment']

_validation_phases = [
    # init phase:
    #   initalizes the module/submodule statement, and maps
    #   the prefix in all extensions to their modulename
    #   from this point, extensions will be validated just as the
    #   other statements
    'init',
    # second init phase initializes statements, including extensions
    'init2',

    # grammar phase:
    #   verifies that the statement hierarchy is correct
    #   and that all arguments are of correct type
    #   complex arguments are parsed and saved in statement-specific
    #   variables
    'grammar',

    # import and include phase:
    #   tries to load each imported and included (sub)module
    'import',

    # type and grouping phase:
    #   verifies all typedefs, types and groupings
    'type',
    'type_2',

    # expansion phases:
    #   first expansion: copy data definition stmts into i_children
    'expand_1',

    # inherit properties phase:
    #   set i_config
    'inherit_properties',

    #   second expansion: expand augmentations into i_children
    'expand_2',
    'expand_3',

    # unique name check phase:
    'unique_name',

    # reference phase:
    #   verifies all references; e.g. leafref, unique, key for config
    'reference_1',
    'reference_2',
    'reference_3',
    'reference_4',

    # unused definitions phase:
    #   add warnings for unused definitions
    'unused',

    # strict phase: check YANG strictness
    'strict',
]

_validation_map = {
    ('init', 'module'):lambda ctx, s: v_init_module(ctx, s),
    ('init', 'submodule'):lambda ctx, s: v_init_module(ctx, s),
    ('init', '$extension'):lambda ctx, s: v_init_extension(ctx, s),
    ('init2', 'import'):lambda ctx, s: v_init_import(ctx, s),
    ('init2', '$has_children'):lambda ctx, s: v_init_has_children(ctx, s),
    ('init2', '*'):lambda ctx, s: v_init_stmt(ctx, s),

    ('grammar', 'module'):lambda ctx, s: v_grammar_module(ctx, s),
    ('grammar', 'submodule'):lambda ctx, s: v_grammar_module(ctx, s),
    ('grammar', 'typedef'):lambda ctx, s: v_grammar_typedef(ctx, s),
    ('grammar', '*'):lambda ctx, s: v_grammar_all(ctx, s),

    ('import', 'module'):lambda ctx, s: v_import_module(ctx, s),
    ('import', 'submodule'):lambda ctx, s: v_import_module(ctx, s),

    ('type', 'grouping'):lambda ctx, s: v_type_grouping(ctx, s),
    ('type', 'augment'):lambda ctx, s: v_type_augment(ctx, s),
    ('type', 'uses'):lambda ctx, s: v_type_uses(ctx, s),
    ('type', 'feature'):lambda ctx, s: v_type_feature(ctx, s),
    ('type', 'if-feature'):lambda ctx, s: v_type_if_feature(ctx, s),
    ('type', 'identity'):lambda ctx, s: v_type_identity(ctx, s),
    ('type', 'status'):lambda ctx, s: v_type_status(ctx, s),
    ('type', 'base'):lambda ctx, s: v_type_base(ctx, s),
    ('type', 'must'):lambda ctx, s: v_type_must(ctx, s),
    ('type', 'when'):lambda ctx, s: v_type_when(ctx, s),
    ('type', '$extension'): lambda ctx, s: v_type_extension(ctx, s),

    ('type_2', 'type'):lambda ctx, s: v_type_type(ctx, s),
    ('type_2', 'typedef'):lambda ctx, s: v_type_typedef(ctx, s),
    ('type_2', 'leaf'):lambda ctx, s: v_type_leaf(ctx, s),
    ('type_2', 'leaf-list'):lambda ctx, s: v_type_leaf_list(ctx, s),

    ('expand_1', 'module'):lambda ctx, s: v_expand_1_children(ctx, s),
    ('expand_1', 'submodule'):lambda ctx, s: v_expand_1_children(ctx, s),

    ('inherit_properties', 'module'): \
        lambda ctx, s: v_inherit_properties(ctx, s),
    ('inherit_properties', 'submodule'): \
        lambda ctx, s: v_inherit_properties(ctx, s),

    ('expand_2', 'augment'):lambda ctx, s: v_expand_2_augment(ctx, s),
    ('expand_3', 'augment'):lambda ctx, s: v_expand_3_augment(ctx, s),

    ('unique_name', 'module'): \
        lambda ctx, s: v_unique_name_defintions(ctx, s),
    ('unique_name', '$has_children'): \
        lambda ctx, s: v_unique_name_children(ctx, s),
    ('unique_name', 'leaf-list'): \
        lambda ctx, s: v_unique_name_leaf_list(ctx, s),

    ('reference_1', 'list'):lambda ctx, s:v_reference_list(ctx, s),
    ('reference_1', 'action'):lambda ctx, s:v_reference_action(ctx, s),
    ('reference_1', 'notification'):lambda ctx, s:v_reference_action(ctx, s),
    ('reference_1', 'choice'):lambda ctx, s: v_reference_choice(ctx, s),
    ('reference_2', 'leaf'):lambda ctx, s:v_reference_leaf_leafref(ctx, s),
    ('reference_2', 'leaf-list'):lambda ctx, s:v_reference_leaf_leafref(ctx, s),
    ('reference_2', 'must'):lambda ctx, s:v_reference_must(ctx, s),
    ('reference_2', 'when'):lambda ctx, s:v_reference_when(ctx, s),
## since we just check in reference_2, it means that we won't check
## xpaths in unused groupings.  the xpath is checked when the grouping is
## used.  the same is true for leafrefs
#    ('reference_3', 'must'):lambda ctx, s:v_reference_must(ctx, s),
#    ('reference_3', 'when'):lambda ctx, s:v_reference_when(ctx, s),
    ('reference_3', 'typedef'):lambda ctx, s:v_reference_leaf_leafref(ctx, s),
    ('reference_3', 'deviation'):lambda ctx, s:v_reference_deviation(ctx, s),
    ('reference_3', 'deviate'):lambda ctx, s:v_reference_deviate(ctx, s),
    ('reference_4', 'deviation'):lambda ctx, s:v_reference_deviation_4(ctx, s),
    ('reference_4', 'revision'):lambda ctx, s:v_reference_revision(ctx, s),

    ('unused', 'module'):lambda ctx, s: v_unused_module(ctx, s),
    ('unused', 'submodule'):lambda ctx, s: v_unused_module(ctx, s),
    ('unused', 'typedef'):lambda ctx, s: v_unused_typedef(ctx, s),
    ('unused', 'grouping'):lambda ctx, s: v_unused_grouping(ctx, s),
}

_v_i_children = {
    'unique_name':True,
    'expand_2':True,
    'expand_3':True,
    'reference_1':True,
    'reference_2':True,
}
"""Phases in this dict are run over the stmts that have i_children.
Note that the tests are not run in grouping definitions."""

_v_i_children_keywords = {
    ('reference_2', 'when'): True,
    ('reference_2', 'must'): True,
}
"""Keywords in this dict are iterated over in a phase in _v_i_children."""

_keyword_with_children = {
    'module':True,
    'submodule':True,
    'container':True,
    'list':True,
    'case':True,
    'choice':True,
    'grouping':True,
    'uses':True,
    'augment':True,
    'input':True,
    'output':True,
    'notification':True,
    'rpc':True,
    'action':True,
}

_validation_variables = [
    ('$has_children', lambda keyword: keyword in _keyword_with_children),
    ('$extension', lambda keyword: util.is_prefixed(keyword)),
]

data_keywords = ['leaf', 'leaf-list', 'container', 'list', 'choice', 'case',
                 'anyxml', 'anydata', 'action', 'rpc', 'notification']

_keywords_with_no_explicit_config = ['action', 'rpc', 'notification']

_copy_uses_keywords = []

_copy_augment_keywords = []

_refinements = [
    # (<keyword>, <list of keywords for which <keyword> can be refined>,
    #  <merge>, <validation function>)
    ('description',
     ['container', 'leaf', 'leaf-list', 'list', 'choice', 'case',
      'anyxml', 'anydata', 'action', 'notification'],
     False, None),
    ('reference',
     ['container', 'leaf', 'leaf-list', 'list', 'choice', 'case',
      'anyxml', 'anydata', 'action', 'notification'],
     False, None),
    ('config',
     ['container', 'leaf', 'leaf-list', 'list', 'choice', 'anyxml', 'anydata'],
     False, None),
    ('presence', ['container'], False, None),
    ('must', ['container', 'leaf', 'leaf-list', 'list', 'anyxml', 'anydata'],
     True, None),
    ('default', ['leaf', ('$1.1', 'leaf-list'), 'choice'],
     False, lambda ctx, target, default: v_default(ctx, target, default)),
    ('mandatory', ['leaf', 'choice', 'anyxml', 'anydata'], False, None),
    ('min-elements', ['leaf-list', 'list'], False, None),
    ('max-elements', ['leaf-list', 'list'], False, None),
    ('if-feature',
     ['container', 'leaf', 'leaf-list', 'list', 'choice', 'case',
      'anyxml', 'anydata'],
     True, None),
]

_singleton_keywords = {
    'type':True,
    'units':True,
    'default':True,
    'config':True,
    'mandatory':True,
    'min-elements':True,
    'max-elements':True
}

_deviate_delete_singleton_keywords = {
    'units':True,
    'default':True
}

_valid_deviations = {
    'type':['leaf', 'leaf-list'],
    'units':['leaf', 'leaf-list'],
    'default':['leaf', 'leaf-list', 'choice'],
    'config':['leaf', 'choice', 'container', 'list', 'leaf-list'],
    'mandatory':['leaf', 'choice'],
    'min-elements':['leaf-list', 'list'],
    'max-elements':['leaf-list', 'list'],
    'must':['leaf', 'choice', 'container', 'list', 'leaf-list'],
    'unique':['list'],
}

### Validation

def validate_module(ctx, module):
    """Validate `module`, which is a Statement representing a (sub)module"""

    if module.i_is_validated:
        return

    def iterate(stmt, phase):
        # if the grammar is not yet checked or if it is checked and
        # valid, then we continue.
        if getattr(stmt, 'is_grammatically_valid', None) is False:
            return
        # first check an exact match
        key = (phase, stmt.keyword)
        res = 'recurse'
        if key in _validation_map:
            f = _validation_map[key]
            res = f(ctx, stmt)
            if res == 'stop':
                raise Abort
        # then also run match by special variable
        for var_name, var_f in _validation_variables:
            key = phase, var_name
            if key in _validation_map and var_f(stmt.keyword) is True:
                f = _validation_map[key]
                res = f(ctx, stmt)
                if res == 'stop':
                    raise Abort
        # then run wildcard
        wildcard = (phase, '*')
        if wildcard in _validation_map:
            f = _validation_map[wildcard]
            res = f(ctx, stmt)
            if res == 'stop':
                raise Abort
        if res == 'continue':
            pass
        else:
            # default is to recurse
            if phase in _v_i_children:
                if stmt.keyword == 'grouping':
                    return
                if stmt.i_module is not None and stmt.i_module != module:
                    # this means that the stmt is from an included, expanded
                    # submodule - already validated.
                    return
                if hasattr(stmt, 'i_children'):
                    for s in stmt.i_children:
                        iterate(s, phase)
                for s in stmt.substmts:
                    if (hasattr(s, 'i_has_i_children') or
                        (phase, s.keyword) in _v_i_children_keywords):
                        iterate(s, phase)
            else:
                for s in stmt.substmts:
                    iterate(s, phase)

    module.i_is_validated = 'in_progress'
    try:
        for phase in _validation_phases:
            iterate(module, phase)
    except Abort:
        pass
    module.i_is_validated = True

def v_init_module(ctx, stmt):
    ## remember that the grammar is not validated
    vsn = stmt.search_one('yang-version')
    if vsn is not None:
        stmt.i_version = vsn.arg
    else:
        stmt.i_version = '1'
    # create a prefix map in the module:
    #   <prefix string> -> (<modulename>, <revision-date> | None)
    stmt.i_prefixes = {}
    # keep track of unused prefixes: <prefix string> -> <import statement>
    stmt.i_unused_prefixes = {}
    # keep track of missing prefixes, to supress mulitple errors
    stmt.i_missing_prefixes = {}
    # insert our own prefix into the map
    prefix = None
    if stmt.keyword == 'module':
        prefix = stmt.search_one('prefix')
        stmt.i_modulename = stmt.arg
        mod = stmt
    else:
        belongs_to = stmt.search_one('belongs-to')
        if belongs_to is not None and belongs_to.arg is not None:
            prefix = belongs_to.search_one('prefix')
            stmt.i_modulename = belongs_to.arg
            mod = ctx.get_module(stmt.i_modulename)
            if mod is None or not mod.i_is_validated:
                # this happens if a submodule is validated standalone
                mod = stmt
        else:
            stmt.i_modulename = ""
            mod = None

    if prefix is not None and prefix.arg is not None:
        stmt.i_prefixes[prefix.arg] = (stmt.arg, None)
        stmt.i_prefix = prefix.arg
    else:
        stmt.i_prefix = None
    # next we try to add prefixes for each import
    for i in stmt.search('import'):
        p = i.search_one('prefix')
        # verify that the prefix is not used
        if p is not None:
            prefix = p.arg
            r = i.search_one('revision-date')
            if r is not None:
                revision = r.arg
            else:
                revision = None
            # check if the prefix is already used by someone else
            if prefix in stmt.i_prefixes:
                (m, _rev) = stmt.i_prefixes[prefix]
                err_add(ctx.errors, p.pos, 'PREFIX_ALREADY_USED', (prefix, m))
            # add the prefix to the unused prefixes
            if (i.arg is not None and p.arg is not None
                and i.arg != stmt.i_modulename):
                stmt.i_prefixes[p.arg] = (i.arg, revision)
                stmt.i_unused_prefixes[p.arg] = i

    stmt.i_features = {}
    stmt.i_identities = {}
    stmt.i_extensions = {}

    stmt.i_including_modulename = None

    # save a pointer to the context
    stmt.i_ctx = ctx
    # keep track of created augment nodes
    stmt.i_undefined_augment_nodes = {}
    # next, set the attribute 'i_module' in each statement to point to the
    # module where the statement is defined.  if the module is a submodule,
    # 'i_main_module' will point to the main module, except if a submodule is
    #    validated stand-alone (then in points to the submodule)
    # 'i_orig_module' will point to the real module / submodule.
    # 'i_module' will point to the main module.
    def set_i_module(s):
        s.i_orig_module = s.top
        s.i_module = s.top
        s.i_main_module = mod
        return
    iterate_stmt(stmt, set_i_module)

def v_init_extension(ctx, stmt):
    """find the modulename of the prefix, and set `stmt.keyword`"""
    (prefix, identifier) = stmt.raw_keyword
    (modname, revision) = util.prefix_to_modulename_and_revision(
        stmt.i_module, prefix, stmt.pos, ctx.errors)
    stmt.keyword = (modname, identifier)
    stmt.i_extension_modulename = modname
    stmt.i_extension_revision = revision
    stmt.i_extension = None

def v_init_stmt(ctx, stmt):
    stmt.i_typedefs = {}
    stmt.i_groupings = {}
    stmt.i_uniques = []

def v_init_has_children(ctx, stmt):
    stmt.i_children = []

def v_init_import(ctx, stmt):
    stmt.i_is_safe_import = False

### grammar phase

def v_grammar_module(ctx, stmt):
    # check the statement hierarchy
    canonical = (ctx.canonical and stmt.i_is_primary_module)
    grammar.chk_module_statements(ctx, stmt, canonical)
    # check revision statements order
    prev = None
    stmt.i_latest_revision = None
    for r in stmt.search('revision'):
        if stmt.i_latest_revision is None or r.arg > stmt.i_latest_revision:
            stmt.i_latest_revision = r.arg
        if prev is not None and r.arg > prev:
            err_add(ctx.errors, r.pos, 'REVISION_ORDER', ())
        prev = r.arg

def v_grammar_typedef(ctx, stmt):
    if types.is_base_type(stmt.arg):
        err_add(ctx.errors, stmt.pos, 'BAD_TYPE_NAME', stmt.arg)

def v_grammar_all(ctx, stmt):
    v_grammar_unique_defs(ctx, stmt)
    v_grammar_identifier(ctx, stmt)

def v_grammar_unique_defs(ctx, stmt):
    """Verify that all typedefs and groupings are unique
    Called for every statement.
    Stores all typedefs in stmt.i_typedef, groupings in stmt.i_grouping
    """
    defs = [('typedef', 'TYPE_ALREADY_DEFINED', stmt.i_typedefs),
            ('grouping', 'GROUPING_ALREADY_DEFINED', stmt.i_groupings)]
    if stmt.parent is None:
        defs.extend(
            [('feature', 'FEATURE_ALREADY_DEFINED', stmt.i_features),
             ('identity', 'IDENTITY_ALREADY_DEFINED', stmt.i_identities),
             ('extension', 'EXTENSION_ALREADY_DEFINED', stmt.i_extensions)])
    for keyword, errcode, stmtdefs in defs:
        for definition in stmt.search(keyword):
            if definition.arg in stmtdefs:
                other = stmtdefs[definition.arg]
                err_add(ctx.errors, definition.pos,
                        errcode, (definition.arg, other.pos))
            else:
                stmtdefs[definition.arg] = definition

def v_grammar_identifier(ctx, stmt):
    try:
        (arg_type, _subspec) = grammar.stmt_map[stmt.keyword]
    except KeyError:
        return
    if (arg_type == 'identifier' and
        grammar.re_identifier_illegal_prefix.search(stmt.arg) is not None):
        if stmt.keyword == 'module' or stmt.keyword == 'submodule':
            mod = stmt
        else:
            mod = stmt.i_module
        if mod.i_version == '1':
            err_add(ctx.errors, stmt.pos, 'XML_IDENTIFIER', stmt.arg)

### import and include phase

def v_import_module(ctx, stmt):
    imports = stmt.search('import')
    includes = stmt.search('include')
    if stmt.keyword == 'module':
        mymodulename = stmt.arg
    else:
        b = stmt.search_one('belongs-to')
        if b is not None:
            mymodulename = b.arg
        else:
            mymodulename = None
    def add_module(i, primary_module):
        # check if the module to import is already added
        modulename = i.arg
        r = i.search_one('revision-date')
        rev = None
        if r is not None:
            rev = r.arg
        m = ctx.get_module(modulename, rev)
        if m is not None and i.keyword == 'import' and i.i_is_safe_import:
            pass
        elif m is not None and m.i_is_validated == 'in_progress':
            err_add(ctx.errors, i.pos,
                    'CIRCULAR_DEPENDENCY', ('module', modulename))
        # try to add the module to the context
        m = ctx.search_module(i.pos, modulename, rev,
                              primary_module=primary_module)
        if m is not None:
            validate_module(ctx, m)
        if (m is not None and r is not None and
            stmt.i_version == '1' and m.i_version == '1.1'):
            err_add(ctx.errors, i.pos,
                    'BAD_IMPORT_YANG_VERSION',
                    (stmt.i_version, m.i_version))
        return m

    for i in imports:
        module = add_module(i, False)
        if module is not None and module.keyword != 'module':
            err_add(ctx.errors, i.pos,
                    'BAD_IMPORT', (module.keyword, i.arg))

    for i in includes:
        submodule = add_module(i, stmt.i_is_primary_module)
        if submodule is not None and submodule.keyword != 'submodule':
            err_add(ctx.errors, i.pos,
                    'BAD_INCLUDE', (submodule.keyword, i.arg))
            return
        if submodule is not None:
            if submodule.i_version != stmt.i_version:
                err_add(ctx.errors, i.pos,
                        'BAD_INCLUDE_YANG_VERSION',
                        (submodule.i_version, stmt.i_version))
                return
            if stmt.keyword == 'module':
                submodule.i_including_modulename = stmt.arg
            else:
                submodule.i_including_modulename = mymodulename
            b = submodule.search_one('belongs-to')
            if b is not None and b.arg != mymodulename:
                err_add(ctx.errors, b.pos,
                    'BAD_SUB_BELONGS_TO',
                        (stmt.arg, submodule.arg, submodule.arg))
            else:
                # check that each submodule included by this submodule
                # is also included by the module
                if stmt.keyword == 'module':
                    for s in submodule.search('include'):
                        if stmt.search_one('include', s.arg) is None:
                            err_add(ctx.errors, s.pos,
                                    'MISSING_INCLUDE',
                                    (s.arg, submodule.arg, stmt.arg))

                # add typedefs, groupings, nodes etc to this module
                for ch in submodule.i_children:
                    if ch not in stmt.i_children:
                        stmt.i_children.append(ch)
                # verify that the submodule's definitions do not collide
                # with the module's definitions
                defs = [
                     (submodule.i_typedefs, stmt.i_typedefs,
                      'TYPE_ALREADY_DEFINED'),
                     (submodule.i_groupings, stmt.i_groupings,
                      'GROUPING_ALREADY_DEFINED'),
                     (submodule.i_features, stmt.i_features,
                      'FEATURE_ALREADY_DEFINED'),
                     (submodule.i_identities, stmt.i_identities,
                      'IDENTITY_ALREADY_DEFINED'),
                     (submodule.i_extensions, stmt.i_extensions,
                      'EXTENSION_ALREADY_DEFINED')]
                for substmtdefs, stmtdefs, errcode in defs:
                    for name in substmtdefs:
                        subdefinition = substmtdefs[name]
                        if name in stmtdefs:
                            # when the same submodule is inlcuded twice
                            # (e.g. by the module and by another submodule)
                            # the same definition will exist multiple times.
                            other = stmtdefs[name]
                            if other != subdefinition:
                                err_add(ctx.errors, other.pos,
                                        errcode, (name, subdefinition.pos))
                        else:
                            stmtdefs[name] = subdefinition

### type phase

def v_type_typedef(ctx, stmt):
    if hasattr(stmt, 'i_is_validated'):
        if stmt.i_is_validated is True:
            # this type has already been validated
            return
        elif stmt.i_is_circular is True:
            return
        elif stmt.i_is_validated == 'in_progress':
            err_add(ctx.errors, stmt.pos,
                    'CIRCULAR_DEPENDENCY', ('type', stmt.arg) )
            stmt.i_is_circular = True
            return

    stmt.i_is_circular = False
    stmt.i_is_validated = 'in_progress'
    stmt.i_default = None
    stmt.i_default_str = ""
    stmt.i_is_unused = True

    stmt.i_leafref = None # path_type_spec
    stmt.i_leafref_ptr = None # pointer to the leaf the leafref refer to
    stmt.i_leafref_expanded = False

    name = stmt.arg
    if stmt.parent.parent is not None:
        # non-top-level typedef; check if it is already defined
        ptype = search_typedef(stmt.parent.parent, name)
        if ptype is not None:
            err_add(ctx.errors, stmt.pos, 'TYPE_ALREADY_DEFINED',
                    (name, ptype.pos))
    type_ = stmt.search_one('type')
    if type_ is None or type_.is_grammatically_valid is False:
        # error is already reported by grammar check
        stmt.i_is_validated = True
        return
    # ensure our type is validated
    v_type_type(ctx, type_)

    # keep track of our leafref
    type_spec = type_.i_type_spec
    if isinstance(type_spec, types.PathTypeSpec):
        stmt.i_leafref = type_spec

    def check_circular_typedef(ctx, type_):
        # ensure the type is validated
        v_type_type(ctx, type_)
        # check the direct typedef
        if (type_.i_typedef is not None and
            type_.i_typedef.is_grammatically_valid is True):
            v_type_typedef(ctx, type_.i_typedef)
        # check all union's types
        membertypes = type_.search('type')
        for t in membertypes:
            check_circular_typedef(ctx, t)

    check_circular_typedef(ctx, type_)

    stmt.i_is_validated = True

    # check if we have a default value
    default = stmt.search_one('default')
    # ... or if we don't; check if our base typedef has one
    if (default is None and
        type_.i_typedef is not None and
        type_.i_typedef.i_default is not None):
        # validate that the base type's default value is still valid
        stmt.i_default = type_.i_typedef.i_default
        stmt.i_default_str = type_.i_typedef.i_default_str
        type_.i_type_spec.validate(ctx.errors, stmt.pos,
                                   stmt.i_default, stmt.i_module,
                                   ' for the inherited default value ')
    elif (default is not None and
          default.arg is not None and
          type_.i_type_spec is not None):
        stmt.i_default = type_.i_type_spec.str_to_val(ctx.errors,
                                                      default.pos,
                                                      default.arg,
                                                      stmt.i_module)
        stmt.i_default_str = default.arg
        if stmt.i_default is not None:
            type_.i_type_spec.validate(ctx.errors, default.pos,
                                       stmt.i_default, stmt.i_module,
                                       ' for the default value')

def v_type_type(ctx, stmt):
    if hasattr(stmt, 'i_is_validated'):
        # already validated
        return

    # set statement-specific variables
    stmt.i_is_validated = True
    stmt.i_is_derived = False
    stmt.i_type_spec = None
    stmt.i_typedef = None
    # Find the base type_spec
    prefix, name = util.split_identifier(stmt.arg)

    if prefix is None or stmt.i_module.i_prefix == prefix:
        # check local typedefs
        stmt.i_typedef = search_typedef(stmt, name)
        if stmt.i_typedef is None:
            # check built-in types
            try:
                stmt.i_type_spec = types.yang_type_specs[name]
            except KeyError:
                err_add(ctx.errors, stmt.pos,
                        'TYPE_NOT_FOUND', (name, stmt.i_module.arg))
                return
        else:
            # ensure the typedef is validated
            if stmt.i_typedef.is_grammatically_valid is True:
                v_type_typedef(ctx, stmt.i_typedef)
            else:
                stmt.i_typedef.i_default = None
                stmt.i_typedef.i_default_str = ""
            stmt.i_typedef.i_is_unused = False
    else:
        # this is a prefixed name, check the imported modules
        pmodule = util.prefix_to_module(
            stmt.i_module, prefix, stmt.pos, ctx.errors)
        if pmodule is None:
            return
        stmt.i_typedef = search_typedef(pmodule, name)
        if stmt.i_typedef is None:
            err_add(ctx.errors, stmt.pos, 'TYPE_NOT_FOUND', (name, pmodule.arg))
            return
        else:
            stmt.i_typedef.i_is_unused = False

    if stmt.i_typedef is not None:
        typedef_type = stmt.i_typedef.search_one('type')
        if typedef_type is not None and hasattr(typedef_type, 'i_type_spec'):
            # copy since we modify the typespec's definition
            stmt.i_type_spec = copy.copy(typedef_type.i_type_spec)
            if stmt.i_type_spec is not None:
                stmt.i_type_spec.definition = ('at ' +
                                               str(stmt.i_typedef.pos) +
                                               ' ')

    if stmt.i_type_spec is None:
        # an error has been added already; skip further validation
        return

    # check the fraction-digits - only applicable when the type is the builtin
    # decimal64
    frac = stmt.search_one('fraction-digits')
    if frac is not None and stmt.arg != 'decimal64':
        err_add(ctx.errors, frac.pos, 'BAD_RESTRICTION', 'fraction_digits')
    elif stmt.arg == 'decimal64' and frac is None:
        err_add(ctx.errors, stmt.pos, 'MISSING_TYPE_SPEC_1',
                ('decimal64', 'fraction-digits'))
    elif stmt.arg == 'decimal64' and frac.is_grammatically_valid:
        stmt.i_is_derived = True
        stmt.i_type_spec = types.Decimal64TypeSpec(frac)

    # check the range restriction
    stmt.i_ranges = []
    rangestmt = stmt.search_one('range')
    if rangestmt is not None:
        if 'range' not in stmt.i_type_spec.restrictions():
            err_add(ctx.errors, rangestmt.pos, 'BAD_RESTRICTION', 'range')
        else:
            stmt.i_is_derived = True
            ranges_spec = types.validate_range_expr(ctx.errors, rangestmt, stmt)
            if ranges_spec is not None:
                stmt.i_ranges = ranges_spec[0]
                stmt.i_type_spec = types.RangeTypeSpec(stmt.i_type_spec,
                                                       ranges_spec)

    # check the length restriction
    stmt.i_lengths = []
    length = stmt.search_one('length')
    if (length is not None and
        'length' not in stmt.i_type_spec.restrictions()):
        err_add(ctx.errors, length.pos, 'BAD_RESTRICTION', 'length')
    elif length is not None:
        stmt.i_is_derived = True
        lengths_spec = types.validate_length_expr(ctx.errors, length, stmt)
        if lengths_spec is not None:
            stmt.i_lengths = lengths_spec[0]
            stmt.i_type_spec = types.LengthTypeSpec(stmt.i_type_spec,
                                                    lengths_spec)

    # check the pattern restrictions
    patterns = stmt.search('pattern')
    if (patterns and
        'pattern' not in stmt.i_type_spec.restrictions()):
        err_add(ctx.errors, patterns[0].pos, 'BAD_RESTRICTION', 'pattern')
    elif patterns:
        stmt.i_is_derived = True
        pattern_specs = [types.validate_pattern_expr(ctx.errors, p)
                         for p in patterns]
        if None not in pattern_specs:
            # all patterns valid
            stmt.i_type_spec = types.PatternTypeSpec(stmt.i_type_spec,
                                                     pattern_specs)

    # check the path restriction
    path = stmt.search_one('path')
    if path is not None and stmt.arg != 'leafref':
        err_add(ctx.errors, path.pos, 'BAD_RESTRICTION', 'path')
    elif stmt.arg == 'leafref' and path is None:
        err_add(ctx.errors, stmt.pos, 'MISSING_TYPE_SPEC_1',
                ('leafref', 'path'))
    elif path is not None:
        stmt.i_is_derived = True
        if path.is_grammatically_valid is True:
            path_spec = types.validate_path_expr(ctx.errors, path)
            if path_spec is not None:
                stmt.i_type_spec = types.PathTypeSpec(stmt.i_type_spec,
                                                      path_spec, path, path.pos)
                stmt.i_type_spec.i_source_stmt = stmt

    # check the base restriction
    bases = stmt.search('base')
    if bases and stmt.arg != 'identityref':
        err_add(ctx.errors, bases[0].pos, 'BAD_RESTRICTION', 'base')
    elif len(bases) > 1 and stmt.i_module.i_version == '1':
        err_add(ctx.errors, bases[1].pos, 'UNEXPECTED_KEYWORD', 'base')
    elif stmt.arg == 'identityref' and not bases:
        err_add(ctx.errors, stmt.pos, 'MISSING_TYPE_SPEC',
                ('identityref', 'base'))
    else:
        idbases = []
        for base in bases:
            v_type_base(ctx, base)
            if base.i_identity is not None:
                idbases.append(base)
        if len(idbases) > 0:
            stmt.i_is_derived = True
            stmt.i_type_spec = types.IdentityrefTypeSpec(idbases)

    # check the require-instance restriction
    req_inst = stmt.search_one('require-instance')
    if (req_inst is not None and
        'require-instance' not in stmt.i_type_spec.restrictions()):
        err_add(ctx.errors, req_inst.pos, 'BAD_RESTRICTION', 'require-instance')
    if (req_inst is not None and stmt.i_type_spec.name == 'leafref' and
        stmt.i_module.i_version == '1'):
        err_add(ctx.errors, req_inst.pos, 'BAD_RESTRICTION', 'require-instance')
    if req_inst is not None:
        stmt.i_type_spec.require_instance = req_inst.arg == 'true'

    # check the enums - only applicable when the type is the builtin
    # enumeration type in YANG version 1, and for derived enumerations in 1.1
    enums = stmt.search('enum')
    if (enums and
        ('enum' not in stmt.i_type_spec.restrictions() or
         stmt.i_module.i_version == '1' and stmt.arg != 'enumeration')):
        err_add(ctx.errors, enums[0].pos, 'BAD_RESTRICTION', 'enum')
    elif stmt.arg == 'enumeration' and not enums:
        err_add(ctx.errors, stmt.pos, 'MISSING_TYPE_SPEC',
                ('enumeration', 'enum'))
    elif enums:
        stmt.i_is_derived = True

        enum_spec = types.validate_enums(ctx.errors, enums, stmt)
        if enum_spec is not None:
            stmt.i_type_spec = types.EnumTypeSpec(stmt.i_type_spec,
                                                  enum_spec)

    # check the bits - only applicable when the type is the builtin
    # bits type in YANG version 1, and for derived bits in 1.1
    bits = stmt.search('bit')
    if (bits and
        ('bit' not in stmt.i_type_spec.restrictions() or
         stmt.i_module.i_version == '1' and stmt.arg != 'bits')):
        err_add(ctx.errors, bits[0].pos, 'BAD_RESTRICTION', 'bit')
    elif stmt.arg == 'bits' and not bits:
        err_add(ctx.errors, stmt.pos, 'MISSING_TYPE_SPEC',
                ('bits', 'bit'))
    elif bits:
        stmt.i_is_derived = True
        bit_spec = types.validate_bits(ctx.errors, bits, stmt)
        if bit_spec is not None:
            stmt.i_type_spec = types.BitTypeSpec(stmt.i_type_spec,
                                                 bit_spec)

    # check the union types
    membertypes = stmt.search('type')
    if membertypes and stmt.arg != 'union':
        err_add(ctx.errors, membertypes[0].pos, 'BAD_RESTRICTION', 'union')
    elif not membertypes and stmt.arg == 'union':
        err_add(ctx.errors, stmt.pos, 'MISSING_TYPE_SPEC',
                ('union', 'type'))
    elif membertypes:
        stmt.i_is_derived = True
        for t in membertypes:
            if t.is_grammatically_valid is True:
                v_type_type(ctx, t)
        stmt.i_type_spec = types.UnionTypeSpec(membertypes)
        if stmt.i_module.i_version == '1':
            t = has_type(stmt, ['empty', 'leafref'])
            if t is not None:
                err_add(ctx.errors, stmt.pos, 'BAD_TYPE_IN_UNION',
                        (t.arg, t.pos))
                return False

def v_check_if_feature(ctx, type, defval):
    for s in type.substmts:
        if defval == s.arg:
            feat = s.search_one('if-feature')
            if feat is not None:
                err_add(ctx.errors, feat.pos, 'DEFAULT_AND_IFFEATURE', ())
            return

def v_check_default(ctx, cur_type, def_value):
    if def_value is None:
        return
    if cur_type.arg in types.yang_type_specs.keys():
        if cur_type.arg == 'enumeration':
            v_check_if_feature(ctx, cur_type, def_value)
        elif cur_type.arg == 'bits':
            for b in def_value:
                v_check_if_feature(ctx, cur_type, b)
        return
    else:
        if cur_type.i_typedef is not None:
            new_type = cur_type.i_typedef.search_one('type')
            v_check_default(ctx, new_type, def_value)

def v_type_leaf(ctx, stmt):
    stmt.i_default = None
    stmt.i_default_str = ""
    if _v_type_common_leaf(ctx, stmt) is False:
        return
    # check if we have a default value
    default = stmt.search_one('default')
    type_ = stmt.search_one('type')
    if default is not None and type_.i_type_spec is not None :
        defval = type_.i_type_spec.str_to_val(ctx.errors,
                                              default.pos,
                                              default.arg,
                                              stmt.i_module)
        stmt.i_default = defval
        stmt.i_default_str = default.arg
        if defval is not None:
            type_.i_type_spec.validate(ctx.errors, default.pos,
                                       defval, stmt.i_module,
                                       ' for the default value')
    elif (default is None and
          type_.i_typedef is not None and
          getattr(type_.i_typedef, 'i_default', None) is not None):
        stmt.i_default = type_.i_typedef.i_default
        stmt.i_default_str = type_.i_typedef.i_default_str
        # validate the type's default value with our new restrictions
        if type_.i_type_spec is not None:
            type_.i_type_spec.validate(ctx.errors, stmt.pos,
                                       stmt.i_default, stmt.i_module,
                                       ' for the default  value')

    v_check_default(ctx, type_, stmt.i_default)

    if default is not None:
        m = stmt.search_one('mandatory')
        if m is not None and m.arg == 'true':
            err_add(ctx.errors, stmt.pos, 'DEFAULT_AND_MANDATORY', ())
            return False

def v_type_leaf_list(ctx, stmt):
    stmt.i_default = []
    if _v_type_common_leaf(ctx, stmt) is False:
        return
    # check if we have default values
    type_ = stmt.search_one('type')
    for default in stmt.search('default'):
        if type_.i_type_spec is not None :
            defval = type_.i_type_spec.str_to_val(ctx.errors,
                                                  default.pos,
                                                  default.arg,
                                                  stmt.i_module)
            if defval is not None:
                stmt.i_default.append(defval)
                type_.i_type_spec.validate(ctx.errors, default.pos,
                                           defval, stmt.i_module,
                                           ' for the default value')

    min_value = stmt.search_one('min-elements')
    max_value = stmt.search_one('max-elements')

    if (stmt.i_default and min_value is not None
            and min_value.arg.isnumeric() and int(min_value.arg) > 0):
        d = stmt.search_one('default')
        err_add(ctx.errors, d.pos, 'DEFAULT_AND_MIN_ELEMENTS', ())
        return False

    if (min_value is not None and min_value.arg.isnumeric()
            and max_value is not None and max_value.arg.isnumeric()):
        if int(min_value.arg) > int(max_value.arg):
            err_add(ctx.errors, min_value.pos, 'MAX_ELEMENTS_AND_MIN_ELEMENTS', ())
            return False

    if (not stmt.i_default
        and type_.i_typedef is not None
        and getattr(type_.i_typedef, 'i_default', None) is not None):

        stmt.i_default.append(type_.i_typedef.i_default)
        # validate the type's default value with our new restrictions
        if type_.i_type_spec is not None:
            type_.i_type_spec.validate(ctx.errors, stmt.pos,
                                       type_.i_typedef.i_default,
                                       stmt.i_module,
                                       ' for the default  value')
    for s in stmt.i_default:
        v_check_default(ctx, type_, s)

def _v_type_common_leaf(ctx, stmt):
    stmt.i_leafref = None # path_type_spec
    stmt.i_leafref_ptr = None # pointer to the leaf the leafref refer to
    stmt.i_leafref_expanded = False
    # check our type
    type_ = stmt.search_one('type')
    if type_ is None or type_.is_grammatically_valid is False:
        # error is already reported by grammar check
        return False

    # ensure our type is validated
    v_type_type(ctx, type_)

    if type_.i_typedef:
        chk_status(ctx, stmt, type_.i_typedef)

    # keep track of our leafref
    type_spec = type_.i_type_spec
    if isinstance(type_spec, types.PathTypeSpec):
        stmt.i_leafref = type_spec

def chk_status(ctx, x, y):
    if x.top.i_modulename != y.top.i_modulename:
        return
    def status(s):
        stat = s.search_one('status')
        if stat is not None:
            return stat.arg
        return 'current'
    xstatus = status(x)
    ystatus = status(y)
    if ((xstatus == 'current' and ystatus != 'current') or
        (xstatus == 'deprecated' and ystatus == 'obsolete')):
        err_add(ctx.errors, x.pos, 'BAD_STATUS_REFERENCE',
                (x.keyword, xstatus, y.keyword, ystatus))

def v_type_grouping(ctx, stmt):
    if hasattr(stmt, 'i_is_validated'):
        if stmt.i_is_validated is True:
            # this grouping has already been validated
            return True
        elif stmt.i_is_validated == 'in_progress':
            err_add(ctx.errors, stmt.pos,
                    'CIRCULAR_DEPENDENCY', ('grouping', stmt.arg) )
            return False

    stmt.i_is_validated = 'in_progress'
    stmt.i_is_unused = True
    stmt.i_has_i_children = True

    name = stmt.arg
    if stmt.parent.parent is not None:
        # non-top-level grouping; check if it is already defined
        pgrouping = search_grouping(stmt.parent.parent, name)
        if pgrouping is not None:
            err_add(ctx.errors, stmt.pos, 'GROUPING_ALREADY_DEFINED',
                    (name, pgrouping.pos))

    # search for circular grouping definitions
    def validate_uses(s):
        if (s.keyword == "uses"
            and getattr(s, 'is_grammatically_valid', None) is True):
            v_type_uses(ctx, s, no_error_report=True)

    iterate_stmt(stmt, validate_uses)

    stmt.i_is_validated = True
    return True

def v_type_uses(ctx, stmt, no_error_report=False):
    # Find the grouping
    prefix, name = util.split_identifier(stmt.arg)

    if hasattr(stmt, 'i_grouping'):
        if stmt.i_grouping is None and no_error_report is False:
            if prefix is None or stmt.i_module.i_prefix == prefix:
                # check local groupings
                pmodule = stmt.i_module
            else:
                pmodule = util.prefix_to_module(
                    stmt.i_module, prefix, stmt.pos, ctx.errors)
                if pmodule is None:
                    return
            err_add(ctx.errors, stmt.pos,
                    'GROUPING_NOT_FOUND', (name, pmodule.arg))
        return

    stmt.i_grouping = None
    if prefix is None or stmt.i_module.i_prefix == prefix:
        # check local groupings
        pmodule = stmt.i_module
        i_grouping = search_grouping(stmt, name)
        if i_grouping is not None and i_grouping.is_grammatically_valid is True:
            if v_type_grouping(ctx, i_grouping) is True:
                stmt.i_grouping = i_grouping

    else:
        # this is a prefixed name, check the imported modules
        pmodule = util.prefix_to_module(
            stmt.i_module, prefix, stmt.pos, ctx.errors)
        if pmodule is None:
            return
        stmt.i_grouping = search_grouping(pmodule, name)
    if stmt.i_grouping is None and no_error_report is False:
        err_add(ctx.errors, stmt.pos,
                'GROUPING_NOT_FOUND', (name, pmodule.arg))
    if stmt.i_grouping is not None:
        chk_status(ctx, stmt, stmt.i_grouping)
        stmt.i_grouping.i_is_unused = False

def v_type_augment(ctx, stmt):
    # make sure the _v_i_children phases run over this one
    stmt.i_has_i_children = True
    if stmt.parent.keyword == 'uses' and stmt.arg.startswith("/"):
        stmt.i_target_node = None
        err_add(ctx.errors, stmt.pos, 'BAD_VALUE',
                (stmt.arg, "descendant-node-id"))
    elif stmt.parent.keyword != 'uses' and not stmt.arg.startswith("/"):
        stmt.i_target_node = None
        err_add(ctx.errors, stmt.pos, 'BAD_VALUE',
                (stmt.arg, "absolute-node-id"))

def v_type_extension(ctx, stmt):
    """verify that the extension matches the extension definition"""
    (modulename, identifier) = stmt.keyword
    revision = stmt.i_extension_revision
    module = modulename_to_module(stmt.i_module, modulename, revision)
    if module is None:
        return
    if identifier not in module.i_extensions:
        if module.i_modulename == stmt.i_orig_module.i_modulename:
            # extension defined in current submodule
            if identifier not in stmt.i_orig_module.i_extensions:
                err_add(ctx.errors, stmt.pos, 'EXTENSION_NOT_DEFINED',
                        (identifier, module.arg))
                return
            else:
                stmt.i_extension = stmt.i_orig_module.i_extensions[identifier]
        else:
            err_add(ctx.errors, stmt.pos, 'EXTENSION_NOT_DEFINED',
                    (identifier, module.arg))
            return
    else:
        stmt.i_extension = module.i_extensions[identifier]
    ext_arg = stmt.i_extension.search_one('argument')
    if stmt.arg is not None and ext_arg is None:
        err_add(ctx.errors, stmt.pos, 'EXTENSION_ARGUMENT_PRESENT',
                identifier)
    elif stmt.arg is None and ext_arg is not None:
        err_add(ctx.errors, stmt.pos, 'EXTENSION_NO_ARGUMENT_PRESENT',
                identifier)

def v_type_feature(ctx, stmt):
    if hasattr(stmt, 'i_is_validated'):
        if stmt.i_is_validated is True:
            # this feature has already been validated
            return
        elif stmt.i_is_validated == 'in_progress':
            err_add(ctx.errors, stmt.pos,
                    'CIRCULAR_DEPENDENCY', ('feature', stmt.arg) )
            return

    stmt.i_is_validated = 'in_progress'

    name = stmt.arg

    # search for circular feature definitions
    def validate_if_feature(s):
        if s.keyword == "if-feature":
            v_type_if_feature(ctx, s, no_error_report=True)
    iterate_stmt(stmt, validate_if_feature)

    stmt.i_is_validated = True

def v_type_if_feature(ctx, stmt, no_error_report=False):
    """verify that the referenced feature exists."""
    # Verify the argument type
    expr = syntax.parse_if_feature_expr(stmt.arg)
    if stmt.i_module.i_version == '1':
        # version 1 allows only a single value as if-feature
        if not isinstance(expr, str):
            err_add(ctx.errors, stmt.pos,
                    'BAD_VALUE', (stmt.arg, 'identifier-ref'))
            return

    def eval_if_feature(expr):
        if isinstance(expr, str):
            return has_feature(expr)
        else:
            op, op1, op2 = expr
            if op == 'not':
                return not eval_if_feature(op1)
            elif op == 'and':
                return eval_if_feature(op1) and eval_if_feature(op2)
            elif op == 'or':
                return eval_if_feature(op1) or eval_if_feature(op2)

    def has_feature(name):
        # raises Abort if the feature is not defined
        # returns True if we compile with the feature
        # returns False if we compile without the feature
        found = None
        prefix, name = util.split_identifier(name)
        if prefix is None or stmt.i_module.i_prefix == prefix:
            # check local features
            pmodule = stmt.i_module
        else:
            # this is a prefixed name, check the imported modules
            pmodule = util.prefix_to_module(
                stmt.i_module, prefix, stmt.pos, ctx.errors)
            if pmodule is None:
                raise Abort
        if name in pmodule.i_features:
            f = pmodule.i_features[name]
            if prefix is None and not is_submodule_included(stmt, f):
                pass
            else:
                found = pmodule.i_features[name]
                chk_status(ctx, stmt.parent, found)
                v_type_feature(ctx, found)
                if pmodule.i_modulename in ctx.features:
                    if name not in ctx.features[pmodule.i_modulename]:
                        return False
                if pmodule.i_modulename in ctx.exclude_features:
                    if name in ctx.exclude_features[pmodule.i_modulename]:
                        return False

        if found is None and no_error_report is False:
            err_add(ctx.errors, stmt.pos,
                    'FEATURE_NOT_FOUND', (name, pmodule.arg))
            raise Abort
        return found is not None

    # Evaluate the if-feature expression, and verify that all
    # referenced features exist.
    try:
        if eval_if_feature(expr) is False:
            stmt.parent.i_not_implemented = True
    except Abort:
        pass

def v_type_status(ctx, stmt):
    if ctx.max_status is not None:
        order = ['current', 'deprecated', 'obsolete']
        if order.index(stmt.arg) > order.index(ctx.max_status):
            stmt.parent.i_not_implemented = True

def v_type_identity(ctx, stmt):
    if hasattr(stmt, 'i_is_validated'):
        if stmt.i_is_validated is True:
            # this identity has already been validated
            return
        elif stmt.i_is_validated == 'in_progress':
            err_add(ctx.errors, stmt.pos,
                    'CIRCULAR_DEPENDENCY', ('identity', stmt.arg) )
            return

    stmt.i_is_validated = 'in_progress'

    name = stmt.arg

    if stmt.i_module.i_version == '1':
        bases = stmt.search('base')
        if len(bases) > 1:
            err_add(ctx.errors, bases[1].pos, 'UNEXPECTED_KEYWORD', 'base')
    # search for circular identity definitions
    def validate_base(s):
        if s.keyword == "base":
            v_type_base(ctx, s, no_error_report=True)
    iterate_stmt(stmt, validate_base)

    stmt.i_is_validated = True

def v_type_base(ctx, stmt, no_error_report=False):
    """verify that the referenced identity exists."""
    # Find the identity
    stmt.i_identity = None
    prefix, name = util.split_identifier(stmt.arg)

    if prefix is None or stmt.i_module.i_prefix == prefix:
        # check local identities
        pmodule = stmt.i_module
    else:
        # this is a prefixed name, check the imported modules
        pmodule = util.prefix_to_module(
            stmt.i_module, prefix, stmt.pos, ctx.errors)
        if pmodule is None:
            return
    if name in pmodule.i_identities:
        i = pmodule.i_identities[name]
        if prefix is None and not is_submodule_included(stmt, i):
            pass
        else:
            stmt.i_identity = i
            v_type_identity(ctx, stmt.i_identity)
    if stmt.i_identity is None and no_error_report is False:
        err_add(ctx.errors, stmt.pos,
                'IDENTITY_NOT_FOUND', (name, pmodule.arg))

def v_type_must(ctx, stmt):
    # check syntax only here
    xpath.v_xpath(ctx, stmt, None)

def v_type_when(ctx, stmt):
    # check syntax only here
    xpath.v_xpath(ctx, stmt, None)

### Expand phases

def v_expand_1_children(ctx, stmt):
    if getattr(stmt, 'is_grammatically_valid', None) is False:
        return
    if stmt.keyword == 'grouping' and hasattr(stmt, "i_expanded"):
        # already expanded
        return
    elif stmt.keyword == 'choice':
        shorthands = ['leaf', 'leaf-list', 'container', 'list', 'choice',
                      'anyxml', 'anydata']
        for s in stmt.substmts:
            if s.keyword in shorthands:
                # create an artifical case node for the shorthand
                create_new_case(ctx, stmt, s)
            elif s.keyword == 'case':
                stmt.i_children.append(s)
                v_expand_1_children(ctx, s)
        return
    elif stmt.keyword in ('action', 'rpc'):
        input_ = stmt.search_one('input')
        if input_ is None:
            # create the implicitly defined input node
            input_ = new_statement(stmt.top, stmt, stmt.pos, 'input', 'input')
            v_init_stmt(ctx, input_)
            input_.i_children = []
            input_.i_module = stmt.i_module
            stmt.i_children.append(input_)
        else:
            # check that there is at least one data definition statement
            found = False
            for c in input_.substmts:
                if c.keyword in data_definition_keywords:
                    found = True
            if not found:
                err_add(ctx.errors, input_.pos,'EXPECTED_DATA_DEF', 'input')

        output = stmt.search_one('output')
        if output is None:
            # create the implicitly defined output node
            output = new_statement(stmt.top, stmt, stmt.pos, 'output', 'output')
            v_init_stmt(ctx, output)
            output.i_children = []
            output.i_module = stmt.i_module
            stmt.i_children.append(output)
        else:
            # check that there is at least one data definition statement
            found = False
            for c in output.substmts:
                if c.keyword in data_definition_keywords:
                    found = True
            if not found:
                err_add(ctx.errors, output.pos,'EXPECTED_DATA_DEF', 'output')

    if stmt.keyword == 'grouping':
        stmt.i_expanded = False
    for s in stmt.substmts:
        if s.keyword in ['input', 'output'] and hasattr(stmt, 'i_children'):
            # must create a copy of the statement which sets the argument,
            # since we need to keep the original stmt hierarchy valid
            news = s.copy(nocopy=['type','typedef','grouping'])
            news.i_groupings = s.i_groupings
            news.i_typedefs = s.i_typedefs
            news.arg = news.keyword
            stmt.i_children.append(news)
            v_expand_1_children(ctx, news)
        elif (s.keyword == 'uses'
              and getattr(s, 'is_grammatically_valid', None)):
            v_expand_1_uses(ctx, s)
            for a in s.search('augment'):
                v_expand_1_children(ctx, a)
            v_inherit_properties(ctx, stmt)
            for a in s.search('augment'):
                v_expand_2_augment(ctx, a)
            for a in s.search('augment'):
                v_expand_3_augment(ctx, a)

        elif s.keyword in data_keywords and hasattr(stmt, 'i_children'):
            stmt.i_children.append(s)
            v_expand_1_children(ctx, s)
        elif s.keyword in _keyword_with_children:
            v_expand_1_children(ctx, s)

    if stmt.keyword == 'grouping':
        stmt.i_expanded = True

    # do not recurse - recursion already done above
    return 'continue'

def v_default(ctx, target, default):
    type_ = target.search_one('type')
    if (type_ is not None
        and getattr(type_, 'i_type_spec', None) is not None):

        defval = type_.i_type_spec.str_to_val(ctx.errors,
                                              default.pos,
                                              default.arg,
                                              target.i_module)
        target.i_default = defval
        target.i_default_str = default.arg
        if defval is not None:
            type_.i_type_spec.validate(ctx.errors, default.pos,
                                       defval, target.i_module,
                                       ' for the default value')

def v_expand_1_uses(ctx, stmt):
    if getattr(stmt, 'is_grammatically_valid', None) is False:
        return

    if not hasattr(stmt, 'i_grouping') or stmt.i_grouping is None:
        return

    # possibly expand any uses within the grouping
    v_expand_1_children(ctx, stmt.i_grouping)

    def find_refine_node(refinement):
        # parse the path into a list of two-tuples of (prefix,identifier)
        pstr = '/' + refinement.arg
        path = [(m[1], m[2]) \
                    for m in syntax.re_schema_node_id_part.findall(pstr)]
        node = stmt.parent
        # recurse down the path
        for prefix, identifier in path:
            module = util.prefix_to_module(
                stmt.i_module, prefix, refinement.pos, ctx.errors)
            if hasattr(node, 'i_children'):
                if module is None:
                    return None
                child = search_child(node.i_children, module.i_modulename,
                                     identifier)
                if child is None:
                    err_add(ctx.errors, refinement.pos, 'NODE_NOT_FOUND',
                            (module.i_modulename, identifier))
                    return None
                node = child
            else:
                err_add(ctx.errors, refinement.pos, 'BAD_NODE_IN_REFINE',
                        (module.i_modulename, identifier))
                return None
        return node

    def replace_from_refinement(target, refinement, keyword, valid_keywords,
                                v_fun=None):
        """allow `keyword` as a refinement in `valid_keywords`"""
        new = refinement.search_one(keyword)
        if new is not None and target.keyword in valid_keywords:
            old = target.search_one(keyword)
            if old is not None:
                target.substmts.remove(old)
            if v_fun is not None:
                v_fun(ctx, target, new)
            new.parent = target
            target.substmts.append(new)
        elif new is not None:
            err_add(ctx.errors, refinement.pos, 'BAD_REFINEMENT',
                    (target.keyword, target.i_module.i_modulename,
                     target.arg, keyword))
            return

    def merge_from_refinement(target, refinement, keyword, valid_keywords,
                              v_fun=None):
        """allow `keyword` as a refinement in `valid_keywords`"""
        for new in refinement.search(keyword):
            if target.keyword in valid_keywords:
                if v_fun is not None:
                    v_fun(ctx, target, new)
                new.parent = target
                target.substmts.append(new)
            else:
                err_add(ctx.errors, refinement.pos, 'BAD_REFINEMENT',
                        (target.keyword, target.i_module.i_modulename,
                         target.arg, keyword))
                return

    (_arg_type, subspec) = grammar.stmt_map[stmt.parent.keyword]
    subspec = grammar.flatten_spec(subspec)
    whens = list(stmt.search('when'))
    for s in whens:
        s.i_origin = 'uses'
    iffeatures = list(stmt.search('if-feature'))
    # first, copy the grouping into our i_children
    for g in stmt.i_grouping.i_children:
        if util.keysearch(g.keyword, 0, subspec) is None:
            err_add(ctx.errors, stmt.pos, 'UNEXPECTED_KEYWORD_USES',
                    (util.keyword_to_str(g.raw_keyword),
                     util.keyword_to_str(stmt.parent.raw_keyword),
                     g.pos))
            continue

        # don't copy the type since it cannot be modified anyway.
        # not copying the type also works better for some plugins that
        # generate output from the i_children list.
        def post_copy(old, new):
            # inline the definition into our module
            new.i_module = stmt.i_module
            if hasattr(old, 'i_not_implemented'):
                new.i_not_implemented = old.i_not_implemented
            new.i_children = []
            new.i_uniques = []
            new.pos.uses_pos = stmt.pos
            # build the i_children list of pointers
            if hasattr(old, 'i_children'):
                for x in old.i_children:
                    # check if this i_child is a pointer to a substmt
                    if x in old.substmts:
                        # if so, create an equivalent pointer
                        idx = old.substmts.index(x)
                        new.i_children.append(new.substmts[idx])
                    else:
                        # otherwise, copy the i_child
                        newx = x.copy(new, stmt,
                                      nocopy=['type','uses', 'unique',
                                              'if-feature',
                                              'typedef','grouping'],
                                      copyf=post_copy)
                        new.i_children.append(newx)
        newg = g.copy(stmt.parent, stmt,
                      nocopy=['type','uses','unique', 'if-feature',
                              'typedef','grouping'],
                      copyf=post_copy)
        for s in whens:
            news = s.copy(newg)
            newg.substmts.append(news)
        for s in iffeatures:
            news = s.copy(newg)
            newg.substmts.append(news)

        if hasattr(stmt, 'i_not_implemented'):
            newg.i_not_implemented = stmt.i_not_implemented

        stmt.parent.i_children.append(newg)

    # copy plain statements from the grouping
    for s in stmt.i_grouping.substmts:
        if s.keyword in _copy_uses_keywords:
            news = s.copy()
            news.parent = stmt.parent
            stmt.parent.substmts.append(news)

    # keep track of already refined nodes
    refined = {}
    # then apply all refinements
    for refinement in stmt.search('refine'):
        target = find_refine_node(refinement)
        if target is None:
            continue
        if target in refined:
            err_add(ctx.errors, refinement.pos, 'MULTIPLE_REFINE',
                    (target.arg, refined[target]))
            continue
        refined[target] = refinement.pos

        for keyword, valid_keywords0, merge, v_fun in _refinements:
            valid_keywords = filter_valid_keywords(valid_keywords0, stmt)
            if merge:
                merge_from_refinement(target, refinement, keyword,
                                      valid_keywords, v_fun)
            else:
                replace_from_refinement(target, refinement, keyword,
                                        valid_keywords, v_fun)

        # replace all vendor-specific statements
        for s in refinement.substmts:
            if util.is_prefixed(s.keyword):
                old = target.search_one(s.keyword)
                if old is not None:
                    target.substmts.remove(old)
                s.parent = target
                target.substmts.append(s)
    v_inherit_properties(ctx, stmt.parent)
    for ch in refined:
        # after refinement, we need to re-run some of the tests, e.g. if
        # the refinement added a default value it needs to be checked.
        v_recheck_target(ctx, ch, reference=False)

def filter_valid_keywords(keywords, stmt):
    res = []
    for i in keywords:
        if isinstance(i, tuple):
            if stmt.i_module.i_version != '1':
                res.append(i[1])
            else:
                res.append(i)
        else:
            res.append(i)
    return res

def v_inherit_properties(ctx, stmt, child=None):
    def walk(s, config_value, allow_explicit):
        cfg = s.search_one('config')
        if cfg is not None:
            if config_value is None and not allow_explicit:
                err_add(ctx.errors, cfg.pos, 'CONFIG_IGNORED', ())
            elif cfg.arg == 'true' and config_value is False:
                err_add(ctx.errors, cfg.pos, 'INVALID_CONFIG', ())
            elif cfg.arg == 'true':
                config_value = True
            elif cfg.arg == 'false':
                config_value = False
        s.i_config = config_value
        if getattr(s, 'is_grammatically_valid', None) is False:
            return
        if s.keyword in _keyword_with_children:
            for ch in s.search('grouping'):
                walk(ch, None, True)
            for ch in s.search('grouping'):
                walk(ch, None, True)
            for ch in s.i_children:
                if ch.keyword in _keywords_with_no_explicit_config:
                    walk(ch, None, False)
                else:
                    if hasattr(ch, 'i_uses'):
                        walk(ch, config_value, True)
                    else:
                        walk(ch, config_value, allow_explicit)

    if child is not None:
        walk(child, stmt.i_config, True)
        return

    for s in stmt.search('grouping'):
        walk(s, None, True)
    for s in stmt.search('augment'):
        if hasattr(stmt,'i_config'):
            walk(s, stmt.i_config, True)
        else:
            walk(s, True, True)
    for s in stmt.i_children:
        if s.keyword in _keywords_with_no_explicit_config:
            walk(s, None, False)
        else:
            walk(s, True, True)

    # do not recurse in this phase
    return 'continue'

def v_expand_2_augment(ctx, stmt):
    """
    First pass of two-pass augment expansion algorithm.

    First observation: since we validate each imported module, all
    nodes that are augmented by other modules already exist.  For each
    node in the path to the target node, if it does not exist, it
    might get created by an augment later in this module.  This only
    applies to nodes defined in our namespace (since all other modules
    already are validated).  For each such node, we add a temporary
    Statement instance, and store a pointer to it.  If we find such a
    temporary node in the nodes we add, we replace it with our real
    node, and delete it from the list of temporary nodes created.
    When we're done with all augment statements, the list of temporary
    nodes should be empty, otherwise it is an error.
    """
    if hasattr(stmt, 'i_target_node'):
        # already expanded
        return
    stmt.i_target_node = find_target_node(ctx, stmt, is_augment=True)

    if stmt.i_target_node is None:
        return
    if not hasattr(stmt.i_target_node, 'i_children'):
        err_add(ctx.errors, stmt.pos, 'BAD_NODE_IN_AUGMENT',
                (stmt.i_target_node.i_module.arg, stmt.i_target_node.arg,
                 stmt.i_target_node.keyword))
        return

    def chk_mandatory(s):
        if s.keyword == 'leaf':
            m = s.search_one('mandatory')
            if m is not None and m.arg == 'true':
                err_add(ctx.errors, m.pos, 'AUGMENT_MANDATORY', s.arg)
        elif s.keyword == 'list' or s.keyword == 'leaf-list':
            m = s.search_one('min-elements')
            if m is not None and m.arg.isnumeric() and int(m.arg) >= 1:
                err_add(ctx.errors, m.pos, 'AUGMENT_MANDATORY', s.arg)
        elif s.keyword == 'container':
            p = s.search_one('presence')
            if p is None:
                for sc in s.i_children:
                    chk_mandatory(sc)
    # if we're augmenting another module, make sure we're not
    # trying to add a mandatory node
    if stmt.i_module.i_modulename != stmt.i_target_node.i_module.i_modulename:
        # 1.1 allows mandatory augment if the augment is conditional
        if stmt.i_module.i_version == '1' or stmt.search_one('when') is None:
            for sc in stmt.i_children:
                chk_mandatory(sc)

    # copy the expanded children into the target node
    def add_tmp_children(node, tmp_children):
        for tmp in tmp_children:
            ch = search_child(node.i_children, stmt.i_module.i_modulename,
                              tmp.arg)
            if ch is not None:
                del ch.i_module.i_undefined_augment_nodes[tmp]
                if not hasattr(ch, 'i_children'):
                    err_add(ctx.errors, tmp.pos, 'BAD_NODE_IN_AUGMENT',
                            (stmt.i_module.i_modulename, ch.arg,
                             ch.keyword))
                    raise Abort
                add_tmp_children(ch, tmp.i_children)
            elif node.keyword == 'choice' and tmp.keyword != 'case':
                # create an artifical case node for the shorthand
                new_case = create_new_case(ctx, node, tmp, expand=False)
                new_case.parent = node
            else:
                node.i_children.append(tmp)
                tmp.parent = node

    def is_expected_keyword(parent, child):
        if parent.keyword == '__tmp_augment__':
            return True
        if parent.keyword == 'choice' and child.keyword != 'case':
            (_arg_type, subspec) = grammar.stmt_map['case']
        else:
            (_arg_type, subspec) = grammar.stmt_map[parent.keyword]
        subspec = grammar.flatten_spec(subspec)
        if util.keysearch(child.keyword, 0, subspec) is None:
            return False
        return True

    for c in stmt.i_children:
        c.i_augment = stmt
        if hasattr(stmt, 'i_not_implemented'):
            c.i_not_implemented = stmt.i_not_implemented

        ch = search_child(stmt.i_target_node.i_children,
                          stmt.i_module.i_modulename, c.arg)
        if ch is not None:
            if ch.keyword == '__tmp_augment__':
                # replace this node with the proper one,
                # and also do this recursively
                del ch.i_module.i_undefined_augment_nodes[ch]
                if not hasattr(c, 'i_children'):
                    err_add(ctx.errors, stmt.pos, 'BAD_NODE_IN_AUGMENT',
                            (stmt.i_module.i_modulename, c.arg,
                             c.keyword))
                    return
                idx = stmt.i_target_node.i_children.index(ch)
                stmt.i_target_node.i_children[idx] = c
                c.parent = stmt.i_target_node
                try:
                    add_tmp_children(c, ch.i_children)
                except Abort:
                    return
            else:
                err_add(ctx.errors, c.pos, 'DUPLICATE_CHILD_NAME',
                        (stmt.arg, stmt.pos, c.arg, ch.pos))
                return
        elif stmt.i_target_node.keyword == 'choice' and c.keyword != 'case':
            if is_expected_keyword(stmt.i_target_node, c) is True:
                # create an artificial case node for the shorthand
                new_case = create_new_case(ctx, stmt.i_target_node, c,
                                           expand=False)
                new_case.parent = stmt.i_target_node
                v_inherit_properties(ctx, stmt.i_target_node, new_case)
            else:
                err_add(ctx.errors, stmt.pos, 'UNEXPECTED_KEYWORD_AUGMENT',
                        (util.keyword_to_str(c.raw_keyword),
                         util.keyword_to_str(stmt.i_target_node.raw_keyword),
                         c.pos))
        elif (stmt.i_target_node.keyword not in
              ('container', 'list', 'choice', 'case', 'input',
                  'output', 'notification', '__tmp_augment__')):
            nd = stmt.i_target_node
            err_add(ctx.errors, stmt.pos, 'BAD_TARGET_NODE',
                    (nd.i_module.i_modulename, nd.arg, nd.keyword))
        else:
            if is_expected_keyword(stmt.i_target_node, c) is True:
                stmt.i_target_node.i_children.append(c)
                c.parent = stmt.i_target_node
                v_inherit_properties(ctx, stmt.i_target_node, c)
            else:
                err_add(ctx.errors, stmt.pos, 'UNEXPECTED_KEYWORD_AUGMENT',
                        (util.keyword_to_str(c.raw_keyword),
                         util.keyword_to_str(stmt.i_target_node.raw_keyword),
                         c.pos))
    for s in stmt.substmts:
        if s.keyword in _copy_augment_keywords:
            stmt.i_target_node.substmts.append(s)
            s.parent = stmt.i_target_node

def v_expand_3_augment(ctx, stmt):
    """
    Second pass of two-pass augment expansion algorithm.

    Find the (possibly expanded) target nodes again.  The reason for
    this is that stmt.i_target_node may point to a __tmp_augment__ node.
    """
    stmt.i_target_node = find_target_node(ctx, stmt, is_augment=True)

def create_new_case(ctx, choice, child, expand=True):
    new_case = new_statement(child.top, choice, child.pos, 'case', child.arg)
    v_init_stmt(ctx, new_case)
    child.parent = new_case
    new_case.i_children = [child]
    new_case.i_module = child.i_module
    s = child.search_one('status')
    if s is not None:
        new_case.substmts.append(s)
    choice.i_children.append(new_case)
    if expand:
        v_expand_1_children(ctx, child)
    return new_case

### Unique name check phase

def v_unique_name_defintions(ctx, stmt):
    """Make sure that all top-level definitions in a module are unique"""
    defs = [('typedef', 'TYPE_ALREADY_DEFINED', stmt.i_typedefs),
            ('grouping', 'GROUPING_ALREADY_DEFINED', stmt.i_groupings)]
    def f(s):
        for keyword, errcode, stmtdefs in defs:
            if s.keyword == keyword and s.arg in stmtdefs:
                err_add(ctx.errors, stmtdefs[s.arg].pos,
                        errcode, (s.arg, s.pos))

    for i in stmt.search('include'):
        submodulename = i.arg
        subm = ctx.get_module(submodulename)
        if subm is not None:
            for s in subm.substmts:
                for ss in s.substmts:
                    iterate_stmt(ss, f)


def v_unique_name_children(ctx, stmt):
    """Make sure that each child of stmt has a unique name"""

    def sort_pos(p1, p2):
        if p1.line < p2.line:
            return p1, p2
        else:
            return p2, p1

    children = {}

    def check(c):
        key = c.i_module.i_modulename, c.arg
        if key in children:
            dup = children[key]
            minpos, maxpos = sort_pos(c.pos, dup.pos)
            pos = chk_uses_pos(c, maxpos)
            err_add(ctx.errors, pos,
                    'DUPLICATE_CHILD_NAME', (stmt.arg, stmt.pos, c.arg, minpos))
        else:
            children[key] = c
        # also check all data nodes in the cases
        if c.keyword == 'choice':
            for case in c.i_children:
                for cc in case.i_children:
                    check(cc)

    for c in stmt.i_children:
        check(c)

def v_unique_name_leaf_list(ctx, stmt):
    """Make sure config true leaf-lists do nothave duplicate defaults"""

    if not stmt.i_config:
        return
    seen = []
    for defval in stmt.i_default:
        if defval in seen:
            err_add(ctx.errors, stmt.pos, 'DUPLICATE_DEFAULT', (defval))
        else:
            seen.append(defval)

### Reference phase

def v_reference_action(ctx, stmt):
    def iterate(s):
        if s.parent is None:
            return
        else:
            parent = s.parent
            if parent.keyword == "list":
                key = parent.search_one('key')
                if (parent.i_config is False and key is None
                    and parent.i_module.i_version == '1.1'):
                    err_add(ctx.errors, stmt.pos, 'BAD_ANCESTOR',
                            (stmt.keyword))
                    return
            elif parent.keyword in ("rpc", "action", "notification"):
                err_add(ctx.errors, stmt.pos, 'BAD_ANCESTOR2',
                        (stmt.keyword, parent.keyword))
                return
            iterate(parent)

    iterate(stmt)

def v_reference_revision(ctx, stmt):
    if not ctx.verify_revision_history:
        return
    if not stmt.i_module.i_is_primary_module:
        return
    if stmt.arg == stmt.parent.i_latest_revision:
        return
    # search_module adds an error if the module isn't found
    ctx.search_module(stmt.pos, stmt.i_module.arg, stmt.arg)

def v_reference_list(ctx, stmt):
    if getattr(stmt, 'i_is_validated', None) is True:
        return
    stmt.i_is_validated = True

    def v_key():
        key = stmt.search_one('key')
        if stmt.i_config is True and key is None:
            if hasattr(stmt, 'i_uses_pos'):
                err_add(ctx.errors, stmt.i_uses_pos, 'NEED_KEY_USES',
                        (stmt.pos))
            else:
                err_add(ctx.errors, stmt.pos, 'NEED_KEY', ())

        stmt.i_key = []
        if key is not None and key.arg is not None:
            found = []
            for x in key.arg.split():
                if x == '':
                    continue
                prefix, name = util.split_identifier(x)
                if prefix is not None and prefix != stmt.i_module.i_prefix:
                    err_add(ctx.errors, key.pos, 'BAD_KEY', x)
                    return
                ptr = util.attrsearch(name, 'arg', stmt.i_children)
                if x in found:
                    err_add(ctx.errors, key.pos, 'DUPLICATE_KEY', x)
                    return
                elif ptr is None or ptr.keyword != 'leaf':
                    err_add(ctx.errors, key.pos, 'BAD_KEY', x)
                    return
                chk_status(ctx, ptr.parent, ptr)
                type_ = ptr.search_one('type')
                if stmt.i_module.i_version == '1':
                    if type_ is not None:
                        t = has_type(type_, ['empty'])
                        if t is not None:
                            err_add(ctx.errors, key.pos, 'BAD_TYPE_IN_KEY',
                                    (t.arg, x))
                            return
                default = ptr.search_one('default')
                if default is not None:
                    err_add(ctx.errors, default.pos, 'KEY_HAS_DEFAULT', ())
                for substmt in ['if-feature', 'when']:
                    s = ptr.search_one(substmt)
                    if s is not None:
                        err_add(ctx.errors, s.pos, 'KEY_BAD_SUBSTMT', substmt)
                mandatory = ptr.search_one('mandatory')
                if mandatory is not None and mandatory.arg == 'false':
                    err_add(ctx.errors, mandatory.pos,
                            'KEY_HAS_MANDATORY_FALSE', ())

                if ptr.i_config != stmt.i_config:
                    cfg = ptr.search_one('config')
                    if cfg is not None:
                        pos = cfg.pos
                    else:
                        pos = ptr.pos
                    err_add(ctx.errors, pos, 'KEY_BAD_CONFIG', name)

                stmt.i_key.append(ptr)
                ptr.i_is_key = True
                found.append(x)

    def v_unique():
        # i_unique is a list of entries, one entry per 'unique' stmt.
        # each entry is a list of pointers to the nodes that make up
        # the unique constraint.
        stmt.i_unique = []
        uniques = stmt.search('unique')
        for u in uniques:
            found = []
            uconfig = None
            for expr in u.arg.split():
                if expr == '':
                    continue
                ptr = stmt
                for x in expr.split('/'):
                    if x == '':
                        continue
                    if ptr.keyword not in ['container', 'list',
                                           'choice', 'case']:
                        err_add(ctx.errors, u.pos, 'BAD_UNIQUE_PART', x)
                        return
                    prefix, name = util.split_identifier(x)
                    if prefix is not None and prefix != stmt.i_module.i_prefix:
                            err_add(ctx.errors, u.pos, 'BAD_UNIQUE_PART', x)
                            return
                    ptr = util.attrsearch(name, 'arg', ptr.i_children)
                    if ptr is None:
                        err_add(ctx.errors, u.pos, 'BAD_UNIQUE_PART', x)
                        return
                    if ptr.keyword == 'list':
                        err_add(ctx.errors, u.pos, 'BAD_UNIQUE_PART_LIST', x)
                if ptr is None or ptr.keyword != 'leaf':
                    err_add(ctx.errors, u.pos, 'BAD_UNIQUE', expr)
                    return
                if ptr in found:
                    err_add(ctx.errors, u.pos, 'DUPLICATE_UNIQUE', expr)
                if hasattr(ptr, 'i_config'):
                    if uconfig is None:
                        uconfig = ptr.i_config
                    elif uconfig != ptr.i_config:
                        err_add(ctx.errors, u.pos, 'BAD_UNIQUE_CONFIG', expr)
                        return
                # add this unique statement to ptr's list of unique conditions
                # it is part of.
                ptr.i_uniques.append(u)
                found.append(ptr)
            if not found:
                err_add(ctx.errors, u.pos, 'BAD_UNIQUE', u.arg)
                return
            # check if all leafs in the unique statements are keys
            if len(list(stmt.i_key)) > 0:
                key = list(stmt.i_key)
                for f in found:
                    if f in key:
                        key.remove(f)
                if len(key) == 0:
                    err_add(ctx.errors, u.pos, 'UNIQUE_IS_KEY', ())
            u.i_leafs = found
            stmt.i_unique.append((u, found))

    def v_max_min_elements():
        min_value = stmt.search_one('min-elements')
        max_value = stmt.search_one('max-elements')
        if (min_value is not None and min_value.arg.isnumeric()
                and max_value is not None and max_value.arg.isnumeric()):
            if int(min_value.arg) > int(max_value.arg):
                err_add(ctx.errors, min_value.pos,
                        'MAX_ELEMENTS_AND_MIN_ELEMENTS', ())
                return

    v_key()
    v_unique()
    v_max_min_elements()

def v_reference_choice(ctx, stmt):
    """Make sure that the default case exists"""
    d = stmt.search_one('default')
    if d is not None:
        m = stmt.search_one('mandatory')
        if m is not None and m.arg == 'true':
            err_add(ctx.errors, stmt.pos, 'DEFAULT_AND_MANDATORY', ())
        ptr = util.attrsearch(d.arg, 'arg', stmt.i_children)
        if ptr is None:
            err_add(ctx.errors, d.pos, 'DEFAULT_CASE_NOT_FOUND', d.arg)
        else:
            # make sure there are no mandatory nodes in the default case
            def chk_no_defaults(s):
                for c in s.i_children:
                    if c.keyword in ('leaf', 'anydata', 'anyxml', 'choice'):
                        m = c.search_one('mandatory')
                        if m is not None and m.arg == 'true':
                            err_add(ctx.errors, c.pos,
                                    'MANDATORY_NODE_IN_DEFAULT_CASE', ())
                    elif c.keyword in ('list', 'leaf-list'):
                        m = c.search_one('min-elements')
                        if (m is not None and m.arg.isnumeric() and
                            int(m.arg) > 0):
                            err_add(ctx.errors, c.pos,
                                    'MANDATORY_NODE_IN_DEFAULT_CASE', ())
                    elif c.keyword == 'container':
                        p = c.search_one('presence')
                        if p is None or p.arg == 'false':
                            chk_no_defaults(c)
            chk_no_defaults(ptr)

def v_reference_leaf_leafref(ctx, stmt):
    """Verify that all leafrefs in a leaf or leaf-list have correct path"""

    if (getattr(stmt, 'i_leafref', None) is not None
        and stmt.i_leafref_expanded is False):

        path_type_spec = stmt.i_leafref
        not_req_inst = not path_type_spec.require_instance
        x = validate_leafref_path(ctx, stmt,
                                  path_type_spec.path_spec,
                                  path_type_spec.path_,
                                  accept_non_config_target=not_req_inst)
        if x is None:
            return
        ptr, expanded_path, path_list = x
        path_type_spec.i_target_node = ptr
        path_type_spec.i_expanded_path = expanded_path
        path_type_spec.i_path_list = path_list
        stmt.i_leafref_expanded = True
        if ptr is not None:
            chk_status(ctx, stmt, ptr)
            if (not hasattr(stmt, 'i_not_implemented') and
                hasattr(ptr, 'i_not_implemented')):
                err_add(ctx.errors, stmt.pos,
                        'LEAFREF_TO_NOT_IMPLEMENTED', ())
            stmt.i_leafref_ptr = (ptr, path_type_spec.pos)

def v_reference_must(ctx, stmt):
    v_xpath(ctx, stmt)

def v_reference_when(ctx, stmt):
    v_xpath(ctx, stmt)

def v_xpath(ctx, stmt):
    if stmt.parent.keyword == 'augment':
        node = stmt.parent.i_target_node
    elif stmt.parent.keyword == 'deviate':
        node = stmt.parent.parent.i_target_node
    elif (getattr(stmt, 'i_origin', None) == 'uses' and
          stmt.parent.keyword != 'choice'):
        node = util.data_node_up(stmt.parent)
    else:
        node = stmt.parent
    if node is not None:
        node = util.closest_ancestor_data_node(node)
    xpath.v_xpath(ctx, stmt, node)

def v_reference_deviation(ctx, stmt):
    stmt.i_target_node = find_target_node(ctx, stmt)

def v_reference_deviate(ctx, stmt):
    def search_children_config_true(node, target):
        # the target node's config is set to 'false', and the node underneath it
        # cannot have 'config' is 'true'
        if node.keyword in data_definition_keywords:
            c_config = node.search_one('config')
            if c_config is not None and c_config.arg == 'true':
                err_add(ctx.errors, c.pos, 'INVALID_CONFIG', ())
                return True
        else:
            return False
        if node is None or not hasattr(node, 'i_children'):
            return False
        else:
            for child in node.i_children:
                if search_children_config_true(child, target):
                    return True
            return False

    def inherit_parent_i_config(node, value):
        if node is None or not hasattr(node, 'i_children'):
            return
        else:
            for child in node.i_children:
                if child.keyword in data_definition_keywords:
                    config = child.search_one('config')
                    if config is None:
                        child.i_config = value
                inherit_parent_i_config(child, value)

    if stmt.parent.i_target_node is None:
        # this is set in v_reference_deviation above.  if none
        # is found, an error has already been reported.
        return
    t = stmt.parent.i_target_node
    if stmt.arg == 'not-supported':
        # make sure there are no sibling deviate statements
        siblings = stmt.parent.search('deviate')
        idx = siblings.index(stmt)
        del siblings[idx]
        if len(siblings) > 0:
            err_add(ctx.errors, siblings[0].pos,
                    'BAD_DEVIATE_WITH_NOT_SUPPORTED', ())
            return
        if t.parent.keyword == 'list' and t in t.parent.i_key:
            err_add(ctx.errors, stmt.pos, 'BAD_DEVIATE_KEY',
                    (t.i_module.arg, t.arg))
            return
        t.i_this_not_supported = True
        if not hasattr(t.parent, 'i_not_supported'):
            t.parent.i_not_supported = []
        t.parent.i_not_supported.append(t)
        # delete the node from i_children
        idx = t.parent.i_children.index(t)
        del t.parent.i_children[idx]
        # find and delete the node from substmts
        # it may not be there if it is a shorthand case
        t1 = t.parent.search_one(t.keyword, t.arg, t.parent.substmts)
        if t1 is not None:
            idx = t.parent.substmts.index(t1)
            del t.parent.substmts[idx]
    elif stmt.arg == 'add':
        for c in stmt.substmts:
            if c.keyword == '_comment':
                continue
            if c.keyword == 'config' and hasattr(t, 'i_config'):
                # config is special: since it is an inherited property
                # with a default, all nodes has a config property. this
                # means that it can only be placed.
                err_add(ctx.errors, c.pos, 'BAD_DEVIATE_ADD',
                        (c.keyword, t.i_module.arg, t.arg))

            elif c.keyword in _singleton_keywords:
                if t.search_one(c.keyword) is not None:
                    err_add(ctx.errors, c.pos, 'BAD_DEVIATE_ADD',
                            (c.keyword, t.i_module.arg, t.arg))
                elif t.keyword not in _valid_deviations[c.keyword]:
                    err_add(ctx.errors, c.pos, 'BAD_DEVIATE_TYPE',
                            c.keyword)
                else:
                    t.substmts.append(c)
            else:
                # multi-valued keyword; just add the statement if it is valid
                if c.keyword not in _valid_deviations:
                    if util.is_prefixed(c.keyword):
                        (prefix, name) = c.keyword
                        pmodule = util.prefix_to_module(
                            c.i_module, prefix, c.pos, [])
                        if (pmodule is not None and
                            pmodule.modulename in grammar.extension_modules):
                            err_add(ctx.errors, c.pos, 'BAD_DEVIATE_TYPE',
                                    c.keyword)

                        else:
                            # unknown module, let's assume the extension can
                            # be deviated
                            t.substmts.append(c)
                    else:
                        err_add(ctx.errors, c.pos, 'BAD_DEVIATE_TYPE',
                                c.keyword)
                elif t.keyword not in _valid_deviations[c.keyword]:
                    err_add(ctx.errors, c.pos, 'BAD_DEVIATE_TYPE',
                            c.keyword)

                else:
                    t.substmts.append(c)
    elif stmt.arg == 'replace':
        for c in stmt.substmts:
            if c.keyword == '_comment':
                continue
            if c.keyword == 'config' and hasattr(t, 'i_config'):
                # config is special: since it is an inherited property
                # with a default, all nodes has a config property.
                # first, save the old property, and then set the property...

                old = t.search_one(c.keyword)
                if old is not None:
                    negc = copy.copy(old)
                    old.arg = c.arg
                else:
                    # use the t.i_config when the target node doesn't exist
                    # config statement.
                    negc = copy.copy(c)
                    negc.arg = 'true' if t.i_config is True else 'false'

                if c.arg == 'true':
                    if negc.arg != c.arg:
                        if (t.parent is not None
                            and t.parent.i_config is False):
                            # recover the target node config value when it
                            # doesn't meet the spec
                            if old is not None:
                                old.arg = negc.arg
                            err_add(ctx.errors, c.pos,
                                    'INVALID_CONFIG', ())
                            continue
                        else:
                            t.i_config = True
                else:
                    if search_children_config_true(t, t):
                        # recover the target node config value when it
                        # doesn't meet the spec
                        if old is not None:
                            old.arg = negc.arg
                        continue
                    else:
                        t.i_config = False
                        inherit_parent_i_config(t, t.i_config)

            if c.keyword in _singleton_keywords:
                old = t.search_one(c.keyword)
            else:
                old = t.search_one(c.keyword, c.arg)
            if old is None:
                if c.keyword != 'config':
                    err_add(ctx.errors, c.pos, 'BAD_DEVIATE_REP',
                            (c.keyword, t.i_module.arg, t.arg))
            else:
                idx = t.substmts.index(old)
                del t.substmts[idx]
                if (c.keyword == 'type'
                    and c.i_typedef is not None
                    and ':' not in c.arg
                    and t.i_module.i_prefix != c.i_module.i_prefix):

                    c.arg = c.i_module.i_prefix + ':' + c.arg
                t.substmts.append(c)
    else: # delete
        for c in stmt.substmts:
            if c.keyword == '_comment':
                continue
            if c.keyword in _singleton_keywords:
                if c.keyword in _deviate_delete_singleton_keywords:
                    old = t.search_one(c.keyword)
                else:
                    err_add(ctx.errors, c.pos, 'BAD_DEVIATE_DEL2',
                            (c.keyword, t.i_module.arg, t.arg))
                    continue
            else:
                old = t.search_one(c.keyword, c.arg)
            if old is None:
                err_add(ctx.errors, c.pos, 'BAD_DEVIATE_DEL',
                        (c.keyword, t.i_module.arg, t.arg))
            else:
                idx = t.substmts.index(old)
                del t.substmts[idx]

# after deviation, we need to re-run some of the tests, e.g. if
# the deviation added a default value it needs to be checked.
def v_reference_deviation_4(ctx, stmt):
    if getattr(stmt, 'i_target_node', None) is None:
        # this is set in v_reference_deviation above.  if none
        # is found, an error has already been reported.
        return
    if hasattr(stmt.i_target_node, 'i_this_not_supported'):
        return
    v_recheck_target(ctx, stmt.i_target_node, reference=True)

def v_recheck_target(ctx, t, reference=False):
    for s in t.search('if-feature'):
        v_type_if_feature(ctx, s)
    if reference:
        for s in t.search('must'):
            v_reference_must(ctx, s)
        for s in t.search('when'):
            v_reference_when(ctx, s)
    if t.keyword == 'leaf':
        v_type_leaf(ctx, t)
        if reference:
            v_reference_leaf_leafref(ctx, t)
    elif t.keyword == 'leaf-list':
        v_type_leaf_list(ctx, t)
        if reference:
            v_reference_leaf_leafref(ctx, t)
    elif t.keyword == 'list':
        t.i_is_validated = False
        if reference:
            v_reference_list(ctx, t)

### Unused definitions phase

def v_unused_module(ctx, module):
    for prefix in module.i_unused_prefixes:
        import_ = module.i_unused_prefixes[prefix]
        err_add(ctx.errors, import_.pos,
                'UNUSED_IMPORT', import_.arg)

    for s in module.i_undefined_augment_nodes:
        err_add(ctx.errors, s.pos, 'NODE_NOT_FOUND',
                (s.i_module.arg, s.arg))

def v_unused_typedef(ctx, stmt):
    if stmt.parent.parent is not None:
        # this is a locally scoped typedef
        if stmt.i_is_unused is True:
            err_add(ctx.errors, stmt.pos,
                    'UNUSED_TYPEDEF', stmt.arg)

def v_unused_grouping(ctx, stmt):
    if stmt.parent.parent is not None:
        # this is a locallay scoped grouping
        if stmt.i_is_unused is True:
            err_add(ctx.errors, stmt.pos,
                    'UNUSED_GROUPING', stmt.arg)

### Strict phase

### Utility functions

def chk_uses_pos(s, pos):
    return getattr(s, 'i_uses_pos', pos)

def modulename_to_module(module, modulename, revision=None):
    if modulename == module.arg:
        return module
    # even if the prefix is defined, the module might not be
    # loaded; the load might have failed
    return module.i_ctx.get_module(modulename, revision)

def has_type(typestmt, names):
    """Return type with name if `type` has name as one of its base types,
    and name is in the `names` list.  otherwise, return None."""
    if typestmt.arg in names:
        return typestmt
    for t in typestmt.search('type'): # check all union's member types
        r = has_type(t, names)
        if r is not None:
            return r
    typedef = getattr(typestmt, 'i_typedef', None)
    if typedef is not None and getattr(typedef, 'i_is_circular', None) is False:
        t = typedef.search_one('type')
        if t is not None:
            return has_type(t, names)
    return None

def is_mandatory_node(stmt):
    if getattr(stmt, 'i_config', True) is False:
        return False
    if stmt.keyword in ('leaf', 'choice', 'anyxml', 'anydata'):
        m = stmt.search_one('mandatory')
        if m is not None and m.arg == 'true':
            return True
    elif stmt.keyword in ('list', 'leaf-list'):
        m = stmt.search_one('min-elements')
        if m is not None and m.arg.isnumeric() and int(m.arg) > 0:
            return True
    elif stmt.keyword == 'container':
        p = stmt.search_one('presence')
        if p is None:
            for c in stmt.i_children:
                if is_mandatory_node(c):
                    return True
    return False

def search_child(children, modulename, identifier):
    for child in children:
        if child.arg == identifier:
            if (child.i_module.i_modulename == modulename or
                child.i_module.i_including_modulename is not None and
                child.i_module.i_including_modulename == modulename):
                return child
    return None

def search_data_node(children, modulename, identifier, last_skipped = None):
    return util.search_data_node(children, modulename, identifier, last_skipped)

def search_typedef(stmt, name):
    """Search for a typedef in scope
    First search the hierarchy, then the module and its submodules."""
    orig_stmt = stmt
    mod = stmt.i_orig_module
    while stmt is not None:
        if name in stmt.i_typedefs:
            t = stmt.i_typedefs[name]
            if (mod is not None and
                mod != t.i_orig_module and
                t.i_orig_module.keyword == 'submodule'):
                # make sure this submodule is included
                if mod.search_one('include', t.i_orig_module.arg) is None:
                    return None
            return t
        stmt = stmt.parent
    # if the original statement isn't the original module, try the module
    # (this covers the case where the statement has been re-parented)
    if mod is not None and orig_stmt is not mod:
        return search_typedef(mod, name)
    return None

def search_grouping(stmt, name):
    """Search for a grouping in scope
    First search the hierarchy, then the module and its submodules."""
    orig_stmt = stmt
    mod = stmt.i_orig_module
    while stmt is not None:
        if name in stmt.i_groupings:
            g = stmt.i_groupings[name]
            if (mod is not None and
                mod != g.i_orig_module and
                g.i_orig_module.keyword == 'submodule'):
                # make sure this submodule is included
                if mod.search_one('include', g.i_orig_module.arg) is None:
                    return None
            return g
        stmt = stmt.parent
    # if the original statement isn't the original module, try the module
    # (this covers the case where the statement has been re-parented)
    if mod is not None and orig_stmt is not mod:
        return search_grouping(mod, name)
    return None

def search_data_keyword_child(children, modulename, identifier):
    for child in children:
        if (child.arg == identifier and
            child.i_module.i_modulename == modulename and
            child.keyword in data_keywords):
            return child
    return None

def find_target_node(ctx, stmt, is_augment=False):
    if getattr(stmt, 'is_grammatically_valid', None) is False:
        return None
    if stmt.arg.startswith("/"):
        is_absolute = True
        arg = stmt.arg
    else:
        is_absolute = False
        arg = "/" + stmt.arg # to make node_id_part below work
    # parse the path into a list of two-tuples of (prefix,identifier)
    path = [(m[1], m[2]) for m in syntax.re_schema_node_id_part.findall(arg)]
    # find the module of the first node in the path
    (prefix, identifier) = path[0]
    module = util.prefix_to_module(stmt.i_module, prefix, stmt.pos, ctx.errors)
    if module is None:
        # error is reported by prefix_to_module
        return None

    if stmt.parent.keyword in ('module', 'submodule') or is_absolute:
        # find the first node
        node = search_child(module.i_children, module.i_modulename, identifier)
        if not is_submodule_included(stmt, node):
            node = None
        if node is None:
            err_add(ctx.errors, stmt.pos, 'NODE_NOT_FOUND',
                    (module.i_modulename, identifier))
            return None
    else:
        chs = [c for c in stmt.parent.parent.i_children
               if stmt.parent in getattr(c, 'i_uses', [])[:1]]
        node = search_child(chs, module.i_modulename, identifier)
        if not is_submodule_included(stmt, node):
            node = None
        if node is None:
            err_add(ctx.errors, stmt.pos, 'NODE_NOT_FOUND',
                    (module.i_modulename, identifier))
            return None

    # then recurse down the path
    for prefix, identifier in path[1:]:
        if hasattr(node, 'i_children'):
            module = util.prefix_to_module(
                stmt.i_module, prefix, stmt.pos, ctx.errors)
            if module is None:
                return None
            child = search_child(node.i_children, module.i_modulename,
                                 identifier)
            if child is None and module == stmt.i_module and is_augment:
                # create a temporary statement
                child = Statement(node.top, node, stmt.pos, '__tmp_augment__',
                                  identifier)
                v_init_stmt(ctx, child)
                child.i_module = module
                child.i_children = []
                child.i_config = node.i_config
                node.i_children.append(child)
                # keep track of this temporary statement
                stmt.i_module.i_undefined_augment_nodes[child] = child
            elif child is None:
                err_add(ctx.errors, stmt.pos, 'NODE_NOT_FOUND',
                        (module.i_modulename, identifier))
                return None
            node = child
        else:
            err_add(ctx.errors, stmt.pos, 'NODE_NOT_FOUND',
                    (module.i_modulename, identifier))
            return None
    return node

def iterate_stmt(stmt, f):
    def _iterate(stmt):
        res = f(stmt)
        if res == 'stop':
            raise Abort
        elif res == 'continue':
            pass
        else:
            # default is to recurse
            for s in stmt.substmts:
                _iterate(s)

    try:
        _iterate(stmt)
    except Abort:
        pass

def iterate_i_children(stmt, f):
    def _iterate(stmt):
        res = f(stmt)
        if res == 'stop':
            raise Abort
        elif res == 'continue':
            pass
        else:
            # default is to recurse
            if hasattr(stmt, 'i_children'):
                for s in stmt.i_children:
                    _iterate(s)

    try:
        _iterate(stmt)
    except Abort:
        pass

def is_submodule_included(src, tgt):
    """Check that the tgt's submodule is included by src, if they belong
    to the same module."""
    if tgt is None or not hasattr(tgt, 'i_orig_module'):
        return True
    if (tgt.i_orig_module.keyword == 'submodule' and
        src.i_orig_module != tgt.i_orig_module and
        src.i_orig_module.i_modulename == tgt.i_orig_module.i_modulename):
        if (src.i_orig_module.keyword == 'submodule' and
            src.i_orig_module.i_version != '1'):
            # In 1.1, if both src and tgt are submodules, src doesn't
            # have to include tgt
            return True
        if src.i_orig_module.search_one('include',
                                        tgt.i_orig_module.arg) is None:
            return False
    return True

def validate_leafref_path(ctx, stmt, path_spec, path,
                          accept_non_leaf_target=False,
                          accept_non_config_target=False):
    """Return the leaf that the path points to and the expanded path arg,
    or None on error."""

    pathpos = path.pos

    # Unprefixed paths in typedefs in YANG 1 were underspecified.  In
    # YANG 1.1 the semantics are defined.  The code below is compatible
    # with old pyang for YANG 1 modules.

    # If an un-prefixed identifier is found, it defaults to the
    # module where the path is defined, except if found within
    # a grouping, in which case it defaults to the module where the
    # grouping is used.
    if (path.parent.parent is not None and
        path.parent.parent.keyword == 'typedef'):
        if path.i_module.i_version == '1':
            local_module = path.i_module
        else:
            local_module = stmt.i_module
    elif stmt.keyword == 'module':
        local_module = stmt
    else:
        local_module = stmt.i_module
    if stmt.keyword == 'typedef':
        in_typedef = True
    else:
        in_typedef = False

    def find_identifier(identifier):
        if util.is_prefixed(identifier):
            (prefix, name) = identifier
            if (path.i_module.keyword == 'submodule' and
                prefix == local_module.i_prefix and
                local_module is not None):
                pmodule = util.prefix_to_module(
                    local_module, prefix, stmt.pos, ctx.errors)
            else:
                pmodule = util.prefix_to_module(
                    path.i_module, prefix, stmt.pos, ctx.errors)
            if pmodule is None:
                raise NotFound
            return (pmodule, name)
        elif in_typedef and stmt.i_module.i_version != '1':
            raise Abort
        else: # local identifier
            return (local_module, identifier)

    def is_identifier(x):
        if util.is_local(x):
            return True
        if isinstance(x, tuple) and len(x) == 2:
            return True
        return False

    def is_predicate(x):
        if isinstance(x, tuple) and len(x) == 4 and x[0] == 'predicate':
            return True
        return False

    def follow_path(ptr, up, dn):
        path_list = []
        last_skipped = None
        if up == -1: # absolute path
            (pmodule, name) = find_identifier(dn[0])
            ptr = search_child(pmodule.i_children, pmodule.i_modulename, name)
            if not is_submodule_included(path, ptr):
                ptr = None
            if ptr is None:
                # check all our submodules
                for inc in path.i_orig_module.search('include'):
                    submod = ctx.get_module(inc.arg)
                    if submod is not None:
                        ptr = search_child(submod.i_children,
                                           submod.arg, name)
                        if ptr is not None:
                            break
                if ptr is None:
                    err_add(ctx.errors, pathpos, 'LEAFREF_IDENTIFIER_NOT_FOUND',
                            (pmodule.arg, name, stmt.arg, stmt.pos))
                    raise NotFound
            path_list.append(('dn', ptr))
            dn = dn[1:]
        else:
            while up > 0:
                if ptr is None:
                    err_add(ctx.errors, pathpos, 'LEAFREF_TOO_MANY_UP',
                            (stmt.arg, stmt.pos))
                    raise NotFound
                if ptr.keyword in ('augment', 'grouping', 'typedef'):
                    # don't check the path here - check in the expanded tree
                    raise Abort
                ptr = ptr.parent
                if ptr is None:
                    err_add(ctx.errors, pathpos, 'LEAFREF_TOO_MANY_UP',
                            (stmt.arg, stmt.pos))
                    raise NotFound
                while ptr.keyword in ['case', 'choice', 'input', 'output']:
                    if ptr.keyword in ['input', 'output']:
                        last_skipped = ptr.keyword
                    ptr = ptr.parent
                    if ptr is None:
                        err_add(ctx.errors, pathpos, 'LEAFREF_TOO_MANY_UP',
                                (stmt.arg, stmt.pos))
                        raise NotFound
                    # continue after the case, maybe also skip the choice
                if ptr is None:
                    err_add(ctx.errors, pathpos, 'LEAFREF_TOO_MANY_UP',
                            (stmt.arg, stmt.pos))
                    raise NotFound
                path_list.append(('up', ptr))
                up = up - 1
            if ptr is None: # or ptr.keyword == 'grouping':
                err_add(ctx.errors, pathpos, 'LEAFREF_TOO_MANY_UP',
                        (stmt.arg, stmt.pos))
                raise NotFound
        if ptr.keyword in ('augment', 'grouping', 'typedef'):
            # don't check the path here - check in the expanded tree
            raise Abort
        i = 0
        key_list = None
        keys = []
        while i < len(dn):
            if is_identifier(dn[i]) is True:
                (pmodule, name) = find_identifier(dn[i])
                module_name = pmodule.i_modulename
            elif ptr.keyword == 'list': # predicate on a list, good
                key_list = ptr
                keys = []
                # check each predicate
                while i < len(dn) and is_predicate(dn[i]) is True:
                    # unpack the predicate
                    (_tag, keyleaf, pup, pdn) = dn[i]
                    (pmodule, pname) = find_identifier(keyleaf)
                    # make sure the keyleaf is really a key in the list
                    pleaf = search_child(ptr.i_key, pmodule.i_modulename, pname)
                    if pleaf is None:
                        err_add(ctx.errors, pathpos, 'LEAFREF_NO_KEY',
                                (pmodule.arg, pname, stmt.arg, stmt.pos))
                        raise NotFound
                    # make sure it's not already referenced
                    if keyleaf in keys:
                        err_add(ctx.errors, pathpos, 'LEAFREF_MULTIPLE_KEYS',
                                (pmodule.arg, pname, stmt.arg, stmt.pos))
                        raise NotFound
                    keys.append((pmodule.arg, pname))
                    if pup == 0:
                        i = i + 1
                        break
                    # check what this predicate refers to; make sure it's
                    # another leaf; either of type leafref to keyleaf, OR same
                    # type as the keyleaf
                    (xkey_list, x_key, xleaf, _x) = follow_path(stmt, pup, pdn)
                    stmt.i_derefed_leaf = xleaf
                    if xleaf.keyword != 'leaf':
                        err_add(ctx.errors, pathpos,
                                'LEAFREF_BAD_PREDICATE_PTR',
                                (pmodule.arg, pname, xleaf.arg, xleaf.pos))
                        raise NotFound
                    i = i + 1
                continue
            else:
                err_add(ctx.errors, pathpos, 'LEAFREF_BAD_PREDICATE',
                        (ptr.i_module.arg, ptr.arg, stmt.arg, stmt.pos))
                raise NotFound
            if ptr.keyword in _keyword_with_children:
                ptr = search_data_node(ptr.i_children, module_name, name,
                                       last_skipped)
                if not is_submodule_included(path, ptr):
                    ptr = None
                if ptr is None:
                    err_add(ctx.errors, pathpos, 'LEAFREF_IDENTIFIER_NOT_FOUND',
                            (module_name, name, stmt.arg, stmt.pos))
                    raise NotFound
            else:
                err_add(ctx.errors, pathpos, 'LEAFREF_IDENTIFIER_BAD_NODE',
                        (module_name, name, stmt.arg, stmt.pos,
                         util.keyword_to_str(ptr.keyword)))
                raise NotFound
            path_list.append(('dn', ptr))
            i = i + 1
        return (key_list, keys, ptr, path_list)

    try:
        if path_spec is None: # e.g. invalid path
            return None
        (up, dn, derefup, derefdn) = path_spec
        if derefup > 0:
            # first follow the deref
            (key_list, keys, ptr, _x) = follow_path(stmt, derefup, derefdn)
            if ptr.keyword != 'leaf':
                err_add(ctx.errors, pathpos, 'LEAFREF_DEREF_NOT_LEAFREF',
                        (ptr.arg, ptr.pos))
                return None
            if ptr.i_leafref is None:
                err_add(ctx.errors, pathpos, 'LEAFREF_DEREF_NOT_LEAFREF',
                        (ptr.arg, ptr.pos))
                return None
            stmt.i_derefed_leaf = ptr
            # make sure the referenced leaf is expanded
            if ptr.i_leafref_expanded is False:
                v_reference_leaf_leafref(ctx, ptr)
            if ptr.i_leafref_ptr is None:
                return None
            (derefed_stmt, _pos) = ptr.i_leafref_ptr
            if derefed_stmt is None:
                # FIXME: what is this??
                return None
            if not hasattr(derefed_stmt, 'i_is_key'):
                # it follows from the YANG spec which says that predicates
                # are only used for constraining keys that the derefed stmt
                # must be a key
                err_add(ctx.errors, pathpos, 'LEAFREF_DEREF_NOT_KEY',
                        (ptr.arg, ptr.pos,
                         derefed_stmt.arg, derefed_stmt.pos))
                return None
            # split ptr's leafref path into two parts:
            # '/a/b/c' --> '/a/b', 'c'
            m = re_path.match(ptr.i_leafref.i_expanded_path)
            s1 = m.group(1)
            s2 = m.group(2)
            # split the deref path into two parts:
            # 'deref(../a)/b' --> '../a', 'b'
            m = re_deref.match(path.arg)
            d1 = m.group(1)
            d2 = m.group(2)
            expanded_path = "%s[%s = current()/%s]/%s" % \
                (s1, s2, d1, d2)
            (key_list, keys, ptr, path_list) = follow_path(derefed_stmt, up, dn)
        else:
            (key_list, keys, ptr, path_list) = follow_path(stmt, up, dn)
            expanded_path = path.arg
        # ptr is now the node that the leafref path points to
        # check that it is a leaf
        if (ptr.keyword not in ('leaf', 'leaf-list') and
            not accept_non_leaf_target):
            err_add(ctx.errors, pathpos, 'LEAFREF_NOT_LEAF',
                    (stmt.arg, stmt.pos))
            return None
        if (key_list == ptr.parent and
            (ptr.i_module.i_modulename, ptr.arg) in keys):
            err_add(ctx.errors, pathpos, 'LEAFREF_MULTIPLE_KEYS',
                    (ptr.i_module.i_modulename, ptr.arg, stmt.arg, stmt.pos))
        if (getattr(stmt, 'i_config', None) is True
            and getattr(ptr, 'i_config', None) is False
            and not accept_non_config_target):
            err_add(ctx.errors, pathpos, 'LEAFREF_BAD_CONFIG',
                    (stmt.arg, ptr.arg, ptr.pos))
        if ptr == stmt:
            err_add(ctx.errors, pathpos, 'CIRCULAR_DEPENDENCY',
                    ('leafref', path.arg))
            return None
        return ptr, expanded_path, path_list
    except NotFound:
        return None
    except Abort:
        return None

### structs used to represent a YANG module

def new_statement(top, parent, pos, keyword, arg=None):
    stmt_class = STMT_CLASS_FOR_KEYWD.get(keyword, Statement)
    return stmt_class(top, parent, pos, keyword, arg)

## Each statement in YANG is represented as an instance of Statement or
## one of its subclasses below.

class Statement(object):

    # https://docs.python.org/3/reference/datamodel.html#slots
    # Fun to see in one place just how many *possible* attributes
    # a Statement can have! Subclasses can add additional slots as needed.
    __slots__ = (
        # Baseline instance attributes, documented in __init__ below
        'top', 'parent', 'pos', 'raw_keyword', 'keyword',
        'ext_mod', 'arg', 'substmts',

        # Applicable to most (all?) Statements, widely used
        'is_grammatically_valid',    # True or False
        'i_is_validated',            # True, False, or 'in_progress'
        'i_config',                  # True or False
        'i_module',
        'i_orig_module',
        'i_main_module',

        'i_not_implemented', # if set (True) this statement is not implemented,
                             # either a false if-feature or status
                             # deprecated/obsolete

        # see v_init_has_children()
        'i_children',

        # Applicable to most (all?) statements - see v_init_stmt()
        'i_typedefs',
        'i_groupings',
        'i_uniques',

        # Only on copied Statements - see copy()
        'i_uses',
        'i_uses_pos',
        'i_uses_top',

        # YANG language extensions
        'i_extension_modulename',
        'i_extension_revision',
        'i_extension',

        # for plugins, etc.
        '__dict__',
    )

    # NOTE: don't use this function directly; instead use
    # statements.new_statement()
    def __init__(self, top, parent, pos, keyword, arg=None):
        self.top = top
        """pointer to the top-level Statement"""

        self.parent = parent
        """pointer to the parent Statement, maybe on semantics"""

        self.stmt_parent = parent
        """pointer to the parent Statement, just on statement"""

        self.pos = copy.copy(pos)
        """position in input stream, for error reporting"""
        if self.pos is not None and self.pos.top is None:
            self.pos.top = self

        self.raw_keyword = keyword
        """the name of the statement
        one of: string() | (prefix::string(), string())"""

        self.keyword = keyword
        """the name of the statement
        one of: string() | (modulename::string(), string())"""

        self.ext_mod = None
        """the name of the module where the extension is defined, if any"""

        self.arg = arg
        """the statement's argument;  a string or None"""

        self.substmts = []
        """the statement's substatements; a list of Statements"""

    def __str__(self):
        return '%s %s' % (self.keyword, self.arg)

    def __repr__(self):
        return '<pyang.%s \'%s\' at %#x>' % (self.__class__.__name__,
                                             self.__str__(), id(self))

    def internal_reset(self):
        for cls in self.__class__.mro():
            for s in getattr(cls, '__slots__', ()):
                if s.startswith('i_') and hasattr(self, s):
                    delattr(self, s)
        for s in self.substmts:
            s.internal_reset()

    def search(self, keyword, children=None, arg=None):
        """Return list of receiver's substmts with `keyword`.
        """
        if children is None:
            children = self.substmts
        return [ch for ch in children
                if ch.keyword == keyword and (arg is None or ch.arg == arg)]

    def search_one(self, keyword, arg=None, children=None):
        """Return receiver's substmt with `keyword` and optionally `arg`.
        """
        if children is None:
            children = self.substmts
        for ch in children:
            if ch.keyword == keyword and (arg is None or ch.arg == arg):
                return ch
        return None

    def copy(self, parent=None, uses=None, uses_top=True,
             nocopy=(), ignore=(), copyf=None):
        new = copy.copy(self)
        new.pos = copy.copy(new.pos)
        if uses is not None:
            if hasattr(new, 'i_uses'):
                # make a copy of i_uses before modifying it
                new.i_uses = list(new.i_uses)
                new.i_uses.insert(0, uses)
            else:
                new.i_uses = [uses]
            new.i_uses_pos = uses.pos
            new.i_uses_top = uses_top
        if parent is None:
            new.parent = self.parent
        else:
            new.parent = parent
        new.substmts = []
        for s in self.substmts:
            if s.keyword in ignore:
                pass
            elif s.keyword in nocopy:
                new.substmts.append(s)
            else:
                new.substmts.append(s.copy(new, uses, False,
                                           nocopy, ignore, copyf))
        if copyf is not None:
            copyf(self, new)
        return new

    def main_module(self):
        """Return the main module to which the receiver belongs."""
        if self.i_module.keyword == "submodule":
            return self.i_module.i_ctx.get_module(
                self.i_module.i_including_modulename)
        return self.i_module

    def pprint(self, indent='', f=None):
        """debug function"""
        if self.arg is not None:
            print(indent + util.keyword_to_str(self.keyword) + " " + self.arg)
        else:
            print(indent + util.keyword_to_str(self.keyword))
        if f is not None:
            f(self, indent)
        for x in self.substmts:
            x.pprint(indent + ' ', f)
        try:
            children = self.i_children
        except AttributeError:
            pass
        else:
            if children:
                print(indent + '--- BEGIN i_children ---')
                for child in children:
                    child.pprint(indent + ' ', f)
                print(indent + '--- END i_children ---')

class ModSubmodStatement(Statement):
    __slots__ = (
        # see v_init_module()
        'i_version',                 # Module stmt YANG version ('1', etc.)
        'i_prefix',
        'i_prefixes',
        'i_unused_prefixes',
        'i_missing_prefixes',
        'i_modulename',
        'i_features',
        'i_identities',
        'i_extensions',
        'i_including_modulename',
        'i_ctx',
        'i_undefined_augment_nodes',
        'i_is_primary_module',

        # see v_grammar_module()
        'i_latest_revision',
    )

    def __init__(self, top, parent, pos, keyword, arg=None):
        Statement.__init__(self, top, parent, pos, keyword, arg)
        self._init_i_attrs()

    def internal_reset(self):
        Statement.internal_reset(self)
        self._init_i_attrs()

    def _init_i_attrs(self):
        self.i_is_primary_module = False
        self.i_is_validated = False

    def prune(self):
        def p(n):
            if hasattr(n, 'i_children'):
                deletes = []
                for ch in n.i_children:
                    if hasattr(ch, 'i_not_implemented'):
                        deletes.append(ch)
                    else:
                        p(ch)
                if len(deletes) > 0:
                    for d in deletes:
                        idx = n.i_children.index(d)
                        del n.i_children[idx]
            for a in n.search('augment'):
                p(a)
        p(self)

class AugmentStatement(Statement):
    __slots__ = (
        # see v_type_augment()
        'i_target_node',              # Statement augmented by self
                                      # also present in DeviationStatement
        'i_has_i_children',           # also present in GroupingStatement
    )


class BaseStatement(Statement):
    __slots__ = (
        # see v_type_base()
        'i_identity',
    )


class BitStatement(Statement):
    __slots__ = (
        'i_position',
    )

class CommentStatement(Statement):
    __slots__ = (
        'i_line_end',
        'i_multi_line',
    )

class ChoiceStatement(Statement):
    __slots__ = (
        'i_augment',
    )


class ContainerStatement(Statement):
    __slots__ = (
        'i_augment',
        'i_not_supported',
        'i_this_not_supported',
    )


class DeviationStatement(Statement):
    __slots__ = (
        'i_target_node',               # Statement deviated by self
                                       # also present in AugmentStatement
    )


class EnumStatement(Statement):
    __slots__ = (
        'i_value',
    )


class GroupingStatement(Statement):
    __slots__ = (
        'i_expanded',                 # True or False, have we expanded already
        'i_has_i_children',           # also present in AugmentStatement
        'i_is_unused',
    )


class ImportStatement(Statement):
    __slots__ = (
        # see v_init_import()
        'i_is_safe_import',
    )


class LeafLeaflistStatement(Statement):
    __slots__ = (
        'i_augment',
        'i_default',                    # also in TypedefStatement
        'i_default_str',                # also in TypedefStatement
        'i_leafref',                    # also in TypedefStatement
        'i_leafref_ptr',                # also in TypedefStatement
        'i_leafref_expanded',           # also in TypedefStatement
        'i_is_key',                     # True if self is a list key
        # see follow_path()
        'i_derefed_leaf',
        'i_this_not_supported',
    )


class ListStatement(Statement):
    __slots__ = (
        'i_augment',
        'i_key',                      # List of Statements that're keys to self
        'i_unique',
        'i_not_supported',
        'i_this_not_supported',
    )


class TypeStatement(Statement):
    __slots__ = (
        # see v_type_type()
        'i_is_derived',
        'i_type_spec',
        'i_typedef',
        'i_ranges',
        'i_lengths',
    )


class TypedefStatement(Statement):
    __slots__ = (
        'i_is_circular',
        'i_is_unused',
        'i_default',                    # also in LeafLeaflistStatement
        'i_default_str',                # also in LeafLeaflistStatement
        'i_leafref',                    # also in LeafLeaflistStatement
        'i_leafref_ptr',                # also in LeafLeaflistStatement
        'i_leafref_expanded',           # also in LeafLeaflistStatement
    )


class UniqueStatement(Statement):
    __slots__ = (
        'i_leafs',
    )


class UsesStatement(Statement):
    __slots__ = (
        # see v_type_uses()
        'i_grouping',                 # "grouping" statement being used
    )


class MustStatement(Statement):
    __slots__ = (
        'i_xpath',                    # parsed xpath expression | None
    )

class WhenStatement(Statement):
    __slots__ = (
        'i_xpath',                    # parsed xpath expression | None
        'i_origin',                   # 'uses'
    )


STMT_CLASS_FOR_KEYWD = {
    'module': ModSubmodStatement,
    'submodule': ModSubmodStatement,

    'augment': AugmentStatement,
    'base': BaseStatement,
    'bit': BitStatement,
    'choice': ChoiceStatement,
    'container': ContainerStatement,
    'deviation': DeviationStatement,
    'enum': EnumStatement,
    'grouping': GroupingStatement,
    'import': ImportStatement,
    'leaf': LeafLeaflistStatement,
    'leaf-list': LeafLeaflistStatement,
    'list': ListStatement,
    'type': TypeStatement,
    'typedef': TypedefStatement,
    'unique': UniqueStatement,
    'uses': UsesStatement,
    'must': MustStatement,
    'when': WhenStatement,
    '_comment': CommentStatement,
    # all other keywords can use generic Statement class
}

def print_tree(stmt, substmts=True, i_children=True, indent=0):
    istr = "  "
    print("%s%s %s      %s %s" % (indent * istr, stmt.keyword,
                                  stmt.arg, stmt, stmt.parent))
    if substmts and stmt.substmts:
        print("%s  substatements:" % (indent * istr))
        for s in stmt.substmts:
            print_tree(s, substmts, i_children, indent+1)
    if i_children and hasattr(stmt, 'i_children'):
        print("%s  i_children:" % (indent * istr))
        for s in stmt.i_children:
            print_tree(s, substmts, i_children, indent+1)

def mk_path_list(stmt):
    """Derives a list of tuples containing
    (module name, prefix, xpath, keys)
    per node in the statement.
    """
    resolved_names = []
    def resolve_stmt(stmt, resolved_names):
        if stmt.keyword in ['case', 'input', 'output']:
            resolve_stmt(stmt.parent, resolved_names)
            return
        def qualified_name_elements(stmt):
            """(module name, prefix, name, keys)"""
            return (
                stmt.i_module.arg,
                stmt.i_module.i_prefix,
                stmt.arg,
                get_keys(stmt)
            )
        if stmt.parent.keyword in ['module', 'submodule']:
            resolved_names.append(qualified_name_elements(stmt))
            return
        else:
            resolve_stmt(stmt.parent, resolved_names)
            resolved_names.append(qualified_name_elements(stmt))
            return
    resolve_stmt(stmt, resolved_names)
    return resolved_names

def mk_path_str(stmt,
                with_prefixes=False,
                prefix_onchange=False,
                prefix_to_module=False,
                resolve_top_prefix_to_module=False,
                with_keys=False):
    """Returns the XPath path of the node.
    with_prefixes indicates whether or not to prefix every node.

    prefix_onchange modifies the behavior of with_prefixes and
      only adds prefixes when the prefix changes mid-XPath.

    prefix_to_module replaces prefixes with the module name of the prefix.

    resolve_top_prefix_to_module resolves the module-level prefix
      to the module name.

    with_keys will include "[key]" to indicate the key names in the XPath.

    Prefixes may be included in the path if the prefix changes mid-path.
    """
    resolved_names = mk_path_list(stmt)
    xpath_elements = []
    last_prefix = None
    for index, resolved_name in enumerate(resolved_names):
        module_name, prefix, node_name, node_keys = resolved_name
        xpath_element = node_name
        if with_prefixes or (prefix_onchange and prefix != last_prefix):
            new_prefix = prefix
            if (prefix_to_module or
                (index == 0 and resolve_top_prefix_to_module)):
                new_prefix = module_name
            xpath_element = '%s:%s' % (new_prefix, node_name)
        if with_keys and node_keys:
            for node_key in node_keys:
                xpath_element = '%s[%s]' % (xpath_element, node_key)
        xpath_elements.append(xpath_element)
        last_prefix = prefix
    return '/%s' % '/'.join(xpath_elements)

def get_xpath(stmt, qualified=False, prefix_to_module=False, with_keys=False):
    """Gets the XPath path of the data node `stmt`.

    Unless qualified=True, does not include prefixes unless the prefix
      changes mid-XPath.

    qualified will add a prefix to each node.

    prefix_to_module will resolve prefixes to module names instead.

    with_keys will include "[key]" to indicate the key names in the XPath.

    For RFC 8040, set prefix_to_module=True:
      /module1:root/node/module2:node/...

    qualified=True:
      /prefix1:root/prefix1:node/prefix2:node/...

    qualified=True, prefix_to_module=True:
      /module1:root/module1:node/module2:node/...

    prefix_to_module=True, with_keys=True:
      /module1:root/node[name][name2]/module2:node/...
    """
    return mk_path_str(
        stmt,
        with_prefixes=qualified,
        prefix_onchange=True,
        prefix_to_module=prefix_to_module,
        with_keys=with_keys
    )

def get_type(stmt):
    """Gets the immediate, top-level type of the node.
    TODO: Add get_prefixed_type method to get prefixed types.
    """
    type_obj = stmt.search_one('type')
    # Return type value if exists
    return getattr(type_obj, 'arg', None)

def get_keys(stmt):
    """Gets the key names for the node if present.
    Returns a list of key name strings.
    """
    key_obj = stmt.search_one('key')
    key_names = []
    keys = getattr(key_obj, 'arg', None)
    if keys:
        key_names = keys.split()
    return key_names

def get_qualified_type(stmt):
    """Gets the qualified, top-level type of the node.
    This enters the typedef if defined instead of using the prefix
    to ensure absolute distinction.
    """
    type_obj = stmt.search_one('type')
    fq_type_name = None
    if type_obj:
        if getattr(type_obj, 'i_typedef', None):
            # If type_obj has typedef, substitute.
            # Absolute module:type instead of prefix:type
            type_obj = type_obj.i_typedef
        type_name = type_obj.arg
        if check_primitive_type(type_obj):
            # Doesn't make sense to qualify a primitive..I think.
            fq_type_name = type_name
        else:
            type_module = type_obj.i_orig_module.arg
            fq_type_name = '%s:%s' % (type_module, type_name)
    return fq_type_name

def get_primitive_type(stmt):
    """Recurses through the typedefs and returns
    the most primitive YANG type defined.
    """
    type_obj = stmt.search_one('type')
    type_name = getattr(type_obj, 'arg', None)
    typedef_obj = getattr(type_obj, 'i_typedef', None)
    if typedef_obj:
        type_name = get_primitive_type(typedef_obj)
    elif type_obj and not check_primitive_type(type_obj):
        raise Exception('%s is not a primitive! Incomplete parse tree?' %
                        type_name)
    return type_name

def check_primitive_type(stmt):
    """i_type_spec appears to indicate primitive type.
    """
    return True if getattr(stmt, 'i_type_spec', None) else False

def get_description(stmt):
    """Retrieves the description of the statement if present.
    """
    description_obj = stmt.search_one('description')
    # Return description value if exists
    return getattr(description_obj, 'arg', None)
