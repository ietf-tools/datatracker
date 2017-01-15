import lxml
#import debug
from lxml.etree import Element, SubElement, ElementTree

ns={
    'x':'http://relaxng.org/ns/structure/1.0',
    'a':'http://relaxng.org/ns/compatibility/annotations/1.0',
}

class DraftParser():

    text = None
    root = None
    name = None

    schema = None

    def __init__(self, schema="v3"):
        self.schema = ElementTree(file=schema+".rng")
        self.rfc_attr = self.schema.xpath("/x:grammar/x:define/x:element[@name='rfc']//x:attribute", namespaces=ns)
        self.rfc_attr_defaults = dict( (a.get('name'), a.get("{%s}defaultValue"%ns['a'], None)) for a in self.rfc_attr )

    def parse_to_xml(self, text, name, **kwargs):
        self.text = text
        self.name = name

#         for item in self.schema.iter():
#             print(item.tag)

        self.root = Element('rfc')
        for attr in self.rfc_attr_defaults:
            if not ':' in attr:
                val = self.rfc_attr_defaults[attr]
                if val:
                    self.root.set(attr, val)
        for attr in kwargs:
            if attr in self.rfc_attr_defaults:
                val = kwargs[attr]
                self.root.set(attr, val)
        self.root.set('docName', self.name)

        self.get_document()
        if len(self.root):
            return lxml.etree.tostring(
                self.root.getroottree(),
                xml_declaration=True,
                encoding='utf-8',
                doctype='<!DOCTYPE rfc SYSTEM "rfc2629.dtd">',
                pretty_print=True,
            ).decode('utf-8')
        else:
            return None

    def get_document(self):
        self.get_front()
        self.get_middle()
        self.get_back()
        return self.root.getroottree()

    def get_front(self):
        front = SubElement(self.root, 'front')

    def get_middle(self):
        middle = SubElement(self.root, 'middle')
        
    def get_back(self):
        back = SubElement(self.root, 'back')
        
