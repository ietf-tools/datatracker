# Copyright (c) 2013 by Ladislav Lhotka, CZ.NIC <lhotka@nic.cz>
#                       Martin Bjorklund <mbj@tail-f.com>
#
# Translator of YANG to the hybrid DSDL schema (see RFC 6110).
#
# Permission to use, copy, modify, and/or distribute this software for any
# purpose with or without fee is hereby granted, provided that the above
# copyright notice and this permission notice appear in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
# WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
# ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
# WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
# ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
# OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

"""Translator from YANG to hybrid DSDL schema.

It is designed as a plugin for the pyang program and defines several
new command-line options:

--dsdl-no-documentation
    No output of DTD compatibility documentation annotations

--dsdl-no-dublin-core
    No output of Dublin Core annotations

--dsdl-record-defs
    Record all top-level defs, even if they are not used

Three classes are defined in this module:

* `DSDLPlugin`: pyang plugin interface class

* `HybridDSDLSchema`: provides instance that performs the mapping
  of input YANG modules to the hybrid DSDL schema.

* `Patch`: utility class representing a patch to the YANG tree
  where augment and refine statements are recorded.
"""

__docformat__ = "reStructuredText"

import sys
import optparse
import time


from pyang import plugin, error, xpath_lexer, util, statements, types

from .schemanode import SchemaNode

def pyang_plugin_init():
    plugin.register_plugin(DSDLPlugin())

class DSDLPlugin(plugin.PyangPlugin):
    def add_output_format(self, fmts):
        self.multiple_modules = True
        fmts['dsdl'] = self
    def add_opts(self, optparser):
        optlist = [
            optparse.make_option("--dsdl-no-documentation",
                                 dest="dsdl_no_documentation",
                                 action="store_true",
                                 default=False,
                                 help="No output of DTD compatibility"
                                 " documentation annotations"),
            optparse.make_option("--dsdl-no-dublin-core",
                                 dest="dsdl_no_dublin_core",
                                 action="store_true",
                                 default=False,
                                 help="No output of Dublin Core"
                                 " metadata annotations"),
            optparse.make_option("--dsdl-record-defs",
                                 dest="dsdl_record_defs",
                                 action="store_true",
                                 default=False,
                                 help="Record all top-level defs"
                                 " (even if not used)"),
            optparse.make_option("--dsdl-lax-yang-version",
                                 dest="dsdl_lax_yang_version",
                                 action="store_true",
                                 default=False,
                                 help="Try to translate modules with "
                                 "unsupported YANG versions (use at own risk)"),
            ]
        g = optparser.add_option_group("Hybrid DSDL schema "
                                       "output specific options")
        g.add_options(optlist)

    def emit(self, ctx, modules, fd):
        if 'submodule' in [ m.keyword for m in modules ]:
            raise error.EmitError("Cannot translate submodules")
        emit_dsdl(ctx, modules, fd)

def emit_dsdl(ctx, modules, fd):
    for epos, etag, eargs in ctx.errors:
        if error.is_error(error.err_level(etag)):
            raise error.EmitError("DSDL translation needs a valid module")
    schema = HybridDSDLSchema().from_modules(modules,
                                  ctx.opts.dsdl_no_dublin_core,
                                  ctx.opts.dsdl_no_documentation,
                                  ctx.opts.dsdl_record_defs,
                                  ctx.opts.dsdl_lax_yang_version,
                                  debug=0)
    fd.write(schema.serialize())

class Patch(object):

    """Instances of this class represent a patch to the YANG tree.

    A Patch is filled with substatements of 'refine' and/or 'augment'
    that are to be applied to a single node.

    Instance variables:

    * `self.path`: list specifying the relative path to the node where
      the patch is to be applied

    * `self.plist`: list of statements to apply
    """

    def __init__(self, path, refaug):
        """Initialize the instance with `refaug` statement.

        `refaug` must be either 'refine' or 'augment'.
        """
        self.path = path
        self.plist = [refaug]

    def pop(self):
        """Pop and return the first element of `self.path`."""
        return self.path.pop(0)

    def combine(self, patch):
        """Add `patch.plist` to `self.plist`."""
        exclusive = set(["config", "default", "mandatory", "presence",
                     "min-elements", "max-elements"])
        kws = set([s.keyword for s in self.plist]) & exclusive
        add = [n for n in patch.plist if n.keyword not in kws]
        self.plist.extend(add)

