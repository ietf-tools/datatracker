"""Name output plugin

"""

import optparse

from pyang import plugin

def pyang_plugin_init():
    plugin.register_plugin(NamePlugin())

class NamePlugin(plugin.PyangPlugin):
    def add_output_format(self, fmts):
        self.multiple_modules = True
        fmts['name'] = self

    def add_opts(self, optparser):
        optlist = [
            optparse.make_option("--name-print-revision",
                                 dest="print_revision",
                                 action="store_true",
                                 help="Print the name and revision in name@revision format"),
            ]
        g = optparser.add_option_group("Name output specific options")
        g.add_options(optlist)

    def setup_fmt(self, ctx):
        ctx.implicit_errors = False

    def emit(self, ctx, modules, fd):
        emit_name(ctx, modules, fd)

def emit_name(ctx, modules, fd):
    for module in modules:
        bstr = ""
        rstr = ""
        if ctx.opts.print_revision:
            rs = module.i_latest_revision
            if rs is None:
                r = module.search_one('revision')
                if r is not None:
                    rs = r.arg
            if rs is not None:
                rstr = '@%s' % rs
        b = module.search_one('belongs-to')
        if b is not None:
            bstr = " (belongs-to %s)" % b.arg
        fd.write("%s%s%s\n" % (module.arg, rstr, bstr))
