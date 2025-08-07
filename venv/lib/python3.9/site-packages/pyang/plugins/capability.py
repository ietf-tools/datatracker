"""Capability URL plugin

"""

import optparse

from pyang import plugin
from pyang import util

def pyang_plugin_init():
    plugin.register_plugin(CapabilityPlugin())

class CapabilityPlugin(plugin.PyangPlugin):
    def add_output_format(self, fmts):
        self.multiple_modules = True
        fmts['capability'] = self
    def add_opts(self, optparser):
        optlist = [
            optparse.make_option("--capability-entity",
                                 dest="capa_entity",
                                 action="store_true",
                                 default=False,
                                 help="Write ampersands as XML entity")
            ]
        g = optparser.add_option_group("Capability output specific options")
        g.add_options(optlist)
    def emit(self, ctx, modules, fd):
        for m in modules:
            emit_capability(ctx, m, fd)

def emit_capability(ctx, m, fd):
    amp = "&amp;" if ctx.opts.capa_entity else "&"
    ns = m.search_one('namespace')
    if ns is None:
        return
    s = ns.arg + "?module=" + m.i_modulename

    latest_rev = util.get_latest_revision(m)
    if latest_rev != "unknown":
        s = s + amp + "revision=" + latest_rev

    if m.i_modulename in ctx.features:
        if len(ctx.features[m.i_modulename]) > 0:
            s = s + amp + "features=" + ",".join(ctx.features[m.i_modulename])
        else:
            # do not report any features from the module
            pass
    else:
        # report all features defined in the module
        fs = [x.arg for x in m.search('feature')]
        s = s + amp + "features=" + ",".join(fs)

    devs = []
    for d in ctx.deviation_modules:
        # check if this deviation module deviates anything in our module
        for dev in d.search('deviation'):
            if (dev.i_target_node is not None and
                dev.i_target_node.i_module.i_modulename == m.i_modulename):
                devs.append(d.i_modulename)
                break

    if len(devs) > 0:
        s = s + amp + "deviations=" +  ",".join(devs)

    fd.write(s + '\n')
