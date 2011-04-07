from ietf.submit.parsers.base import FileParser


class XMLParser(FileParser):

    # If some error is found after this method invocation
    # no other file parsing is recommended
    def critical_parse(self):
        super(XMLParser, self).critical_parse()
        self.parse_filename_extension()
        return self.parsed_info

    def parse_filename_extension(self):
        if not self.fd.name.endswith('.xml'):
            self.parsed_info.add_error('Format of this document must be XML')
