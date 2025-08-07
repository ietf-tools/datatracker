"""Makefile dependency rule output plugin

"""

import optparse
import os.path

from pyang import plugin
from pyang import error

def pyang_plugin_init():
    plugin.register_plugin(DependPlugin())

class DependPlugin(plugin.PyangPlugin):
    def add_opts(self, optparser):
        optlist = [
            optparse.make_option("--depend-target",
                                 dest="depend_target",
                                 help="Makefile rule target"),
            optparse.make_option("--depend-no-submodules",
                                 dest="depend_no_submodules",
                                 action="store_true",
                                 help="Do not generate dependencies for " \
                                 "included submodules"),
            optparse.make_option("--depend-from-submodules",
                                 dest="depend_from_submodules",
                                 action="store_true",
                                 help="Generate dependencies from " \
                                 "included submodules"),
            optparse.make_option("--depend-recurse",
                                 dest="depend_recurse",
                                 action="store_true",
                                 help="Generate dependencies to all " \
                                     "imports, recursively"),
            optparse.make_option("--depend-extension",
                                 dest="depend_extension",
                                 help="YANG module file name extension"),
            optparse.make_option("--depend-include-path",
                                 dest="depend_include_path",
                                 action="store_true",
                                 help="Include file path in the prerequisites"),
            optparse.make_option("--depend-ignore-module",
                                 dest="depend_ignore",
                                 default=[],
                                 action="append",
                                 help="(sub)module to ignore in the" \
                                     " prerequisites.  This option can be" \
                                     " given multiple times."),
            ]
        g = optparser.add_option_group("Depend output specific options")
        g.add_options(optlist)
    def add_output_format(self, fmts):
        self.multiple_modules = True
        fmts['depend'] = self
    def emit(self, ctx, modules, fd):
        # cannot do this unless everything is ok for our module
        modulenames = [m.arg for m in modules]
        for epos, etag, eargs in ctx.errors:
            if ((epos.top is None or epos.top.arg in modulenames) and
                error.is_error(error.err_level(etag))):
                raise error.EmitError("%s contains errors" % epos.top.arg)
        emit_depend(ctx, modules, fd)

def emit_depend(ctx, modules, fd):
    for module in modules:
        if ctx.opts.depend_target is None:
            fd.write('%s :' % module.pos.ref)
        else:
            fd.write('%s :' % ctx.opts.depend_target)
        prereqs = []
        add_prereqs(ctx, module, prereqs)
        for i in prereqs:
            if i in ctx.opts.depend_ignore:
                continue
            if ctx.opts.depend_include_path:
                m = ctx.get_module(i)
                if ctx.opts.depend_extension is None:
                    filename = m.pos.ref
                else:
                    basename = os.path.splitext(m.pos.ref)[0]
                    filename = '%s%s' % (basename, ctx.opts.depend_extension)
                fd.write(' %s' % filename)
            else:
                if ctx.opts.depend_extension is None:
                    ext = ""
                else:
                    ext = ctx.opts.depend_extension
                fd.write(' %s%s' % (i, ext))
        fd.write('\n')

def add_prereqs(ctx, module, prereqs):
    new = [(i.arg, i.search_one("revision-date")) for i in module.search("import") if i.arg not in prereqs]
    if not ctx.opts.depend_no_submodules:
        new += [(i.arg, i.search_one("revision-date")) for i in module.search("include")
                if i.arg not in prereqs and i.arg not in new]
    if ctx.opts.depend_from_submodules:
        for i in module.search("include"):
            subm = ctx.get_module(i.arg)
            if subm is not None:
                new += [(i.arg, i.search_one("revision-date")) for i in subm.search("import")
                        if i.arg not in prereqs and i.arg not in new]
    prereqs.extend(i[0] for i in new)
    if ctx.opts.depend_recurse:
        for modulename, revision_date in new:
            revision = revision_date.arg if revision_date is not None else None
            m = ctx.get_module(modulename, revision)
            add_prereqs(ctx, m, prereqs)
