"""uml output plugin
1) download plantuml.sourceforge.net/
2) Invoke with:
>pyang -f uml <file.yang> > <file.uml>
>java -jar plantuml.jar <file.uml>

3) result in img/module.png

For huge models Java might spit out memory exceptions, increase heap with e.g. -Xmx256m flag to java

"""
# TODO:
# -elements with same name at same level, we assume the path is unique
# cleanup choice and case with function

import optparse
import sys
import datetime
import re

from pyang import plugin
from pyang import error
from pyang import syntax
from pyang import statements
from pyang import util
from pyang.error import err_add


def pyang_plugin_init():
    plugin.register_plugin(UMLPlugin())

class UMLPlugin(plugin.PyangPlugin):
    def add_opts(self, optparser):
        optlist = [
            optparse.make_option("--uml-classes-only",
                                 action="store_true",
                                 dest="uml_classes_only",
                                 default=False,
                                 help="Generate UML with classes only, no attributes "),
            optparse.make_option("--uml-split-pages",
                                 dest="uml_pages_layout",
                                 help="Generate UML output split into pages (separate .png files), NxN, example 2x2 "),
            optparse.make_option("--uml-output-directory",
                                 dest="uml_outputdir",
                                 help="Put generated <modulename>.png or <title>.png file(s) in OUTPUTDIR (default img/) "),
            optparse.make_option("--uml-title",
                                 dest="uml_title",
                                 help="Set the title of the generated UML, including the output file name"),
            optparse.make_option("--uml-header",
                                 dest="uml_header",
                                 help="Set the page header of the generated UML"),
            optparse.make_option("--uml-footer",
                                 dest="uml_footer",
                                 help="Set the page footer of the generated UML. If not specified, a default footer will be generated"),
            optparse.make_option("--uml-long-identifiers",
                                 action="store_true",
                                 dest="uml_longids",
                                 default=False,
                                 help="Use the full schema identifiers for UML class names."),
            optparse.make_option("--uml-inline-groupings",
                                 action="store_true",
                                 dest="uml_inline",
                                 default=False,
                                 help="Inline groupings where they are used."),
            optparse.make_option("--uml-inline-augments",
                                 action="store_true",
                                 dest="uml_inline_augments",
                                 default=False,
                                 help="Inline augmentations where they are used."),
            optparse.make_option("--uml-description",
                                 action="store_true",
                                 dest="uml_descr",
                                 default=False,
                                 help="Include description of structural nodes in diagram."),
            optparse.make_option("--uml-no",
                                 dest="uml_no",
                                 default="",
                                 help="Suppress parts of the diagram. \nValid suppress values are: module, uses, leafref, identity, identityref, typedef, import, annotation, circles, stereotypes, prefix, footer, title. "
                                      "Annotations suppresses YANG constructs represented as annotations such as config statements for containers and module info. Module suppresses module box around the diagram and module information. " 
                                      "Prefix suppresses the the prefix in the name of packages. \nIf footer or title are selected, the options --uml-footer and --uml-title respectively will be ignored. \nExample --uml-no=circles,stereotypes,typedef,import"),
            optparse.make_option("--uml-truncate",
                                 dest="uml_truncate",
                                 default="",
                                 help="Leafref attributes and augment elements can have long paths making the classes too wide. \nThis option will only show the tail of the path. \nExample --uml-truncate=augment,leafref"),
            optparse.make_option("--uml-max-enums",
                                 dest="uml_max_enums",
                                 default="3",
                                 help="The maximum number of enumerated values to render"),
            optparse.make_option("--uml-max-bits",
                                 dest="uml_max_bits",
                                 help="The maximum number of bit values to render. If set also enables rendering of bits typedefs as a 'bits' class"),
            optparse.make_option("--uml-more-values",
                                 dest="uml_more_values",
                                 default="",
                                 help="Use an alternative to 'MORE' to indicate that there are more enumerated or bits values than are shown. \nValid value: ellipsis. \nNote that ellipsis is rendered as '...'. \nExample --uml-more-values=ellipsis"),
            optparse.make_option("--uml-filter",
                                 action="store_true",
                                 dest="uml_gen_filter_file",
                                 default=False,
                                 help="Generate filter file, comment out lines with '-' and use with option '--filter-file' to filter the UML diagram"),
            optparse.make_option("--uml-filter-file",
                                 dest="uml_filter_file",
                                 help="NOT IMPLEMENTED: Only paths in the filter file will be included in the diagram"),
            optparse.make_option("--uml-unbounded",
                                 dest="uml_unbounded",
                                 default="",
                                 help="Change how the unbounded upper limit multiplicity of relationships is rendered from the default 'N'. \nValid value: *. \nExample --uml-unbounded=* "),
            optparse.make_option("--uml-choice",
                                 dest="uml_choice",
                                 default="",
                                 help="Change how the choice statement is rendered from the default of a dotted line. \nValid values are one of: aggregation, composition, generalization, navigable-association, realization. \nExample --uml-choice=composition"),
            optparse.make_option("--uml-case",
                                 dest="uml_case",
                                 default="",
                                 help="Change how case statement is rendered from the default of a dotted line. \nValid values are one of: aggregation, composition, generalization, navigable-association, realization. \nExample --uml-case=generalization"),
            optparse.make_option("--uml-uses",
                                 dest="uml_uses",
                                 default="",
                                 help="Change how the uses statement is rendered from the default of a navigable association. \nValid values are one of: aggregation, composition, dependency. generalization, realization. \nThis option has no effect if option --uml-inline-groupings is selected. \nExample --uml-uses=dependency"),
            ]
        if hasattr(optparser, 'uml_opts'):
            g = optparser.uml_opts
        else:
            g = optparser.add_option_group("UML specific options")
            optparser.uml_opts = g
        g.add_options(optlist)

    def add_output_format(self, fmts):
        self.multiple_modules = True
        fmts['uml'] = self

    def pre_validate(self, ctx, modules):
        module = modules[0]
        self.mods = [module.arg] + [i.arg for i in module.search('include')]

    def emit(self, ctx, modules, fd):
        for epos, etag, eargs in ctx.errors:
            if ((epos.top is None or epos.top.arg in self.mods) and
                error.is_error(error.err_level(etag))):
                self.fatal("%s contains errors" % epos.top.arg)


        if ctx.opts.uml_pages_layout is not None:
            if re.match('[0-9]x[0-9]', ctx.opts.uml_pages_layout) is None:
                self.fatal("Illegal page split option %s, should be [0-9]x[0-9], example 2x2" % ctx.opts.uml_pages_layout)


        umldoc = uml_emitter(ctx)
        umldoc.emit(modules, fd)

    def fatal(self, exitCode=1):
        raise error.EmitError(self, exitCode)


