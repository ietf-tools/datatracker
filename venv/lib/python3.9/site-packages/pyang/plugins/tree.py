"""Tree output plugin

Compatible with RFC 8340 and RFC 8791.

Idea copied from libsmi.
"""

import optparse
import sys
import re

from pyang import plugin
from pyang import statements
from pyang import util

def pyang_plugin_init():
    plugin.register_plugin(TreePlugin())

class TreePlugin(plugin.PyangPlugin):
    def __init__(self):
        plugin.PyangPlugin.__init__(self, 'tree')

    def add_output_format(self, fmts):
        self.multiple_modules = True
        fmts['tree'] = self

    def add_opts(self, optparser):
        optlist = [
            optparse.make_option("--tree-help",
                                 dest="tree_help",
                                 action="store_true",
                                 help="Print help on tree symbols and exit"),
            optparse.make_option("--tree-depth",
                                 type="int",
                                 dest="tree_depth",
                                 help="Number of levels to print"),
            optparse.make_option("--tree-line-length",
                                 type="int",
                                 dest="tree_line_length",
                                 help="Maximum line length"),
            optparse.make_option("--tree-path",
                                 dest="tree_path",
                                 help="Subtree to print"),
            optparse.make_option("--tree-print-groupings",
                                 dest="tree_print_groupings",
                                 action="store_true",
                                 help="Print groupings"),
            optparse.make_option("--tree-no-expand-uses",
                                 dest="tree_no_expand_uses",
                                 action="store_true",
                                 help="Do not expand uses of groupings"),
            optparse.make_option("--tree-module-name-prefix",
                                 dest="modname_prefix",
                                 action="store_true",
                                 help="Prefix with module names instead of " +
                                 "prefixes"),
            ]
        if plugin.is_plugin_registered('restconf'):
            optlist.append(
                optparse.make_option("--tree-print-yang-data",
                                     dest="tree_print_yang_data",
                                     action="store_true",
                                     help="Print ietf-restconf:yang-data " +
                                     "structures")
            )
        if plugin.is_plugin_registered('structure'):
            optlist.append(
                optparse.make_option("--tree-print-structures",
                                     dest="tree_print_structures",
                                     action="store_true",
                                     help="Print ietf-yang-structure-ext" +
                                     ":structure")
            )
        g = optparser.add_option_group("Tree output specific options")
        g.add_options(optlist)

    def setup_ctx(self, ctx):
        if ctx.opts.tree_help:
            print_help()
            sys.exit(0)

    def setup_fmt(self, ctx):
        ctx.implicit_errors = False

    def emit(self, ctx, modules, fd):
        if ctx.opts.tree_path is not None:
            path = ctx.opts.tree_path.split('/')
            if path[0] == '':
                path = path[1:]
        else:
            path = None
        emit_tree(ctx, modules, fd, ctx.opts.tree_depth,
                  ctx.opts.tree_line_length, path)

def print_help():
    print("""
Each node is printed as:

<status>--<flags> <name><opts> <type> <if-features>

  <status> is one of:
    +  for current
    x  for deprecated
    o  for obsolete

  <flags> is one of:
    rw  for configuration data
    ro  for non-configuration data, output parameters to rpcs
        and actions, and notification parameters
    -w  for input parameters to rpcs and actions
    -u  for uses of a grouping
    -x  for rpcs and actions
    -n  for notifications

  <name> is the name of the node
    (<name>) means that the node is a choice node
   :(<name>) means that the node is a case node

   If the node is augmented into the tree from another module, its
   name is printed as <prefix>:<name>.

  <opts> is one of:
    ?  for an optional leaf, choice, anydata or anyxml
    !  for a presence container
    *  for a leaf-list or list
    [<keys>] for a list's keys

    <type> is the name of the type for leafs and leaf-lists, or
           "<anydata>" or "<anyxml>" for anydata and anyxml, respectively

    If the type is a leafref, the type is printed as "-> TARGET", where
    TARGET is the leafref path, with prefixes removed if possible.

  <if-features> is the list of features this node depends on, printed
    within curly brackets and a question mark "{...}?"
""")

