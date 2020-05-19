from ietf.submit.parsers.base import FileParser


class PSParser(FileParser):
    ext = 'ps'
    mimetypes = ['application/postscript', ]

    # If some error is found after this method invocation
    # no other file parsing is recommended
    def critical_parse(self):
        super(PSParser, self).critical_parse()
        return self.parsed_info
