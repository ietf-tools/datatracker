#! /usr/bin/env python
import argparse
import codecs
import json
import numbers
import re
import sys
import xml.etree.ElementTree as ET




class Error(Exception):
    """Abstract base class for exceptions in this program."""

    return_value = 3

    def __init__(self, path):
        self.path = path

    def __str__(self):
        return "error at " + self.path

class DataTypeError(Error):
    """Exception raised for values with wrong type."""

    def __init__(self, path, datatype, value):
        Error.__init__(self, path)
        self.datatype = datatype
        self.value = value

    def __str__(self):
        return Error.__str__(self) + (
           ' - %r is not a valid value of "%s" type'
           % (self.value, self.datatype))

class NodeTypeError(Error):
    """Exception raised if the JSON object type doesn't fit the data model."""

    def __init__(self, path, node_type):
        Error.__init__(self, path)
        self.node_type = node_type

    def __str__(self):
        return Error.__str__(self) + " -  must be a " + self.node_type

class InvalidNodeError(Error):
    """Exception raised for nodes that are not found in the data model."""

    def __str__(self):
        return Error.__str__(self) + " - invalid node"

class MissingKeyError(Error):
    """Exception raised if a list entry doesn't have all keys."""

    def __init__(self, path, key):
        Error.__init__(self, path)
        self.key = key

    def __str__(self):
        return Error.__str__(self) + " - missing key '{}:{}'".format(*self.key)

class InvalidAnnotationObjectError(Error):
    """Exception raise for an invalid annotation object."""

    def __str__(self):
        return Error.__str__(self) + " - invalid annotation object"

class InvalidAnnotationError(Error):
    """
    Exception raised for annotations that are not found in the data model.
    """

    def __init__(self, path, annot):
        Error.__init__(self, path)
        self.annot = annot

    def __str__(self):
        return Error.__str__(self) + " - invalid annotation " + self.annot

class JSONError(Error):
    """Exception raised for broken JSON input."""

    def __str__(self):
        return "%s" % self.path