def emit_tree(ctx, modules, fd, depth, llen, path):
    def print_header(module):
        if not printed_header:
            bstr = ""
            b = module.search_one('belongs-to')
            if b is not None:
                bstr = " (belongs-to %s)" % b.arg
            fd.write("%s: %s%s\n" % (module.keyword, module.arg, bstr))
            printed_header.append(None)

    printed_header = []

    for module in modules:
        if printed_header:
            fd.write("\n")
        del printed_header[:]
            

        chs = [ch for ch in module.i_children
               if ch.keyword in statements.data_definition_keywords]
        if path is not None and len(path) > 0:
            chs = [ch for ch in chs if ch.arg == path[0]]
            chpath = path[1:]
        else:
            chpath = path

        if len(chs) > 0:
            print_header(module)
            print_children(chs, module, fd, '', chpath, 'data', depth, llen,
                           ctx.opts.tree_no_expand_uses,
                           prefix_with_modname=ctx.opts.modname_prefix)

        mods = [module]
        for i in module.search('include'):
            subm = ctx.get_module(i.arg)
            if subm is not None:
                mods.append(subm)
        section_delimiter_printed=False
        for m in mods:
            for augment in m.search('augment'):
                if (hasattr(augment, 'i_target_node') and
                    hasattr(augment.i_target_node, 'i_module') and
                    augment.i_target_node.i_module not in modules + mods):
                    # this augment has not been printed; print it
                    print_header(module)
                    if not section_delimiter_printed:
                        fd.write('\n')
                        section_delimiter_printed = True
                    print_path("  augment", ":", augment.arg, fd, llen)
                    mode = 'augment'
                    if augment.i_target_node.keyword == 'input':
                        mode = 'input'
                    elif augment.i_target_node.keyword == 'output':
                        mode = 'output'
                    elif augment.i_target_node.keyword == 'notification':
                        mode = 'notification'
                    print_children(augment.i_children, m, fd,
                                   '  ', path, mode, depth, llen,
                                   ctx.opts.tree_no_expand_uses,
                                   prefix_with_modname=ctx.opts.modname_prefix)

        rpcs = [ch for ch in module.i_children
                if ch.keyword == 'rpc']
        rpath = path
        if path is not None:
            if len(path) > 0:
                rpcs = [rpc for rpc in rpcs if rpc.arg == path[0]]
                rpath = path[1:]
            else:
                rpcs = []
        if len(rpcs) > 0:
            print_header(module)
            fd.write("\n  rpcs:\n")
            print_children(rpcs, module, fd, '  ', rpath, 'rpc', depth, llen,
                           ctx.opts.tree_no_expand_uses,
                           prefix_with_modname=ctx.opts.modname_prefix)

        notifs = [ch for ch in module.i_children
                  if ch.keyword == 'notification']
        npath = path
        if path is not None:
            if len(path) > 0:
                notifs = [n for n in notifs if n.arg == path[0]]
                npath = path[1:]
            else:
                notifs = []
        if len(notifs) > 0:
            print_header(module)
            fd.write("\n  notifications:\n")
            print_children(notifs, module, fd, '  ', npath,
                           'notification', depth, llen,
                           ctx.opts.tree_no_expand_uses,
                           prefix_with_modname=ctx.opts.modname_prefix)

        if ctx.opts.tree_print_groupings:
            section_delimiter_printed = False
            for m in mods:
                for g in m.search('grouping'):
                    print_header(module)
                    if not section_delimiter_printed:
                        fd.write('\n')
                        section_delimiter_printed = True
                    fd.write("  grouping %s:\n" % g.arg)
                    print_children(g.i_children, m, fd,
                                   '  ', path, 'grouping', depth, llen,
                                   ctx.opts.tree_no_expand_uses,
                                   prefix_with_modname=ctx.opts.modname_prefix)

        if ctx.opts.tree_print_yang_data:
            yds = module.search(('ietf-restconf', 'yang-data'))
            if len(yds) > 0:
                print_header(module)
                section_delimiter_printed = False
                for yd in yds:
                    if not section_delimiter_printed:
                        fd.write('\n')
                        section_delimiter_printed = True
                    fd.write("  yang-data %s:\n" % yd.arg)
                    print_children(yd.i_children, module, fd, '  ', path,
                                   'yang-data', depth, llen,
                                   ctx.opts.tree_no_expand_uses,
                                   prefix_with_modname=ctx.opts.modname_prefix)

        if ctx.opts.tree_print_structures:
            sxs = module.search(('ietf-yang-structure-ext', 'structure'))
            if len(sxs) > 0:
                if not printed_header:
                    print_header(module)
                section_delimiter_printed = False
                for sx in sxs:
                    if not section_delimiter_printed:
                        fd.write('\n')
                        section_delimiter_printed = True
                    fd.write("  structure %s:\n" % sx.arg)
                    print_children(sx.i_children, module, fd, '  ', path,
                                   'structure', depth, llen,
                                   ctx.opts.tree_no_expand_uses,
                                   prefix_with_modname=ctx.opts.modname_prefix)

            sxs = module.search(('ietf-yang-structure-ext',
                                 'augment-structure'))
            if len(sxs) > 0:
                if not printed_header:
                    print_header(module)
                section_delimiter_printed = False
                for sx in sxs:
                    if not section_delimiter_printed:
                        fd.write('\n')
                        section_delimiter_printed = True
                    fd.write("  augment-structure %s:\n" % sx.arg)
                    print_children(sx.i_children, module, fd, '  ', path,
                                   'structure', depth, llen,
                                   ctx.opts.tree_no_expand_uses,
                                   prefix_with_modname=ctx.opts.modname_prefix)


