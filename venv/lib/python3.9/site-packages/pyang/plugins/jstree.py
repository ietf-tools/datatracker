"""JS-Tree output plugin
Generates a html/javascript page that presents a tree-navigator
to the YANG module(s).
"""

import optparse

from pyang import plugin
from pyang import statements
from pyang import util

def pyang_plugin_init():
    plugin.register_plugin(JSTreePlugin())

class JSTreePlugin(plugin.PyangPlugin):
    def add_output_format(self, fmts):
        self.multiple_modules = True
        fmts['jstree'] = self

    def add_opts(self, optparser):
        optlist = [
            optparse.make_option("--jstree-no-path",
                                 dest="jstree_no_path",
                                 action="store_true",
                                 help="""Do not include paths to make
                                       page less wide"""),
            optparse.make_option("--jstree-path",
                                 dest="jstree_path",
                                 help="Subtree to print"),
            ]

        g = optparser.add_option_group("JSTree output specific options")
        g.add_options(optlist)

    def setup_fmt(self, ctx):
        ctx.implicit_errors = False

    def emit(self, ctx, modules, fd):
        if ctx.opts.jstree_path is not None:
            path = ctx.opts.jstree_path.split('/')
            if path[0] == '':
                path = path[1:]
        else:
            path = None
        emit_header(modules, fd, ctx)
        emit_css(fd, ctx)
        emit_js(fd, ctx)
        emit_bodystart(modules, fd, ctx)
        emit_tree(modules, fd, ctx, path)
        emit_footer(fd, ctx)


def emit_css(fd, ctx):
    fd.write("""
<style type="text/css" media="all">

body, h1, h2, h3, h4, h5, h6, p, td, table td, input, select {
        font-family: Verdana, Helvetica, Arial, sans-serif;
        font-size: 10pt;
}

body, ol, li, h2 {padding:0; margin: 0;}

ol#root  {padding-left: 5px; margin-top: 2px; margin-bottom: 1px;
          list-style: none;}

#root ol {padding-left: 5px; margin-top: 2px; margin-bottom: 1px;
          list-style: none;}

#root li {margin-bottom: 1px; padding-left: 5px;  margin-top: 2px;
          font-size: x-small;}

.panel   {border-bottom: 1px solid #999; margin-bottom: 2px; margin-top: 2px;
          background: #eee;}

#root ul {margin-bottom: 1px; margin-top: 2px; list-style-position: inside;}

#root a {text-decoration: none;}

.folder {
   """+get_folder_css()+"""
}

.doc {
   """+get_doc_css()+"""
}

.leaf {
   """+get_leaf_css()+"""
}

.leaf-list {
   """+get_leaf_list_css()+"""
}

.action {
   """+get_action_css()+"""
}

.tier1  {margin-left: 0;     }
.tier2  {margin-left: 1.5em; }
.tier3  {margin-left: 3em;   }
.tier4  {margin-left: 4.5em; }
.tier5  {margin-left: 6em;   }
.tier6  {margin-left: 7.5em; }
.tier7  {margin-left: 9em;   }
.tier8  {margin-left: 10.5em;}
.tier9  {margin-left: 12em;  }
.tier10 {margin-left: 13.5em;}
.tier11 {margin-left: 15em;  }
.tier12 {margin-left: 16.5em;}

.level1 {padding-left: 0;    }
.level2 {padding-left: 1em;  }
.level3 {padding-left: 2em;  }
.level4 {padding-left: 3em;  }
</style>
""")

def emit_js(fd, ctx):
    fd.write("""
<script language="javascript1.2">
function toggleRows(elm) {
 var rows = document.getElementsByTagName("TR");
 elm.style.backgroundImage = """ + '"' + get_leaf_img() + '"' + """;
 var newDisplay = "none";
 var thisID = elm.parentNode.parentNode.parentNode.id + "-";
 // Are we expanding or contracting? If the first child is hidden, we expand
  for (var i = 0; i < rows.length; i++) {
   var r = rows[i];
   if (matchStart(r.id, thisID, true)) {
    if (r.style.display == "none") {
     if (document.all) newDisplay = "block"; //IE4+ specific code
     else newDisplay = "table-row"; //Netscape and Mozilla
     elm.style.backgroundImage = """ + '"' + get_folder_open_img() + '"' + """;
    }
    break;
   }
 }

 // When expanding, only expand one level.  Collapse all desendants.
 var matchDirectChildrenOnly = (newDisplay != "none");

 for (var j = 0; j < rows.length; j++) {
   var s = rows[j];
   if (matchStart(s.id, thisID, matchDirectChildrenOnly)) {
     s.style.display = newDisplay;
     var cell = s.getElementsByTagName("TD")[0];
     var tier = cell.getElementsByTagName("DIV")[0];
     var folder = tier.getElementsByTagName("A")[0];
     if (folder.getAttribute("onclick") != null) {
     folder.style.backgroundImage = """+'"'+get_folder_closed_img()+'"'+""";
     }
   }
 }
}

function matchStart(target, pattern, matchDirectChildrenOnly) {
 var pos = target.indexOf(pattern);
 if (pos != 0)
    return false;
 if (!matchDirectChildrenOnly)
    return true;
 if (target.slice(pos + pattern.length, target.length).indexOf("-") >= 0)
    return false;
 return true;
}

function collapseAllRows() {
 var rows = document.getElementsByTagName("TR");
 for (var i = 0; i < rows.length; i++) {
   var r = rows[i];
   if (r.id.indexOf("-") >= 0) {
     r.style.display = "none";
   }
 }
}

function expandAllRows() {
  var rows = document.getElementsByTagName("TR");
  for (var i = 0; i < rows.length; i ++) {
    var r = rows[i];
    if (r.id.indexOf("-") >= 0) {
      r.style.display = "table-row";
    }
  }
}
</script>
""")

def emit_header(modules, fd, ctx):
    title = ""
    for m in modules:
        title = title + " " + m.arg
    fd.write("<head><title>%s \n</title>" %title)

def emit_footer(fd, ctx):
    fd.write("""
</table>
</div>
</body>
</html>

""")

levelcnt = [0]*100