class Translator (object):
    """Translate JSON to XML according to a YANG data model.

    Instance variables:

    - `self.prefix`: dictionary mapping module names to prefix

    - `self.uri`: dictionary mapping module names to namespace URI

    - `self.qn_re`, self.num_re`, `self.bra_re`: compiled regular
      expressions.
    """

    def __init__(self, jtox):
        self.tree = jtox["tree"]
        self.annots = jtox["annotations"]
        self.prefix = {}
        self.uri = {}
        self.node_modules = set()
        for m in jtox["modules"]:
            # The namespace urn:ietf:params:xml:ns:netconf:base:1.0 is added by the default.
            # Don't add it twice as this will cause the generated XML to be invalid
            prefix, uri = jtox["modules"][m]
            if uri != "urn:ietf:params:xml:ns:netconf:base:1.0":
                self.prefix[m] = prefix
                self.uri[m] = uri
                ET.register_namespace(self.prefix[m], self.uri[m])
        ident = "[a-zA-Z_][-_.a-zA-Z0-9]*"
        self.qn_re = re.compile(r"^\s*(%s(?::%s)?)\s*(.*)$" % ((ident,)*2))
        self.num_re = re.compile(r"^\s*([0-9]+)\s*\]\s*(.*)$")
        self.bra_re = re.compile(r"""^=\s*([^"'\]\s]+|"[^"]*"|'[^']*')\s*\]\s*(.*)$""")

    def et_qname(self, mod_name, node_name):
        """Return the qualified node name as undestood by ElementTree."""
        return "{%s}%s" % (self.uri[mod_name], node_name)

    def translate(self, json_doc, xml_root):
        """Translate `json_doc` and attach the result under `xml_root`."""
        try:
            try:
                json_doc.fileno                               # Is it a file?
            except AttributeError:
                d = json.loads(json_doc)
            else:
                d = json.load(json_doc)
        except ValueError as e:
            raise JSONError(e)
        return self.translate_obj(d, None, self.tree, xml_root, "/")

    def translate_obj(self, json_obj, ns, node, xml_parent, path):
        """Translate object and attach it to the output XML tree.

        Arguments:

        - `json_obj`: JSON object to translate,

        - `ns`: current namespace (module name)

        - `node`: corresponding schema node in the jtox driver structure,

        - `xml_parent`: parent XML element for the resulting tree

        - `path`: JSON pointer of `json_obj` (for error messages)

        """
        def check_val(cond, path, ytyp):
            if not cond:
                raise NodeTypeError(path, ytyp)

        def is_array(val):
            return isinstance(val, list) and val != [None]

        def is_scalar(val):
            return not (is_array(val) or isinstance(val, dict))

        for key in json_obj:
            if key[0] == "@":
                if key == "@":
                    self.handle_annotations(json_obj["@"], xml_parent, ns, path)
                continue
            job = json_obj[key]
            new_path = path + key
            tag, mod_name, node_spec = self.node_lookup(key, ns, node, new_path)
            qn = self.et_qname(mod_name, tag)
            if node_spec[0] == "container":
                check_val(isinstance(job, dict), new_path, "container")
                el = ET.SubElement(xml_parent, qn)
                self.translate_obj(job, mod_name, node_spec[1], el,
                                   new_path + "/")
            elif node_spec[0] == "list":
                check_val(is_array(job), new_path, "list")
                i = 0
                keys = node_spec[2][:]
                keys.reverse()
                for child in job:
                    check_val(isinstance(child, dict), new_path, "list entry")
                    el = ET.SubElement(xml_parent, qn)
                    ent_path = new_path + "/%d/" % i
                    self.translate_obj(child, mod_name, node_spec[1],
                                       el, ent_path)
                    # Rearrange the subtree so that keys come first and in order
                    for k in keys:
                        knode = el.find(self.et_qname(*k))
                        try:
                            el.remove(knode)
                        except (ValueError, TypeError):
                            raise MissingKeyError(ent_path, k)
                        el.insert(0,knode)
                    i += 1
            elif node_spec[0] == "leaf":
                check_val(is_scalar(job), new_path, "leaf")
                aobj = json_obj.get("@" + key)
                self.handle_leaf(job, node_spec[1], mod_name,
                                 qn, xml_parent, new_path, aobj)
            elif node_spec[0] == "leaf-list":
                check_val(is_array(job), new_path, "leaf-list")
                aarr = json_obj.get("@" + key, [])
                la = len(aarr)
                i = 0
                for child in job:
                    check_val(is_scalar(child), new_path, "leaf-list entry")
                    aobj = aarr[i] if i < la else None
                    self.handle_leaf(child, node_spec[1], mod_name, qn,
                                     xml_parent, new_path + "/%d" % i, aobj)
                    i += 1
            elif node_spec[0] == "anyxml":
                el = ET.SubElement(xml_parent, qn)
                aobj = json_obj.get("@" + key)
                if aobj:
                    self.handle_annotations(aobj, el, mod_name, new_path)
                if isinstance(job, dict):
                    self.handle_anyxml(job, el)
                else:
                    el.text = str(job)

    def handle_annotations(self, annot_obj, elem, mod_name, path):
        if not isinstance(annot_obj, dict):
            raise InvalidAnnotationObjectError(path)
        for ann in annot_obj:
            try:
                atyp = self.annots[ann]
            except KeyError:
                raise InvalidAnnotationError(path, ann)
            aval = self.text_value(annot_obj[ann], atyp, mod_name, path)
            if aval is None :
                tsp = atyp[0] if isinstance(atyp, list) else atyp
                raise DataTypeError(path + "/@" + ann, tsp, annot_obj[ann])
            m, a = ann.split(":")
            self.node_modules.add(m)
            elem.attrib[self.et_qname(m, a)] = aval

    def handle_leaf(self, value, ytyp, mod_name, leaf_name,
                    xml_parent, path, annot_obj):
        """
        Install the transformed leaf with `value` under `xml_parent`.
        """
        tval = self.text_value(value, ytyp, mod_name, path)
        if tval is None :
            tsp = ytyp[0] if isinstance(ytyp, list) else ytyp
            raise DataTypeError(path, tsp, value)
        el = ET.SubElement(xml_parent, leaf_name)
        el.text = tval
        if annot_obj:
            self.handle_annotations(annot_obj, el, mod_name, path)

    def handle_anyxml(self, obj, parent):
        """Translate anyxml content from JSON object `obj` and attach under `el`."""
        for ch in obj:
            cobj = obj[ch]
            if isinstance(cobj, dict):
                el = ET.SubElement(parent, ch)
                self.handle_anyxml(cobj, el)
            elif isinstance(cobj, list):
                for eob in cobj:
                    el = ET.SubElement(parent, ch)
                    if isinstance(eob, dict):
                        self.handle_anyxml(eob, el)
                    else:
                        el.text = str(eob)
            else:
                el = ET.SubElement(parent, ch)
                el.text = str(cobj)

    def node_lookup(self, name, ns, parent, path):
        """Return tag, module name and node specification for `name`."""
        fst, sep, snd = name.partition(":")
        try:
            spec = parent[name]
        except KeyError:
            if sep and fst == ns:
                try:
                    spec = parent[snd]
                except KeyError:
                    raise InvalidNodeError(path)
            else:
                raise InvalidNodeError(path)
        if sep:
            self.node_modules.add(fst)
            return snd, fst, spec
        return fst, ns, spec

    def text_value(self, value, type_spec, mod_name, path):
        """Return `value` translated to its XML form.

        Return `None` if `value` cannot be represented as an instance
        of the datatype specified by `type_spec`.

        Arguments:

        - `value`: leaf value as found in JSON;

        - `type_spec`: type specification produced by the "jtox" plugin;

        - `mod_name`: module name of the containing leaf

        - `path`: path of the node containing `value` (for error reporting)
        """
        def handle_int(value, bits, unsigned):
            if (bits == 64 and isinstance(value, str)
                or isinstance(value, numbers.Integral)
                or isinstance(value, numbers.Real) and value.is_integer()):

                try:
                    val = int(value)
                except ValueError:
                    return None
            else:
                return None
            if unsigned:
                lo = 0
                hi = 2 ** bits
            else:
                hi = 2 ** (bits-1)
                lo = -hi
            return "%d" % val if lo <= val < hi else None

        t = type_spec[0] if isinstance(type_spec, list) else type_spec
        if t == 'empty':
            return "" if value == [None] else None
        if t.startswith("int"):
            return handle_int(value, int(t[3:]), False)
        if t.startswith("uint"):
            return handle_int(value, int(t[4:]), True)
        if t == "decimal64":
            if not isinstance(value, str):
                return None
            ip, dp, fp = value.partition('.')
            try:
                if dp:
                    fp = fp.rstrip("0")
                    if len(fp) == 0:
                        fp = "0"
                    if len(fp) > type_spec[1]:
                        return None
                    ival = int(ip + fp)
                else:
                    ival = int(ip)
            except ValueError:
                return None
            hi = 2 ** 63
            lo = -hi
            return ip + dp + fp if lo <= ival < hi else None
        if t == "boolean":
            if value is True:
                return "true"
            elif value is False:
                return "false"
            else:
                return None
        if t == "union":
            for memb in type_spec[1]:
                tval = self.text_value(value, memb, mod_name, path)
                if tval is not None:
                    return tval
            return None
        if t == "identityref":
            try:
                fst, sep, snd = value.partition(":")
                if sep:
                    m = fst
                    idv = snd
                else:
                    m = mod_name
                    idv = value
                return "%s:%s" % (self.prefix[m], idv)
            except:
                return None
        if t == "instance-identifier":
            result = ""
            node = self.tree
            try:
                rest = value.strip()
                m = None
                while len(rest) > 0:
                    result += rest[0]
                    zb = rest[1:]
                    if rest[0] == "/":
                        mo = self.qn_re.search(zb)
                        t, m, spec = self.node_lookup(mo.group(1), m, node, path)
                        result += self.prefix[m] + ":" + t
                        rest = mo.group(2)
                        if spec[0] in ("container", "list"):
                            node = spec[1]
                    elif rest[0] == "[":
                        mo = self.num_re.search(zb)
                        if mo is None:
                            mo = self.qn_re.search(zb)
                            t, m, spec = self.node_lookup(mo.group(1), m, node, path)
                            result +=  self.prefix[m] + ":" + t + "="
                            mo = self.bra_re.search(mo.group(2))
                        result += mo.group(1).strip() + "]"
                        rest = mo.group(2)
                    else:
                        return None
            except:
                return None
            return result
        return str(value)