def unexpand_uses(i_children):
    res = []
    uses = []
    for ch in i_children:
        if hasattr(ch, 'i_uses'):
            # take first from i_uses, which means "closest" grouping
            g = ch.i_uses[0].arg
            if g not in uses:
                # first node from this uses
                uses.append(g)
                res.append(ch.i_uses[0])
        else:
            res.append(ch)
    return res

def print_path(pre, post, path, fd, llen):
    def print_comps(pre, p, is_first):
        line = pre + '/' + p[0]
        p = p[1:]
        if len(line) > llen:
            # too long, print it anyway; it won't fit next line either
            pass
        else:
            while len(p) > 0 and len(line) + 1 + len(p[0]) <= llen:
                if len(p) == 1 and len(line) + 1 + len(p[0]) + len(post) > llen:
                    # if this is the last component, ensure 'post' fits
                    break
                line += '/' + p[0]
                p = p[1:]
        if len(p) == 0:
            line += post
        line += '\n'
        fd.write(line)
        if len(p) > 0:
            if is_first:
                pre = ' ' * (len(pre) + 2) # indent next line
            print_comps(pre, p, False)

    line = pre + ' ' + path + post
    if llen is None or len(line) <= llen:
        fd.write(line + '\n')
    else:
        p = path.split('/')
        if p[0] == '':
            p = p[1:]
        pre += " "
        print_comps(pre, p, True)

