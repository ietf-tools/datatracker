"""Description of YANG & YIN grammar."""

import copy
import re

from . import util
from . import error
from . import syntax

module_header_stmts = [
    ('yang-version', '?'),
    ('namespace', '1'),
    ('prefix', '1'),
]

submodule_header_stmts = [
    ('yang-version', '?'),
    ('belongs-to', '1'),
]

linkage_stmts = [
    ('import', '*'),
    ('include', '*'),
]

meta_stmts = [
    ('organization', '?'),
    ('contact', '?'),
    ('description', '?'),
    ('reference', '?'),
]

revision_stmts = [
    ('revision', '*'),
]

data_def_stmts = [
    ('container', '*'),
    ('leaf', '*'),
    ('leaf-list', '*'),
    ('list', '*'),
    ('choice', '*'),
    ('$1.1', ('anydata', '*')),
    ('anyxml', '*'),
    ('uses', '*'),
]

body_stmts = [
    ('$interleave',
     [('extension', '*'),
      ('feature', '*'),
      ('identity', '*'),
      ('typedef', '*'),
      ('grouping', '*'),
      ('rpc', '*'),
      ('notification', '*'),
      ('deviation', '*'),
      ('augment', '*'),
      ] +
     data_def_stmts
    )
]

cut = ('$cut', '*')
"""Marker for end of statement block.

Special substatement which marks the end of a block in which the
substatements may occur in any order.
"""

top_stmts = [
    ('$choice', [[('module', '1')],
                 [('submodule', '1')]])
]
"""Top-level statements."""

def add_stmt(stmt, arg_rules):
    """Use by plugins to add grammar for an extension statement."""
    (arg, rules) = arg_rules
    stmt_map[stmt] = (arg, rules)

def add_to_stmts_rules(stmts, rules):
    """Use by plugins to add extra rules to the existing rules for
    a statement."""
    def is_rule_less_than(ra, rb):
        rka = ra[0]
        rkb = rb[0]
        if not util.is_prefixed(rkb):
            # old rule is non-prefixed; append new rule after
            return False
        if not util.is_prefixed(rka):
            # old rule prefixed, but new rule is not, insert
            return True
        # both are prefixed, compare modulename
        return rka[0] < rkb[0]
    for s in stmts:
        (arg, rules0) = stmt_map[s]
        for r in rules:
            i = 0
            while i < len(rules0):
                if is_rule_less_than(r, rules0[i]):
                    rules0.insert(i, r)
                    break
                i += 1
            if i == len(rules0):
                rules0.insert(i, r)

