# Copyright (c) 2014 by Ladislav Lhotka, CZ.NIC <lhotka@nic.cz>
#
# Pyang plugin generating a XSLT1 stylesheet for XML->JSON translation.
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

"""JSONXSL output plugin

This plugin takes a YANG data model and produces an XSLT1 stylesheet
that is able to translate any valid XML instance document or NETCONF
message into JSON.
"""

import os
import sys
import xml.etree.ElementTree as ET

from pyang import plugin, error
from pyang.util import unique_prefixes

ss = ET.Element("stylesheet",
                {"version": "1.0",
                 "xmlns": "http://www.w3.org/1999/XSL/Transform",
                 "xmlns:nc": "urn:ietf:params:xml:ns:netconf:base:1.0",
                 "xmlns:en": "urn:ietf:params:xml:ns:netconf:notification:1.0"})
"""Root element of the output XSLT stylesheet."""

type_class = dict((t,"unquoted") for t in
                  ("boolean", "int8", "int16", "int32",
                   "uint8", "uint16", "uint32"))
"""Classification of types suited for JSON translation."""

type_class.update((t,t) for t in
                  ("empty", "instance-identifier", "identityref", "string"))

union_class = dict((t,"integer") for t in
                   ("int8", "int16", "int32",
                   "uint8", "uint16", "uint32"))
"""Classification of types needed for resolving union-typed values."""

union_class.update({"boolean": "boolean"})

def pyang_plugin_init():
    plugin.register_plugin(JsonXslPlugin())

