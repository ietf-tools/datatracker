from ietf.submit.parsers.base import FileParser


class XMLParser(FileParser):
    ext = 'xml'
    mimetype = 'application/xml'

    # If some error is found after this method invocation
    # no other file parsing is recommended
    def critical_parse(self):
        super(XMLParser, self).critical_parse()
        return self.parsed_info
    