def emit_bodystart(modules, fd, ctx):
    fd.write("""
<body onload="collapseAllRows();">
<a href="http://www.tail-f.com">
   <img src="""+get_tailf_logo()+""" />
</a>
<div class="app">
<div style="background: #eee; border: dashed 1px #000;">
""")
    for module in modules:
        bstr = ""
        b = module.search_one('belongs-to')
        if b is not None:
            bstr = " (belongs-to %s)" % b.arg

        nsstr = ""
        ns = module.search_one('namespace')
        if ns is not None:
            nsstr = ns.arg
        pr = module.search_one('prefix')

        prstr = ""
        if pr is not None:
            prstr = pr.arg

        if module.keyword == 'module':
            fd.write("""<h1> %s: <font color=blue>%s%s</font>, Namespace:
                     <font color=blue>%s</font>, Prefix:
                     <font color=blue>%s</font></h1> \n"""
                     % (module.keyword.capitalize(),
                        module.arg,
                        bstr,
                        nsstr,
                        prstr))
        else:
            fd.write("<h1> %s: <font color=blue>%s%s</font></h1> \n"
                     % (module.keyword.capitalize(), module.arg, bstr))

    fd.write("""
 <table width="100%">

 <tr>
  <!-- specifing one or more widths keeps columns
       constant despite changes in visible content -->
  <th align=left>
     Element
     <a href='#' onclick='expandAllRows();'>[+]Expand all</a>
     <a href='#' onclick='collapseAllRows();'>[-]Collapse all</a>
  </th>
  <th align=left>Schema</th>
  <th align=left>Type</th>
  <th align=left>Flags</th>
  <th align=left>Opts</th>
  <th align=left>Status</th>
  <th align=left>Path</th>
</tr>
""")

def emit_tree(modules, fd, ctx, path):
    global levelcnt
    for module in modules:
        bstr = ""
        b = module.search_one('belongs-to')
        if b is not None:
            bstr = " (belongs-to %s)" % b.arg
        ns = module.search_one('namespace')
        if ns is not None:
            nsstr = ns.arg
        pr = module.search_one('prefix')
        if pr is not None:
            prstr = pr.arg
        else:
            prstr = ""

        temp_mod_arg = module.arg
        # html plugin specific changes
        if hasattr(ctx, 'html_plugin_user'):
            from pyang.plugins.html import force_link
            temp_mod_arg = force_link(ctx, module, module)

        levelcnt[1] += 1
        chs = [ch for ch in module.i_children
               if ch.keyword in statements.data_definition_keywords]
        if path is not None and len(path) > 0:
            chs = [ch for ch in chs if ch.arg == path[0]]
            path = path[1:]

        if len(chs) > 0:
            fd.write("""<tr id="%s" class="a">
                         <td id="p1">
                            <div id="p2" class="tier1">
                               <a href="#" id="p3"
                                  onclick="toggleRows(this);return false;"
                                  class="folder">&nbsp;
                               </a>
                               <font color=blue>%s</font>
                            </div>
                         </td> \n""" %(levelcnt[1], temp_mod_arg))
            fd.write("""<td>%s</td><td></td><td></td><td></td><td>
                        </td></tr>\n""" %module.keyword)
            #fd.write("<td>module</td><td></td><td></td><td></td><td></td></tr>\n")

            # print_children(chs, module, fd, '  ', path, 'data', depth, llen)
            print_children(chs, module, fd, ' ', path, ctx, 2)

        rpcs = module.search('rpc')
        if path is not None:
            if len(path) > 0:
                rpcs = [rpc for rpc in rpcs if rpc.arg == path[0]]
                path = path[1:]
            else:
                rpcs = []

        levelcnt[1] += 1
        if len(rpcs) > 0:
            fd.write("""<tr id="%s" class="a">
                         <td nowrap id="p1000">
                            <div id="p2000" class="tier1">
                               <a href="#" id="p3000"
                                  onclick="toggleRows(this);
                                  return false;" class="folder">&nbsp;
                               </a>
                               %s:rpcs
                            </div>
                         </td> \n""" %(levelcnt[1],prstr))
            fd.write("<td></td><td></td><td></td><td></td><td></td></tr>\n")
            print_children(rpcs, module, fd, ' ', path, ctx, 2)

        notifs = module.search('notification')
        if path is not None:
            if len(path) > 0:
                notifs = [n for n in notifs if n.arg == path[0]]
                path = path[1:]
            else:
                notifs = []
        levelcnt[1] += 1
        if len(notifs) > 0:
            fd.write("""<tr id="%s" class="a">
                        <td nowrapid="p4000">
                           <div id="p5000" class="tier1">
                              <a href="#" id="p6000"
                                 onclick="toggleRows(this);return false;"
                                 class="folder">&nbsp;
                              </a>%s:notifs
                           </div>
                        </td> \n""" %(levelcnt[1],prstr))
            fd.write("<td></td><td></td><td></td><td></td><td></td></tr>\n")
            print_children(notifs, module, fd, ' ', path, ctx, 2)


def print_children(i_children, module, fd, prefix, path, ctx, level=0):
    for ch in i_children:
        print_node(ch, module, fd, prefix, path, ctx, level)

