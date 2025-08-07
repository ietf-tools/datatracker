
import optparse

from pyang import plugin

paths_in_module = []
leafrefs = []
key = ''
class_keywords = ["container", "list", "case", "choice", "augment"]
servicepoints = ["servicepoint", "productpoint"]
classnamecolor = " {0.113725, 0.352941, 0.670588}"
mandatoryconfig = " {0.600000, 0.152941, 0.152941}"
optionalconfig = " {0.129412, 0.501961, 0.254902}"
notconfig = " {0.549020, 0.486275, 0.133333}"
#which line for containment, omnigraffles makes some bezier, override this
containsline = " tail type: \"FilledDiamond\", head type: \"None\", line type: \"Straight\" "
leafrefline = " line type: \"Straight\", head type: \"FilledArrow\" "



def pyang_plugin_init():
    plugin.register_plugin(OmniPlugin())

class OmniPlugin(plugin.PyangPlugin):
    def add_output_format(self, fmts):
        self.multiple_modules = True
        fmts['omni'] = self

    def add_opts(self, optparser):
        optlist = [
            optparse.make_option("--omni-path",
                                 dest="omni_tree_path",
                                 help="Subtree to print"),
            ]
        g = optparser.add_option_group("OmniGraffle output specific options")
        g.add_options(optlist)

    def setup_fmt(self, ctx):
        ctx.implicit_errors = False

    def emit(self, ctx, modules, fd):
        if ctx.opts.omni_tree_path is not None:
            path = ctx.opts.omni_tree_path.split('/')
            if path[0] == '':
                path = path[1:]
        else:
            path = None

        print_omni_header(modules, fd, path, ctx)
        emit_modules(modules, fd, path, ctx)
        post_process(fd, ctx)
        print_omni_footer(modules, fd, path, ctx)

def print_omni_header(modules, fd, path, ctx):
    # Build doc name from module names
    name = ''
    for m in modules:
        name += m.arg
    name = name[:32]

    fd.write("""
tell application id "com.omnigroup.OmniGraffle6"
    activate
	make new document with properties {name:\"%s\"}
    set bounds of window 1 to {50, 50, 1200, 800}
	tell first canvas of document \"%s\"
        set canvasSize to {600, 600}
		set name to \"YANG Model\"
		set adjusts pages to true

		make new shape at end of graphics with properties {fill: no fill, draws stroke: false, draws shadow: false, autosizing: full, size: {32.000000, 20.000000}, text: {size: 8, alignment: center, font: "HelveticaNeue", text: "leafref"}, origin: {2403.202333, 169.219094}}
		make new line at end of graphics with properties {point list: {{2513.245592418806, 185.5962102698529}, {2373.745592418806, 185.3149602698529}}, draws shadow: false, head type: "FilledArrow"}
		make new shape at end of graphics with properties {fill: no fill, draws stroke: false, draws shadow: false, autosizing: full, size: {105.000000, 20.000000}, text: {size: 8, alignment: center, font: "HelveticaNeue", text: "Schema tree, containment"}, origin: {2397.741930, 138.863190}}
		make new line at end of graphics with properties {point list: {{2374.993645107464, 154.4881903780727}, {2514.493645107464, 154.4881903780727}}, draws shadow: false, tail type: "FilledDiamond"}
		make new shape at end of graphics with properties {autosizing: vertically only, size: {139.500000, 14.000000}, text: {alignment: center, font: "Helvetica-Bold", text: "Legend"}, text placement: top, origin: {2366.929155, 43.937008}, vertical padding: 0}
		make new shape at end of graphics with properties {autosizing: vertically only, size: {139.500000, 56.000000}, text: {{color: {0.600000, 0.152941, 0.152941}, text: "Mandatory config
"}, {color: {0.129412, 0.501961, 0.254902}, text: "Optional config
"}, {color: {0.129412, 0.501961, 0.254902}, text: "Key leaf", underlined: true}, {color: {0.129412, 0.501961, 0.254902}, text: "
"}, {color: {0.549020, 0.486275, 0.133333}, text: "Not config"}}, text placement: top, origin: {2366.929155, 57.937008}, vertical padding: 0}
		assemble graphics -2 through -1 table shape { 2, 1 }
		assemble graphics -5 through -1

    """ %(name, name))