stmt_map = {
    'module':
        ('identifier',
         module_header_stmts +
         [cut] +
         linkage_stmts +
         [cut] +
         meta_stmts +
         [cut] +
         revision_stmts +
         [cut] +
         body_stmts),
    'submodule':
        ('identifier',
         submodule_header_stmts +
         [cut] +
         linkage_stmts +
         [cut] +
         meta_stmts +
         [cut] +
         revision_stmts +
         [cut] +
         body_stmts),
    'yang-version':
        ('version', []),
    'namespace':
        ('uri', []),
    'prefix':
        ('identifier', []),
    'import':
        ('identifier',
         [('prefix', '1'),
          ('revision-date', '?'),
          ('$1.1', ('description', '?')),
          ('$1.1', ('reference', '?'))]),
    'include':
        ('identifier',
         [('revision-date', '?'),
          ('$1.1', ('description', '?')),
          ('$1.1', ('reference', '?'))]),
    'revision-date':
        ('date', []),
    'revision':
        ('date',
         [('description', '?'),
          ('reference', '?')]),
    'belongs-to':
        ('identifier',
         [('prefix', '1')]),
    'organization':
        ('string', []),
    'contact':
        ('string', []),
    'description':
        ('string', []),
    'reference':
        ('string', []),
    'units':
        ('string', []),
    'extension':
        ('identifier',
         [('argument', '?'),
          ('status', '?'),
          ('description', '?'),
          ('reference', '?')]),
    'argument':
        ('identifier',
         [('yin-element', '?')]),
    'yin-element':
        ('boolean', []),
    'feature':
        ('identifier',
         [('if-feature', '*'),
          ('status', '?'),
          ('description', '?'),
          ('reference', '?')]),
    'if-feature':
        ('if-feature-expr', []),
    'identity':
        ('identifier',
         [('$1.1', ('if-feature', '*')),
          ('base', '*'), # '?' in yang version 1; checked in statements.py
          ('status', '?'),
          ('description', '?'),
          ('reference', '?')]),
    'base':
        ('identifier-ref', []),
    'require-instance':
        ('boolean', []),
    'fraction-digits':
        ('fraction-digits-arg', []),
    'typedef':
        ('identifier',
         [('type', '1'),
          ('units', '?'),
          ('default', '?'),
          ('status', '?'),
          ('description', '?'),
          ('reference', '?'),
          ]),
    'type':
        ('identifier-ref',
         [('$choice',
           [[('fraction-digits', '?'),
             ('range', '?')],
            [('length', '?'),
             ('pattern', '*')],
            [('enum', '*')],
            [('bit', '*')],
            [('path', '?'),
             ('require-instance', '?')],
            [('require-instance', '?')],
            [('base', '*')], # '?' in yang version 1; checked in statements.py
            [('type', '*')]])]),
    'range':
        ('range-arg',
         [('error-message', '?'),
          ('error-app-tag', '?'),
          ('description', '?'),
          ('reference', '?'),
          ]),
    'length':
        ('length-arg',
         [('error-message', '?'),
          ('error-app-tag', '?'),
          ('description', '?'),
          ('reference', '?'),
          ]),
    'pattern':
        ('string',
         [('$1.1', ('modifier', '?')),
          ('error-message', '?'),
          ('error-app-tag', '?'),
          ('description', '?'),
          ('reference', '?'),
          ]),
    'default':
        ('string', []),
    'enum':
        ('enum-arg',
         [('value', '?'),
          ('$1.1', ('if-feature', '*')),
          ('status', '?'),
          ('description', '?'),
          ('reference', '?'),
          ]),
    'path':
        ('path-arg', []),

    'bit':
        ('identifier',
         [('position', '?'),
          ('$1.1', ('if-feature', '*')),
          ('status', '?'),
          ('description', '?'),
          ('reference', '?'),
          ]),
    'position':
        ('non-negative-integer', []),
    'status':
        ('status-arg', []),
    'config':
        ('boolean', []),
    'mandatory':
        ('boolean', []),
    'presence':
        ('string', []),
    'ordered-by':
        ('ordered-by-arg', []),
    'must':
        ('string',
         [('error-message', '?'),
          ('error-app-tag', '?'),
          ('description', '?'),
          ('reference', '?'),
          ]),
    'error-message':
        ('string', []),
    'error-app-tag':
        ('string', []),
    'min-elements':
        ('non-negative-integer', []),
    'max-elements':
        ('max-value', []),
    'value':
        ('integer', []),
    'modifier':
        ('modifier-arg', []),
    'grouping':
        ('identifier',
         [('status', '?'),
          ('description', '?'),
          ('reference', '?'),
          ('$interleave',
           [('typedef', '*'),
            ('grouping', '*')] +
           data_def_stmts +
           [('$1.1', ('action', '*')),
            ('$1.1', ('notification', '*'))]),
          ]),
    'container':
        ('identifier',
         [('when', '?'),
          ('if-feature', '*'),
          ('must', '*'),
          ('presence', '?'),
          ('config', '?'),
          ('status', '?'),
          ('description', '?'),
          ('reference', '?'),
          ('$interleave',
           [('typedef', '*'),
            ('grouping', '*')] +
           data_def_stmts +
           [('$1.1', ('action', '*')),
            ('$1.1', ('notification', '*'))]),
          ]),
    'leaf':
        ('identifier',
         [('when', '?'),
          ('if-feature', '*'),
          ('type', '1'),
          ('units', '?'),
          ('must', '*'),
          ('default', '?'),
          ('config', '?'),
          ('mandatory', '?'),
          ('status', '?'),
          ('description', '?'),
          ('reference', '?'),
          ]),
    'leaf-list':
        ('identifier',
         [('when', '?'),
          ('if-feature', '*'),
          ('type', '1'),
          ('units', '?'),
          ('must', '*'),
          ('$1.1', ('default', '*')),
          ('config', '?'),
          ('min-elements', '?'),
          ('max-elements', '?'),
          ('ordered-by', '?'),
          ('status', '?'),
          ('description', '?'),
          ('reference', '?'),
          ]),
    'list':
        ('identifier',
         [('when', '?'),
          ('if-feature', '*'),
          ('must', '*'),
          ('key', '?'),
          ('unique', '*'),
          ('config', '?'),
          ('min-elements', '?'),
          ('max-elements', '?'),
          ('ordered-by', '?'),
          ('status', '?'),
          ('description', '?'),
          ('reference', '?'),
          ('$interleave',
           [('typedef', '*'),
            ('grouping', '*')] +
           data_def_stmts +
           [('$1.1', ('action', '*')),
            ('$1.1', ('notification', '*'))]),
          ]),
    'key':
        ('key-arg', []),
    'unique':
        ('unique-arg', []),
    'choice':
        ('identifier',
         [('when', '?'),
          ('if-feature', '*'),
          ('default', '?'),
          ('config', '?'),
          ('mandatory', '?'),
          ('status', '?'),
          ('description', '?'),
          ('reference', '?'),
          ('$interleave',
           [('case', '*'),
            ('$1.1', ('choice', '*')),
            ('container', '*'),
            ('leaf', '*'),
            ('leaf-list', '*'),
            ('list', '*'),
            ('$1.1', ('anydata', '*')),
            ('anyxml', '*'),
            ]),
          ]),
    'case':
        ('identifier',
         [('when', '?'),
          ('if-feature', '*'),
          ('status', '?'),
          ('description', '?'),
          ('reference', '?'),
          ('$interleave',
           data_def_stmts),
          ]),
    'anydata':
        ('identifier',
         [('when', '?'),
          ('if-feature', '*'),
          ('must', '*'),
          ('config', '?'),
          ('mandatory', '?'),
          ('status', '?'),
          ('description', '?'),
          ('reference', '?'),
          ]),
    'anyxml':
        ('identifier',
         [('when', '?'),
          ('if-feature', '*'),
          ('must', '*'),
          ('config', '?'),
          ('mandatory', '?'),
          ('status', '?'),
          ('description', '?'),
          ('reference', '?'),
          ]),
    'uses':
        ('identifier-ref',
         [('when', '?'),
          ('if-feature', '*'),
          ('status', '?'),
          ('description', '?'),
          ('reference', '?'),
          ('refine', '*'),
          ('augment', '*'),
          ]),
    'refine':
        ('descendant-schema-nodeid',
         [('must', '*'),
          ('$1.1', ('if-feature', '*')),
          ('presence', '?'),
          ('default', '?'),
          ('config', '?'),
          ('mandatory', '?'),
          ('min-elements', '?'),
          ('max-elements', '?'),
          ('description', '?'),
          ('reference', '?'),
          ]),
    'augment':
        ('schema-nodeid',
         [('when', '?'),
          ('if-feature', '*'),
          ('status', '?'),
          ('description', '?'),
          ('reference', '?'),
          ('$interleave',
           [('case', '*')] +
           data_def_stmts +
           [('$1.1', ('action', '*')),
            ('$1.1', ('notification', '*'))]),
          ]),
    'when':
        ('string',
         [('description', '?'),
          ('reference', '?'),
          ]),
    'rpc':
        ('identifier',
         [('if-feature', '*'),
          ('status', '?'),
          ('description', '?'),
          ('reference', '?'),
          ('$interleave',
           [('typedef', '*'),
            ('grouping', '*')]),
          ('input', '?'),
          ('output', '?'),
          ]),
    'action':
        ('identifier',
         [('if-feature', '*'),
          ('status', '?'),
          ('description', '?'),
          ('reference', '?'),
          ('$interleave',
           [('typedef', '*'),
            ('grouping', '*')]),
          ('input', '?'),
          ('output', '?'),
          ]),
    'input':
        (None,
         [('$1.1', ('must', '*')),
          ('$interleave',
           [('typedef', '*'),
            ('grouping', '*')] +
           data_def_stmts),
          ]),
    'output':
        (None,
         [('$1.1', ('must', '*')),
          ('$interleave',
           [('typedef', '*'),
            ('grouping', '*')] +
           data_def_stmts),
          ]),
    'notification':
        ('identifier',
         [('if-feature', '*'),
          ('$1.1', ('must', '*')),
          ('status', '?'),
          ('description', '?'),
          ('reference', '?'),
          ('$interleave',
           [('typedef', '*'),
            ('grouping', '*')] +
           data_def_stmts),
          ]),
    'deviation':
        ('absolute-schema-nodeid',
         [('description', '?'),
          ('reference', '?'),
          ('deviate', '+')]),
    'deviate':
        ('deviate-arg',
         [('type', '?'),
          ('units', '?'),
          ('must', '*'),
          ('unique', '*'),
          ('default', '?'),
          ('config', '?'),
          ('mandatory', '?'),
          ('min-elements', '?'),
          ('max-elements', '?'),
          ]),
    }