class uml_emitter:
    key = ''
    unique = ''
    ctx_pagelayout = '1x1'
    ctx_outputdir = "img/"
    ctx_title_text = None
    ctx_fullpath = False
    ctx_classesonly = False
    ctx_description = False
    ctx_leafrefs = True
    ctx_uses = True
    ctx_identityrefs = True
    ctx_identities = True
    ctx_typedefs = True
    ctx_imports = True
    ctx_annotations = True
    ctx_circles = True
    ctx_stereotypes = True
    ctx_truncate_leafrefs = False
    ctx_truncate_augments = False
    ctx_inline_augments = False
    ctx_no_module = False
    ctx_unbounded_maxelem = "N"
    ctx_more_string = "MORE"

    ctx_filterfile = False
    ctx_usefilterfile = None
    groupings = dict()
    uses = []
    uses_as_string = dict()
    leafrefs = []
    filterpaths = []
    identities = []
    augments = []
    augmentpaths = []
    baseid = []
    thismod_prefix = ''
    _ctx = None
    post_strings = []
    end_strings = []
    module_prefixes = []
    leafref_classes = []

    choice_relation_symbol = ".."
    case_relation_symbol = ".."
    uses_relation_symbol = "-->"
    uses_relation_label = "uses"

    def __init__(self, ctx):
        self._ctx = ctx
        self.ctx_fullpath = ctx.opts.uml_longids
        self.ctx_description = ctx.opts.uml_descr
        self.ctx_classesonly = ctx.opts.uml_classes_only
        # output dir from option -D or default img/
        if ctx.opts.uml_outputdir is not None:
            self.ctx_outputdir = ctx.opts.uml_outputdir
            if self.ctx_outputdir[len(self.ctx_outputdir)-1] != '/':
                self.ctx_outputdir += '/'
        else:
            self.ctx_outputdir = 'img/'

        # split into pages ? option -s
        if ctx.opts.uml_pages_layout is not None:
            self.ctx_pagelayout = ctx.opts.uml_pages_layout

        # Title from option -t
        self.ctx_title_text = ctx.opts.uml_title

        self.ctx_inline_augments = ctx.opts.uml_inline_augments

        no = ctx.opts.uml_no.split(",")
        self.ctx_leafrefs = not "leafref" in no
        self.ctx_uses = not "uses" in no
        self.ctx_annotations = not "annotation" in no
        self.ctx_identityrefs = not "identityref" in no
        self.ctx_identities = not "identity" in no
        self.ctx_typedefs = not "typedef" in no
        self.ctx_imports = not "import" in no
        self.ctx_circles = not "circles" in no
        self.ctx_stereotypes = not "stereotypes" in no
        self.ctx_prefix = not "prefix" in no
        self.ctx_title = not "title" in no
        self.ctx_footer = not "footer" in no

        nostrings = ("module", "leafref", "uses", "annotation", "identityref", "typedef", "import", "circles", "stereotypes", "prefix", "footer", "title")
        if ctx.opts.uml_no != "":
            for no_opt in no:
                if no_opt not in nostrings:
                    sys.stderr.write("\"%s\" no valid argument to --uml-no=...,  valid arguments: %s \n" %(no_opt, nostrings))

        unbounded_strings = ("*")
        if ctx.opts.uml_unbounded != "":
            if ctx.opts.uml_unbounded in unbounded_strings:
                self.ctx_unbounded_maxelem = ctx.opts.uml_unbounded
            else:
                sys.stderr.write("\"%s\" no valid argument to --uml-unbounded-multiplcity=..., valid arguments (one only): %s \n" %(ctx.opts.uml_unbounded, unbounded_strings))

        relationship_strings = ("aggregation", "association", "composition", "generalization", "navigable-association", "realization")
        if ctx.opts.uml_choice != "":
            if ctx.opts.uml_choice in relationship_strings:
                if ctx.opts.uml_choice == 'generalization':
                    self.choice_relation_symbol = "<|--"
                elif ctx.opts.uml_choice == 'aggregation':
                    self.choice_relation_symbol = "o--"
                elif ctx.opts.uml_choice == 'association':
                    self.choice_relation_symbol = "--"
                elif ctx.opts.uml_choice == 'composition':
                    self.choice_relation_symbol = "*--"
                elif ctx.opts.uml_choice == 'navigable-association':
                    self.choice_relation_symbol = "-->"
                elif ctx.opts.uml_choice == 'realization':
                    self.choice_relation_symbol = "<|.."
            else:
                sys.stderr.write("\"%s\" no valid argument to --uml-choice=...,  valid arguments (one only): %s \n" %(ctx.opts.uml_choice, relationship_strings))
        if ctx.opts.uml_case != "":
            if ctx.opts.uml_case in relationship_strings:
                if ctx.opts.uml_case == 'generalization':
                    self.case_relation_symbol = "<|--"
                elif ctx.opts.uml_case == 'aggregation':
                    self.case_relation_symbol = "o--"
                elif ctx.opts.uml_case == 'association':
                    self.case_relation_symbol = "--"
                elif ctx.opts.uml_case == 'composition':
                    self.case_relation_symbol = "*--"
                elif ctx.opts.uml_case == 'navigable-association':
                    self.case_relation_symbol = "-->"
                elif ctx.opts.uml_case == 'realization':
                    self.case_relation_symbol = "<|.."
            else:
                sys.stderr.write("\"%s\" no valid argument to --uml-case=...,  valid arguments (one only): %s \n" %(ctx.opts.uml_case, relationship_strings))
        uses_strings = ("aggregation", "association", "composition", "dependency", "generalization", "realization")
        if ctx.opts.uml_uses != "":
            if ctx.opts.uml_uses in uses_strings:
                if ctx.opts.uml_uses == 'generalization':
                    self.uses_relation_symbol = "--|>"
                elif ctx.opts.uml_uses == 'aggregation':
                    self.uses_relation_symbol = "o--"
                elif ctx.opts.uml_uses == 'association':
                    self.uses_relation_symbol = "--"
                elif ctx.opts.uml_uses == 'composition':
                    self.uses_relation_symbol = "*--"
                elif ctx.opts.uml_uses == 'dependency':
                    self.uses_relation_symbol = "..>"
                    self.uses_relation_label = "<<uses>>"
                elif ctx.opts.uml_uses == 'realization':
                    self.uses_relation_symbol = "..|>"
            else:
                sys.stderr.write("\"%s\" no valid argument to --uml-uses=...,  valid arguments (one only): %s \n" %(ctx.opts.uml_uses, uses_strings))

        self.ctx_filterfile = ctx.opts.uml_gen_filter_file

        self.ctx_truncate_augments = "augment" in ctx.opts.uml_truncate.split(",")
        self.ctx_truncate_leafrefs = "leafref" in ctx.opts.uml_truncate.split(",")
        self.ctx_no_module = "module" in no

        truncatestrings = ("augment", "leafref")
        if ctx.opts.uml_truncate != "":
            for trunc in ctx.opts.uml_truncate.split(","):
                if trunc not in truncatestrings:
                    sys.stderr.write("\"%s\" no valid argument to --uml-truncate=...,  valid arguments: %s \n" %(trunc, truncatestrings))

        if ctx.opts.uml_filter_file is not None:
            try:
                self.ctx_usefilterfile = open(ctx.opts.uml_filter_file, "r")
                self.filterpaths = self.ctx_usefilterfile.readlines()
                self.ctx_usefilterfile.close()
            except IOError:
                raise error.EmitError("Filter file %s does not exist" %ctx.opts.uml_filter_file, 2)

        more_strings = ("ellipsis")
        if ctx.opts.uml_more_values in more_strings:
            if ctx.opts.uml_more_values == "ellipsis":
                self.ctx_more_string = "..."
        else:
            sys.stderr.write("\"%s\" no valid argument to --uml-more=...,  valid argument: %s \n" %(ctx.opts.uml_more_values, more_strings))

    def emit(self, modules, fd):
        title = ''
        if self.ctx_title_text is not None:
            title = self.ctx_title_text
        else:
            for m in modules:
                title += m.arg + '_'
            title = title[:len(title)-1]
            title = title[:32]
        for m in modules:
            prefix = m.search_one('prefix')
            if prefix is not None:
                self.module_prefixes.append(prefix.arg)

        if not self.ctx_filterfile:
            self.emit_uml_header(title, fd)

        for module in modules:
            pre = module.search_one('prefix')
            if pre is not None:
                self.thismod_prefix = pre.arg
            if not self.ctx_no_module:
                self.emit_module_header(module, fd)
            self.emit_module_class(module, fd)
            for s in module.substmts:
                self.emit_stmt(module, s, fd)

            if not self.ctx_filterfile:
                self.post_process_module(module, fd)
        if not self.ctx_filterfile:
            self.post_process_diagram(fd)


        if not self.ctx_filterfile:
            self.emit_uml_footer(module, fd)


    def emit_stmt(self, mod, stmt, fd):
        # find  good UML roots

        if stmt.keyword == 'container':
            self.emit_container(mod, stmt, fd)
            for s in stmt.substmts:
                self.emit_child_stmt(stmt, s, fd)

        elif stmt.keyword == 'augment' and not self.ctx_filterfile:
            # HERE
            a = stmt.arg
            if self.ctx_truncate_augments:
                a = '...' + a[a.rfind('/'):]

            if not self.ctx_inline_augments:
                fd.write('class \"%s\" as %s << (A,CadetBlue) augment>>\n' %(a, self.full_path(stmt)))
            # ugly, the augmented elemented is suffixed with _ in emit_header
            # fd.write('_%s <-- %s : augment \n' %(self.full_path(stmt), self.full_path(stmt)))

            # also, since we are the root, add the module as parent
            if self.full_path(stmt) not in self.augmentpaths and not self.ctx_inline_augments:
                fd.write('%s *--  %s \n' %(self.full_path(mod), self.full_path(stmt)))
                self.augmentpaths.append(self.full_path(stmt))

            # MEF
            prefix, _ = util.split_identifier(stmt.arg)
            # FIXME: previous code skipped first char, possibly in error
            prefix = self.thismod_prefix if prefix is None else prefix[1:]

            node = statements.find_target_node(self._ctx, stmt, True)
            if node is not None and prefix in self.module_prefixes and not self.ctx_inline_augments:
                # sys.stderr.write("Found augment target : %s , %s \n" %(stmt.arg, self.full_path(node)))
                self.augments.append(self.full_path(stmt) + '-->' + self.full_path(node) + ' : augments' + '\n')
            else:
                # sys.stderr.write("Not Found augment target : %s \n" %(stmt.arg))
                pass

            if self.ctx_inline_augments and node is not None:
                # Emit augment target, in case that module was given as input this results in duplicate, but plantUML do not care
                # The False flag stops emit_child from continuing iterating further down the tree
                self.emit_child_stmt(node.parent, node, fd, False)
                for s in stmt.substmts:
                    s.parent = node
                    self.emit_child_stmt(node, s, fd)

            else:
                for s in stmt.substmts:
                    self.emit_child_stmt(stmt, s, fd)

        elif stmt.keyword == 'list':
            self.emit_list(mod, stmt, fd)
            for s in stmt.substmts:
                self.emit_child_stmt(stmt, s, fd)

        elif stmt.keyword == 'grouping' and not self._ctx.opts.uml_inline:
            self.emit_grouping(mod, stmt, fd, True)

        elif stmt.keyword == 'choice':
            if not self.ctx_filterfile:
                fd.write('class \"%s\" as %s <<choice>> \n' % (self.full_display_path(stmt), self.full_path(stmt)))
                fd.write('%s %s %s : choice \n' % (self.full_path(mod), self.choice_relation_symbol, self.full_path(stmt)))
            # sys.stderr.write('in choice %s \n', self.full_path(mod))
            for children in stmt.substmts:
                self.emit_child_stmt(stmt, children, fd)

        elif stmt.keyword == 'case':
            if not self.ctx_filterfile:
                fd.write('class \"%s\" as %s \n' %(self.full_display_path(stmt), self.full_path(stmt)))
                fd.write('%s %s %s  : choice\n' % (self.full_path(mod), self.case_relation_symbol, self.full_path(stmt)))
            # sys.stderr.write('in case %s \n', full_path(mod))
            for children in mod.substmts:
                self.emit_child_stmt(stmt, children, fd)

        elif stmt.keyword == 'identity':
            self.emit_identity(mod, stmt, fd)

        if not self.ctx_classesonly and not self.ctx_filterfile:
            if stmt.keyword == 'typedef':
                self.emit_typedef(mod, stmt,fd)
            elif stmt.keyword == 'rpc':
                self.emit_action(mod, stmt,fd)
            elif stmt.keyword == 'notification':
                self.emit_notif(mod, stmt,fd)
                for s in stmt.substmts:
                    self.emit_child_stmt(stmt, s, fd)
            elif stmt.keyword == 'feature':
                self.emit_feature(mod,stmt, fd)
            elif stmt.keyword == 'deviation':
                self.emit_deviation(mod,stmt, fd)


        # go down one level and search for good UML roots
        # I think we have covered all....
        # else:
            # sys.stderr.write('skipping top level: %s:%s\n' % (stmt.keyword, stmt.arg))
            # for s in stmt.substmts:
              # emit_stmt(mod, s, fd)


    def emit_child_stmt(self, parent, node, fd, cont = True):
        keysign = ''
        keyprefix = ''
        uniquesign = ''

        # manage shorthand omitting case in choice
        if parent.keyword == 'choice' and node.keyword in ('container', 'leaf', 'leaf-list', 'list'):
            # create fake parent statement.keyword = 'case' statement.arg = node.arg
            newparent = statements.Statement(parent, parent, None, 'case', node.arg)
            fd.write('class \"%s\" as %s <<case>> \n' % (node.arg, self.full_path(newparent)))
            fd.write('%s %s %s : choice %s\n' % (self.full_path(parent), self.case_relation_symbol, self.full_path(newparent), node.parent.arg))

            parent = newparent


        if node.keyword == 'container':
            self.emit_container(parent, node, fd)
            if cont:
                for children in node.substmts:
                    self.emit_child_stmt(node, children, fd)
        elif node.keyword == 'grouping' and not self._ctx.opts.uml_inline:
            self.emit_grouping(parent, node, fd)

        elif node.keyword == 'list':
            self.emit_list(parent, node, fd)
            if cont:
                for children in node.substmts:
                    self.emit_child_stmt(node, children, fd)

        elif node.keyword == 'choice':
            if not self.ctx_filterfile:
                fd.write('class \"%s\" as %s <<choice>> \n' % (self.full_display_path(node), self.full_path(node)))
                fd.write('%s %s %s : choice \n' % (self.full_path(parent), self.choice_relation_symbol, self.full_path(node)))
            if cont:
                for children in node.substmts:
                    # try pointing to parent
                    self.emit_child_stmt(node, children, fd)
                    # self.emit_child_stmt(parent, children, fd)
        elif node.keyword == 'case':
            # sys.stderr.write('in case \n')
            if not self.ctx_filterfile:
                fd.write('class \"%s\" as %s <<case>>\n' %(self.full_display_path(node), self.full_path(node)))
                fd.write('%s %s %s  : choice %s\n' % (self.full_path(parent), self.case_relation_symbol, self.full_path(node), node.parent.arg))

            if cont:
                for children in node.substmts:
                    self.emit_child_stmt(node, children, fd)
        elif node.keyword == 'uses':
            if not self.ctx_filterfile and not self._ctx.opts.uml_inline:
                fd.write('%s : %s {uses} \n' %(self.full_path(parent), node.arg))
            if not self._ctx.opts.uml_inline:
                self.emit_uses(parent, node)
            if hasattr(node, 'i_grouping') and (self._ctx.opts.uml_inline) and cont:
                grouping_node = node.i_grouping
                if grouping_node is not None:
                    # inline grouping here
                    # sys.stderr.write('Found  target grouping to inline %s %s \n' %(grouping_node.keyword, grouping_node.arg))
                    for children in grouping_node.substmts:
                        # make the inlined parent to parent rather then the grouping to make full path unique
                        children.parent = parent
                        self.emit_child_stmt(parent, children, fd)

        # moved stuff below here in order to include annotations for classes-only
        elif node.keyword == 'description' and self.ctx_description:
            # make plain ASCII
            descrstr = ''.join([x for x in node.arg if ord(x) < 128])
            self.annotate_node(parent, descrstr, fd)
        elif node.keyword == 'config':
            self.annotate_node(parent, "<b>Config = </b>" + node.arg, fd)
        elif node.keyword == 'must':
            self.emit_must(parent, node, fd)
        elif node.keyword == ('tailf-common', 'hidden'):
            self.annotate_node(parent, "<b>Hidden </b>" + node.arg, fd)
        elif node.keyword[1] == 'servicepoint':
            self.annotate_node(parent, "<b>FastMap SERVICE: </b>" + node.arg, fd)
            # self.lollipop_node(parent, node.arg, fd)
        elif node.keyword == 'presence':
            self.annotate_node(parent, "<b>Presence: </b>" + node.arg, fd)
        elif node.keyword == 'when':
            self.annotate_node(parent, "<b>When: </b>" + node.arg, fd)
        elif node.keyword == 'status':
            self.annotate_node(parent, "<b>Status: </b>" + node.arg, fd)
        elif node.keyword == 'if-feature':
            self.annotate_node(parent, "<b>if-feature: </b>" + node.arg, fd)


        if not self.ctx_classesonly and not self.ctx_filterfile:
            if node.keyword == 'leaf':
                if node.arg in self.key: # matches previously found key statement
                    keysign = ' {key}'
                    keyprefix = '+'
                if node.arg in self.unique: # matches previously found unique statement
                    keysign = ' {unique}'
                # fd.write('%s : %s%s %s %s\n' %(full_path(parent), keysign, make_plantuml_keyword(node.arg), typestring(node), attribs(node) ))
                typestring = self.typestring(node).replace("\n", " ")
                fd.write('%s : %s%s%s %s %s\n' %(self.full_path(parent), keyprefix, node.arg + ' : ', typestring, keysign, self.attribs(node) ))
                self.emit_must_leaf(parent, node, fd)
            elif node.keyword == 'leaf-list':
                fd.write('%s : %s %s %s\n' %(self.full_path(parent), node.arg, '[]: ' + self.typestring(node), self.attribs(node)) )
                self.emit_must_leaf(parent, node, fd)
            elif node.keyword == 'notification':
                self.emit_notif(parent, node, fd)
                if cont:
                    for children in node.substmts:
                        self.emit_child_stmt(node, children, fd)
            elif node.keyword in ['action', ('tailf-common', 'action')]:
                self.emit_action(parent, node, fd)
            elif node.keyword == ('tailf-common', 'callpoint'):
                fd.write('%s : callpoint:%s()\n' %(self.full_path(parent), node.arg) )
            elif node.keyword == ('tailf-common', 'cdb-oper'):
                fd.write('%s : cdboper()\n' %self.full_path(parent))
            elif node.keyword == ('anyxml'):
                fd.write('%s : %s anyxml \n' %(self.full_path(parent), node.arg))
            elif node.keyword == 'key':
                self.key = node.arg.split(" ") # multiple keys, make list of every key
            elif node.keyword == 'unique':
                self.unique = node.arg.split(" ") # multiple keys, make list of every key
            # else:  probably unknown extension
                # fd.write('%s : %s %s' %(self.full_path(parent), node.keyword, node.arg))

        # fd.write('\n')

    def emit_uml_header(self, title, fd):
        fd.write('\'Download plantuml from http://plantuml.sourceforge.net/ \n')
        fd.write('\'Generate png with java -jar plantuml.jar <file> \n')
        fd.write('\'Output in img/<module>.png \n')
        fd.write('\'If Java spits out memory error increase heap size with java -Xmx1024m  -jar plantuml.jar <file> \n')


        fd.write('@startuml %s%s.png \n' %(self.ctx_outputdir, title))

        fd.write('hide empty fields \n')
        fd.write('hide empty methods \n')

        fd.write('hide <<case>> circle\n')
        fd.write('hide <<augment>> circle\n')
        fd.write('hide <<choice>> circle\n')
        fd.write('hide <<leafref>> stereotype\n')
        fd.write('hide <<leafref>> circle\n')

        if not self.ctx_circles:
            fd.write('hide circles \n')
        if not self.ctx_stereotypes:
            fd.write('hide stereotypes \n')



        # split into pages ? option -s
        fd.write('page %s \n' %self.ctx_pagelayout)

        if self.ctx_title:
            fd.write('Title %s \n' %title)

        if self._ctx.opts.uml_header is not None:
            fd.write('center header\n <size:48> %s </size>\n endheader \n' %self._ctx.opts.uml_header)


    def emit_module_header(self, module, fd):
        # print imported modules as packages
        if self.ctx_imports:
            imports = module.search('import')
            for i in imports:
                #pre = self.make_plantuml_keyword((i.search_one('prefix')).arg)
                #pkg = self.make_plantuml_keyword(i.arg)
                #fd.write('package %s.%s \n' %(pre, pkg))
                pre = i.search_one('prefix').arg
                pkg = i.arg
                if self.ctx_prefix :
                    fd.write('package \"%s:%s\" as %s_%s { \n' % (pre, pkg, self.make_plantuml_keyword(pre), self.make_plantuml_keyword(pkg)))
                else:
                    fd.write('package \"%s\" as %s_%s { \n' % (pkg, self.make_plantuml_keyword(pre),self.make_plantuml_keyword(pkg)))

                # search for augments and place them in correct package
                ## augments = module.search('augment')
                ## if augments:
                ##     # remove duplicates
                ##     augments = list(set(augments))
                ## for a in augments:
                ##     a_pre = self.first_component(a.arg)
                ##     a_pkg = ''
                ##     if pre == a_pre: # augments element in this module, ugly trick use _suffix here
                ##             fd.write('class \"%s\" as %s \n' %(a.arg, self.make_plantuml_keyword(a.arg)))
                fd.write('} \n')

        bt = module.search_one('belongs-to')
        if bt is not None:
            # Wrap parent module around this sub-module
            fd.write('package %s {\n' % bt.arg)
            self.post_strings.append('} \n')



        # pkg name for this module
        #this_pkg = self.make_plantuml_keyword(module.search_one('prefix').arg) + '.' + self.make_plantuml_keyword(module.arg)
        pkg = module.arg

        # define a empty package for the module
        # this ensures that PlantUML knows that its keyword represents a package and not a class when referenced before the main definition of the package within the Plant UML code,
        # e.g., by the note definition that follows below
        if self.ctx_prefix:
            fd.write('package \"%s:%s\" as %s_%s { \n' %(self.thismod_prefix, pkg, self.make_plantuml_keyword(self.thismod_prefix), self.make_plantuml_keyword(pkg)))
        else:
            fd.write('package \"%s\" as %s_%s { \n' % (pkg, self.make_plantuml_keyword(self.thismod_prefix), self.make_plantuml_keyword(pkg)))
        fd.write('} \n')

        # print package for this module and a class to represent module (notifs and rpcs)
        # print module info as note
        if self.ctx_annotations:
            fd.write('note top of %s_%s : ' %(self.make_plantuml_keyword(self.thismod_prefix), self.make_plantuml_keyword(pkg)))
            ns = module.search_one('namespace')
            if ns is not None:
                fd.write('<b>Namespace: </b> %s \\n' % ns.arg)

            if  self.thismod_prefix is not None:
                fd.write('<b>Prefix: </b> %s \\n' % self.thismod_prefix)

            bt = module.search_one('belongs-to')
            if bt is not None:
                fd.write('<b>Belongs-to: </b> %s \\n' % bt.arg)

            if module.search_one('organization'):
                o = module.search_one('organization').arg
                o = o.replace('\n', ' \\n')
                fd.write('<b>Organization : </b>\\n%s \\n' % o)

            if module.search_one('contact'):
                c = module.search_one('contact').arg
                c = c.replace('\n', ' \\n')
                fd.write('<b>Contact : </b>\\n%s \\n' % c)

            if module.search_one('description')  and (self.ctx_description):
                d = module.search_one('description').arg
                d = d.replace('\n', ' \\n')
                fd.write('<b>Description : </b>\\n%s \\n' % d)

            if module.search_one('revision'):
                fd.write('<b>Revision : </b> %s \\n' % module.search_one('revision').arg)
            fd.write('\n')

        # This package
        if self.ctx_prefix:
            fd.write('package \"%s:%s\" as %s_%s { \n' %(self.thismod_prefix, pkg, self.make_plantuml_keyword(self.thismod_prefix), self.make_plantuml_keyword(pkg)))
        else:
            fd.write('package \"%s\" as %s_%s { \n' %(pkg, self.make_plantuml_keyword(self.thismod_prefix), self.make_plantuml_keyword(pkg)))

        includes = module.search('include')
        for inc in includes:
            fd.write('package \"%s\" as %s { \n' %(inc.arg, self.make_plantuml_keyword(inc.arg)))
            fd.write('}\n')

    def emit_module_class(self, module, fd):
        fd.write('class \"%s\" as %s << (M, #33CCFF) module>> \n' %(self.full_display_path(module), self.full_path(module)))



    def emit_uml_footer(self, module, fd):
        if self.ctx_footer:
            if self._ctx.opts.uml_footer is not None:
                fd.write('center footer\n <size:24> %s </size>\n endfooter \n' %self._ctx.opts.uml_footer)
            else:
                now = datetime.datetime.now()
                fd.write('center footer\n <size:20> UML Generated : %s </size>\n endfooter \n' %now.strftime("%Y-%m-%d %H:%M"))

        fd.write('@enduml \n')

    def annotate_node(self, node, note, fd):
        if self.ctx_annotations:
            fd.write('note bottom of %s\n' %(self.full_path(node)) )
            fd.write('%s\n' %note)
            fd.write('end note \n')

    def lollipop_node(self, node , text, fd):
        fd.write("%s ()-- %s \n" %(text,self.full_path(node)))


    def emit_container(self, parent, node, fd):
        presence = node.search_one("presence")
        if presence is not None:
            cardinality = "0..1"
        else:
            cardinality = "1"

        if not self.ctx_filterfile:
        # and (not self.ctx_usefilterfile or self.full_path(node) in self.filterpaths):
            fd.write('class \"%s\" as  %s <<container>> \n' %(self.full_display_path(node), self.full_path(node)))
            fd.write('%s *-- \"%s\" %s \n' %(self.full_path(parent), cardinality, self.full_path(node)))
        else:
            fd.write(self.full_path(node) + '\n')



    def emit_list(self, parent, node, fd):
        if not self.ctx_filterfile:
            fd.write('class \"%s\" as %s << (L, #FF7700) list>> \n' %(self.full_display_path(node), self.full_path(node)))
            minelem = '0'
            maxelem = self.ctx_unbounded_maxelem
            oby = ''
            mi = node.search_one('min-elements')
            if mi is not None:
                minelem = mi.arg
            ma = node.search_one('max-elements')
            if ma is not None:
                maxelem = ma.arg
            orderedby = node.search_one('ordered-by')
            if orderedby is not None:
                oby = ': ordered-by : ' + orderedby.arg
            fd.write('%s *-- \"%s..%s\" %s %s\n' %(self.full_path(parent), minelem, maxelem, self.full_path(node), oby))
        else:
            fd.write(self.full_path(node) + '\n')

    def emit_identity(self, mod, stmt, fd):
        if self.ctx_identities:
            # add module prefix to ensure global uniqueness across modules
            identity = self.thismod_prefix + ':' + stmt.arg
            keyword = self.make_plantuml_keyword(identity)+'_identity'
            self.post_strings.append('class \"%s\" as %s << (I,Silver) identity>> \n' %(self.full_display_path(stmt), keyword))
            if identity not in self.identities:
                self.identities.append(identity)
            base = stmt.search_one('base')
            if base is not None:
                # if base does not include prefix, add prefix of current module
                baseid = base.arg
                if ':' not in baseid:
                    baseid = self.thismod_prefix+':'+baseid
                if baseid not in self.baseid:
                    self.baseid.append(baseid)
                self.post_strings.append('%s <|-- %s \n' %(self.make_plantuml_keyword(baseid)+'_identity', keyword))


    def emit_feature(self, parent, feature, fd):
        fd.write('%s : %s \n' %(self.full_path(parent), 'feature : ' + feature.arg) )

    def emit_deviation(self, parent, deviation, fd):
        fd.write('%s : %s \n' %(self.full_path(parent), 'deviation : ' + deviation.arg) )

    def emit_action(self, parent, action, fd):
        fd.write('%s : %s(' %(self.full_path(parent), action.arg) )
        # pretty ugly, but unlike for rpc and notifs we do not want to unfold a complete UML structure
        # rather a in out param list
        for params in action.substmts:
            if params.keyword == 'input':
                inputs = params.search('leaf')
                inputs += params.search('leaf-list')
                inputs += params.search('list')
                inputs += params.search('container')
                inputs += params.search('anyxml')
                inputs += params.search('uses')
                # inputs = root_elems(params)
                for i in inputs:
                    fd.write(' in: %s' %(self.make_plantuml_keyword(i.arg)) )
            if params.keyword == 'output':
                outputs = params.search('leaf')
                outputs += params.search('leaf-list')
                outputs += params.search('list')
                outputs += params.search('container')
                outputs += params.search('anyxml')
                outputs += params.search('uses')
                # outputs = root_elems(params)
                for o in outputs:
                    fd.write(' out: %s' %(self.make_plantuml_keyword(o.arg)) )
        fd.write(')\n')

        for params in action.substmts:
            use = params.search('uses')
            for u in use:
                self.emit_uses(parent, u)
               # fd.write('%s --> %s : uses \n' %(full_path(parent), full_path(u)))
               # p = full_path(parent)
               # us =  make_plantuml_keyword(u.arg)
               # uses.append([p,us])

    def emit_typedef(self, m, t, fd):
        if self.ctx_typedefs:
            keyword = self.make_plantuml_keyword(self.thismod_prefix) + '_' + self.make_plantuml_keyword(t.arg) + '_typedef'
            e = t.search_one('type')
            if e.arg == 'enumeration':
                # enum_name = self.full_path(t, False)
                fd.write('enum \"%s\" as %s <<enumeration>> {\n' %(t.arg, keyword))
                for enums in e.substmts[:int(self._ctx.opts.uml_max_enums)]:
                    fd.write('%s\n' %enums.arg)
                if len(e.substmts) > int(self._ctx.opts.uml_max_enums):
                    fd.write('%s\n' %(self.ctx_more_string))
                fd.write("}\n")
            elif e.arg == 'bits' and self._ctx.opts.uml_max_bits is not None:
                fd.write(
                    'class \"%s\" as %s << (B, Khaki) bits>> {\n' % (
                    t.arg, self.full_path(t)))
                for bits in e.substmts[
                             :int(self._ctx.opts.uml_max_bits)]:
                    fd.write('%s\n' % bits.arg)
                if len(e.substmts) > int(self._ctx.opts.uml_max_bits):
                    fd.write('%s\n' %(self.ctx_more_string))
                fd.write("}\n")
            else:
                fd.write('class \"%s\" as %s << (T, YellowGreen) typedef>>\n' %(t.arg, keyword))
                fd.write('%s : %s\n' %(keyword, self.typestring(t)))


    def emit_notif(self, parent, node, fd):
        # ALTERNATIVE 1
        # notif as class stereotype, ugly, but easier to layout params
        fd.write('class \"%s\" as %s << (N,#00D1B2) notification>> \n' % (self.full_display_path(node), self.full_path(node)))
        fd.write('%s -- %s : notification \n' % (self.make_plantuml_keyword(self.full_path(parent)), self.full_path(node)))
        # for params in node.substmts:
        #    self.emit_child_stmt(node, params, fd)

        # ALTERNATIVE 2
        # notif as oper, better, but hard to layout params
        #fd.write('%s : notif:%s()\n' %(make_plantuml_keyword(module), make_plantuml_keyword(stmt.arg)) )
        #for params in stmt.substmts:
        #    emit_child_stmt(stmt, params, fd)

    def emit_uses(self, parent, node):
        p = self.full_path(parent)
        # MEF
        # u =  self.make_plantuml_keyword(node.arg)
        u =  self.make_plantuml_keyword(self.grouping_name(node.arg))
        # MEF
        # sys.stderr.write('Uses : %s %s \n' %(p,u))
        self.uses.append([p,u])
        self.uses_as_string[u] = node.arg

    def emit_grouping(self, module, stmt, fd, glob = False):
        if not self.ctx_filterfile:
            # MEF
            # When referenced from this module
            self.groupings[self.make_plantuml_keyword(self.grouping_name(stmt.arg))] = (self.full_path(stmt))
            # when reference from this other modules
            self.groupings[self.make_plantuml_keyword(self.grouping_name(self.thismod_prefix + ':' + stmt.arg))] = (self.full_path(stmt))
            # sys.stderr.write('Grouping : %s %s \n' %(self.make_plantuml_keyword(self.grouping_name(stmt.arg)),  self.full_path(stmt)))
            if glob: # indicate grouping visible outside module
                fd.write('class \"%s\" as %s <<(G,Lime) grouping>> \n' %(self.full_display_path(stmt), self.full_path(stmt)))
            else:
                fd.write('class \"%s\" as %s <<(G,Red) grouping>> \n' %(self.full_display_path(stmt), self.full_path(stmt)))
            # sys.stderr.write('emit grouping : %s\n' %(self.full_path(stmt)))
            # Groupings are not really part of the schema tree
            # fd.write('%s --  %s \n' %(self.full_path(module), self.full_path(stmt)))
        else:
            fd.write(self.full_path(stmt) + '\n')
        for children in stmt.substmts:
            self.emit_child_stmt(stmt, children, fd)

    def attribs(self, node):
        # use UML attribute properties for various YANG leaf elements
        attribs = ''

        default = node.search_one('default')
        if default is not None:
            attribs = attribs + ' = ' + default.arg +' '

        mandatory =  node.search_one('mandatory')
        if mandatory is not None:
            if mandatory.arg == 'true':
                attribs = attribs + ' {mandatory}'

        units = node.search_one('units')
        if units is not None:
            attribs = attribs + ' {' + units.arg + '}'

        orderedby = node.search_one('ordered-by)')
        if orderedby is not None:
            attribs = attribs + ' {ordered-by:' + orderedby.arg + '}'

        status = node.search_one('status')
        if status is not None:
            attribs = attribs + ' {' + status.arg + '}'

        config = node.search_one('config')
        if config is not None:
            attribs = attribs + ' {Config : ' + config.arg + '}'

        feature = node.search_one('if-feature')
        if feature is not None:
            attribs = attribs + ' {if-feature : ' + feature.arg + '}'

        return attribs

    def typestring(self, node):
        t = node.search_one('type')
        s = t.arg
        if t.arg == 'enumeration':
            s = s + ' : {'
            for enums in t.substmts[:3]:
                s = s + enums.arg + ','
            if len(t.substmts) > 3:
                s = s + "..."
            s = s + '}'
        elif t.arg == 'leafref':
            # sys.stderr.write('in leafref \n')
            s = s + ' : '
            p = t.search_one('path')
            if p is not None:
                # inthismodule, n = self.find_target_node(p)
                leafrefkey = p.arg
                leafrefkey =  leafrefkey[leafrefkey.rfind("/")+1:]
                leafrefparent = p.arg
                leafrefparent = leafrefparent[0:(leafrefparent.rfind("/"))]

                # shorten leafref attribute stuff here....
                if self.ctx_truncate_leafrefs:
                    s = s + '...' + leafrefkey
                else:
                    s = s + p.arg

                # leafrefs might contain functions like current and deref wich makes PlantUML turn it into
                # methods. Replace () with {}
                s = s.replace('(', '{')
                s = s.replace(')', '}')

                if node.i_leafref_ptr is not None:
                    target_node = node.i_leafref_ptr[0]
                else:
                    target_node = None

                if target_node is not None:

                    if node.keyword == 'typedef':
                        source_keyword = self.make_plantuml_keyword(self.thismod_prefix) + '_' + self.make_plantuml_keyword(node.arg) + '_typedef'
                    else:
                        source_keyword = self.full_path(node.parent)

                    target_prefix, _ = util.split_identifier(leafrefkey)
                    # FIXME: previous code skipped first char, possibly in error
                    if target_prefix is None:
                        target_prefix = self.thismod_prefix

                    # if target node (last node in path) is located in the list of input modules, a relation to the target class can be created
                    if target_prefix in self.module_prefixes:
                        # if the relation is internal to this module append to leafrefs else append to end of diagram outside the scope of any input module
                        target_keyword = self.full_path(target_node.parent)
                        if target_prefix == self.thismod_prefix:
                            self.leafrefs.append(source_keyword + '-->' + '"' + leafrefkey + '"' + target_keyword + ': ' + node.arg + '\n')
                        else:
                            self.end_strings.append(source_keyword + '-->' + '"' + leafrefkey + '"' + target_keyword + ': ' + node.arg + '\n')
                    else:
                        # no target within input modules, so create a class as placeholder
                        target_keyword = self.full_path(target_node.parent) + '_leafref'
                        # add a class to represent the target of the leafref, if not already previously created during processing of this module
                        if target_keyword not in self.leafref_classes:
                            self.post_strings.append('class \"%s\" as %s <<leafref>> \n' %(leafrefparent, target_keyword))
                            self.leafref_classes.append(target_keyword)
                        self.leafrefs.append(source_keyword + '-->' + '"' + leafrefkey + '"' + target_keyword + ': ' + node.arg + '\n')
                        sys.stderr.write("Info: Leafref %s outside diagram. Prefix = %s\n" %(p.arg, target_prefix))

                else:
                    sys.stderr.write("Info: Did not find leafref target %s\n" %p.arg)
                #if n is not None and (inthismodule):
                    # sys.stderr.write('leafref %s : target %s \n' %(p.arg, full_path(n)))
                    # sys.stderr.write('in this module %s : \n' %inthismodule)
                    # self.leafrefs.append(self.full_path(node.parent) + '-->' + '"' + leafrefkey + '"' + self.full_path(n.parent) + ': ' + node.arg + '\n')
                #elif n is not None and not inthismodule:
                    # sys.stderr.write('in this module %s : \n' %inthismodule)
                    # self.leafrefs.append('class \"%s\" as %s <<(L, Red)>>\n' %(leafrefparent, self.full_path(n.parent)))
                    # self.leafrefs.append('%s : %s\n' %(self.full_path(n.parent), leafrefkey))
                    # self.leafrefs.append(self.full_path(node.parent) + '-->' + '"' + leafrefkey + '"' + self.full_path(n.parent) + ': ' + node.arg + '\n')
        elif t.arg == 'identityref':
            b = t.search_one('base')
            if b is not None:
                s = s + ' {' + b.arg + '}'
                if self.ctx_identityrefs and self.ctx_identities:
                    baseid = b.arg
                    if ':' not in baseid:
                        # if no prefix found, it must be defined in this module, so add this module's prefix
                        baseid = self.thismod_prefix + ':' + baseid

                    if baseid not in self.baseid:
                        self.baseid.append(baseid)

                    if node.keyword == 'typedef':
                        keyword = self.make_plantuml_keyword(self.thismod_prefix) + '_' + self.make_plantuml_keyword(node.arg) + '_typedef'
                    else:
                        keyword = self.full_path(node.parent)

                    # add a relation to the baseid:
                    # if baseid is defined in this module, then an identity class will have been defined in this module and
                    # if baseid is not in an input module, then function post_process_module() will then add a placeholder class for the identity
                    # in both the above cases the keyword will be then same
                    # if baseid is in another input module, then an identity class will have been defined there (with the same keyword), in which case the relation must be defined outside of the module packages
                    prefix, _ = util.split_identifier(baseid)
                    if prefix == self.thismod_prefix or prefix not in self.module_prefixes:
                        self.post_strings.append(keyword + '-->' + self.make_plantuml_keyword(baseid) + '_identity : ' + node.arg + '\n')
                    else:
                        self.end_strings.append(keyword + '-->' + self.make_plantuml_keyword(baseid) + '_identity : ' + node.arg + '\n')


        elif t.arg == 'union':
            uniontypes = t.search('type')
            s = s + '{' + uniontypes[0].arg
            for uniontype in uniontypes[1:2]:
                s = s + ', ' + uniontype.arg
            if  len(uniontypes) > 3:
                s = s + ',..}'
            else:
                s = s + '}'


        typerange = t.search_one('range')
        if typerange is not None:
            s = s + ' [' + typerange.arg + ']'
        length = t.search_one('length')
        if length is not None:
            s = s + ' {length = ' + length.arg + '}'

        pattern = t.search_one('pattern')
        if pattern is not None: # truncate long patterns
            s = s + ' {pattern = ' + pattern.arg[:20]
            if len(pattern.arg) < 20:
                s = s + '}'
            else:
                s = s + '...}'

        return s

    def emit_must_leaf(self, parent, node, fd):
        annot = ''
        must = node.search('must')
        if len(must) > 0 :
            annot = "<b>Must</b> (" + node.arg + "):\n"
            for m in must:
                annot = annot + m.arg + '\n'

        when = node.search_one('when')
        if when is not None:
            annot = annot +  "<b>When</b> (" + node.arg + "):\n" + when.arg + '\n'

        if annot != '':
            self.annotate_node(parent, annot, fd)


    def emit_must(self, parent, node, fd):
        self.annotate_node(parent, "<b>Must:</b>\n" + node.arg, fd)

    def full_display_path(self, stmt):
        pathsep = "/"
        path = stmt.arg
        if stmt.keyword not in ('grouping', 'choice', 'case'):
            if self.ctx_fullpath:
                while stmt.parent is not None:
                    stmt = stmt.parent
                    if stmt.arg is not None:
                        path = stmt.arg + pathsep + path
        return path

    def augment2identifier(self, stmt):
        pathsep = "_I_"
        path = stmt.arg
        # for augment paths we need to remove initial /
        if path.startswith("/"):
            path = path[1:]
        # get module prefix
        mod = path[0:path.find(':')] + '_'
        while stmt.parent is not None:
            stmt = stmt.parent
            if stmt.arg is not None:
                path = stmt.arg + pathsep + path
        path = mod + path.replace(mod, '')
        return self.make_plantuml_keyword(path)


    def full_path(self, stmt):
        pathsep = "_I_"
        path = stmt.arg
        # for augment paths we need to remove initial /
        if path.startswith("/"):
            path = path[1:]
        else:
            if stmt.keyword == 'case':
                path = path + '-case'
            elif stmt.keyword == 'grouping':
                path = path + '-grouping'

            while stmt.parent is not None:
                stmt = stmt.parent
                if stmt.arg is not None:
                    path = stmt.arg + pathsep + path
        return self.make_plantuml_keyword(path)

    def last_component(self, s):
        last = s[s.rfind("/")+1:]
        return self.make_plantuml_keyword(last)

    def next_tolast_component(self, s):
        if self.ctx_fullpath:
            return s[0:(s.rfind("_I_"))]
        else:
            return s

    def first_component(self, s):
        first = s[1:s.find(":")]
        return self.make_plantuml_keyword(first)

    def grouping_name(self, s):
        s = s.replace(':', '_I_')
        return s


    def make_plantuml_keyword(self, s):
        #plantuml does not like -/:. in identifiers, fixed :)
        s = s.replace('-', '_')
        s = s.replace('/', '_')
        s = s.replace(':', '_')
        # RFC 7950 allows YANG identifiers to contain dots and dashes, so to ensure there is no chance of a clash of keywords where say identifiers 'a.b' and 'a-b' exist, use 2 underscores for dots
        s = s.replace('.', '__')

        return s


    def find_target_node(self, stmt):
        inthismod = True
        if stmt.arg.startswith('/'):
            is_absolute = True
            arg = stmt.arg
        else:
            is_absolute = False
            arg = "/" + stmt.arg
        # parse the path into a list of two-tuples of (prefix,identifier)
        path = [(m[1], m[2]) for m in syntax.re_schema_node_id_part.findall(arg)]
        # find the module of the first node in the path
        (prefix, identifier) = path[0]
        if prefix == '':
            inthismod = True
        else:
            inthismod = (prefix == self.thismod_prefix)
        # sys.stderr.write("prefix for %s : %s \n" %(path, prefix))
        module = util.prefix_to_module(
            stmt.i_module, prefix, stmt.pos, self._ctx.errors)
        if module is None:
            # error is reported by prefix_to_module
            return inthismod, None
        if is_absolute:
            # find the first node
            node = statements.search_data_keyword_child(module.i_children,
                                                        module.i_modulename,
                                                        identifier)
            if node is None:
                # check all our submodules
                for inc in module.search('include'):
                    submod = self._ctx.get_module(inc.arg)
                    if submod is not None:
                        node = statements.search_data_keyword_child(
                            submod.i_children,
                            submod.i_modulename,
                            identifier)
                        if node is not None:
                            break
                if node is None:
                    err_add(self._ctx.errors, stmt.pos, 'NODE_NOT_FOUND',
                            (module.arg, identifier))
                    return inthismod, None
            path = path[1:]
        else:
            if hasattr(stmt.parent, 'i_annotate_node'):
                node = stmt.parent.i_annotate_node
            else:
                err_add(self._ctx.errors, stmt.pos, 'BAD_ANNOTATE', ())
                return inthismod, None

        # then recurse down the path
        for prefix, identifier in path:
            module = util.prefix_to_module(
                stmt.i_module, prefix, stmt.pos, self._ctx.errors)
            if module is None:
                return None
            if hasattr(node, 'i_children'):
                children = node.i_children
            else:
                children = []
            child = statements.search_data_keyword_child(children,
                                                         module.i_modulename,
                                                         identifier)
            if child is None:
                err_add(self._ctx.errors, stmt.pos, 'NODE_NOT_FOUND',
                        (module.arg, identifier))
                return inthismod, None
            node = child

        stmt.i_annotate_node = node
        return inthismod, node


    def post_process_diagram(self, fd):
        if self.ctx_uses:
            for p,u in self.uses:
                try:
                    fd.write('%s %s %s : %s \n' % (p, self.uses_relation_symbol, self.groupings[u], self.uses_relation_label))
                except KeyError: # grouping in imported module, TODO correct paths
                    # Grouping in other module, use red...
                    # fd.write('class \"%s\" as %s << (G,Red) grouping>>\n' %(self.uses_as_string[u], self.make_plantuml_keyword(self.uses_as_string[u])))
                    # fd.write('%s --> %s : uses \n' %(p, self.make_plantuml_keyword(self.uses_as_string[u])))
                    sys.stderr.write("Info: Skipping uses reference to %s, grouping not in input files \n" %self.uses_as_string[u])
                    pass

        if self.ctx_leafrefs: # TODO correct paths for external leafrefs
            for l in self.leafrefs:
                fd.write(l)

        for s in self.end_strings:
            fd.write(s)

        # remove duplicates
        self.augments = list(set(self.augments))
        for augm in self.augments:
            fd.write(augm)


    def post_process_module(self, module, fd):

        for base in self.baseid:
            # If a base is not defined in the module, define it, if it is not in another input module
            if not base in self.identities:
                prefix, _ = util.split_identifier(base)
                if prefix not in self.module_prefixes:
                    keyword = self.make_plantuml_keyword(base) + '_identity'
                    fd.write('class \"%s\" as %s << (I,Silver) identity>> \n' %(base, keyword))

        for s in self.post_strings:
            fd.write(s)

        self.baseid = []
        self.identities = []
        self.leafref_classes = []
        self.post_strings = []

        if not self.ctx_no_module:
            fd.write("} \n\n")
            if self.ctx_imports:
                imports = module.search('import')
                for i in imports:
                    mod = self.make_plantuml_keyword(i.search_one('prefix').arg) + '_' + self.make_plantuml_keyword(i.arg)
                    fd.write('%s +-- %s_%s\n' %(mod,self.make_plantuml_keyword(self.thismod_prefix), self.make_plantuml_keyword(module.arg)))