def print_children(i_children, module, fd, prefix, path, mode, depth,
                   llen, no_expand_uses, width=0, prefix_with_modname=False):
    if depth == 0:
        if i_children:
            fd.write(prefix + '     ...\n')
        return
    def get_width(w, chs):
        for ch in chs:
            if ch.keyword in ['choice', 'case']:
                nlen = 3 + get_width(0, ch.i_children)
            else:
                if ch.i_module.i_modulename == module.i_modulename:
                    nlen = len(ch.arg)
                else:
                    nlen = len(ch.i_module.i_prefix) + 1 + len(ch.arg)
            if nlen > w:
                w = nlen
        return w

    if no_expand_uses:
        i_children = unexpand_uses(i_children)

    if width == 0:
        width = get_width(0, i_children)

    for ch in i_children:
        if ((ch.keyword == 'input' or ch.keyword == 'output') and
            len(ch.i_children) == 0):
            pass
        else:
            if (ch == i_children[-1] or
                (i_children[-1].keyword == 'output' and
                 len(i_children[-1].i_children) == 0)):
                # the last test is to detect if we print input, and the
                # next node is an empty output node; then don't add the |
                newprefix = prefix + '   '
            else:
                newprefix = prefix + '  |'
            if ch.keyword == 'input':
                mode = 'input'
            elif ch.keyword == 'output':
                mode = 'output'
            print_node(ch, module, fd, newprefix, path, mode, depth, llen,
                       no_expand_uses, width,
                       prefix_with_modname=prefix_with_modname)

def print_node(s, module, fd, prefix, path, mode, depth, llen,
               no_expand_uses, width, prefix_with_modname=False):

    line = "%s%s--" % (prefix[0:-1], get_status_str(s))

    brcol = len(line) + 4

    if s.i_module.i_modulename == module.i_modulename:
        name = s.arg
    else:
        if prefix_with_modname:
            name = s.i_module.i_modulename + ':' + s.arg
        else:
            name = s.i_module.i_prefix + ':' + s.arg
    flags = get_flags_str(s, mode)
    if s.keyword == 'list':
        name += '*'
        line += flags + " " + name
    elif s.keyword == 'container':
        p = s.search_one('presence')
        if p is not None:
            name += '!'
        line += flags + " " + name
    elif s.keyword  == 'choice':
        m = s.search_one('mandatory')
        if m is None or m.arg == 'false':
            line += flags + ' (' + name + ')?'
        else:
            line += flags + ' (' + name + ')'
    elif s.keyword == 'case':
        line += ':(' + name + ')'
        brcol += 1
    else:
        if s.keyword == 'leaf-list':
            name += '*'
        elif (s.keyword == 'leaf' and not hasattr(s, 'i_is_key')
              or s.keyword == 'anydata' or s.keyword == 'anyxml'):
            m = s.search_one('mandatory')
            if m is None or m.arg == 'false':
                name += '?'
        t = get_typename(s, prefix_with_modname)
        if t == '':
            line += "%s %s" % (flags, name)
        elif (llen is not None and
              len(line) + len(flags) + width+1 + len(t) + 4 > llen):
            # there's no room for the type name
            if (get_leafref_path(s) is not None and
                len(t) + brcol > llen):
                # there's not even room for the leafref path; skip it
                # 7 is len('leafref') - check if we can print it
                if len(line) + len(flags) + width+1 + 7 + 4 > llen:
                    line += "%s %s" % (flags, name)
                    fd.write(line + '\n')
                    line = prefix + ' ' * (brcol - len(prefix)) + ' leafref'
                else:
                    line += "%s %-*s   leafref" % (flags, width+1, name)
            else:
                line += "%s %s" % (flags, name)
                fd.write(line + '\n')
                line = prefix + ' ' * (brcol - len(prefix)) + ' ' + t
        else:
            line += "%s %-*s   %s" % (flags, width+1, name, t)

    if s.keyword == 'list':
        if s.search_one('key') is not None:
            keystr = " [%s]" % re.sub(r'\s+', ' ', s.search_one('key').arg)
            if (llen is not None and
                len(line) + len(keystr) > llen):
                fd.write(line + '\n')
                line = prefix + ' ' * (brcol - len(prefix))
            line += keystr
        else:
            line += " []"

    features = s.search('if-feature')
    featurenames = [f.arg for f in features]
    if hasattr(s, 'i_augment'):
        afeatures = s.i_augment.search('if-feature')
        featurenames.extend([f.arg for f in afeatures
                             if f.arg not in featurenames])

    if len(featurenames) > 0:
        fstr = " {%s}?" % ",".join(featurenames)
        if (llen is not None and len(line) + len(fstr) > llen):
            fd.write(line + '\n')
            line = prefix + ' ' * (brcol - len(prefix))
        line += fstr

    fd.write(line + '\n')
    if hasattr(s, 'i_children') and s.keyword != 'uses':
        if depth is not None:
            depth = depth - 1
        chs = s.i_children
        if path is not None and len(path) > 0:
            chs = [ch for ch in chs
                   if ch.arg == path[0]]
            path = path[1:]
        if s.keyword in ['choice', 'case']:
            print_children(chs, module, fd, prefix, path, mode, depth,
                           llen, no_expand_uses, width - 3,
                           prefix_with_modname=prefix_with_modname)
        else:
            print_children(chs, module, fd, prefix, path, mode, depth, llen,
                           no_expand_uses,
                           prefix_with_modname=prefix_with_modname)

