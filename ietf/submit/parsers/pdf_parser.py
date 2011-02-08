from ietf.submit.parsers.base import FileParser


class PDFParser(FileParser):

    def parse_critical_filename_extension(self):
        if not self.fd.name.endswith('.pdf'):
            self.parsed_info.add_error('Format of this document must be PDF')