"""YANG statement definitions.

Maps a statement name to a 2-tuple:
    (<argument type name> | None, <list of substatements> )
Each substatement is a 2-tuple:
    (<statement name>, <occurence>) |
    ('$interleave', <list of substatements to interleave>)
    ('$choice', <list of <case>>)
where <occurence> is one of: '?', '1', '+', '*'.
and <case> is a list of substatements
"""


re_identifier_illegal_prefix = re.compile("^[xX][mM][lL]")


extension_modules = []
"""A list of YANG module names for which extensions are validated"""

def register_extension_module(modname):
    """Add a modulename to the list of known YANG module where extensions
    are defined.
    Used by plugins to register that they implement extensions from
    a particular module."""
    extension_modules.append(modname)

def chk_module_statements(ctx, module_stmt, canonical=False):
    """Validate the statement hierarchy according to the grammar.

    Return True if module is valid, False otherwise.
    """
    return chk_statement(ctx, module_stmt, top_stmts, canonical)

def chk_statement(ctx, stmt, grammar, canonical=False):
    """Validate `stmt` according to `grammar`.

    Marks each statement in the hierearchy with stmt.is_grammatically_valid,
    which is a boolean.

    Return True if stmt is valid, False otherwise.
    """
    n = len(ctx.errors)
    if canonical:
        canspec = grammar
    else:
        canspec = []
    _chk_stmts(ctx, stmt.pos, [stmt], None, (grammar, canspec), canonical)
    return n == len(ctx.errors)