def get_status_str(s):
    status = s.search_one('status')
    if status is None or status.arg == 'current':
        return '+'
    elif status.arg == 'deprecated':
        return 'x'
    elif status.arg == 'obsolete':
        return 'o'

def get_flags_str(s, mode):
    if mode == 'input':
        return "-w"
    elif s.keyword in ('rpc', 'action', ('tailf-common', 'action')):
        return '-x'
    elif s.keyword == 'notification':
        return '-n'
    elif s.keyword == 'uses':
        return '-u'
    elif s.i_config is True:
        return 'rw'
    elif s.i_config is False or mode in ('output', 'notification'):
        return 'ro'
    else:
        return ''

def get_leafref_path(s):
    t = s.search_one('type')
    if t is not None:
        if t.arg == 'leafref':
            return t.search_one('path')
    else:
        return None

def get_typename(s, prefix_with_modname=False):
    t = s.search_one('type')
    if t is not None:
        if t.arg == 'leafref':
            p = t.search_one('path')
            if p is not None:
                # Try to make the path as compact as possible.
                # Remove local prefixes, and only use prefix when
                # there is a module change in the path.
                target = []
                curprefix = s.i_module.i_prefix
                for name in p.arg.split('/'):
                    prefix, name = util.split_identifier(name)
                    if prefix is None or prefix == curprefix:
                        target.append(name)
                    else:
                        if prefix_with_modname:
                            if prefix in s.i_module.i_prefixes:
                                # Try to map the prefix to the module name
                                module_name, _ = s.i_module.i_prefixes[prefix]
                            else:
                                # If we can't then fall back to the prefix
                                module_name = prefix
                            target.append(module_name + ':' + name)
                        else:
                            target.append(prefix + ':' + name)
                        curprefix = prefix
                return "-> %s" % "/".join(target)
            else:
                # This should never be reached. Path MUST be present for
                # leafref type. See RFC6020 section 9.9.2
                # (https://tools.ietf.org/html/rfc6020#section-9.9.2)
                if prefix_with_modname:
                    prefix, name = util.split_identifier(t.arg)
                    if prefix is None:
                        # No prefix specified. Leave as is
                        return t.arg
                    else:
                        # Prefix found. Replace it with the module name
                        if prefix in s.i_module.i_prefixes:
                            # Try to map the prefix to the module name
                            module_name, _ = s.i_module.i_prefixes[prefix]
                        else:
                            # If we can't then fall back to the prefix
                            module_name = prefix
                        return module_name + ':' + name
                else:
                    return t.arg
        else:
            if prefix_with_modname:
                prefix, name = util.split_identifier(t.arg)
                if prefix is None:
                    # No prefix specified. Leave as is
                    return t.arg
                else:
                    # Prefix found. Replace it with the module name
                    if prefix in s.i_module.i_prefixes:
                        # Try to map the prefix to the module name
                        module_name, _ = s.i_module.i_prefixes[prefix]
                    else:
                        # If we can't then fall back to the prefix
                        module_name = prefix
                    return module_name + ':' + name
            else:
                return t.arg
    elif s.keyword == 'anydata':
        return '<anydata>'
    elif s.keyword == 'anyxml':
        return '<anyxml>'
    else:
        return ''