class JsonXslPlugin(plugin.PyangPlugin):
    def add_output_format(self, fmts):
        self.multiple_modules = True
        fmts['jsonxsl'] = self

    def setup_fmt(self, ctx):
        ctx.implicit_errors = False

    def emit(self, ctx, modules, fd):
        """Main control function.

        Set up the top-level parts of the stylesheet, then process
        recursively all nodes in all data trees, and finally emit the
        serialized stylesheet.
        """
        for epos, etag, eargs in ctx.errors:
            if error.is_error(error.err_level(etag)):
                raise error.EmitError("JSONXSL plugin needs a valid module")
        self.real_prefix = unique_prefixes(ctx)
        self.top_names = []
        for m in modules:
            self.top_names.extend([c.arg for c in m.i_children if
                                   c.keyword not in ("rpc", "notification")])
        tree = ET.ElementTree(ss)
        ET.SubElement(ss, "output", method="text")
        xsltdir = os.environ.get("PYANG_XSLT_DIR",
                                 "/usr/local/share/yang/xslt")
        ET.SubElement(ss, "include", href=xsltdir + "/jsonxsl-templates.xsl")
        ET.SubElement(ss, "strip-space", elements="*")
        nsmap = ET.SubElement(ss, "template", name="nsuri-to-module")
        ET.SubElement(nsmap, "param", name="uri")
        choo = ET.SubElement(nsmap, "choose")
        for module in self.real_prefix:
            ns_uri = module.search_one("namespace").arg
            ss.attrib["xmlns:" + self.real_prefix[module]] = ns_uri
            when = ET.SubElement(choo, "when", test="$uri='" + ns_uri + "'")
            self.xsl_text(module.i_modulename, when)
            self.process_module(module)
        tree.write(fd, encoding="unicode", xml_declaration=True)

    def process_module(self, yam):
        """Process data nodes, RPCs and notifications in a single module."""
        for ann in yam.search(("ietf-yang-metadata", "annotation")):
            self.process_annotation(ann)
        for ch in yam.i_children[:]:
            if ch.keyword == "rpc":
                self.process_rpc(ch)
            elif ch.keyword == "notification":
                self.process_notification(ch)
            else:
                continue
            yam.i_children.remove(ch)
        self.process_children(yam, "//nc:*", 1)

    def process_annotation(self, ann):
        """Process metadata annotation."""
        tmpl = self.xsl_template("@" + self.qname(ann))
        ET.SubElement(tmpl, "param", name="level", select="0")
        ct = self.xsl_calltemplate("leaf", tmpl)
        ET.SubElement(ct, "with-param", name="level", select="$level")
        self.xsl_withparam("nsid", ann.i_module.i_modulename + ":", ct)
        self.type_param(ann, ct)

    def process_rpc(self, rpc):
        """Process input and output parts of `rpc`."""
        p = "/nc:rpc/" + self.qname(rpc)
        tmpl = self.xsl_template(p)
        inp = rpc.search_one("input")
        if inp is not None:
            ct = self.xsl_calltemplate("rpc-input", tmpl)
            self.xsl_withparam("nsid", rpc.i_module.i_modulename + ":", ct)
            self.process_children(inp, p, 2)
        outp = rpc.search_one("output")
        if outp is not None:
            self.process_children(outp, "/nc:rpc-reply", 1)

    def process_notification(self, ntf):
        """Process event notification `ntf`."""
        p = "/en:notification/" + self.qname(ntf)
        tmpl = self.xsl_template(p)
        ct = self.xsl_calltemplate("container", tmpl)
        self.xsl_withparam("level", "1", ct)
        if ntf.arg == "eventTime":            # local name collision
            self.xsl_withparam("nsid", ntf.i_module.i_modulename + ":", ct)
        self.process_children(ntf, p, 2)

    def process_children(self, node, path, level, parent=None):
        """Process all children of `node`.

        `path` is the Xpath of `node` which is used in the 'select'
        attribute of XSLT templates.
        """
        data_parent = parent if parent else node
        chs = node.i_children
        for ch in chs:
            if ch.keyword in ["choice", "case"]:
                self.process_children(ch, path, level, node)
                continue
            p = path + "/" + self.qname(ch)
            tmpl = self.xsl_template(p)
            ct = self.xsl_calltemplate(ch.keyword, tmpl)
            self.xsl_withparam("level", "%d" % level, ct)
            if (data_parent.i_module is None or
                ch.i_module.i_modulename != data_parent.i_module.i_modulename):
                self.xsl_withparam("nsid", ch.i_module.i_modulename + ":", ct)
            if ch.keyword in ["leaf", "leaf-list"]:
                self.type_param(ch, ct)
            elif ch.keyword != "anyxml" and ch.keyword != "anydata":
                offset = 2 if ch.keyword == "list" else 1
                self.process_children(ch, p, level + offset)

    def type_param(self, node, ct):
        """Resolve the type of a leaf or leaf-list node for JSON.
        """
        types = self.get_types(node)
        ftyp = types[0]
        if len(types) == 1:
            if ftyp in type_class:
                jtyp = type_class[ftyp]
            else:
                jtyp = "other"
            self.xsl_withparam("type", jtyp, ct)
        elif ftyp in ["string", "enumeration", "bits", "binary",
                      "identityref", "instance-identifier"]:
            self.xsl_withparam("type", "string", ct)
        else:
            opts = []
            for t in types:
                if t in union_class:
                    ut = union_class[t]
                elif t in ["int64", "uint64"] or t.startswith("decimal@"):
                    ut = t
                else:
                    ut = "other"
                if ut not in opts:
                    opts.append(ut)
                    if ut == "other":
                        break
                    if ut == "decimal" and "integer" not in opts:
                        opts.append("integer")
            self.xsl_withparam("type", "union", ct)
            self.xsl_withparam("options", ",".join(opts) + ",", ct)

    def get_types(self, node):
        res = []
        def resolve(typ):
            if typ.arg == "union":
                for ut in typ.i_type_spec.types:
                    resolve(ut)
            elif typ.arg == "decimal64":
                res.append("decimal@" +
                           typ.search_one("fraction-digits").arg)
            elif typ.i_typedef is not None:
                resolve(typ.i_typedef.search_one("type"))
            else:
                res.append(typ.arg)
        typ = node.search_one("type")
        if typ.arg == "leafref":
            resolve(node.i_leafref_ptr[0].search_one("type"))
        else:
            resolve(typ)
        return res

    def qname(self, node):
        """Return the qualified name of `node`.

        In JSON, namespace identifiers are YANG module names.
        """
        return self.real_prefix[node.main_module()] + ":" + node.arg

    def xsl_template(self, name):
        """Construct an XSLT 'template' element matching `name`."""
        return ET.SubElement(ss, "template" , match = name)

    def xsl_text(self, text, parent):
        """Construct an XSLT 'text' element containing `text`.

        `parent` is this element's parent.
        """
        res = ET.SubElement(parent, "text")
        res.text = text
        return res

    def xsl_calltemplate(self, name, parent):
        """Construct an XSLT 'call-template' element.

        `parent` is this element's parent.
        `name` is the name of the template to be called.
        """
        return ET.SubElement(parent, "call-template", name=name)

    def xsl_withparam(self, name, value, parent):
        """Construct an XSLT 'with-param' element.

        `parent` is this element's parent.
        `name` is the parameter name.
        `value` is the parameter value.
        """
        res = ET.SubElement(parent, "with-param", name=name)
        res.text = value
        return res