class HybridDSDLSchema(object):

    """Instance of this class maps YANG to the hybrid DSDL schema.

    Typically, only a single instance is created.

    Instance variables:

    * `self.all_defs`: dictionary of all named pattern
      definitions. The keys are mangled names of the definitions.

    * `self.data`: root of the data tree.

    * `self.debug`: debugging information level (0 = no debugging).

    * `self.gg_level`: level of immersion in global groupings.

    * `self.global_defs`: dictionary of global (aka chameleon) named
      pattern definitions. The keys are mangled names of the
      definitions.

    * `self.identities`: dictionary of identity names as keys and the
      corresponding name pattern definitions as values.

    * `self.identity_deps: each item has an identity (statement) as
      the key and a list of identities derived from the key identity
      as the value.

    * `self.local_defs`: dictionary of local named pattern
      definitions. The keys are mangled names of the definitions.

    * `self.local_grammar`: the inner <grammar> element containing the
      mapping of a single YANG module.

    * `self.module`: the module being processed.

    * `self.module_prefixes`: maps module names to (disambiguated)
      prefixes.

    * `self.namespaces`: maps used namespace URIs to (disambiguated)
      prefixes.

    * `self.notifications`: root of the subtree containing
      notifications.

    * `self.prefix_stack`: stack of active module prefixes. A new
      prefix is pushed on the stack for an augment from an external
      module.

    * `self.rpcs`: root of the subtree containing RPC signatures.

    * `self.stmt_handler`: dictionary of methods that are dispatched
      for handling individual YANG statements. Its keys are YANG
      statement keywords.

    * `self.top_grammar`: the outer (root) <grammar> element.

    * `self.type_handler`: dictionary of methods that are dispatched
      for handling individual YANG types. Its keys are the names of
      YANG built-in types.

    * `self.tree`: outer <start> pattern.

    """

    YANG_version = 1.1
    """Checked against the yang-version statement, if present."""

    dc_uri = "http://purl.org/dc/terms"
    """Dublin Core URI"""
    a_uri =  "http://relaxng.org/ns/compatibility/annotations/1.0"
    """DTD compatibility annotations URI"""

    datatype_map = {
        "int8": "byte",
        "int16": "short",
        "int32": "int",
        "int64": "long",
        "uint8": "unsignedByte",
        "uint16": "unsignedShort",
        "uint32": "unsignedInt",
        "uint64": "unsignedLong",
        "decimal64": "decimal",
        "binary": "base64Binary",
        "string": "string",
    }
    """Mapping of simple datatypes from YANG to W3C datatype library"""

    data_nodes = ("leaf", "container", "leaf-list", "list",
                  "anydata", "anyxml", "rpc", "notification")
    """Keywords of YANG data nodes."""

    schema_nodes = data_nodes + ("choice", "case")
    """Keywords of YANG schema nodes."""

    def __init__(self):
        """Initialize the dispatch dictionaries."""
        self.stmt_handler = {
            "action": self.noop,
            "anyxml": self.anyxml_stmt,
            "anydata": self.anyxml_stmt,
            "argument": self.noop,
            "augment": self.noop,
            "base": self.noop,
            "belongs-to": self.noop,
            "bit": self.noop,
            "case": self.case_stmt,
            "choice": self.choice_stmt,
            "config": self.nma_attribute,
            "contact": self.noop,
            "container": self.container_stmt,
            "default": self.noop,
            "deviation": self.noop,
            "deviate": self.noop,
            "description": self.description_stmt,
            "enum" : self.enum_stmt,
            "error-app-tag": self.noop,
            "error-message": self.noop,
            "extension": self.noop,
            "feature": self.noop,
            "fraction-digits": self.noop,
            "identity": self.noop,
            "if-feature": self.noop,
            "import" : self.noop,
            "include" : self.include_stmt,
            "input": self.noop,
            "grouping" : self.noop,
            "key": self.noop,
            "leaf": self.leaf_stmt,
            "leaf-list": self.leaf_list_stmt,
            "length": self.noop,
            "list": self.list_stmt,
            "mandatory": self.noop,
            "max-elements": self.noop,
            "min-elements": self.noop,
            "modifier": self.noop,
            "module": self.noop,
            "must": self.must_stmt,
            "namespace": self.noop,
            "notification": self.notification_stmt,
            "ordered-by": self.nma_attribute,
            "organization": self.noop,
            "output": self.noop,
            "path": self.noop,
            "pattern": self.noop,
            "position": self.noop,
            "prefix": self.noop,
            "presence": self.noop,
            "range": self.noop,
            "reference": self.reference_stmt,
            "refine": self.noop,
            "require-instance": self.noop,
            "revision": self.noop,
            "revision-date": self.noop,
            "rpc": self.rpc_stmt,
            "status": self.nma_attribute,
            "submodule": self.noop,
            "type": self.type_stmt,
            "typedef" : self.noop,
            "unique" : self.unique_stmt,
            "units" : self.nma_attribute,
            "uses" : self.uses_stmt,
            "value": self.noop,
            "when" : self.when_stmt,
            "yang-version": self.yang_version_stmt,
            "yin-element": self.noop,
        }
        self.ext_handler = {
            "ietf-yang-metadata": {
                "annotation": self.noop
            }
        }
        self.type_handler = {
            "boolean": self.boolean_type,
            "binary": self.binary_type,
            "bits": self.bits_type,
            "decimal64": self.numeric_type,
            "enumeration": self.choice_type,
            "empty": self.noop,
            "identityref": self.identityref_type,
            "instance-identifier": self.instance_identifier_type,
            "int8": self.numeric_type,
            "int16": self.numeric_type,
            "int32": self.numeric_type,
            "int64": self.numeric_type,
            "leafref": self.leafref_type,
            "string" : self.string_type,
            "uint8": self.numeric_type,
            "uint16": self.numeric_type,
            "uint32": self.numeric_type,
            "uint64": self.numeric_type,
            "union": self.choice_type,
        }

    def serialize(self):
        """Return the string representation of the receiver."""
        res = '<?xml version="1.0" encoding="UTF-8"?>'
        for ns in self.namespaces:
            self.top_grammar.attr["xmlns:" + self.namespaces[ns]] = ns
        res += self.top_grammar.start_tag()
        for ch in self.top_grammar.children:
            res += ch.serialize()
        res += self.tree.serialize()
        for d in self.global_defs:
            res += self.global_defs[d].serialize()
        for i in self.identities:
            res += self.identities[i].serialize()
        return res + self.top_grammar.end_tag()

    def from_modules(self, modules, no_dc=False, no_a=False,
                     record_defs=False, lax_yang_version=False, debug=0):
        """Return the instance representing mapped input modules."""
        self.namespaces = {
            "urn:ietf:params:xml:ns:netmod:dsdl-annotations:1" : "nma",
        }
        if not no_dc:
            self.namespaces[self.dc_uri] = "dc"
        if not no_a:
            self.namespaces[self.a_uri] = "a"
        self.global_defs = {}
        self.all_defs = {}
        self.identity_deps = {}
        self.identities = {}
        self.debug = debug
        self.module_prefixes = {}
        gpset = {}
        self.gg_level = 0
        metadata = []
        self.has_meta = False
        for module in modules[0].i_ctx.modules.values():
            yver = module.search_one("yang-version")
            if yver and float(yver.arg) > 1.0 and not lax_yang_version:
                raise error.EmitError(
                    "DSDL plugin supports only YANG version 1.")
            if module.keyword == "module":
                for idn in module.i_identities.values():
                    self.register_identity(idn)
        for module in modules:
            self.add_namespace(module)
            self.module = module
            annots = module.search(("ietf-yang-metadata", "annotation"))
            for ann in annots:
                aname = (self.module_prefixes[ann.main_module().arg] + ":" +
                         ann.arg)
                optel = SchemaNode("optional")
                atel = SchemaNode("attribute", optel).set_attr("name", aname)
                self.handle_substmts(ann, atel)
                metadata.append(optel)
        if metadata:
            self.has_meta = True
            metel = SchemaNode.define("__yang_metadata__")
            self.global_defs["__yang_metadata__"] = metel
            for mattr in metadata:
                metel.subnode(mattr)
        for module in modules:
            self.module = module
            self.prefix_stack = [self.module_prefixes[module.arg]]
            for aug in module.search("augment"):
                self.add_patch(gpset, aug)
            for sub in [ module.i_ctx.get_module(inc.arg)
                         for inc in module.search("include") ]:
                for aug in sub.search("augment"):
                    self.add_patch(gpset, aug)
        self.setup_top()
        for module in modules:
            self.module = module
            self.local_defs = {}
            if record_defs:
                self.preload_defs()
            self.prefix_stack = [self.module_prefixes[module.arg]]
            self.create_roots(module)
            self.lookup_expand(module, list(gpset))
            self.handle_substmts(module, self.data, gpset)
            for d in list(self.local_defs.values()):
                self.local_grammar.subnode(d)
            self.tree.subnode(self.local_grammar)
            self.all_defs.update(self.local_defs)
        self.all_defs.update(self.global_defs)
        self.dc_element(self.top_grammar, "date", time.strftime("%Y-%m-%d"))
        return self

    def setup_top(self):
        """Create top-level elements of the hybrid schema."""
        self.top_grammar = SchemaNode("grammar")
        self.top_grammar.attr = {
            "xmlns": "http://relaxng.org/ns/structure/1.0",
            "datatypeLibrary": "http://www.w3.org/2001/XMLSchema-datatypes"}
        self.tree = SchemaNode("start")

    def create_roots(self, yam):
        """Create the top-level structure for module `yam`."""
        self.local_grammar = SchemaNode("grammar")
        self.local_grammar.attr = {
            "ns": yam.search_one("namespace").arg,
            "nma:module": self.module.arg}
        src_text = "YANG module '%s'" % yam.arg
        revs = yam.search("revision")
        if len(revs) > 0:
            src_text += " revision %s" % self.current_revision(revs)
        self.dc_element(self.local_grammar, "source", src_text)
        start = SchemaNode("start", self.local_grammar)
        self.data = SchemaNode("nma:data", start, interleave=True)
        self.data.occur = 2
        self.rpcs = SchemaNode("nma:rpcs", start, interleave=False)
        self.notifications = SchemaNode("nma:notifications", start,
                                        interleave=False)

    def yang_to_xpath(self, xpe):
        """Transform YANG's `xpath` to a form suitable for Schematron.

        1. Prefixes are added to unprefixed local names. Inside global
           groupings, the prefix is represented as the variable
           '$pref' which is substituted via Schematron abstract
           patterns.
        2. '$root' is prepended to every absolute location path.
        """
        if self.gg_level:
            pref = "$pref:"
        else:
            pref = self.prefix_stack[-1] + ":"
        toks = xpath_lexer.scan(xpe)
        prev = None
        res = ""
        for tok in toks:
            if (tok.type == "SLASH" and
                prev not in ("DOT", "DOTDOT", "RPAREN", "RBRACKET", "name",
                             "wildcard", "prefix_test")):
                res += "$root"
            elif tok.type == "name" and ":" not in tok.value:
                res += pref
            res += tok.value
            if tok.type != "_whitespace":
                prev = tok.type
        return res

    def add_namespace(self, module):
        """Add item uri:prefix for `module` to `self.namespaces`.

        The prefix to be actually used for `uri` is returned.  If the
        namespace is already present, the old prefix is used.  Prefix
        clashes are resolved by disambiguating `prefix`.
        """
        uri = module.search_one("namespace").arg
        prefix = module.search_one("prefix").arg
        if uri in self.namespaces:
            return self.namespaces[uri]
        end = 1
        new = prefix
        while new in list(self.namespaces.values()):
            new = "%s%x" % (prefix,end)
            end += 1
        self.namespaces[uri] = new
        self.module_prefixes[module.arg] = new
        for inc in module.search("include"):
            self.module_prefixes[inc.arg] = new
        return new

    def register_identity(self, id_stmt):
        """Register `id_stmt` with its base identity, if any.
        """
        bst = id_stmt.search_one("base")
        if bst:
            bder = self.identity_deps.setdefault(bst.i_identity, [])
            bder.append(id_stmt)

    def add_derived_identity(self, id_stmt):
        """Add pattern def for `id_stmt` and all derived identities.

        The corresponding "ref" pattern is returned.
        """
        p = self.add_namespace(id_stmt.main_module())
        if id_stmt not in self.identities:   # add named pattern def
            self.identities[id_stmt] = SchemaNode.define("__%s_%s" %
                                                         (p, id_stmt.arg))
            parent = self.identities[id_stmt]
            if id_stmt in self.identity_deps:
                parent = SchemaNode.choice(parent, occur=2)
                for i in self.identity_deps[id_stmt]:
                    parent.subnode(self.add_derived_identity(i))
            idval = SchemaNode("value", parent, p+":"+id_stmt.arg)
            idval.attr["type"] = "QName"
        res = SchemaNode("ref")
        res.attr["name"] = self.identities[id_stmt].attr["name"]
        return res

    def preload_defs(self):
        """Preload all top-level definitions."""
        for d in (self.module.search("grouping") +
                  self.module.search("typedef")):
            uname, dic = self.unique_def_name(d)
            self.install_def(uname, d, dic)

    def add_prefix(self, name, stmt):
        """Return `name` prepended with correct prefix.

        If the name is already prefixed, the prefix may be translated
        to the value obtained from `self.module_prefixes`.  Unmodified
        `name` is returned if we are inside a global grouping.
        """
        if self.gg_level:
            return name
        pref, colon, local = name.partition(":")
        if colon:
            return (self.module_prefixes[stmt.i_module.i_prefixes[pref][0]]
                    + ":" + local)
        else:
            return self.prefix_stack[-1] + ":" + pref

    def qname(self, stmt):
        """Return (prefixed) node name of `stmt`.

        The result is prefixed with the local prefix unless we are
        inside a global grouping.
        """
        if self.gg_level:
            return stmt.arg
        return self.prefix_stack[-1] + ":" + stmt.arg

    def dc_element(self, parent, name, text):
        """Add DC element `name` containing `text` to `parent`."""
        if self.dc_uri in self.namespaces:
            dcel = SchemaNode(self.namespaces[self.dc_uri] + ":" + name,
                              text=text)
            parent.children.insert(0,dcel)

    def get_default(self, stmt, refd):
        """Return default value for `stmt` node.

        `refd` is a dictionary of applicable refinements that is
        constructed in the `process_patches` method.
        """
        if refd["default"]:
            return refd["default"]
        defst = stmt.search_one("default")
        if defst:
            return defst.arg
        return None

    def unique_def_name(self, stmt, inrpc=False):
        """Mangle the name of `stmt` (typedef or grouping).

        Return the mangled name and dictionary where the definition is
        to be installed. The `inrpc` flag indicates when we are inside
        an RPC, in which case the name gets the "__rpc" suffix.
        """
        module = stmt.main_module()
        name = ""
        while True:
            pref = stmt.arg if stmt.arg else stmt.keyword
            name = "__" + pref + name
            if stmt.keyword == "grouping":
                name = "_" + name
            if stmt.parent.parent is None:
                break
            stmt = stmt.parent
        defs = (self.global_defs
                if stmt.keyword in ("grouping", "typedef")
                else self.local_defs)
        if inrpc:
            name += "__rpc"
        return (module.arg + name, defs)

    def add_patch(self, pset, augref):
        """Add patch corresponding to `augref` to `pset`.

        `augref` must be either 'augment' or 'refine' statement.
        """
        try:
            path = [ self.add_prefix(c, augref)
                     for c in augref.arg.split("/") if c ]
        except KeyError:
            # augment of a module that's not among input modules
            return
        car = path[0]
        patch = Patch(path[1:], augref)
        if car in pset:
            sel = [ x for x in pset[car] if patch.path == x.path ]
            if sel:
                sel[0].combine(patch)
            else:
                pset[car].append(patch)
        else:
            pset[car] = [patch]

    def apply_augments(self, auglist, p_elem, pset):
        """Handle substatements of augments from `auglist`.

        The augments are applied in the context of `p_elem`.  `pset`
        is a patch set containing patches that may be applicable to
        descendants.
        """
        for a in auglist:
            par = a.parent
            if a.search_one("when") is None:
                wel = p_elem
            else:
                if p_elem.interleave:
                    kw = "interleave"
                else:
                    kw = "group"
                wel = SchemaNode(kw, p_elem, interleave=p_elem.interleave)
                wel.occur = p_elem.occur
            if par.keyword == "uses":
                self.handle_substmts(a, wel, pset)
                continue
            if par.keyword == "submodule":
                mnam = par.i_including_modulename
            else:
                mnam = par.arg
            if self.prefix_stack[-1] == self.module_prefixes[mnam]:
                self.handle_substmts(a, wel, pset)
            else:
                self.prefix_stack.append(self.module_prefixes[mnam])
                self.handle_substmts(a, wel, pset)
                self.prefix_stack.pop()

    def current_revision(self, r_stmts):
        """Pick the most recent revision date.

        `r_stmts` is a list of 'revision' statements.
        """
        cur = max([[int(p) for p in r.arg.split("-")] for r in r_stmts])
        return "%4d-%02d-%02d" % tuple(cur)

    def insert_doc(self, p_elem, docstring):
        """Add <a:documentation> with `docstring` to `p_elem`."""
        dtag = self.namespaces[self.a_uri] + ":documentation"
        elem = SchemaNode(dtag, text=docstring)
        p_elem.annots.append(elem)

    def install_def(self, name, dstmt, def_map, interleave=False):
        """Install definition `name` into the appropriate dictionary.

        `dstmt` is the definition statement ('typedef' or 'grouping')
        that is to be mapped to a RELAX NG named pattern '<define
        name="`name`">'. `def_map` must be either `self.local_defs` or
        `self.global_defs`. `interleave` determines the interleave
        status inside the definition.
        """
        delem = SchemaNode.define(name, interleave=interleave)
        delem.attr["name"] = name
        def_map[name] = delem
        if def_map is self.global_defs:
            self.gg_level += 1
        self.handle_substmts(dstmt, delem)
        if def_map is self.global_defs:
            self.gg_level -= 1

    def rng_annotation(self, stmt, p_elem):
        """Append YIN representation of extension statement `stmt`."""
        ext = stmt.i_extension
        prf, extkw = stmt.raw_keyword
        (modname,rev)=stmt.i_module.i_prefixes[prf]
        prefix = self.add_namespace(
            statements.modulename_to_module(self.module,modname,rev))
        eel = SchemaNode(prefix + ":" + extkw, p_elem)
        argst = ext.search_one("argument")
        if argst:
            if argst.search_one("yin-element", "true"):
                SchemaNode(prefix + ":" + argst.arg, eel, stmt.arg)
            else:
                eel.attr[argst.arg] = stmt.arg
        self.handle_substmts(stmt, eel)

    def propagate_occur(self, node, value):
        """Propagate occurence `value` to `node` and its ancestors.

        Occurence values are defined and explained in the SchemaNode
        class.
        """
        while node.occur < value:
            node.occur = value
            if node.name == "define":
                break
            node = node.parent

    def process_patches(self, pset, stmt, elem, altname=None):
        """Process patches for data node `name` from `pset`.

        `stmt` provides the context in YANG and `elem` is the parent
        element in the output schema. Refinements adding documentation
        and changing the config status are immediately applied.

        The returned tuple consists of:
        - a dictionary of refinements, in which keys are the keywords
          of the refinement statements and values are the new values
          of refined parameters.
        - a list of 'augment' statements that are to be applied
          directly under `elem`.
        - a new patch set containing patches applicable to
          substatements of `stmt`.
        """
        if altname:
            name = altname
        else:
            name = stmt.arg
        new_pset = {}
        augments = []
        refine_dict = dict.fromkeys(("presence", "default", "mandatory",
                                     "min-elements", "max-elements"))
        if not isinstance(pset, dict):
            raise ValueError('pset is of type %s' % type(pset).__name__)
        for p in pset.pop(self.add_prefix(name, stmt), []):
            if p.path:
                head = p.pop()
                if head in new_pset:
                    new_pset[head].append(p)
                else:
                    new_pset[head] = [p]
            else:
                for refaug in p.plist:
                    if refaug.keyword == "augment":
                        augments.append(refaug)
                    else:
                        for s in refaug.substmts:
                            if s.keyword == "description":
                                self.description_stmt(s, elem, None)
                            elif s.keyword == "reference":
                                self.reference_stmt(s, elem, None)
                            elif s.keyword == "must":
                                self.must_stmt(s, elem, None)
                            elif s.keyword == "config":
                                self.nma_attribute(s, elem)
                            elif refine_dict.get(s.keyword, False) is None:
                                refine_dict[s.keyword] = s.arg
        return (refine_dict, augments, new_pset)

    def get_minmax(self, stmt, refine_dict):
        """Return pair of (min,max)-elements values for `stmt`.

        `stmt` must be a 'list' or 'leaf-list'. Applicable refinements
        from `refine_dict` are also taken into account.
        """
        minel = refine_dict["min-elements"]
        maxel = refine_dict["max-elements"]
        if minel is None:
            minst = stmt.search_one("min-elements")
            if minst:
                minel = minst.arg
            else:
                minel = "0"
        if maxel is None:
            maxst = stmt.search_one("max-elements")
            if maxst:
                maxel = maxst.arg
        if maxel == "unbounded":
            maxel = None
        return (minel, maxel)

    def lookup_expand(self, stmt, names):
        """Find schema nodes under `stmt`, also in used groupings.

        `names` is a list with qualified names of the schema nodes to
        look up. All 'uses'/'grouping' pairs between `stmt` and found
        schema nodes are marked for expansion.
        """
        if not names:
            return []
        todo = [stmt]
        while todo:
            pst = todo.pop()
            for sub in pst.substmts:
                if sub.keyword in self.schema_nodes:
                    qname = self.qname(sub)
                    if qname in names:
                        names.remove(qname)
                        par = sub.parent
                        while hasattr(par,"d_ref"): # par must be grouping
                            par.d_ref.d_expand = True
                            par = par.d_ref.parent
                        if not names:
                            return [] # all found
                elif sub.keyword == "uses":
                    g = sub.i_grouping
                    g.d_ref = sub
                    todo.append(g)
        return names

    def type_with_ranges(self, tchain, p_elem, rangekw, gen_data):
        """Handle types with 'range' or 'length' restrictions.

        `tchain` is the chain of type definitions from which the
        ranges may need to be extracted. `rangekw` is the statement
        keyword determining the range type (either 'range' or
        'length'). `gen_data` is a function that generates the
        output schema node (a RELAX NG <data> pattern).
        """
        ranges = self.get_ranges(tchain, rangekw)
        if not ranges:
            return p_elem.subnode(gen_data())
        if len(ranges) > 1:
            p_elem = SchemaNode.choice(p_elem)
            p_elem.occur = 2
        for r in ranges:
            d_elem = gen_data()
            for p in self.range_params(r, rangekw):
                d_elem.subnode(p)
            p_elem.subnode(d_elem)

    def get_ranges(self, tchain, kw):
        """Return list of ranges defined in `tchain`.

        `kw` is the statement keyword determining the type of the
        range, i.e. 'range' or 'length'. `tchain` is the chain of type
        definitions from which the resulting range is obtained.

        The returned value is a list of tuples containing the segments
        of the resulting range.
        """
        (lo, hi) = ("min", "max")
        ran = None
        for t in tchain:
            rstmt = t.search_one(kw)
            if rstmt is None:
                continue
            parts = [ p.strip() for p in rstmt.arg.split("|") ]
            ran = [ [ i.strip() for i in p.split("..") ] for p in parts ]
            if ran[0][0] != 'min':
                lo = ran[0][0]
            if ran[-1][-1] != 'max':
                hi = ran[-1][-1]
        if ran is None:
            return None
        if len(ran) == 1:
            return [(lo, hi)]
        else:
            return [(lo, ran[0][-1])] + ran[1:-1] + [(ran[-1][0], hi)]

    def range_params(self, ran, kw):
        """Return list of <param>s corresponding to range `ran`.

        `kw` is the statement keyword determining the type of the
        range, i.e. 'range' or 'length'. `ran` is the internal
        representation of a range as constructed by the `get_ranges`
        method.
        """
        if kw == "length":
            if ran[0][0] != "m" and (len(ran) == 1 or ran[0] == ran[1]):
                elem = SchemaNode("param").set_attr("name","length")
                elem.text = ran[0]
                return [elem]
            min_ = SchemaNode("param").set_attr("name","minLength")
            max_ = SchemaNode("param").set_attr("name","maxLength")
        else:
            if len(ran) == 1:
                ran *= 2  # duplicating the value
            min_ = SchemaNode("param").set_attr("name","minInclusive")
            max_ = SchemaNode("param").set_attr("name","maxInclusive")
        res = []
        if ran[0][0] != "m":
            elem = min_
            elem.text = ran[0]
            res.append(elem)
        if ran[1][0] != "m":
            elem = max_
            elem.text = ran[1]
            res.append(elem)
        return res

    def handle_stmt(self, stmt, p_elem, pset=None):
        """
        Run handler method for statement `stmt`.

        `p_elem` is the parent node in the output schema. `pset` is
        the current "patch set" - a dictionary with keys being QNames
        of schema nodes at the current level of hierarchy for which
        (or descendants thereof) any pending patches exist. The values
        are instances of the Patch class.

        All handler methods are defined below and must have the same
        arguments as this method. They should create the output schema
        fragment corresponding to `stmt`, apply all patches from
        `pset` belonging to `stmt`, insert the fragment under `p_elem`
        and perform all side effects as necessary.
        """
        if self.debug > 0:
            sys.stderr.write("Handling '%s %s'\n" %
                             (util.keyword_to_str(stmt.raw_keyword), stmt.arg))
        try:
            method = self.stmt_handler[stmt.keyword]
        except KeyError:
            if isinstance(stmt.keyword, tuple):
                try:
                    method = self.ext_handler[stmt.keyword[0]][stmt.keyword[1]]
                except KeyError:
                    method = self.rng_annotation
                method(stmt, p_elem)
                return
            else:
                raise error.EmitError(
                    "Unknown keyword %s - this should not happen.\n"
                    % stmt.keyword)
        if pset is None:
            pset = {}
        method(stmt, p_elem, pset)

    def handle_substmts(self, stmt, p_elem, pset=None):
        """Handle all substatements of `stmt`."""
        if pset is None:
            pset = {}
        for sub in stmt.substmts:
            self.handle_stmt(sub, p_elem, pset)

    # Handlers for YANG statements

    def noop(self, stmt, p_elem, pset=None):
        """`stmt` is not handled in the regular way."""
        pass

    def anyxml_stmt(self, stmt, p_elem, pset):
        elem = SchemaNode.element(self.qname(stmt), p_elem)
        if self.has_meta:
            elem.annot(
                SchemaNode("ref").set_attr("name", "__yang_metadata__"))
        SchemaNode("parentRef", elem).set_attr("name", "__anyxml__")
        refd, _, _ = self.process_patches(pset, stmt, elem)
        if p_elem.name == "choice":
            elem.occur = 3
        elif refd["mandatory"] or stmt.search_one("mandatory", "true"):
            elem.occur = 2
            self.propagate_occur(p_elem, 2)
        self.handle_substmts(stmt, elem)

    def nma_attribute(self, stmt, p_elem, pset=None):
        """Map `stmt` to a NETMOD-specific attribute.

        The name of the attribute is the same as the 'keyword' of
        `stmt`.
        """
        att = "nma:" + stmt.keyword
        if att not in p_elem.attr:
            p_elem.attr[att] = stmt.arg

    def case_stmt(self, stmt, p_elem, pset):
        celem = SchemaNode.case(p_elem)
        if p_elem.default_case != stmt.arg:
            celem.occur = 3
        refd, augs, new_pset = self.process_patches(pset, stmt, celem)
        left = self.lookup_expand(stmt, list(new_pset))
        for a in augs:
            left = self.lookup_expand(a, left)
        self.handle_substmts(stmt, celem, new_pset)
        self.apply_augments(augs, celem, new_pset)

    def choice_stmt(self, stmt, p_elem, pset):
        chelem = SchemaNode.choice(p_elem)
        chelem.attr["nma:name"] = stmt.arg
        refd, augs, new_pset = self.process_patches(pset, stmt, chelem)
        left = self.lookup_expand(stmt, list(new_pset))
        for a in augs:
            left = self.lookup_expand(a, left)
        if refd["mandatory"] or stmt.search_one("mandatory", "true"):
            chelem.attr["nma:mandatory"] = "true"
            self.propagate_occur(chelem, 2)
        else:
            defv = self.get_default(stmt, refd)
            if defv is not None:
                chelem.default_case = defv
            else:
                chelem.occur = 3
        self.handle_substmts(stmt, chelem, new_pset)
        self.apply_augments(augs, chelem, new_pset)

    def container_stmt(self, stmt, p_elem, pset):
        celem = SchemaNode.element(self.qname(stmt), p_elem)
        if self.has_meta:
            celem.annot(
                SchemaNode("ref").set_attr("name", "__yang_metadata__"))
        refd, augs, new_pset = self.process_patches(pset, stmt, celem)
        left = self.lookup_expand(stmt, list(new_pset))
        for a in augs:
            left = self.lookup_expand(a, left)
        if (p_elem.name == "choice" and p_elem.default_case != stmt.arg
            or p_elem.name == "case" and
            p_elem.parent.default_case != stmt.parent.arg and
            len(stmt.parent.i_children) < 2 or
            refd["presence"] or stmt.search_one("presence")):
            celem.occur = 3
        self.handle_substmts(stmt, celem, new_pset)
        self.apply_augments(augs, celem, new_pset)

    def description_stmt(self, stmt, p_elem, pset):
        # ignore imported and top-level descriptions + desc. of enum
        if (self.a_uri in self.namespaces and
            stmt.i_module == self.module != stmt.parent and
            stmt.parent.keyword != "enum"):
            self.insert_doc(p_elem, stmt.arg)

    def enum_stmt(self, stmt, p_elem, pset):
        elem = SchemaNode("value", p_elem, stmt.arg)
        for sub in stmt.search("status"):
            self.handle_stmt(sub, elem)

    def include_stmt(self, stmt, p_elem, pset):
        if stmt.parent.keyword == "module":
            subm = self.module.i_ctx.get_module(stmt.arg)
            self.handle_substmts(subm, p_elem, pset)

    def leaf_stmt(self, stmt, p_elem, pset):
        qname = self.qname(stmt)
        elem = SchemaNode.element(qname)
        if self.has_meta:
            elem.annot(
                SchemaNode("ref").set_attr("name", "__yang_metadata__"))
        if p_elem.name == "_list_" and qname in p_elem.keys:
            p_elem.keymap[qname] = elem
            elem.occur = 2
        else:
            p_elem.subnode(elem)
        refd, _, _ = self.process_patches(pset, stmt, elem)
        if (p_elem.name == "choice" and p_elem.default_case != stmt.arg or
            p_elem.name == "case" and
            p_elem.parent.default_case != stmt.parent.arg and
            len(stmt.parent.i_children) < 2):

            elem.occur = 3
        elif refd["mandatory"] or stmt.search_one("mandatory", "true"):
            self.propagate_occur(elem, 2)
        if elem.occur == 0:
            defv = self.get_default(stmt, refd)
            if defv is not None:
                elem.default = defv
                self.propagate_occur(elem, 1)
        self.handle_substmts(stmt, elem)

    def leaf_list_stmt(self, stmt, p_elem, pset):
        lelem = SchemaNode.leaf_list(self.qname(stmt), p_elem)
        lelem.attr["nma:leaf-list"] = "true"
        if self.has_meta:
            lelem.annot(
                SchemaNode("ref").set_attr("name", "__yang_metadata__"))
        refd, _, _ = self.process_patches(pset, stmt, lelem)
        lelem.minEl, lelem.maxEl = self.get_minmax(stmt, refd)
        if int(lelem.minEl) > 0:
            self.propagate_occur(p_elem, 2)
        self.handle_substmts(stmt, lelem)

    def list_stmt(self, stmt, p_elem, pset):
        lelem = SchemaNode.list(self.qname(stmt), p_elem)
        if self.has_meta:
            lelem.annot(
                SchemaNode("ref").set_attr("name", "__yang_metadata__"))
        keyst = stmt.search_one("key")
        if keyst:
            lelem.keys = [self.add_prefix(k, stmt) for k in keyst.arg.split()]
        refd, augs, new_pset = self.process_patches(pset, stmt, lelem)
        left = self.lookup_expand(stmt, list(new_pset) + lelem.keys)
        for a in augs:
            left = self.lookup_expand(a, left)
        lelem.minEl, lelem.maxEl = self.get_minmax(stmt, refd)
        if int(lelem.minEl) > 0:
            self.propagate_occur(p_elem, 2)
        self.handle_substmts(stmt, lelem, new_pset)
        self.apply_augments(augs, lelem, new_pset)

    def must_stmt(self, stmt, p_elem, pset):
        mel = SchemaNode("nma:must")
        p_elem.annot(mel)
        mel.attr["assert"] = self.yang_to_xpath(stmt.arg)
        em = stmt.search_one("error-message")
        if em:
            SchemaNode("nma:error-message", mel, em.arg)
        eat = stmt.search_one("error-app-tag")
        if eat:
            SchemaNode("nma:error-app-tag", mel, eat.arg)

    def notification_stmt(self, stmt, p_elem, pset):
        notel = SchemaNode("nma:notification", self.notifications)
        notel.occur = 2
        elem = SchemaNode.element(self.qname(stmt), notel,
                                  interleave=True, occur=2)
        _, augs, new_pset = self.process_patches(pset, stmt, elem)
        self.handle_substmts(stmt, elem, new_pset)
        self.apply_augments(augs, elem, new_pset)

    def reference_stmt(self, stmt, p_elem, pset):
        # ignore imported and top-level descriptions + desc. of enum
        if (self.a_uri in self.namespaces and
            stmt.i_module == self.module != stmt.parent and
            stmt.parent.keyword != "enum"):
            self.insert_doc(p_elem, "See: " + stmt.arg)

    def rpc_stmt(self, stmt, p_elem, pset):
        rpcel = SchemaNode("nma:rpc", self.rpcs)
        _, _, r_pset = self.process_patches(pset, stmt, rpcel)
        inpel = SchemaNode("nma:input", rpcel)
        elem = SchemaNode.element(self.qname(stmt), inpel, occur=2)
        _, augs, pset = self.process_patches(r_pset, stmt, elem, "input")
        inst = stmt.search_one("input")
        if inst:
            self.handle_substmts(inst, elem, pset)
        else:
            SchemaNode("empty", elem)
        self.apply_augments(augs, elem, pset)
        _,  augs, pset = self.process_patches(r_pset, stmt, None, "output")
        oust = stmt.search_one("output")
        if oust or augs:
            outel = SchemaNode("nma:output", rpcel)
            outel.occur = 2
            if oust:
                self.handle_substmts(oust, outel, pset)
            self.apply_augments(augs, outel, pset)
        self.handle_substmts(stmt, rpcel, r_pset)

    def type_stmt(self, stmt, p_elem, pset):
        """Handle ``type`` statement.

        Built-in types are handled by one of the specific type
        callback methods defined below.
        """
        typedef = stmt.i_typedef
        if typedef and not stmt.i_is_derived: # just ref
            uname, dic = self.unique_def_name(typedef)
            if uname not in dic:
                self.install_def(uname, typedef, dic)
            SchemaNode("ref", p_elem).set_attr("name", uname)
            defst = typedef.search_one("default")
            if defst:
                dic[uname].default = defst.arg
                occur = 1
            else:
                occur = dic[uname].occur
            if occur > 0:
                self.propagate_occur(p_elem, occur)
            return
        chain = [stmt]
        tdefault = None
        while typedef:
            type_ = typedef.search_one("type")
            chain.insert(0, type_)
            if tdefault is None:
                tdef = typedef.search_one("default")
                if tdef:
                    tdefault = tdef.arg
            typedef = type_.i_typedef
        if tdefault and p_elem.occur == 0:
            p_elem.default = tdefault
            self.propagate_occur(p_elem, 1)
        self.type_handler[chain[0].arg](chain, p_elem)

    def unique_stmt(self, stmt, p_elem, pset):
        def addpref(nid):
            xpath_nodes = []
            child = stmt.parent
            for node in nid.split("/"):
                prefixed_name = self.add_prefix(node, stmt)
                node_name = prefixed_name
                if ":" in prefixed_name:
                    node_name = prefixed_name.split(":")[1]
                if child is not None:
                    child = statements.search_child(child.substmts,
                                                    child.i_module.i_modulename,
                                                    node_name)
                if child is None or child.keyword not in ["choice", "case"]:
                    xpath_nodes.append(prefixed_name)
            return "/".join(xpath_nodes)
        uel = SchemaNode("nma:unique")
        p_elem.annot(uel)
        uel.attr["tag"] = " ".join(
            [addpref(nid) for nid in stmt.arg.split()])

    def uses_stmt(self, stmt, p_elem, pset):
        expand = False
        grp = stmt.i_grouping
        for sub in stmt.substmts:
            if sub.keyword in ("refine", "augment"):
                expand = True
                self.add_patch(pset, sub)
        if expand:
            self.lookup_expand(grp, list(pset))
        elif len(self.prefix_stack) <= 1 and not hasattr(stmt,"d_expand"):
            uname, dic = self.unique_def_name(
                stmt.i_grouping, not p_elem.interleave)
            if uname not in dic:
                self.install_def(uname, stmt.i_grouping, dic,
                                 p_elem.interleave)
            elem = SchemaNode("ref", p_elem).set_attr("name", uname)
            occur = dic[uname].occur
            if occur > 0:
                self.propagate_occur(p_elem, occur)
            self.handle_substmts(stmt, elem)
            return
        self.handle_substmts(grp, p_elem, pset)

    def when_stmt(self, stmt, p_elem, pset=None):
        p_elem.attr["nma:when"] = self.yang_to_xpath(stmt.arg)

    def yang_version_stmt(self, stmt, p_elem, pset):
        if float(stmt.arg) > self.YANG_version:
            raise error.EmitError("Unsupported YANG version: %s" % stmt.arg)

    # Handlers for YANG types

    def binary_type(self, tchain, p_elem):
        def gen_data():
            return SchemaNode("data").set_attr("type", "base64Binary")
        self.type_with_ranges(tchain, p_elem, "length", gen_data)

    def bits_type(self, tchain, p_elem):
        elem = SchemaNode("list", p_elem)
        zom = SchemaNode("zeroOrMore", elem)
        choi = SchemaNode.choice(zom, occur=2)
        for bit in tchain[0].search("bit"):
            SchemaNode("value", choi, bit.arg)

    def boolean_type(self, tchain, p_elem):
        elem = SchemaNode.choice(p_elem, occur=2)
        SchemaNode("value", elem, "true")
        SchemaNode("value", elem, "false")

    def choice_type(self, tchain, p_elem):
        """Handle ``enumeration`` and ``union`` types."""
        elem = SchemaNode.choice(p_elem, occur=2)
        self.handle_substmts(tchain[0], elem)

    def empty_type(self, tchain, p_elem):
        SchemaNode("empty", p_elem)

    def identityref_type(self, tchain, p_elem):
        bid = tchain[0].search_one("base").i_identity
        if bid not in self.identity_deps:
            sys.stderr.write("%s: warning: identityref has empty value space\n"
                             % tchain[0].pos)
            p_elem.subnode(SchemaNode("notAllowed"))
            p_elem.occur = 0
            return
        der = self.identity_deps[bid]
        if len(der) > 1:
            p_elem = SchemaNode.choice(p_elem, occur=2)
        for i in der:
            p_elem.subnode(self.add_derived_identity(i))

    def instance_identifier_type(self, tchain, p_elem):
        SchemaNode("parentRef", p_elem).attr["name"] = "__instance-identifier__"
        ii = SchemaNode("nma:instance-identifier")
        p_elem.annot(ii)
        rinst = tchain[0].search_one("require-instance")
        if rinst:
            ii.attr["require-instance"] = rinst.arg

    def leafref_type(self, tchain, p_elem):
        typ = tchain[0]
        occur = p_elem.occur
        pathstr = typ.parent.i_leafref.i_expanded_path
        p_elem.attr["nma:leafref"] = self.yang_to_xpath(pathstr)
        while isinstance(typ.i_type_spec, types.PathTypeSpec):
            typ = typ.i_type_spec.i_target_node.search_one("type")
        self.handle_stmt(typ, p_elem)
        if occur == 0:
            p_elem.occur = 0

    def mapped_type(self, tchain, p_elem):
        """Handle types that are simply mapped to RELAX NG."""
        SchemaNode("data", p_elem).set_attr("type",
                                            self.datatype_map[tchain[0].arg])

    def numeric_type(self, tchain, p_elem):
        """Handle numeric types."""
        typ = tchain[0].arg
        def gen_data():
            elem = SchemaNode("data").set_attr("type", self.datatype_map[typ])
            if typ == "decimal64":
                fd = tchain[0].search_one("fraction-digits").arg
                SchemaNode("param",elem,"19").set_attr("name","totalDigits")
                SchemaNode("param",elem,fd).set_attr("name","fractionDigits")
            return elem
        self.type_with_ranges(tchain, p_elem, "range", gen_data)

    def string_type(self, tchain, p_elem):
        pels = []
        for t in tchain:
            for pst in t.search("pattern"):
                pels.append(SchemaNode("param",
                                       text=pst.arg).set_attr("name","pattern"))
        def get_data():
            elem = SchemaNode("data").set_attr("type", "string")
            for p in pels:
                elem.subnode(p)
            return elem
        self.type_with_ranges(tchain, p_elem, "length", get_data)