def print_node(s, module, fd, prefix, path, ctx, level=0):

    global levelcnt
    fontstarttag = ""
    fontendtag = ""
    status = get_status_str(s)
    nodetype = ''
    options = ''
    folder = False
    if s.i_module.i_modulename == module.i_modulename:
        name = s.arg
    else:
        name = s.i_module.i_prefix + ':' + s.arg

    pr = module.search_one('prefix')
    if pr is not None:
        prstr = pr.arg
    else:
        prstr = ""

    descr = s.search_one('description')
    descrstring = "No description"
    if descr is not None:
        descrstring = descr.arg
    flags = get_flags_str(s)
    if s.keyword in ('list', 'input', 'output', 'rpc', 'notification', 'action'):
        folder = True
    elif s.keyword == 'container':
        folder = True
        p = s.search_one('presence')
        if p is not None:
            pr_str = p.arg
            options = "<abbr title=\"" + pr_str + "\">Presence</abbr>"
    elif s.keyword  == 'choice':
        folder = True
        m = s.search_one('mandatory')
        if m is None or m.arg == 'false':
            name = '(' + s.arg + ')'
            options = 'Choice'
        else:
            name = '(' + s.arg + ')'
    elif s.keyword == 'case':
        folder = True
        # fd.write(':(' + s.arg + ')')
        name = ':(' + s.arg + ')'
    else:
        if s.keyword == 'leaf-list':
            options = '*'
        elif s.keyword == 'leaf' and not hasattr(s, 'i_is_key'):
            m = s.search_one('mandatory')
            if m is None or m.arg == 'false':
                options = '?'
        nodetype = get_typename(s)

    if s.keyword == 'list' and s.search_one('key') is not None:
        name += '[' + s.search_one('key').arg +  ']'

    descr = s.search_one('description')
    if descr is not None:
        descrstring = ''.join([x for x in descr.arg if ord(x) < 128])
    else:
        descrstring = "No description"
    levelcnt[level] += 1
    idstring = str(levelcnt[1])

    for i in range(2,level+1):
        idstring += '-' + str(levelcnt[i])

    pathstr = ""
    if not ctx.opts.jstree_no_path:
        pathstr = statements.mk_path_str(s, True)

    if '?' in options:
        fontstarttag = "<em>"
        fontendtag = "</em>"
    keyword = s.keyword

    type_html_info = ""
    attr_html_info = ""
    element_htmnl_info = ""
    if folder:
        if hasattr(ctx, 'html_plugin_user'):
            from pyang.plugins.html import force_link
            name = force_link(ctx, s, module, name)
        attr_html_info = """<abbr title="%s">%s</abbr>""" % (descrstring, name)
        classstring = s.keyword
        if s.keyword in ('action', 'rpc', 'notification'):
            type_html_info = """<td nowrap><abbr title="%s">%s</abbr></td>
                             """ % (action_params(s), "parameters")
        else:
            type_html_info = """<td nowrap>%s</td>""" % (nodetype)
        element_html_info = """
            <td nowrap id="p4000">
               <div id="p5000" class="tier%s">
                 <a href="#" id="p6000"
                    onclick="toggleRows(this);return false"
                    class="%s">&nbsp;
                 </a>
                 %s
              </div>
            </td>""" % (level, "folder", attr_html_info)
    else:
        attr_html_info = """<abbr title="%s"> %s %s %s</abbr>
            """ % (descrstring, fontstarttag, name, fontendtag)
        if s.keyword == ('tailf-common', 'action'):
            type_html_info = """<td nowrap><abbr title="%s">%s</abbr></td>
                """ % (action_params(s), "parameters")
            classstring = "action"
        else:
            type_html_info = """<td nowrap><abbr title="%s">%s</abbr></td>
                """ % (typestring(s), nodetype)
            classstring = s.keyword
        element_html_info = """
            <td nowrap>
               <div id=9999 class=tier%s>
                  <a class="%s">&nbsp;</a>
                  %s
               </div>
            </td> """ % (level, classstring, attr_html_info)
    fd.write("""
        <tr id="%s" class="a">
        %s
        <td nowrap>%s</td>
        %s
        <td nowrap>%s</td>
        <td>%s</td>
        <td>%s</td>
        <td nowrap>%s</td>
        </tr>""" % (idstring, element_html_info, classstring, type_html_info,
                    flags, options, status, pathstr))

    if hasattr(s, 'i_children'):
        level += 1
        chs = s.i_children
        if path is not None and len(path) > 0:
            chs = [ch for ch in chs
                   if ch.arg == path[0]]
            path = path[1:]
        if s.keyword in ['choice', 'case']:
            print_children(chs, module, fd, prefix, path, ctx, level)
        else:
            print_children(chs, module, fd, prefix, path, ctx, level)

def get_status_str(s):
    status = s.search_one('status')
    if status is None or status.arg == 'current':
        return 'current'
    else:
        return status

def get_flags_str(s):
    if s.keyword == 'rpc':
        return ''
    elif s.keyword == 'notification':
        return ''
    elif s.i_config:
        return 'config'
    else:
        return 'no config'

def get_typename(s):
    t = s.search_one('type')
    if t is not None:
        return t.arg
    else:
        return ''

def typestring(node):

    def get_nontypedefstring(node):
        s = ""
        found  = False
        t = node.search_one('type')
        if t is not None:
            s = t.arg + '\n'
            if t.arg == 'enumeration':
                found = True
                s = s + ' : {'
                for enums in t.substmts:
                    s = s + enums.arg + ','
                s = s + '}'
            elif t.arg == 'leafref':
                found = True
                s = s + ' : '
                p = t.search_one('path')
                if p is not None:
                    s = s + p.arg

            elif t.arg == 'identityref':
                found = True
                b = t.search_one('base')
                if b is not None:
                    s = s + ' {' + b.arg + '}'

            elif t.arg == 'union':
                found = True
                uniontypes = t.search('type')
                s = s + '{' + uniontypes[0].arg
                for uniontype in uniontypes[1:]:
                    s = s + ', ' + uniontype.arg
                s = s + '}'

            typerange = t.search_one('range')
            if typerange is not None:
                found = True
                s = s + ' [' + typerange.arg + ']'
            length = t.search_one('length')
            if length is not None:
                found = True
                s = s + ' {length = ' + length.arg + '}'

            pattern = t.search_one('pattern')
            if pattern is not None: # truncate long patterns
                found = True
                s = s + ' {pattern = ' + pattern.arg + '}'
        return s

    s = get_nontypedefstring(node)

    if s != "":
        t = node.search_one('type')
        # chase typedef
        type_namespace = None
        i_type_name = None
        prefix, name = util.split_identifier(t.arg)
        if prefix is None or t.i_module.i_prefix == prefix:
            # check local typedefs
            pmodule = node.i_module
            typedef = statements.search_typedef(t, name)
        else:
            # this is a prefixed name, check the imported modules
            err = []
            pmodule = util.prefix_to_module(t.i_module, prefix, t.pos, err)
            if pmodule is None:
                return
            typedef = statements.search_typedef(pmodule, name)
        if typedef is not None:
            s = s + get_nontypedefstring(typedef)
    return s

def action_params(action):
    s = ""
    for params in action.substmts:

        if params.keyword == 'input':
            inputs = params.search('leaf')
            inputs += params.search('leaf-list')
            inputs += params.search('list')
            inputs += params.search('container')
            inputs += params.search('anyxml')
            inputs += params.search('uses')
            for i in inputs:
                s += ' in: ' + i.arg + "\n"

        if params.keyword == 'output':
            outputs = params.search('leaf')
            outputs += params.search('leaf-list')
            outputs += params.search('list')
            outputs += params.search('container')
            outputs += params.search('anyxml')
            outputs += params.search('uses')
            for o in outputs:
                s += 'out: ' + o.arg + "\n"
    return s

