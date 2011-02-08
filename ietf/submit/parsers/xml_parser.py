from ietf.submit.parsers.base import FileParser


class XMLParser(FileParser):

    def parse_critical_filename_extension(self):
        if not self.fd.name.endswith('.xml'):
            self.parsed_info.add_error('Format of this document must be XML')
