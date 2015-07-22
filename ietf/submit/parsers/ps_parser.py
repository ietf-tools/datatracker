from ietf.submit.parsers.base import FileParser


class PSParser(FileParser):

    # If some error is found after this method invocation
    # no other file parsing is recommended
    def critical_parse(self):
        super(PSParser, self).critical_parse()
        self.parse_filename_extension('ps')
        self.parse_file_type('ps', 'application/postscript')
        return self.parsed_info