def get_folder_css():
    return (
        "background:url(data:image/gif;base64,R0lGODlhGgAOALMLAJmZmYuLi3p6ev///"
        "+zs7MzMzGZmZqqqqrS0tLq6uuHh4f///wAAAAAAAAAAAAAAACH5BAEAAAsALAAAAAAaAA4"
        "AAASJcMlJq714qgROKUtxAABBgJkUFMQwFEhyFoFAKini7idSHwGDQXAYYAADxQdBOjiBQ"
        "qGgYKx4AomCYoYAHqLRVVUCKCBdSthhCgYDKIDuTpnoGgptgxged3FHBgpgU2MTASsmdCM"
        "1gkNFGDVaHx91QQQ3KZGSZocHBCEpEgIrCYdxn6EVAnoIGREAOw==) no-repeat;\n"
        "float: left; padding-right: 30px;margin-left: 3px;\n")

def get_doc_css():
    return (
        "background:url(data:image/gif;base64,R0lGODlhDAAOALMJAMzMzODg4P///+np6"
        "a+vr+7u7jMzM5mZmYmJif///wAAAAAAAAAAAAAAAAAAAAAAACH5BAEAAAkALAAAAAAMAA4"
        "AAARFEEhyCAEjackPCESwBRxwCKD4BSSACCgxrKyJ3B42sK2FSINgsAa4AApI4W5yFCCTy"
        "wts+txJp9TC4IrFcruwi2FMLgMiADs=) no-repeat;\n"
        "float: left; padding-right: 10px; margin-left: 3px;\n"
        "cursor: pointer;\n")

def get_leaf_css():
    return (
        "background:url(data:image/gif;base64,R0lGODlhEAAQANUAAAAtAAA5AABDAAFPA"
        "QBSAAFaAQldBwBhAAFrAR1tHAJzAglzCRx7Gyd8JieCIiWMIjqPNzySO0OUPkCVQEOYQUO"
        "bP0idQ02hSkmjQ1ClTFKnUlesVVmuWVqvVF6zWlu1UmG2YWK3X2O4XGi9ZG3CY3TJbHbNZ"
        "3jNbHzRboDVcYPYdIjdd////wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAACH5BAkAAC0AIf8LSUNDUkdCRzEwMTL/AAAHqGFwc"
        "GwCIAAAbW50clJHQiBYWVogB9kAAgAZAAsAGgALYWNzcEFQUEwAAAAAYXBwbAAAAAAAAAA"
        "AAAAAAAAAAAAAAPbWAAEAAAAA0y1hcHBsAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAALZGVzYwAAAQgAAABvZHNjbQAAAXgAAAVsY3BydAAABuQ"
        "AAAA4d3RwdAAABxwAAAAUclhZWgAABzAAAAAUZ1hZWgAAB0QAAAAUYlhZWgAAB1gAAAAUc"
        "lRSQwAAB2wAAAAOY2hhZAAAB3wAAAAsYlRSQwAAB2wAAAAOZ1RS/0MAAAdsAAAADmRlc2M"
        "AAAAAAAAAFEdlbmVyaWMgUkdCIFByb2ZpbGUAAAAAAAAAAAAAABRHZW5lcmljIFJHQiBQc"
        "m9maWxlAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAABtbHVjAAAAAAAAAB4AAAAMc2tTSwAAACgAAAF4aHJIUgAAACgAAAGgY2FFUwAAACQAA"
        "AHIcHRCUgAAACYAAAHsdWtVQQAAACoAAAISZnJGVQAAACgAAAI8emhUVwAAABYAAAJkaXR"
        "JVAAAACgAAAJ6bmJOTwAAACYAAAKia29LUgAAABYAAP8CyGNzQ1oAAAAiAAAC3mhlSUwAA"
        "AAeAAADAGRlREUAAAAsAAADHmh1SFUAAAAoAAADSnN2U0UAAAAmAAAConpoQ04AAAAWAAA"
        "DcmphSlAAAAAaAAADiHJvUk8AAAAkAAADomVsR1IAAAAiAAADxnB0UE8AAAAmAAAD6G5sT"
        "kwAAAAoAAAEDmVzRVMAAAAmAAAD6HRoVEgAAAAkAAAENnRyVFIAAAAiAAAEWmZpRkkAAAA"
        "oAAAEfHBsUEwAAAAsAAAEpHJ1UlUAAAAiAAAE0GFyRUcAAAAmAAAE8mVuVVMAAAAmAAAFG"
        "GRhREsAAAAuAAAFPgBWAWEAZQBvAGIAZQD/YwBuAP0AIABSAEcAQgAgAHAAcgBvAGYAaQB"
        "sAEcAZQBuAGUAcgBpAQ0AawBpACAAUgBHAEIAIABwAHIAbwBmAGkAbABQAGUAcgBmAGkAb"
        "AAgAFIARwBCACAAZwBlAG4A6AByAGkAYwBQAGUAcgBmAGkAbAAgAFIARwBCACAARwBlAG4"
        "A6QByAGkAYwBvBBcEMAQzBDAEOwRMBD0EOAQ5ACAEPwRABD4ERAQwBDkEOwAgAFIARwBCA"
        "FAAcgBvAGYAaQBsACAAZwDpAG4A6QByAGkAcQB1AGUAIABSAFYAQpAadSgAIABSAEcAQgA"
        "ggnJfaWPPj/AAUAByAG8AZgBp/wBsAG8AIABSAEcAQgAgAGcAZQBuAGUAcgBpAGMAbwBHA"
        "GUAbgBlAHIAaQBzAGsAIABSAEcAQgAtAHAAcgBvAGYAaQBsx3y8GAAgAFIARwBCACDVBLh"
        "c0wzHfABPAGIAZQBjAG4A/QAgAFIARwBCACAAcAByAG8AZgBpAGwF5AXoBdUF5AXZBdwAI"
        "ABSAEcAQgAgBdsF3AXcBdkAQQBsAGwAZwBlAG0AZQBpAG4AZQBzACAAUgBHAEIALQBQAHI"
        "AbwBmAGkAbADBAGwAdABhAGwA4QBuAG8AcwAgAFIARwBCACAAcAByAG8AZgBpAGxmbpAaA"
        "CAAUgBHAEIAIGPPj//wZYdO9k4AgiwAIABSAEcAQgAgMNcw7TDVMKEwpDDrAFAAcgBvAGY"
        "AaQBsACAAUgBHAEIAIABnAGUAbgBlAHIAaQBjA5MDtQO9A7kDugPMACADwAPBA78DxgOvA"
        "7sAIABSAEcAQgBQAGUAcgBmAGkAbAAgAFIARwBCACAAZwBlAG4A6QByAGkAYwBvAEEAbAB"
        "nAGUAbQBlAGUAbgAgAFIARwBCAC0AcAByAG8AZgBpAGUAbA5CDhsOIw5EDh8OJQ5MACAAU"
        "gBHAEIAIA4XDjEOSA4nDkQOGwBHAGUAbgBlAGwAIABSAEcAQgAgAFAAcgBvAGYAaQBsAGk"
        "AWQBsAGX/AGkAbgBlAG4AIABSAEcAQgAtAHAAcgBvAGYAaQBpAGwAaQBVAG4AaQB3AGUAc"
        "gBzAGEAbABuAHkAIABwAHIAbwBmAGkAbAAgAFIARwBCBB4EMQRJBDgEOQAgBD8EQAQ+BEQ"
        "EOAQ7BEwAIABSAEcAQgZFBkQGQQAgBioGOQYxBkoGQQAgAFIARwBCACAGJwZEBjkGJwZFA"
        "EcAZQBuAGUAcgBpAGMAIABSAEcAQgAgAFAAcgBvAGYAaQBsAGUARwBlAG4AZQByAGUAbAA"
        "gAFIARwBCAC0AYgBlAHMAawByAGkAdgBlAGwAcwBldGV4dAAAAABDb3B5cmlnaHQgMjAwr"
        "zcgQXBwbGUgSW5jLiwgYWxsIHJpZ2h0cyByZXNlcnZlZC4AWFlaIAAAAAAAAPNSAAEAAAA"
        "BFs9YWVogAAAAAAAAdE0AAD3uAAAD0FhZWiAAAAAAAABadQAArHMAABc0WFlaIAAAAAAAA"
        "CgaAAAVnwAAuDZjdXJ2AAAAAAAAAAEBzQAAc2YzMgAAAAAAAQxCAAAF3v//8yYAAAeSAAD"
        "9kf//+6L///2jAAAD3AAAwGwALAAAAAAQABAAAAZywJZwSCwaj8hkS3FUOJ9Po+LxIZVKJ"
        "9WKSVxgRiBQiIRKqRBERMXD4XRIp7gJLTwwNppLhsTnfw5DBxEXExYih4ckDoBCBRQREB2"
        "Skh4YBUQEEQ16GZ0dFQZFAw0UF3oXEgkDRgKtrq5GAQFKRAC0t0dBADs=) no-repeat;"
        "\nfloat: left; padding-right: 10px;margin-left: 3px;\n")

