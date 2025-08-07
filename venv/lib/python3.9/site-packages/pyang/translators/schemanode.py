# Copyright (c) 2013 by Ladislav Lhotka, CZ.NIC <lhotka@nic.cz>
#
# Python class representing a node in a RELAX NG schema.
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

from xml.sax.saxutils import escape

class SchemaNode(object):

    """This class represents a node in a RELAX NG schema.

    The details are tailored to the specific features of the hybrid
    DSDL schema generated from YANG modules, but the class may be
    reasonably used for representing any other RELAX NG schema.

    Specific types of nodes are created using class methods below.

    Instance variables:

    * `self.attr` - dictionary of XML attributes. Keys are attribute
      names and values attribute values.

    * `self.children` - list of child nodes.

    * `self.default` - default value (only for "element" nodes)

    * `self.interleave` - boolean flag determining the interleave
      status. If True, the children of `self` will end up inside
      <interleave>.

    * `self.keys` - list of QNames of YANG list keys (only for "_list_"
      nodes having children).

    * `self.keymap` - dictionary of key nodes (only for "_list_" nodes
      having children). The keys of the dictionary are the QNames of
      YANG list keys.

    * `self.minEl` - minimum number of items (only for "_list_" nodes).

    * `self.maxEl` - maximum number of items (only for "_list_" nodes).

    * `self.name` - name of the schema node (XML element name).

    * `self.occur` - specifies the occurrence status using integer
      values: 0=optional, 1=implicit, 2=mandatory, 3=presence.

    * `self.parent` - parent node.

    * `self.text` - text content.
    """

    @classmethod
    def element(cls, name, parent=None, interleave=None, occur=0):
        """Create an element node."""
        node = cls("element", parent, interleave=interleave)
        node.attr["name"] = name
        node.occur = occur
        return node

    @classmethod
    def leaf_list(cls, name, parent=None, interleave=None):
        """Create _list_ node for a leaf-list."""
        node = cls("_list_", parent, interleave=interleave)
        node.attr["name"] = name
        node.keys = None
        node.minEl = "0"
        node.maxEl = None
        node.occur = 3
        return node

    @classmethod
    def list(cls, name, parent=None, interleave=None):
        """Create _list_ node for a list."""
        node = cls.leaf_list(name, parent, interleave=interleave)
        node.keys = []
        node.keymap = {}
        return node

    @classmethod
    def choice(cls, parent=None, occur=0):
        """Create choice node."""
        node = cls("choice", parent)
        node.occur = occur
        node.default_case = None
        return node

    @classmethod
    def case(cls, parent=None):
        """Create case node."""
        node = cls("case", parent)
        node.occur = 0
        return node

    @classmethod
    def define(cls, name, parent=None, interleave=False):
        """Create define node."""
        node = cls("define", parent, interleave=interleave)
        node.occur = 0
        node.attr["name"] = name
        return node

    def __init__(self, name, parent=None, text="", interleave=None):
        """Initialize the object under `parent`.
        """
        self.name = name
        self.parent = parent
        if parent is not None:
            parent.children.append(self)
        self.text = text
        self.adjust_interleave(interleave)
        self.children = []
        self.annots = []
        self.attr = {}

    def rng_children(self):
        """Return receiver's children that are not extensions."""
        return [c for c in self.children if ":" not in c.name]

    def serialize_children(self):
        """Return serialization of receiver's children.
        """
        return ''.join([ch.serialize() for ch in self.children])

    def serialize_annots(self):
        """Return serialization of receiver's annotation elements.
        """
        return ''.join([ch.serialize() for ch in self.annots])

    def adjust_interleave(self, interleave):
        """Inherit interleave status from parent if undefined."""
        if interleave is None and self.parent:
            self.interleave = self.parent.interleave
        else:
            self.interleave = interleave

    def subnode(self, node):
        """Make `node` receiver's child."""
        self.children.append(node)
        node.parent = self
        node.adjust_interleave(node.interleave)

    def annot(self, node):
        """Add `node` as an annotation of the receiver."""
        self.annots.append(node)
        node.parent = self

    def set_attr(self, key, value):
        """Set attribute `key` to `value` and return the receiver."""
        self.attr[key] = value
        return self

    def start_tag(self, alt=None, empty=False):
        """Return XML start tag for the receiver."""
        if alt:
            name = alt
        else:
            name = self.name
        result = "<" + name
        for it in self.attr:
            result += ' %s="%s"' % (it, escape(self.attr[it], {'"':"&quot;", '%': "%%"}))
        if empty:
            return result + "/>%s"
        else:
            return result + ">"

    def end_tag(self, alt=None):
        """Return XML end tag for the receiver."""
        if alt:
            name = alt
        else:
            name = self.name
        return "</" + name + ">"

    def serialize(self, occur=None):
        """Return RELAX NG representation of the receiver and subtree.
        """
        fmt = self.ser_format.get(self.name, SchemaNode._default_format)
        return fmt(self, occur) % (escape(self.text) +
                                   self.serialize_children())

    def _default_format(self, occur):
        """Return the default serialization format."""
        if self.text or self.children:
            return self.start_tag() + "%s" + self.end_tag()
        return self.start_tag(empty=True)

    def _wrapper_format(self, occur):
        """Return the serializatiopn format for <start>."""
        return self.start_tag() + self._chorder() + self.end_tag()

    def _define_format(self, occur):
        """Return the serialization format for a define node."""
        if hasattr(self, "default"):
            self.attr["nma:default"] = self.default
        middle = self._chorder() if self.rng_children() else "<empty/>%s"
        return (self.start_tag() + self.serialize_annots().replace("%", "%%")
                + middle + self.end_tag())

    def _element_format(self, occur):
        """Return the serialization format for an element node."""
        if occur:
            occ = occur
        else:
            occ = self.occur
        if occ == 1:
            if hasattr(self, "default"):
                self.attr["nma:default"] = self.default
            else:
                self.attr["nma:implicit"] = "true"
        middle = self._chorder() if self.rng_children() else "<empty/>%s"
        fmt = (self.start_tag() + self.serialize_annots().replace("%", "%%") +
               middle + self.end_tag())
        if (occ == 2 or self.parent.name == "choice"
            or self.parent.name == "case" and len(self.parent.children) == 1):
            return fmt
        else:
            return "<optional>" + fmt + "</optional>"

    def _chorder(self):
        """Add <interleave> if child order is arbitrary."""
        if (self.interleave and
            len([ c for c in self.children if ":" not in c.name ]) > 1):
            return "<interleave>%s</interleave>"
        return "%s"

    def _list_format(self, occur):
        """Return the serialization format for a _list_ node."""
        if self.keys:
            self.attr["nma:key"] = " ".join(self.keys)
            keys = ''.join([self.keymap[k].serialize(occur=2)
                            for k in self.keys])
        else:
            keys = ""
        if self.maxEl:
            self.attr["nma:max-elements"] = self.maxEl
        if int(self.minEl) == 0:
            ord_ = "zeroOrMore"
        else:
            ord_ = "oneOrMore"
            if int(self.minEl) > 1:
                self.attr["nma:min-elements"] = self.minEl
        middle = self._chorder() if self.rng_children() else "<empty/>%s"
        return ("<" + ord_ + ">" + self.start_tag("element") +
                (self.serialize_annots() + keys).replace("%", "%%")  +
                middle + self.end_tag("element") + "</" + ord_ + ">")

    def _choice_format(self, occur):
        """Return the serialization format for a choice node."""
        middle = "%s" if self.rng_children() else "<empty/>%s"
        fmt = self.start_tag() + middle + self.end_tag()
        if self.occur != 2:
            return "<optional>" + fmt + "</optional>"
        else:
            return fmt

    def _case_format(self, occur):
        """Return the serialization format for a case node."""
        if self.occur == 1:
            self.attr["nma:implicit"] = "true"
        ccnt = len(self.rng_children())
        if ccnt == 0:
            return "<empty/>%s"
        if ccnt == 1 or not self.interleave:
            return self.start_tag("group") + "%s" + self.end_tag("group")
        return (self.start_tag("interleave") + "%s" +
                self.end_tag("interleave"))

    ser_format = { "nma:data": _wrapper_format,
                   "nma:input": _wrapper_format,
                   "nma:notification": _wrapper_format,
                   "nma:output": _wrapper_format,
                   "element": _element_format,
                   "_list_": _list_format,
                   "choice": _choice_format,
                   "case": _case_format,
                   "define": _define_format,
                   }
    """Class variable - dictionary of methods returning string
    serialization formats. Keys are node names."""