def _chk_stmts(ctx, pos, stmts, parent, spec, canonical):
    for stmt in stmts:
        stmt.is_grammatically_valid = False
        if stmt.keyword == '_comment':
            chk_grammar = False
        elif not util.is_prefixed(stmt.keyword):
            chk_grammar = True
        else:
            (modname, _identifier) = stmt.keyword
            if modname in extension_modules:
                chk_grammar = True
            else:
                chk_grammar = False
        if chk_grammar:
            match_res = _match_stmt(ctx, stmt, spec, canonical)
        else:
            match_res = None
        if match_res is None and chk_grammar:
            if canonical:
                save_errors = ctx.errors
                ctx.errors = []
                if _match_stmt(ctx, stmt, (spec[1], []), False) is not None:
                    ctx.errors = save_errors
                    if stmt.i_module.i_version == '1':
                        errcode = 'UNEXPECTED_KEYWORD_CANONICAL'
                    else:
                        errcode = 'UNEXPECTED_KEYWORD_CANONICAL_v1.1'
                    error.err_add(ctx.errors, stmt.pos,
                                  errcode,
                                  util.keyword_to_str(stmt.raw_keyword))
                else:
                    ctx.errors = save_errors
                    error.err_add(ctx.errors, stmt.pos, 'UNEXPECTED_KEYWORD',
                                  util.keyword_to_str(stmt.raw_keyword))
            else:
                error.err_add(ctx.errors, stmt.pos, 'UNEXPECTED_KEYWORD',
                              util.keyword_to_str(stmt.raw_keyword))
        elif match_res is not None and chk_grammar:
            try:
                (arg_type, subspec) = stmt_map[stmt.keyword]
            except KeyError:
                error.err_add(ctx.errors, stmt.pos, 'UNEXPECTED_KEYWORD',
                              util.keyword_to_str(stmt.raw_keyword))
                return
            # verify the statement's argument
            if arg_type is None and stmt.arg is not None:
                error.err_add(ctx.errors, stmt.pos,
                              'UNEXPECTED_ARGUMENT', stmt.arg)
            elif arg_type is not None and stmt.arg is None:
                error.err_add(ctx.errors, stmt.pos,
                              'EXPECTED_ARGUMENT',
                              util.keyword_to_str(stmt.keyword))
            elif (arg_type is not None and arg_type != 'string' and
                  syntax.arg_type_map[arg_type](stmt.arg) is False):
                error.err_add(ctx.errors, stmt.pos,
                              'BAD_VALUE', (stmt.arg, arg_type))
            elif (arg_type == 'identifier' and
                  ctx.max_identifier_len is not None
                  and len(stmt.arg) > ctx.max_identifier_len):
                error.err_add(ctx.errors, stmt.pos, 'LONG_IDENTIFIER',
                              (stmt.arg, ctx.max_identifier_len))
                # recoverable error
                stmt.is_grammatically_valid = True
            else:
                stmt.is_grammatically_valid = True

            if canonical:
                cansubspec = subspec
            else:
                cansubspec = []
            _chk_stmts(ctx, stmt.pos, stmt.substmts, stmt,
                       (subspec, cansubspec), canonical)
            spec = match_res
        else:
            # unknown extension
            stmt.is_grammatically_valid = True
            nspec = [('$any', '*')]
            _chk_stmts(ctx, stmt.pos, stmt.substmts, stmt,
                       (nspec, nspec), canonical)
        # update last know position
        pos = stmt.pos
    # any non-optional statements left are errors
    for keywd, occurence in spec[0]:
        if occurence == '1' or occurence == '+':
            if parent is None:
                error.err_add(ctx.errors, pos, 'EXPECTED_KEYWORD',
                              util.keyword_to_str(keywd))
            else:
                error.err_add(ctx.errors, pos, 'EXPECTED_KEYWORD_2',
                              (util.keyword_to_str(keywd),
                               util.keyword_to_str(parent.raw_keyword)))