def get_leaf_list_css():
    return (
        "background:url(data:image/gif;base64,R0lGODlhEAAQANUAAAAAAAAtAAk3CQA5A"
        "ABDAAFPAQBVAAFaAQBhAAFrAgJzAglzCRx7Gyd8JgCCCyeCIgCMDSWMIjqPNzySOwCUDwW"
        "UFECVQEOYQQCbEUidQ0OePx6fJk2hSgCiEg2iG1ClTEimRFKnUg6oHVesVSatL1muWVqvV"
        "F6zXFu1UmG2YWK3X2O4XGi9ZG3CY3TJbHbNZ3jNbHzRboDVcYPYdIjddxrfKyziPUHnUlX"
        "rZmTudf///wAAAAAAAAAAAAAAAAAAACH5BAkKADsAIf8LSUNDUkdCRzEwMTL/AAAHqGFwc"
        "GwCIAAAbW50clJHQiBYWVogB9kAAgAZAAsAGgALYWNzcEFQUEwAAAAAYXBwbAAAAAAAAAA"
        "AAAAAAAAAAAAAAPbWAAEAAAAA0y1hcHBsAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAALZGVzYwAAAQgAAABvZHNjbQAAAXgAAAVsY3BydAAABuQ"
        "AAAA4d3RwdAAABxwAAAAUclhZWgAABzAAAAAUZ1hZWgAAB0QAAAAUYlhZWgAAB1gAAAAUc"
        "lRSQwAAB2wAAAAOY2hhZAAAB3wAAAAsYlRSQwAAB2wAAAAOZ1RS/0MAAAdsAAAADmRlc2M"
        "AAAAAAAAAFEdlbmVyaWMgUkdCIFByb2ZpbGUAAAAAAAAAAAAAABRHZW5lcmljIFJHQiBQc"
        "m9maWxlAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAABtbHVjAAAAAAAAAB4AAAAMc2tTSwAAACgAAAF4aHJIUgAAACgAAAGgY2FFUwAAACQAA"
        "AHIcHRCUgAAACYAAAHsdWtVQQAAACoAAAISZnJGVQAAACgAAAI8emhUVwAAABYAAAJkaXR"
        "JVAAAACgAAAJ6bmJOTwAAACYAAAKia29LUgAAABYAAP8CyGNzQ1oAAAAiAAAC3mhlSUwAA"
        "AAeAAADAGRlREUAAAAsAAADHmh1SFUAAAAoAAADSnN2U0UAAAAmAAAConpoQ04AAAAWAAA"
        "DcmphSlAAAAAaAAADiHJvUk8AAAAkAAADomVsR1IAAAAiAAADxnB0UE8AAAAmAAAD6G5sT"
        "kwAAAAoAAAEDmVzRVMAAAAmAAAD6HRoVEgAAAAkAAAENnRyVFIAAAAiAAAEWmZpRkkAAAA"
        "oAAAEfHBsUEwAAAAsAAAEpHJ1UlUAAAAiAAAE0GFyRUcAAAAmAAAE8mVuVVMAAAAmAAAFG"
        "GRhREsAAAAuAAAFPgBWAWEAZQBvAGIAZQD/YwBuAP0AIABSAEcAQgAgAHAAcgBvAGYAaQB"
        "sAEcAZQBuAGUAcgBpAQ0AawBpACAAUgBHAEIAIABwAHIAbwBmAGkAbABQAGUAcgBmAGkAb"
        "AAgAFIARwBCACAAZwBlAG4A6AByAGkAYwBQAGUAcgBmAGkAbAAgAFIARwBCACAARwBlAG4"
        "A6QByAGkAYwBvBBcEMAQzBDAEOwRMBD0EOAQ5ACAEPwRABD4ERAQwBDkEOwAgAFIARwBCA"
        "FAAcgBvAGYAaQBsACAAZwDpAG4A6QByAGkAcQB1AGUAIABSAFYAQpAadSgAIABSAEcAQgA"
        "ggnJfaWPPj/AAUAByAG8AZgBp/wBsAG8AIABSAEcAQgAgAGcAZQBuAGUAcgBpAGMAbwBHA"
        "GUAbgBlAHIAaQBzAGsAIABSAEcAQgAtAHAAcgBvAGYAaQBsx3y8GAAgAFIARwBCACDVBLh"
        "c0wzHfABPAGIAZQBjAG4A/QAgAFIARwBCACAAcAByAG8AZgBpAGwF5AXoBdUF5AXZBdwAI"
        "ABSAEcAQgAgBdsF3AXcBdkAQQBsAGwAZwBlAG0AZQBpAG4AZQBzACAAUgBHAEIALQBQAHI"
        "AbwBmAGkAbADBAGwAdABhAGwA4QBuAG8AcwAgAFIARwBCACAAcAByAG8AZgBpAGxmbpAaA"
        "CAAUgBHAEIAIGPPj//wZYdO9k4AgiwAIABSAEcAQgAgMNcw7TDVMKEwpDDrAFAAcgBvAGY"
        "AaQBsACAAUgBHAEIAIABnAGUAbgBlAHIAaQBjA5MDtQO9A7kDugPMACADwAPBA78DxgOvA"
        "7sAIABSAEcAQgBQAGUAcgBmAGkAbAAgAFIARwBCACAAZwBlAG4A6QByAGkAYwBvAEEAbAB"
        "nAGUAbQBlAGUAbgAgAFIARwBCAC0AcAByAG8AZgBpAGUAbA5CDhsOIw5EDh8OJQ5MACAAU"
        "gBHAEIAIA4XDjEOSA4nDkQOGwBHAGUAbgBlAGwAIABSAEcAQgAgAFAAcgBvAGYAaQBsAGk"
        "AWQBsAGX/AGkAbgBlAG4AIABSAEcAQgAtAHAAcgBvAGYAaQBpAGwAaQBVAG4AaQB3AGUAc"
        "gBzAGEAbABuAHkAIABwAHIAbwBmAGkAbAAgAFIARwBCBB4EMQRJBDgEOQAgBD8EQAQ+BEQ"
        "EOAQ7BEwAIABSAEcAQgZFBkQGQQAgBioGOQYxBkoGQQAgAFIARwBCACAGJwZEBjkGJwZFA"
        "EcAZQBuAGUAcgBpAGMAIABSAEcAQgAgAFAAcgBvAGYAaQBsAGUARwBlAG4AZQByAGUAbAA"
        "gAFIARwBCAC0AYgBlAHMAawByAGkAdgBlAGwAcwBldGV4dAAAAABDb3B5cmlnaHQgMjAwr"
        "zcgQXBwbGUgSW5jLiwgYWxsIHJpZ2h0cyByZXNlcnZlZC4AWFlaIAAAAAAAAPNSAAEAAAA"
        "BFs9YWVogAAAAAAAAdE0AAD3uAAAD0FhZWiAAAAAAAABadQAArHMAABc0WFlaIAAAAAAAA"
        "CgaAAAVnwAAuDZjdXJ2AAAAAAAAAAEBzQAAc2YzMgAAAAAAAQxCAAAF3v//8yYAAAeSAAD"
        "9kf//+6L///2jAAAD3AAAwGwALAAAAAAQABAAAAaFwJ1wSCwaj8jkTnFUOJ9PoyKCarlcs"
        "BmNSVyAWKmUqhWTzRLEhOZUKplasPgLLUQwRiHOp8XnoxBDCBMcFhkrh4ctD4BCBxcTEia"
        "SkiQiEEQGEw16H50mHjkdRAUNFxx6HBsVFDgYrkIEsbIEEDe2thQ7AwNGEL42vpcBSQ41D"
        "kpDCcpCQQA7) no-repeat;\n"
        "float: left; padding-right: 10px; margin-left: 3px;\n")

