# Copyright The IETF Trust 2011-2020, All Rights Reserved


import re

import debug                            # pyflakes:ignore

from ietf.submit.parsers.base import FileParser


class PlainParser(FileParser):
    ext = 'txt'
    mimetypes = ['text/plain', ]

    def __init__(self, fd):
        super(PlainParser, self).__init__(fd)

    # If some error is found after this method invocation
    # no other file parsing is recommended
    def critical_parse(self):
        super(PlainParser, self).critical_parse()
        self.check_file_charset()
        self.parse_name()
        return self.parsed_info

    def check_file_charset(self):
        charset = self.parsed_info.charset
        if not charset in ['us-ascii', 'utf-8',]:
            self.parsed_info.add_error('A plain text ASCII document is required.  '
                'Found an unexpected encoding: "%s".  '
                'You probably have one or more non-ascii characters in your file.'  % charset
            )
        if self.fd.charset and charset != self.fd.charset:
            self.parsed_info.add_error("Unexpected charset mismatch: upload: %s, libmagic: %s" % (self.fd.charset, charset))


    def parse_name(self):
        self.fd.file.seek(0)
        draftre = re.compile(r'(draft-\S+)')
        revisionre = re.compile(r'.*-(\d+)$')
        limit = 80
        if self.parsed_info.charset in ['us-ascii', 'utf-8']:
            while limit:
                limit -= 1
                try:
                    line = self.fd.readline().decode(self.parsed_info.charset)
                except UnicodeDecodeError:
                    return
                match = draftre.search(line)
                if not match:
                    continue
                name = match.group(1)
                name = re.sub(r'^[^\w]+', '', name)
                name = re.sub(r'[^\w]+$', '', name)
                name = re.sub(r'\.txt$', '', name)
                extra_chars = re.sub(r'[0-9a-z\-]', '', name)
                if extra_chars:
                    if len(extra_chars) == 1:
                        self.parsed_info.add_error(('The document name on the first page, "%s", contains a disallowed character with byte code: %s ' % (name, ord(extra_chars[0]))) +
                                                    '(see https://www.ietf.org/id-info/guidelines.html#naming for details).')
                    else:
                        self.parsed_info.add_error(('The document name on the first page, "%s", contains disallowed characters with byte codes: %s ' % (name, (', '.join([ str(ord(c)) for c in extra_chars] )))) +
                                                    '(see https://www.ietf.org/id-info/guidelines.html#naming for details).')
                match_revision = revisionre.match(name)
                if match_revision:
                    self.parsed_info.metadata.rev = match_revision.group(1)
                else:
                    self.parsed_info.add_error('The name found on the first page of the document does not contain a revision: "%s"' % (name,))
                name = re.sub(r'-\d+$', '', name)
                self.parsed_info.metadata.name = name
                return
        self.parsed_info.add_error('The first page of the document does not contain a legitimate name that starts with draft-*')
