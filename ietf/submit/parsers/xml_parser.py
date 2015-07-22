from ietf.submit.parsers.base import FileParser


class XMLParser(FileParser):

    # If some error is found after this method invocation
    # no other file parsing is recommended
    def critical_parse(self):
        super(XMLParser, self).critical_parse()
        self.parse_filename_extension('xml')
        self.parse_file_type('xml', 'application/xml')
        return self.parsed_info
    