def get_action_css():
    return (
        "background:url(data:image/gif;base64,R0lGODlhEAAQALMAAAAAABERETMzM1VVV"
        "WZmZnd3d4iIiJmZmaqqqru7u8zMzO7u7v///wAAAAAAAAAAACH5BAkKAA0AIf8LSUNDUkd"
        "CRzEwMTL/AAAHqGFwcGwCIAAAbW50clJHQiBYWVogB9kAAgAZAAsAGgALYWNzcEFQUEwAA"
        "AAAYXBwbAAAAAAAAAAAAAAAAAAAAAAAAPbWAAEAAAAA0y1hcHBsAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAALZGVzYwAAAQgAAABvZHNjbQAAA"
        "XgAAAVsY3BydAAABuQAAAA4d3RwdAAABxwAAAAUclhZWgAABzAAAAAUZ1hZWgAAB0QAAAA"
        "UYlhZWgAAB1gAAAAUclRSQwAAB2wAAAAOY2hhZAAAB3wAAAAsYlRSQwAAB2wAAAAOZ1RS/"
        "0MAAAdsAAAADmRlc2MAAAAAAAAAFEdlbmVyaWMgUkdCIFByb2ZpbGUAAAAAAAAAAAAAABR"
        "HZW5lcmljIFJHQiBQcm9maWxlAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAABtbHVjAAAAAAAAAB4AAAAMc2tTSwAAACgAAAF4aHJIUgAAACg"
        "AAAGgY2FFUwAAACQAAAHIcHRCUgAAACYAAAHsdWtVQQAAACoAAAISZnJGVQAAACgAAAI8e"
        "mhUVwAAABYAAAJkaXRJVAAAACgAAAJ6bmJOTwAAACYAAAKia29LUgAAABYAAP8CyGNzQ1o"
        "AAAAiAAAC3mhlSUwAAAAeAAADAGRlREUAAAAsAAADHmh1SFUAAAAoAAADSnN2U0UAAAAmA"
        "AAConpoQ04AAAAWAAADcmphSlAAAAAaAAADiHJvUk8AAAAkAAADomVsR1IAAAAiAAADxnB"
        "0UE8AAAAmAAAD6G5sTkwAAAAoAAAEDmVzRVMAAAAmAAAD6HRoVEgAAAAkAAAENnRyVFIAA"
        "AAiAAAEWmZpRkkAAAAoAAAEfHBsUEwAAAAsAAAEpHJ1UlUAAAAiAAAE0GFyRUcAAAAmAAA"
        "E8mVuVVMAAAAmAAAFGGRhREsAAAAuAAAFPgBWAWEAZQBvAGIAZQD/YwBuAP0AIABSAEcAQ"
        "gAgAHAAcgBvAGYAaQBsAEcAZQBuAGUAcgBpAQ0AawBpACAAUgBHAEIAIABwAHIAbwBmAGk"
        "AbABQAGUAcgBmAGkAbAAgAFIARwBCACAAZwBlAG4A6AByAGkAYwBQAGUAcgBmAGkAbAAgA"
        "FIARwBCACAARwBlAG4A6QByAGkAYwBvBBcEMAQzBDAEOwRMBD0EOAQ5ACAEPwRABD4ERAQ"
        "wBDkEOwAgAFIARwBCAFAAcgBvAGYAaQBsACAAZwDpAG4A6QByAGkAcQB1AGUAIABSAFYAQ"
        "pAadSgAIABSAEcAQgAggnJfaWPPj/AAUAByAG8AZgBp/wBsAG8AIABSAEcAQgAgAGcAZQB"
        "uAGUAcgBpAGMAbwBHAGUAbgBlAHIAaQBzAGsAIABSAEcAQgAtAHAAcgBvAGYAaQBsx3y8G"
        "AAgAFIARwBCACDVBLhc0wzHfABPAGIAZQBjAG4A/QAgAFIARwBCACAAcAByAG8AZgBpAGw"
        "F5AXoBdUF5AXZBdwAIABSAEcAQgAgBdsF3AXcBdkAQQBsAGwAZwBlAG0AZQBpAG4AZQBzA"
        "CAAUgBHAEIALQBQAHIAbwBmAGkAbADBAGwAdABhAGwA4QBuAG8AcwAgAFIARwBCACAAcAB"
        "yAG8AZgBpAGxmbpAaACAAUgBHAEIAIGPPj//wZYdO9k4AgiwAIABSAEcAQgAgMNcw7TDVM"
        "KEwpDDrAFAAcgBvAGYAaQBsACAAUgBHAEIAIABnAGUAbgBlAHIAaQBjA5MDtQO9A7kDugP"
        "MACADwAPBA78DxgOvA7sAIABSAEcAQgBQAGUAcgBmAGkAbAAgAFIARwBCACAAZwBlAG4A6"
        "QByAGkAYwBvAEEAbABnAGUAbQBlAGUAbgAgAFIARwBCAC0AcAByAG8AZgBpAGUAbA5CDhs"
        "OIw5EDh8OJQ5MACAAUgBHAEIAIA4XDjEOSA4nDkQOGwBHAGUAbgBlAGwAIABSAEcAQgAgA"
        "FAAcgBvAGYAaQBsAGkAWQBsAGX/AGkAbgBlAG4AIABSAEcAQgAtAHAAcgBvAGYAaQBpAGw"
        "AaQBVAG4AaQB3AGUAcgBzAGEAbABuAHkAIABwAHIAbwBmAGkAbAAgAFIARwBCBB4EMQRJB"
        "DgEOQAgBD8EQAQ+BEQEOAQ7BEwAIABSAEcAQgZFBkQGQQAgBioGOQYxBkoGQQAgAFIARwB"
        "CACAGJwZEBjkGJwZFAEcAZQBuAGUAcgBpAGMAIABSAEcAQgAgAFAAcgBvAGYAaQBsAGUAR"
        "wBlAG4AZQByAGUAbAAgAFIARwBCAC0AYgBlAHMAawByAGkAdgBlAGwAcwBldGV4dAAAAAB"
        "Db3B5cmlnaHQgMjAwrzcgQXBwbGUgSW5jLiwgYWxsIHJpZ2h0cyByZXNlcnZlZC4AWFlaI"
        "AAAAAAAAPNSAAEAAAABFs9YWVogAAAAAAAAdE0AAD3uAAAD0FhZWiAAAAAAAABadQAArHM"
        "AABc0WFlaIAAAAAAAACgaAAAVnwAAuDZjdXJ2AAAAAAAAAAEBzQAAc2YzMgAAAAAAAQxCA"
        "AAF3v//8yYAAAeSAAD9kf//+6L///2jAAAD3AAAwGwALAAAAAAQABAAAARDsIFJ62xYDhD"
        "Y+l+CXJIxBQoxEMdUtNI1KQUVA1nO4XqeAQKebwgUDn+DgPEoUS6PuyfRydQplVXMDpvdS"
        "q3U7G0YAQA7) no-repeat;\n"
        "float: left; height: 14px; width: 12px; padding-right: 10px; "
        "margin-left: 3px;\n")

