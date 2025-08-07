"""SMIv2 plugin

Verifies SMIv2 YANG statements as defined in RFC 6643.

This implementation relaxes one rule from RFC 6643; it allows
smiv2:subid if an ancestor statement has a smiv2:oid or smiv2:subid
statement.  RFC 6643 requires the parent statement to have the
smiv2:oid or smiv2:subid statement.

Verifies the grammar of the smiv2 extension statements, and sets
i_smi_oid built from the smiv2:oid and smiv2:subid statements.
"""

import re

from pyang import plugin
from pyang import syntax
from pyang import grammar
from pyang import statements
from pyang import error
from pyang.error import err_add

smi_module_name = 'ietf-yang-smiv2'

re_smi_oid = re.compile(r"^(([0-1](\.[1-3]?[0-9]))|(2\.(0|([1-9]\d*))))" \
                        r"(\.(0|([1-9]\d*)))*$")

class SMIPlugin(plugin.PyangPlugin):
    pass

def _chk_smi_oid(s):
    return re_smi_oid.search(s) is not None

def _chk_smi_max_access(s):
    return s in ['not-accessible', 'accessible-for-notify', 'read-only',
                 'read-write', 'read-create']

def pyang_plugin_init():
    """Called by pyang plugin framework at to initialize the plugin."""

    # Register the plugin
    plugin.register_plugin(SMIPlugin())

    # Add our special argument syntax checkers
    syntax.add_arg_type('smi-oid', _chk_smi_oid)
    syntax.add_arg_type('smi-max-access', _chk_smi_max_access)

    # Register that we handle extensions from the YANG module 'ietf-yang-smiv2'
    grammar.register_extension_module(smi_module_name)

    # Register the special grammar
    for stmt, occurence, (arg, rules), add_to_stmts in smi_stmts:
        grammar.add_stmt((smi_module_name, stmt), (arg, rules))
        grammar.add_to_stmts_rules(add_to_stmts,
                                   [((smi_module_name, stmt), occurence)])

    # Add validation step
    statements.add_validation_phase('smi_set_oid', after='inherit_properties')
    statements.add_validation_fun('smi_set_oid',
                                  [(smi_module_name, 'oid')],
                                  v_set_oid)
    statements.add_validation_fun('smi_set_oid',
                                  [(smi_module_name, 'subid')],
                                  v_set_subid)

    # Register special error codes
    error.add_error_code('SMIv2_BAD_SUBID', 1,
                         "subid needs an oid or subid statement in an ancestor")
    error.add_error_code('SMIv2_SUBID_AND_OID', 1,
                         "subid and oid cannot be given at the same time")

smi_stmts = [

    # (<keyword>, <occurence when used>,
    #  (<argument type name | None>, <substmts>),
    #  <list of keywords where <keyword> can occur>)

    ('display-hint', '?',
     ('string', []),
     ['leaf', 'typedef']),

    ('max-access', '?',
     ('smi-max-access', []),
     ['leaf', 'typedef']),

    ('defval', '?',
     ('string', []),
     ['leaf']),

    ('implied', '?',
     ('identifier', []),
     ['list']),

    ('alias', '*',
     ('identifier', [('status', '?'),
                     ('description', '?'),
                     ('reference', '?'),
                     ((smi_module_name, 'oid'), '1')]),
     ['module', 'submodule']),

    ('oid', '?',
     ('smi-oid', []),
     ['leaf', 'list', 'container', 'augment', 'notification', 'identity']),

    ('subid', '?',
     ('non-negative-integer', []),
     ['leaf', 'list', 'container', 'augment', 'notification']),

]

re_sub = re.compile("[0-9]+")

def v_set_oid(ctx, stmt):
    oid = [int(s) for s in re_sub.findall(stmt.arg)]
    stmt.parent.i_smi_oid = oid

def v_set_subid(ctx, stmt):
    if stmt.parent.search_one((smi_module_name, 'oid')) is not None:
        err_add(ctx.errors, stmt.pos, 'SMIv2_SUBID_AND_OID', ())
        return

    def find_ancestor_oid(s):
        if s.parent is None:
            return None
        if hasattr(s.parent, 'i_smi_oid'):
            return s.parent.i_smi_oid
        return find_ancestor_oid(s.parent)
    oid = find_ancestor_oid(stmt.parent)
    if oid is None:
        err_add(ctx.errors, stmt.pos, 'SMIv2_BAD_SUBID', ())
        return
    stmt.parent.i_smi_oid = oid + [int(stmt.arg)]