def main():
    """Parse arguments, open files, create and run the translator."""
    parser = argparse.ArgumentParser(
        description="JSON to XML conversion driven by a YANG data model.")
    parser.add_argument("jtox", metavar="driver_file", action="store",
                        help="driver file produced by YANG plugin 'jtox'")
    parser.add_argument("json", metavar='json_file', action="store",
                        help="JSON instance document (or '-' for standard input)")
    parser.add_argument("-t", "--target", action="store", default="data",
                        help="type of the resulting XML document (default: data)")
    parser.add_argument("-o", "--output", action="store",
                        help="output file (default: standard output)")
    args = parser.parse_args()
    if args.target not in ["data", "config"]:
        sys.stderr.write("%s: error: unknown target '%s'\n" % (parser.prog, args.target))
        return 2
    try:
        dfile = codecs.open(args.jtox, encoding="utf-8")
        jfile = sys.stdin \
            if args.json == "-" else codecs.open(args.json, encoding="utf-8")
        outfile = sys.stdout if args.output is None else open(args.output, "wb")
        jtox = json.load(dfile)
    except IOError as e:
        sys.stderr.write("%s: error: %s: '%s'\n" %
                         (parser.prog, e.strerror, e.filename))
        return 1
    except ValueError as e:
        sys.stderr.write("%s: error: %s\n" %
                         (parser.prog, e.message))
        return 1
    nc_uri = "urn:ietf:params:xml:ns:netconf:base:1.0"
    ET.register_namespace("nc", nc_uri)
    root_el = ET.Element("{%s}%s" % (nc_uri, args.target))
    trans = Translator(jtox)
    try:
        trans.translate(jfile, root_el)
    except Error as e:
        sys.stderr.write("%s: %s\n" % (parser.prog, e))
        return e.return_value
    for m in set(trans.prefix) - trans.node_modules:
        root_el.attrib["xmlns:" + trans.prefix[m]] = trans.uri[m]
    ET.ElementTree(root_el).write(outfile, encoding="utf-8", xml_declaration=True)
    return 0

if __name__ == "__main__":
    sys.exit(main())
