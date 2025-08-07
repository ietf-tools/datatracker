"""RESTCONF plugin

Verifies RESTCONF YANG statements as defined in RFC 8040.

Verifies the grammar of the restconf extension statements.
"""

from pyang import plugin
from pyang import grammar
from pyang import statements
from pyang import error
from pyang.error import err_add

restconf_module_name = 'ietf-restconf'

class RESTCONFPlugin(plugin.PyangPlugin):
    def __init__(self):
        plugin.PyangPlugin.__init__(self, 'restconf')

def pyang_plugin_init():
    """Called by pyang plugin framework at to initialize the plugin."""

    # Register the plugin
    plugin.register_plugin(RESTCONFPlugin())

    # Register that we handle extensions from the YANG module 'ietf-restconf'
    grammar.register_extension_module(restconf_module_name)

    yd = (restconf_module_name, 'yang-data')
    statements.add_data_keyword(yd)
    statements.add_keyword_with_children(yd)
    statements.add_keywords_with_no_explicit_config(yd)

    # Register the special grammar
    for stmt, occurence, (arg, rules), add_to_stmts in restconf_stmts:
        grammar.add_stmt((restconf_module_name, stmt), (arg, rules))
        grammar.add_to_stmts_rules(add_to_stmts,
                                   [((restconf_module_name, stmt), occurence)])

    # Add validation functions
    statements.add_validation_fun('expand_2',
                                  [yd],
                                  v_yang_data)

    # Register special error codes
    error.add_error_code('RESTCONF_YANG_DATA_CHILD', 1,
                         "the 'yang-data' extension must have exactly one " +
                         "child that is a container")

restconf_stmts = [

    # (<keyword>, <occurence when used>,
    #  (<argument type name | None>, <substmts>),
    #  <list of keywords where <keyword> can occur>)

    ('yang-data', '*',
     ('identifier', grammar.data_def_stmts),
     ['module', 'submodule']),

]

def v_yang_data(ctx, stmt):

    def ensure_container(s):
        if len(s.i_children) != 1:
            return False
        ch = s.i_children[0]
        if ch.keyword == 'choice':
            for c in ch.i_children:
                if not ensure_container(c):
                    return False
        elif ch.keyword != 'container':
            return False
        return True

    if not ensure_container(stmt):
        err_add(ctx.errors, stmt.pos, 'RESTCONF_YANG_DATA_CHILD', ())
