"""ietf-yang-metadata plugin

Verifies metadata YANG statements as defined in RFC 7952
"""

from pyang import plugin
from pyang import grammar

md_module_name = 'ietf-yang-metadata'

class MDPlugin(plugin.PyangPlugin):
    pass

def pyang_plugin_init():
    """Called by pyang plugin framework at to initialize the plugin."""

    # Register the plugin
    plugin.register_plugin(MDPlugin())

    # Register that we handle extensions from the YANG module
    # 'ietf-yang-metadata'
    grammar.register_extension_module(md_module_name)

    # Register the special grammar
    for stmt, occurence, (arg, rules), add_to_stmts in md_stmts:
        grammar.add_stmt((md_module_name, stmt), (arg, rules))
        grammar.add_to_stmts_rules(add_to_stmts,
                                   [((md_module_name, stmt), occurence)])

md_stmts = [

    # (<keyword>, <occurence when used>,
    #  (<argument type name | None>, <substmts>),
    #  <list of keywords where <keyword> can occur>)

    ('annotation', '*',
     ('identifier', [('if-feature', '*'),
                     ('status', '?'),
                     ('type', '1'),
                     ('unit', '?'),
                     ('description', '?'),
                     ('reference', '?')]),
     ['module', 'submodule']),
]