def post_process(fd, ctx):
    for s in leafrefs:
        # dont try to connect to class not given as input to pyang

        if s.strip().split(" to ")[1].split(" with ")[0] in paths_in_module:
            fd.write(s)


def print_omni_footer(modules, fd, path, ctx):
    fd.write("""
    layout
    end tell
end tell
""")



def print_module_info(module, fd, ctx):
    title = module.arg
    print_text(title, fd, ctx)

def emit_modules(modules, fd, path, ctx):
    for module in modules:
        print_module_info(module, fd, ctx)

        chs = [ch for ch in module.i_children]
        if path is not None and len(path) > 0:
            chs = [ch for ch in chs
                   if ch.arg == path[0]]
            path = path[1:]
        # TEST
        for ch in chs:
            print_node(module, ch, module, fd, path, ctx, 'true')
        for augment in module.search('augment'):
            print_node(module, augment, module, fd, path, ctx, 'true')


def iterate_children(parent, s, module, fd, path, ctx):
    if hasattr(s, 'i_children'):
        for ch in s.i_children:
            print_node(s, ch, module, fd, path, ctx)

def print_class_header(s, fd, ctx, root='false'):
    global servicepoints
    service = ""
    for sub in s.substmts:
        if sub.keyword[1] in servicepoints:
            service = "SERVICE\n"

    fd.write("make new shape at end of graphics with properties {autosizing: full, size: {187.500000, 14.000000}, text: {{alignment: center, font: \"Helvetica-Bold\", text: \"%s \"}, {alignment: center, color:%s, font: \"Helvetica-Bold\", text: \"%s \"}}, text placement: top, origin: {150.000000, 11.500000}, vertical padding: 0}\n" %(service + s.keyword, classnamecolor, s.arg))



def print_class_stuff(s, fd, ctx):
    number = print_attributes(s, fd, ctx)
    #print_actions(s,fd, ctx)
    close_class(number, s, fd, ctx)
    print_associations(s,fd, ctx)

def print_attributes(s,fd, ctx):
    global key
    if s.keyword == 'list':
        keystring = s.search_one('key')
        if keystring is not None:
            key = keystring.arg.split(" ")
    else:
        key = ''

    if hasattr(s, 'i_children'):
        found_attrs = False
        found_actions = False
        index = False

        # Search attrs
        for ch in s.i_children:
            index = False
            if ch.keyword in ["leaf", "leaf-list"]:
                if not found_attrs:
                    # first attr in attr section
                    fd.write("make new shape at end of graphics with properties {autosizing:full, size:{187.5, 28.0}, text:{")
                    found_attrs = True
                else:
                    # comma before new textitem
                    fd.write(", ")
                if ch.keyword == "leaf-list":
                    append = "[]"
                else:
                    append = ""
                if ch.arg in key:
                    index = True
                print_leaf(ch, append, index, fd, ctx)
        if found_attrs:
            # close attr section
            fd.write("}, text placement:top, origin:{150.0, 25.5}, vertical padding:0}\n")

        # Search actions
        for ch in s.i_children:
            if ch.keyword == ('tailf-common', 'action'):
                if not found_actions:
                    fd.write("make new shape at end of graphics with properties {autosizing:full, size:{187.5, 28.0}, text:{text:\"")
                    found_actions = True
                print_action(ch, fd, ctx)
        if found_actions:
            fd.write("\"}, text placement:top, origin:{150.0, 25.5}, vertical padding:0}\n")

        # return number of sections in class
        return (found_attrs + found_actions) + 1

def close_class(number, s, fd, ctx):
    fd.write("local %s\n" % fullpath(s))
    fd.write("set %s to assemble ( graphics -%s through -1 ) table shape {%s, 1}\n"
             % (fullpath(s), number, number))


