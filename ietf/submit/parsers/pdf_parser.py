from ietf.submit.parsers.base import FileParser


class PDFParser(FileParser):

    # If some error is found after this method invocation
    # no other file parsing is recommended
    def critical_parse(self):
        super(PDFParser, self).critical_parse()
        self.parse_filename_extension('pdf')
        self.parse_file_type('pdf', 'application/pdf')
        return self.parsed_info
