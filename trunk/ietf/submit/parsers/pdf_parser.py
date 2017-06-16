from ietf.submit.parsers.base import FileParser


class PDFParser(FileParser):
    ext = 'pdf'
    mimetypes = ['application/pdf', ]

    # If some error is found after this method invocation
    # no other file parsing is recommended
    def critical_parse(self):
        super(PDFParser, self).critical_parse()
        return self.parsed_info
