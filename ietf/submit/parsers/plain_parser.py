import re

from ietf.idtracker.models import InternetDraft
from ietf.submit.error_manager import MainErrorManager
from ietf.submit.parsers.base import FileParser

MAX_PLAIN_FILE_SIZE = 6000000
NONE_WG_PK = 1027


class PlainParser(FileParser):

    def parse_critical_max_size(self):
        if self.fd.size > MAX_PLAIN_FILE_SIZE:
            self.parsed_info.add_error(MainErrorManager.get_error_str('EXCEEDED_SIZE'))

    def parse_critical_001_file_charset(self):
        import magic
        self.fd.file.seek(0)
        m = magic.open(magic.MAGIC_MIME)
        m.load()
        filetype = m.buffer(self.fd.file.read())
        if not 'ascii' in filetype:
            self.parsed_info.add_error('A plain text document must be submitted.')

    def parse_critical_002_filename(self):
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
            filename = match.group(0)
            filename = re.sub('^[^\w]+', '', filename)
            filename = re.sub('[^\w]+$', '', filename)
            filename = re.sub('\.txt$', '', filename)
            extra_chars = re.sub('[0-9a-z\-]', '', filename)
            if extra_chars:
                self.parsed_info.add_error('Filename contains non alpha-numeric character: %s' % ', '.join(set(extra_chars)))
            match_revision = revisionre.match(filename)
            if match_revision:
                self.parsed_info.metadraft.revision = match_revision.group(0)
            filename = re.sub('-\d+$', '', filename)
            self.parsed_info.metadraft.filename = filename
            return
        self.parsed_info.add_error(MainErrorManager.get_error_str('INVALID_FILENAME'))

    def parse_critical_003_wg(self):
        filename = self.parsed_info.metadraft.filename
        try:
            existing_draft = InternetDraft.objects.get(filename=filename)
            self.parsed_info.metadraft.wg = existing_draft.group
        except InternetDraft.DoesNotExist:
            if filename.startswith('draft-ietf-'):
                # Extra check for WG that contains dashes
                for group in IETFWG.objects.filter(group_acronym__acronym__contains='-'):
                    if filename.startswith('draft-ietf-%s-' % group.group_acronym.acronym):
                        self.parsed_info.metadraft.wg = group
                        return
                group_acronym = filename.split('-')[2]
                try:
                    self.parsed_info.metadraft.wg = IETFWG.objects.get(group_acronym__acronym=group_acronym)
                except IETFWG.DoesNotExist:
                    self.parsed_info.add_error('Invalid WG ID: %s' % group_acronym)
            else:
                self.parsed_info.metadraft.wg = IETFWG.objects.get(pk=NONE_WG_PK)