def get_tailf_logo():
    return (
        "\"data:image/gif;base64,R0lGODlhSQAgAOYAAAEVLwIVMQYZMwkcNgseOA4gOhEkPR"
        "QmQBUoQRosRB4wSCM0Syc4Tyg4Tyw8UzBAVjREWjpJXj5NYUBOYkNRZUVUaFVVVUhWakxa"
        "bVJbbVFecVNhc1hkdlpmeGZmmVxpelttgGFtfmRvgGRxgWt2hm14iHF8i22AknSAjnaAkn"
        "iAjnqEkoOMmoyMnoaQnoiTn4yUoZKapZ2dsZaeqZieqZegqZuhrJKkpJ2msKOqs6ivtqiv"
        "uKmwt6mwubG2wKK5ubW7w7i9xb+/v73CycTIzsbK0MjOzsrO08zS1s/S2NLU2tXY3dja3d"
        "ze493g5OPk5ePl6eXo6err7e7u8e7w8fLy9P7+/gAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACH5BAkA"
        "AFcAIf8LSUNDUkdCRzEwMTL/AAACMEFEQkUCEAAAbW50clJHQiBYWVogB9AACAALABMAMw"
        "A7YWNzcEFQUEwAAAAAbm9uZQAAAAAAAAAAAAAAAAAAAAAAAPbWAAEAAAAA0y1BREJFAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAKY3BydAAAAP"
        "wAAAAyZGVzYwAAATAAAABrd3RwdAAAAZwAAAAUYmtwdAAAAbAAAAAUclRSQwAAAcQAAAAO"
        "Z1RSQwAAAdQAAAAOYlRSQwAAAeQAAAAOclhZWgAAAfQAAAAUZ1hZWgAAAggAAAAUYlhZWg"
        "AAAhwAAAAUdGV4/3QAAAAAQ29weXJpZ2h0IDIwMDAgQWRvYmUgU3lzdGVtcyBJbmNvcnBv"
        "cmF0ZWQAAABkZXNjAAAAAAAAABFBZG9iZSBSR0IgKDE5OTgpAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAABYWVogAAAAAAAA81EAAQAAAAEWzFhZWiAAAAAAAAAAAAAAAAAAAAAAY3"
        "VydgAAAAAAAAABAjMAAGN1cnYAAAAAAAAAAQIzAABjdXJ2AAAAAAAAAAECMwAAWFlaIAAA"
        "AAAAADKcGAAAT6UAAAT8WFlaIAAAAAAAADSNAACgLAAAD5VYWVogAAAAAAAAJjEAABAvAA"
        "C+nAAsAAAAAEkAIAAAB/+AVleDhIWGh4iEVoKJjY5Xi4yPk5SDUDg4UZKVjYtSTU5TkZyk"
        "gw4EAw5Lg1UbEhQRpVdUMRULCQoNI4uynAMICAMkrA4FBgOyFAQGBgcHBgtTvZwFwAUai1"
        "UPBggFG6QbBMAIzwYJTYcDBcjThQPMAzaQ2tzepNzA5rcFRIY54gYktCMEAwIEGIOs0Ov2"
        "rRILcQgMjFgSxYkPJoZeAJSwaVqVKpIW2qsUotoBBU94KUpoAuAEle1GsdrGsJKVD9UMOI"
        "CZ0EqOGRK46ZxBY8ahGTVm2ODhKIaNGUbn0RxZCCpRqzRsROB2YEGMGIasREnwbtwBAmgD"
        "2LDCIgDat8v/ILxA5BZVEan1Gg4CALfvMrMFAoRVkuDAuMMICOSwAgMi4mMYDkE0cCTbVL"
        "1XCBhGzHkcgbBB1G0mV6C0gLVtS6vGF2wYQYgHKiu8XChAaQOrmTUza0BA2CEbOiww3LVD"
        "Bw6GOBjvoMEBvgMJCjUGFttyXkMVsmvXfmE4uQQUKIRNWEEox46FFkXRgI9A1CvTyckWid"
        "mRFQ45HVRxRME8+rBWENEeCq9RNx9tlWyQ336N9BeRQPZ54l0BrsEH24HXJZifNA2a14gS"
        "ObBgAgkjFNZNhfFVN1uGishUiIIROcBhIg4GhIgNE3SDVmnjUFigfNbVRAgEEkwwgQQSQP"
        "Di/4L8+WcIBsuM5kyPKF4YJFVXCKAbM74Rgl+MDNLoJCEXwFYadAlQ+aOK9BXiGDCfEQKj"
        "TjMiUiNHhOAAWwIj9HDEEkNMWKWBV2LGFwEFIArAkjHWecidjFgBY0SLJSSFoGtiKGQhOX"
        "R6yJc6UdHkg4IsAoFQD4R5BRSCRpKipt78d8h9G45qAASRnhojFZFealgBJUSCE3VICELY"
        "rxjIGpYG+T3C7HdDDNKErhGtwKsVULBATjciiLUCawYQEeBW+SxQ7CNWKLGAULE8MpkCFE"
        "jg3TgGPIABBQtUQx28xUhJZAKsRbQABUom8gC++BTQwSS7kcPMZqNtGRHEzORD75tuz/DW"
        "JSLvsEaADpOg8E7ExiRgDG8E3AKuMQwUQHHKEZwMZyOOHVNfIzFAEJExC2ywgxImOHAAjw"
        "+s8EQOzrH8ARBQhNCNORKwsEQVLAhdGjuIIGqMAys42kkVSQQBBBFQqCTFEUAAgQRIkEgx"
        "BBBHSMFLukAM0cQoVlCBNhBFiHrIFEWkHbeym0SibE8A8mQ4T5C4mF56sloRCAA7\"")