def _match_stmt(ctx, stmt, specs, canonical):
    """Match stmt against the spec.

    Return None | spec'
    spec' is an updated spec with the matching spec consumed
    """
    (spec, canspec) = specs
    i = 0
    while i < len(spec):
        keywd, occurence = spec[i]
        if keywd == '$any':
            return (spec, canspec)
        if keywd == '$1.1':
            (keywd, occurence) = occurence
            if (stmt.i_module.i_version == '1' and
                keywd == stmt.keyword):
                return None
        if keywd == stmt.keyword:
            if occurence == '1' or occurence == '?':
                # consume this match
                if canonical:
                    return (spec[i+1:], spec_del_kwd(keywd, canspec))
                else:
                    return (spec[:i] + spec[i+1:], canspec)
            if occurence == '+':
                # mark that we have found the one that was needed
                c = (keywd, '*')
                if canonical:
                    return ([c] + spec[i+1:], canspec)
                else:
                    return (spec[:i] + [c] + spec[i+1:], canspec)
            else:
                # occurane == '*'
                if canonical:
                    return (spec[i:], canspec)
                else:
                    return (spec, canspec)
        elif keywd == '$choice':
            cases = occurence
            j = 0
            while j < len(cases):
                # check if this alternative matches - check for a
                # match with each optional keyword
                save_errors = copy.copy(ctx.errors)
                if spec == top_stmts:
                    match_res = _match_stmt(ctx, stmt, (cases[j],[]), False)
                else:
                    match_res = _match_stmt(ctx, stmt, (cases[j],cases[j]),
                                            canonical)
                if match_res is not None:
                    # this case branch matched, use it.
                    # remove the choice and add res to the spec.
                    nspec = spec[:i] + match_res[0] + spec[i+1:]
                    return (nspec, canspec)
                # we must not report errors on non-matching branches
                ctx.errors = save_errors
                j += 1
        elif keywd == '$interleave':
            cspec = occurence
            match_res = _match_stmt(ctx, stmt, (cspec, cspec), canonical)
            if match_res is not None:
                # we got a match
                return (spec, canspec)
        elif util.is_prefixed(stmt.keyword):
            # allow extension statements mixed with these
            # set canonical to False in this call to just remove the
            # matching stmt from the spec
            match_res = _match_stmt(ctx, stmt, (spec[i+1:], canspec), False)
            if match_res is not None:
                return (spec[:i+1] + match_res[0], canspec)
            else:
                return None
        elif keywd == '$cut':
            # any non-optional statements left are errors
            for keywd, occurence in spec[:i]:
                if occurence == '1' or occurence == '+':
                    error.err_add(ctx.errors, stmt.pos, 'UNEXPECTED_KEYWORD_1',
                                  (util.keyword_to_str(stmt.raw_keyword),
                                   util.keyword_to_str(keywd)))
            # consume them so we don't report the same error again
            spec = spec[i:]
            i = 0
        elif canonical:
            if occurence == '1' or occurence == '+':
                if stmt.i_module.i_version == '1':
                    errcode = 'UNEXPECTED_KEYWORD_CANONICAL_1'
                else:
                    errcode = 'UNEXPECTED_KEYWORD_CANONICAL_1_v1.1'
                error.err_add(ctx.errors, stmt.pos,
                              errcode,
                              (util.keyword_to_str(stmt.raw_keyword),
                               util.keyword_to_str(keywd)))
                # consume it so we don't report the same error again
                spec = spec[i:]
                i = 0
        # check next in spec
        i += 1
    return None