def print_node(parent, s, module, fd, path, ctx, root='false'):
    # We have a class
    if s.keyword in class_keywords:
        print_class_header(s, fd, ctx, root)
        paths_in_module.append(fullpath(s))
        print_class_stuff(s, fd, ctx)

        #  Do not try to create relationship to module
        if parent != module:
            presence = s.search_one("presence")
            if presence is not None:
                print_aggregation(parent, s, fd, "0", "1", ctx)
            else:
                print_aggregation(parent, s, fd, "1", "1", ctx)


        iterate_children(parent, s, module, fd, path, ctx)


def print_associations(s, fd, ctx):
    # find leafrefs and identityrefs

    if hasattr(s, 'i_children'):
        for ch in s.i_children:
            if hasattr(ch, 'i_leafref_ptr') and (ch.i_leafref_ptr is not None):
                to = ch.i_leafref_ptr[0]
                print_association(s, to.parent, ch, to, "leafref", fd, ctx)


def print_aggregation(parent, this, fd, lower, upper, ctx):
    fd.write("connect %s to %s with properties {%s} \n" %(fullpath(parent),fullpath(this), containsline))

def print_rpc(rpc, fd, ctx, root='false'):
    fd.write("<UML:Class xmi.id = \'%s\' name = \'%s\' " %(fullpath(rpc), rpc.arg))

def print_action(action, fd, ctx, root='false'):
    fd.write("%s()\n" %action.arg)


def print_notification(notification, fd, ctx, root='false'):
    fd.write("<UML:Class xmi.id = \'%s\' name = \'%s\' " %(fullpath(notification), notification.arg))

def print_inout(parent, s, fd, ctx, root='false'):
    fd.write("<UML:Class xmi.id = \'%s\' name = \'%s-%s\' " %(fullpath(s), parent.arg, s.keyword))

def print_leaf(leaf, append, index, fd, ctx):

    if leaf.i_config:
        c =  '(rw)'
        color = optionalconfig
    else:
        c = '(ro)'
        color = notconfig

    m = leaf.search_one('mandatory')
    if m is None or m.arg == 'false':
        mand = '?'
    else:
        mand = ''
        color = mandatoryconfig
    if not index:
        fd.write("{font: \"Helvetica-Oblique\", color: %s, text: \"%s%s%s %s %s\n\"}"
                 % (color, leaf.arg, append, mand, c, get_typename(leaf)))
    else:
        fd.write("{font: \"Helvetica-Oblique\", color: %s, underlined: true, text: \"%s%s%s %s %s\n\"}"
                 % (color, leaf.arg, append, mand, c, get_typename(leaf)))


def print_association(fromclass, toclass, fromleaf, toleaf, association, fd, ctx):

    leafrefs.append("connect " + (fullpath(fromclass)) + " to " + fullpath(toclass) + " with properties {" + leafrefline + "}\n", )

def print_text(t, fd, ctx):
    fd.write("make new shape at end of graphics with properties {fill: no fill, draws stroke: false, draws shadow: false, autosizing: full, size: {57.000000, 30.000000}, text: {size: 16, alignment: center, font: \"HelveticaNeue\", text: \"%s\"}, origin: {100, 4.500000}}\n" %t)

def get_typename(s):
    t = s.search_one('type')
    if t is not None:
        s = t.arg
        # if t.arg == 'enumeration':
        #   s = s + ' : {'
        #   for enums in t.substmts[:10]:
        #       s = s + enums.arg + ','
        #   if len(t.substmts) > 3:
        #       s = s + "..."
        #   s = s + '}'
        # elif t.arg == 'leafref':
        #   s = s + ' : '
        #   p = t.search_one('path')
        #   if p is not None:
        #       s = s + p.arg
        return s


def fullpath(stmt):
    pathsep = "_"
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
    path = path.replace('-', '_')
    path = path.replace(':', '_')
    path = path.replace('/', '_')
    return path