def get_folder_open_img():
    return (
        "url(data:image/gif;base64,R0lGODlhGgAOALMLAJmZmYqKiv///+zs7MzMzGZmZrOz"
        "s7q6uqqqqnZ2duHh4f///wAAAAAAAAAAAAAAACH5BAEAAAsALAAAAAAaAA4AAASScMlJq7"
        "14qgMMIQuBAMAwZBRADIJAGMfwBQE6GW0uGzRS2wuAQPHhABAIAyBAABSe0IJKgiAEDgSF"
        "7OVDBKNQwEQlbBG5CZAiAA4oxsoc8WBAFEALe9SQ6rS2dU5vCwJsTwECKUwmcyMBCYMhUH"
        "gTj1kfRTwFJxKFBYgVlpdNNCUVBHcWCUwHpQacFgJCqp98GBEAOw==)")

def get_folder_closed_img():
    return (
        "url(data:image/gif;base64,R0lGODlhGgAOALMLAJmZmYuLi3p6ev///+zs7MzMzGZm"
        "ZqqqqrS0tLq6uuHh4f///wAAAAAAAAAAAAAAACH5BAEAAAsALAAAAAAaAA4AAASJcMlJq7"
        "14qgROKUtxAABBgJkUFMQwFEhyFoFAKini7idSHwGDQXAYYAADxQdBOjiBQqGgYKx4AomC"
        "YoYAHqLRVVUCKCBdSthhCgYDKIDuTpnoGgptgxged3FHBgpgU2MTASsmdCM1gkNFGDVaHx"
        "91QQQ3KZGSZocHBCEpEgIrCYdxn6EVAnoIGREAOw==)")

def get_leaf_img():
    return (
        "url(data:image/gif;base64,R0lGODlhGgAOALMLAJmZmYuLi3p6ev///+zs7MzMzGZm"
        "ZqqqqrS0tLq6uuHh4f///wAAAAAAAAAAAAAAACH5BAEAAAsALAAAAAAaAA4AAASJcMlJq7"
        "14qgROKUtxAABBgJkUFMQwFEhyFoFAKini7idSHwGDQXAYYAADxQdBOjiBQqGgYKx4AomC"
        "YoYAHqLRVVUCKCBdSthhCgYDKIDuTpnoGgptgxged3FHBgpgU2MTASsmdCM1gkNFGDVaHx"
        "91QQQ3KZGSZocHBCEpEgIrCYdxn6EVAnoIGREAOw==)")
