import lxml
from lxml.etree import Element, SubElement, ElementTree

ns={
    'x':'http://relaxng.org/ns/structure/1.0',
    'a':'http://relaxng.org/ns/compatibility/annotations/1.0',
}
schema = ElementTree(file="v3.rng")     # TODO: use a path relative to this file or something
rfc_attributes = schema.xpath("/x:grammar/x:define/x:element[@name='rfc']//x:attribute", namespaces=ns)
rfc_attr_defaults = dict( (a.get('name'), a.get("{%s}defaultValue"%ns['a'], None)) for a in rfc_attributes )

class DraftParser():

    text = None
    root = None
    name = None

    def parse_to_xml(self, text, name, **kwargs):
        self.text = text
        self.name = name

#         for item in self.schema.iter():
#             print(item.tag)

        self.root = Element('rfc')
        for attr in rfc_attr_defaults:
            val = rfc_attr_defaults[attr]
            if val:
                self.root.set(attr, val)
        for attr in kwargs:
            if attr in rfc_attr_defaults:
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
        
