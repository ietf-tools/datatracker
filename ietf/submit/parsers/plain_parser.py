import re

from ietf.submit.error_manager import MainErrorManager
from ietf.submit.parsers.base import FileParser

MAX_PLAIN_FILE_SIZE = 6000000

class PlainParser(FileParser):
    
    def parse_critical_max_size(self):
        if self.fd.size > MAX_PLAIN_FILE_SIZE:
            self.parsed_info.add_error(MainErrorManager.get_error_str('EXCEEDED_SIZE'))

    def parse_critical_file_charset(self):
        import magic
        self.fd.file.seek(0)
        m = magic.open(magic.MAGIC_MIME)
        m.load()
        filetype=m.buffer(self.fd.file.read())
        if not 'ascii' in filetype:
            self.parsed_info.add_error('A plain text document must be submitted.');

    def parse_filename(self):
        self.fd.file.seek(0)
        draftre = re.compile('(draft-\S+)')
        limit = 80
        while limit:
            line = self.fd.readline()
            match = draftre.match(line)
            if not match:
                continue
            filename = match.group(0)
            filename = re.sub('^[^\w]+', '', filename)
            filename = re.sub('[^\w]+$', '', filename)
            filename = re.sub('\.txt$', '', filename)
            line = re.sub('^[^\w]+', '')
