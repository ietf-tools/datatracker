"""Identifiers output plugin
"""

from pyang import plugin
from pyang import statements

def pyang_plugin_init():
    plugin.register_plugin(IdentifiersPlugin())

class IdentifiersPlugin(plugin.PyangPlugin):
    def __init__(self):
        plugin.PyangPlugin.__init__(self, 'identifiers')

    def add_output_format(self, fmts):
        self.multiple_modules = True
        fmts['identifiers'] = self

    def setup_fmt(self, ctx):
        ctx.implicit_errors = False
        ctx.identifier_state = self
        self.nodes = {}
        self.typedefs = {}
        self.groupings = {}
        self.enums = {}
        self.identities = {}
        self.features = {}
        statements.add_validation_fun('grammar', ['enum'], add_enum)
        statements.add_validation_fun('grammar', ['typedef'], add_typedef)
        statements.add_validation_fun('grammar', ['grouping'], add_grouping)
        statements.add_validation_fun('grammar', ['identity'], add_identity)
        statements.add_validation_fun('grammar', ['feature'], add_feature)
        statements.add_validation_fun('grammar',
                                      statements.data_keywords,
                                      add_node)

    def emit(self, ctx, modules, fd):
        emit_identifiers(ctx, modules, fd)

def add_enum(ctx, s):
    m = s.i_module.i_modulename
    if not m in ctx.identifier_state.enums:
        ctx.identifier_state.enums[m] = set()
    ctx.identifier_state.enums[m].add(s.arg)

def add_typedef(ctx, s):
    m = s.i_module.i_modulename
    if not m in ctx.identifier_state.typedefs:
        ctx.identifier_state.typedefs[m] = set()
    ctx.identifier_state.typedefs[m].add(s.arg)

def add_grouping(ctx, s):
    m = s.i_module.i_modulename
    if not m in ctx.identifier_state.groupings:
        ctx.identifier_state.groupings[m] = set()
    ctx.identifier_state.groupings[m].add(s.arg)

def add_identity(ctx, s):
    m = s.i_module.i_modulename
    if not m in ctx.identifier_state.identities:
        ctx.identifier_state.identities[m] = set()
    ctx.identifier_state.identities[m].add(s.arg)

def add_feature(ctx, s):
    m = s.i_module.i_modulename
    if not m in ctx.identifier_state.features:
        ctx.identifier_state.features[m] = set()
    ctx.identifier_state.features[m].add(s.arg)

def add_node(ctx, s):
    m = s.i_module.i_modulename
    if not m in ctx.identifier_state.nodes:
        ctx.identifier_state.nodes[m] = set()
    ctx.identifier_state.nodes[m].add(s.arg)


def emit_identifiers(ctx, modules, fd):
    print_identifiers(fd, 'nodes', modules, ctx.identifier_state.nodes)
    print_identifiers(fd, 'typedefs', modules, ctx.identifier_state.typedefs)
    print_identifiers(fd, 'groupings', modules, ctx.identifier_state.groupings)
    print_identifiers(fd, 'enums', modules, ctx.identifier_state.enums)
    print_identifiers(fd, 'identities', modules,
                      ctx.identifier_state.identities)
    print_identifiers(fd, 'features', modules, ctx.identifier_state.features)

def print_identifiers(fd, title, modules, names):
    r = set()
    for m in modules:
        if m.i_modulename in names:
            r = r.union(names[m.i_modulename])
    if len(r) > 0:
        fd.write(title + ':\n')
        for name in sorted(r):
            fd.write('  %s\n' % name)
