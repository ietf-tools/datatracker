"""MEF usage guidelines plugin
See MEF Assigned Names and Numbers (MANN) at https://wiki.mef.net/display/MANN/MEF+Assigned+Names+and+Numbers
"""

import optparse

from pyang import plugin
from pyang.plugins import lint

def pyang_plugin_init():
    plugin.register_plugin(MEFPlugin())

class MEFPlugin(lint.LintPlugin):
    def __init__(self):
        lint.LintPlugin.__init__(self)
        self.namespace_prefixes = ['urn:mef:yang:', 'urn:mef:xid:']
        self.modulename_prefixes = ['mef']

    def add_opts(self, optparser):
        optlist = [
            optparse.make_option("--mef",
                                 dest="mef",
                                 action="store_true",
                                 help="Validate the module(s) according to " \
                                 "MEF rules."),
            ]
        optparser.add_options(optlist)

    def setup_ctx(self, ctx):
        if not ctx.opts.mef:
            return

        ctx.max_line_len = 70
        self._setup_ctx(ctx)
