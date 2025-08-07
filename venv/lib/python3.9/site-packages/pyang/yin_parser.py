import copy
from xml.parsers import expat

from . import syntax
from . import error
from . import statements
from . import util

yin_namespace = "urn:ietf:params:xml:ns:yang:yin:1"

# We're using expat to parse to our own primitive dom-like
# structure, because we need to keep track of the linenumber per
# statement.  And expat is easier to work with than minidom.
class Element(object):
    def __init__(self, ns, local_name, attrs, pos):
        self.ns = ns
        self.local_name = local_name
        self.attrs = attrs
        self.pos = copy.copy(pos)
        self.children = []
        self.data = ''

    def find_child(self, ns, local_name):
        for ch in self.children:
            if ch.ns == ns and ch.local_name == local_name:
                return ch
        return None

    def remove_child(self, ch):
        self.children.remove(ch)

    def find_attribute(self, name):
        try:
            return self.attrs[name]
        except KeyError:
            return None

    def remove_attribute(self, name):
        del self.attrs[name]

class YinParser(object):

    ns_sep = "}"
    """namespace separator"""

    def __init__(self, extra=None):
        self.parser = expat.ParserCreate("UTF-8", self.ns_sep)
        self.parser.CharacterDataHandler = self.char_data
        self.parser.StartElementHandler = self.start_element
        self.parser.EndElementHandler = self.end_element
        self.extra = {} if extra is None else extra

    @staticmethod
    def split_qname(qname):
        """Split `qname` into namespace URI and local name

        Return namespace and local name as a tuple."""
        res = qname.split(YinParser.ns_sep)
        if len(res) == 1:       # no namespace
            return None, res[0]
        else:
            return res

    def parse(self, ctx, ref, text):
        """Parse the string `text` containing a YIN (sub)module.

        Return a Statement on success or None on failure.
        """

        self.ctx = ctx
        self.pos = error.Position(ref)
        self.top = None
        self.top_element = None

        self.uri = None
        self.nsmap = {}
        self.prefixmap = {}
        self.included = []
        self.extensions = {}

        self.data = ''
        self.element_stack = []

        try:
            self.parser.Parse(text.encode('utf-8'), True)
        except error.Abort:
            return None
        except expat.ExpatError as ex:
            self.pos.line = ex.lineno
            error.err_add(self.ctx.errors, self.pos, 'SYNTAX_ERROR',
                          str(ex).split(":")[0])
            return None

        self.look_ahead()
        self.create_statement(self.top_element, None)
        return self.top

    def get_lineno(self):
        """Return current line of the parser."""

        return self.parser.CurrentLineNumber
    lineno = property(get_lineno, doc="parser position")

    # Handlers for Expat events

    def start_element(self, name, attrs):
        name = str(name) # convert from unicode strings
        self.pos.line = self.lineno
        (ns, local_name) = self.split_qname(name)
        e = Element(ns, local_name, attrs, self.pos)
        if self.data.lstrip() != '':
            error.err_add(self.ctx.errors, self.pos, 'SYNTAX_ERROR',
                          "unexpected element - mixed content")
        self.data = ''
        if not self.element_stack:
            # this is the top-level element
            self.top_element = e
            self.element_stack.append(e)
            # special case - the top-level statement has its argument
            # as an attribute, so we can save it here
            try:
                (argname, _arg_is_elem) = syntax.yin_map[e.local_name]
                arg = e.find_attribute(argname)
                # create and save the top-level statement here, so
                # we get a correct Statement in pos.
                stmt = statements.new_statement(None, None,
                                                e.pos, e.local_name, arg)
                self.top = stmt
                self.pos.top = stmt
            except:
                pass
            return
        else:
            parent = self.element_stack[-1]
            parent.children.append(e)
            self.element_stack.append(e)

    def char_data(self, data):
        self.data += data

    def end_element(self, name):
        self.pos.line = self.lineno
        e = self.element_stack[-1]
        e.data = self.data
        self.data = ''
        # end of statement, pop from stack
        del self.element_stack[-1]

    # Builds the statement tree

    def create_statement(self, e, parent):
        if e.ns == yin_namespace:
            keywd = e.local_name
            try:
                (argname, arg_is_elem) = syntax.yin_map[keywd]
            except KeyError:
                error.err_add(self.ctx.errors, e.pos,
                              'UNKNOWN_KEYWORD', keywd)
                return None
        else:
            # extension
            try:
                prefix = self.prefixmap[e.ns]
            except KeyError:
                error.err_add(self.ctx.errors, e.pos,
                              'MODULE_NOT_IMPORTED', e.ns)
                return None
            keywd = (prefix, e.local_name)
            keywdstr = util.keyword_to_str(keywd)
            if 'no_extensions' in self.extra:
                return None
            res = self.find_extension(e.ns, e.local_name)
            if res is None:
                error.err_add(self.ctx.errors, e.pos,
                              'UNKNOWN_KEYWORD', keywdstr)
                return None
            (arg_is_elem, argname)  = res

        keywdstr = util.keyword_to_str(keywd)
        if arg_is_elem is True:
            # find the argument element
            arg_elem = e.find_child(e.ns, argname)
            if arg_elem is None:
                arg = None
                error.err_add(self.ctx.errors, e.pos,
                              'MISSING_ARGUMENT_ELEMENT', (argname, keywdstr))

            else:
                if self.ctx.trim_yin:
                    arg = "\n".join([x.strip() for x in
                                     arg_elem.data.strip().splitlines()])
                else:
                    arg = arg_elem.data
                e.remove_child(arg_elem)
        elif arg_is_elem is False:
            arg = e.find_attribute(argname)
            if arg is None:
                error.err_add(self.ctx.errors, e.pos,
                              'MISSING_ARGUMENT_ATTRIBUTE', (argname, keywdstr))
            else:
                e.remove_attribute(argname)
        else:
            # no arguments
            arg = None

        self.check_attr(e.pos, e.attrs)

        if parent is not None:
            stmt = statements.new_statement(self.top, parent, e.pos, keywd, arg)
            parent.substmts.append(stmt)
        else:
            stmt = self.top

        for ch in e.children:
            self.create_statement(ch, stmt)

    def check_attr(self, pos, attrs):
        """Check for unknown attributes."""

        for at in attrs:
            (ns, local_name) = self.split_qname(at)
            if ns is None:
                error.err_add(self.ctx.errors, pos,
                              'UNEXPECTED_ATTRIBUTE', local_name)
            elif ns == yin_namespace:
                error.err_add(self.ctx.errors, pos,
                              'UNEXPECTED_ATTRIBUTE', "{"+at)
            # allow foreign attributes
            # FIXME: hmm... is this the right thing to do?
            # these things are supposed to be handled with extensions...

    def look_ahead(self):
        # To find an extension <smi:oid> we need to find the module
        # that corresponds to 'smi'.  We get extension's URI from expat,
        # so we need a map from URI -> module.  This works for
        # imported modules, but for extensions defined in the local
        # module we have to check if the extension's URI is
        # the local URI.
        #
        # If we're a submodule, we need to find our module's
        # namespace, so we need to parse the module :(

        # 1.  find our own namespace URI
        if self.top_element.local_name == 'module':
            p = self.top_element.find_child(yin_namespace, 'namespace')
            if p is not None:
                self.uri = p.find_attribute('uri')
            p = self.top_element.find_child(yin_namespace, 'prefix')
            if p is not None:
                self.prefixmap[self.uri] = p.find_attribute('value')
        elif self.top_element.local_name == 'submodule':
            p = self.top_element.find_child(yin_namespace, 'belongs-to')
            modname = p.find_attribute('module')
            # read the parent module in order to find the namespace uri
            res = self.ctx.read_module(modname, extra={'no_include':True,
                                                       'no_extensions':True})
            if not res:
                pass
            elif res == 'not_found':
                error.err_add(self.ctx.errors, p.pos,
                              'MODULE_NOT_FOUND', modname)
            elif isinstance(res, tuple) and res[0] == 'read_error':
                error.err_add(self.ctx.errors, p.pos, 'READ_ERROR', res[1])
            else:
                namespace = res.search_one('namespace')
                if namespace is None or namespace.arg is None:
                    pass
                else:
                    # success - save our uri
                    self.uri = namespace.arg
        else:
            return

        # 2.  read all imports and includes and add the modules to the context
        #     and to the nsmap.
        if not hasattr(self.ctx, 'yin_module_map'):
            self.ctx.yin_module_map = {}

        if self.top.keyword == 'module':
            if self.top.arg not in self.ctx.yin_module_map:
                self.ctx.yin_module_map[self.top.arg] = []
            mymodules = self.ctx.yin_module_map[self.top.arg]
        else:
            mymodules = []

        for ch in self.top_element.children:
            if ch.ns == yin_namespace and ch.local_name == 'import':
                modname = ch.find_attribute('module')
                if modname is not None:
                    if modname in mymodules:
                        # circular import; ignore here and detect in validation
                        pass
                    else:
                        mymodules.append(modname)
                        mod = self.ctx.search_module(ch.pos, modname)
                        if mod is not None:
                            ns = mod.search_one('namespace')
                            if ns is not None and ns.arg is not None:
                                # record the uri->mod mapping
                                self.nsmap[ns.arg] = mod
                                # also record uri->prefix, where prefix
                                # is the *yang* prefix, *not* the XML prefix
                                # (it can be different in theory...)
                                p = ch.find_child(yin_namespace, 'prefix')
                                if p is not None:
                                    prefix = p.find_attribute('value')
                                    if prefix is not None:
                                        self.prefixmap[ns.arg] = prefix

            elif (ch.ns == yin_namespace and ch.local_name == 'include' and
                  'no_include' not in self.extra):
                modname = ch.find_attribute('module')
                if modname is not None:
                    mod = self.ctx.search_module(ch.pos, modname)
                    if mod is not None:
                        self.included.append(mod)

        # 3.  find all extensions defined locally
        for ch in self.top_element.children:
            if ch.ns == yin_namespace and ch.local_name == 'extension':
                extname = ch.find_attribute('name')
                if extname is None:
                    continue
                arg = ch.find_child(yin_namespace, 'argument')
                if arg is None:
                    self.extensions[extname] = (None, None)
                else:
                    argname = arg.find_attribute('name')
                    if argname is None:
                        continue
                    arg_is_elem = arg.find_child(yin_namespace, 'yin-element')
                    if arg_is_elem is None:
                        self.extensions[extname] = (False, argname)
                        continue
                    val = arg_is_elem.find_attribute('value')
                    if val == 'false':
                        self.extensions[extname] = (False, argname)
                    elif val == 'true':
                        self.extensions[extname] = (True, argname)

    def find_extension(self, uri, extname):
        def find_in_mod(mod):
            ext = self.search_definition(mod, 'extension', extname)
            if ext is None:
                return None
            ext_arg = ext.search_one('argument')
            if ext_arg is None:
                return (None, None)
            arg_is_elem = ext_arg.search_one('yin-element')
            if arg_is_elem is None or arg_is_elem.arg == 'false':
                return (False, ext_arg.arg)
            else:
                return (True, ext_arg.arg)

        if uri == self.uri:
            # extension is defined locally or in one of our submodules
            try:
                return self.extensions[extname]
            except KeyError:
                pass
            # check submodules
            for submod in self.included:
                res = find_in_mod(submod)
                if res is not None:
                    return res
            return None
        else:
            try:
                mod = self.nsmap[uri]
                return find_in_mod(mod)
            except KeyError:
                return None

    def search_definition(self, module, keyword, arg):
        """Search for a defintion with `keyword` `name`
        Search the module and its submodules."""
        r = module.search_one(keyword, arg)
        if r is not None:
            return r
        for i in module.search('include'):
            modulename = i.arg
            m = self.ctx.search_module(i.pos, modulename)
            if m is not None:
                r = m.search_one(keyword, arg)
                if r is not None:
                    return r
        return None
