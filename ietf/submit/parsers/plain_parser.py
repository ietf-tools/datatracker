import datetime
import re

from django.conf import settings
from ietf.idtracker.models import InternetDraft, IETFWG
from django.template.defaultfilters import filesizeformat
from ietf.submit.parsers.base import FileParser

NONE_WG_PK = 1027


class PlainParser(FileParser):

    def __init__(self, fd):
        super(PlainParser, self).__init__(fd)

    # If some error is found after this method invocation
    # no other file parsing is recommended
    def critical_parse(self):
        super(PlainParser, self).critical_parse()
        self.parse_max_size()
        self.parse_file_charset()
        self.parse_filename()
        return self.parsed_info

    def parse_max_size(self):
        if self.fd.size > settings.MAX_PLAIN_DRAFT_SIZE:
            self.parsed_info.add_error('File size is larger than %s' % filesizeformat(settings.MAX_PLAIN_DRAFT_SIZE))
        self.parsed_info.metadraft.filesize = self.fd.size
        self.parsed_info.metadraft.submission_date = datetime.date.today()

    def parse_file_charset(self):
        import magic
        self.fd.file.seek(0)
        m = magic.open(magic.MAGIC_MIME)
        m.load()
        filetype = m.buffer(self.fd.file.read())
        if not 'ascii' in filetype:
            self.parsed_info.add_error('A plain text document must be submitted.')

    def parse_filename(self):
        self.fd.file.seek(0)
        draftre = re.compile('(draft-\S+)')
        revisionre = re.compile('.*-(\d+)$')
        limit = 80
        while limit:
            limit -= 1
            line = self.fd.readline()
            match = draftre.search(line)
            if not match:
                continue
            filename = match.group(1)
            filename = re.sub('^[^\w]+', '', filename)
            filename = re.sub('[^\w]+$', '', filename)
            filename = re.sub('\.txt$', '', filename)
            extra_chars = re.sub('[0-9a-z\-]', '', filename)
            if extra_chars:
                self.parsed_info.add_error(u'Filename contains non alpha-numeric character: %s' % (', '.join(set(extra_chars))).decode('ascii','replace'))
            match_revision = revisionre.match(filename)
            if match_revision:
                self.parsed_info.metadraft.revision = match_revision.group(1)
            else:
                self.parsed_info.add_error(u'The filename found on the first page of the document does not contain a revision: "%s"' % (filename,))
            filename = re.sub('-\d+$', '', filename)
            self.parsed_info.metadraft.filename = filename
            return
        self.parsed_info.add_error('The first page of the document does not contain a legitimate filename that start with draft-*')