def spec_del_kwd(keywd, spec):
    i = 0
    for kw, s in spec:
        if kw == keywd:
            return spec[:i] + spec[i+1:]
        i = i + 1
    return spec

def flatten_spec(spec):
    res = []
    for kw, s in spec:
        if kw == '$interleave':
            res.extend(flatten_spec(s))
        elif kw == '$1.1':
            res.append((s))
        elif kw == '$choice':
            for branch in s:
                for bs in flatten_spec(branch):
                    if bs not in res:
                        res.append(bs)
        else:
            if (kw, s) not in res:
                res.append((kw,s))
    return res


def sort_canonical(keyword, stmts):
    """Sort all `stmts` in the canonical order defined by `keyword`.
    Return the sorted list.  The `stmt` list is not modified.
    If `keyword` does not have a canonical order, the list is returned
    as is.
    """

    try:
        (_arg_type, subspec) = stmt_map[keyword]
    except KeyError:
        return stmts
    res = []
    # keep the order of data definition statements and case
    keep = [s[0] for s in data_def_stmts] + ['case']
    for kw, _spec in flatten_spec(subspec):
        # keep comments before a statement together with that statement
        comments = []
        for s in stmts:
            if s.keyword == '_comment':
                comments.append(s)
            elif s.keyword == kw and kw not in keep:
                res.extend(comments)
                comments = []
                res.append(s)
            else:
                comments = []

    # then copy all other statements (extensions)
    res.extend([stmt for stmt in stmts if stmt not in res])
    return res
