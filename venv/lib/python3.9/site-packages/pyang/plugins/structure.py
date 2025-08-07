"""YANG structure plugin

Verifies the grammar of the structure extension statements,
as defined in RFC 8791.
"""

import pyang
from pyang import plugin
from pyang import grammar
from pyang import statements
from pyang import error
from pyang.error import err_add

module_name = 'ietf-yang-structure-ext'

class StructurePlugin(plugin.PyangPlugin):
    def __init__(self):
        plugin.PyangPlugin.__init__(self, 'structure')

def pyang_plugin_init():
    """Called by pyang plugin framework at to initialize the plugin."""

    # Register the plugin
    plugin.register_plugin(StructurePlugin())

    # Register that we handle extensions from the YANG module
    # 'ietf-yang-structure-ext'
    grammar.register_extension_module(module_name)

    sx = (module_name, 'structure')
    statements.add_data_keyword(sx)
    statements.add_keyword_with_children(sx)
    statements.add_keywords_with_no_explicit_config(sx)
    asx = (module_name, 'augment-structure')
    statements.add_data_keyword(asx)
    statements.add_keyword_with_children(asx)
    statements.add_keywords_with_no_explicit_config(asx)

    # Register the special grammar
    for (stmt, occurance, (arg, rules), add_to_stmts) in structure_stmts:
        grammar.add_stmt((module_name, stmt), (arg, rules))
        grammar.add_to_stmts_rules(add_to_stmts,
                                   [((module_name, stmt), occurance)])

body_stmts = [
    ('description', '?'),
    ('reference', '?'),
    ('$interleave', grammar.data_def_stmts)
    ]

## FIXME: validate augment-structure

structure_stmts = [

    # (<keyword>, <occurance when used>,
    #  (<argument type name | None>, <substmts>),
    #  <list of keywords where <keyword> can occur>)

    ('structure', '*',
     ('identifier', body_stmts),
     ['module', 'submodule']),

    ('augment-structure', '*',
     ('absolute-schema-nodeid', body_stmts),
     ['module', 'submodule']),

]
