
import re
import magic
import datetime
import debug                            # pyflakes:ignore

from django.conf import settings
from django.template.defaultfilters import filesizeformat

class MetaData(object):
    rev = None
    name = None
    group = None
    file_size = None
    first_two_pages = None
    pages = None
    submission_date = None
    document_date = None
    authors = None

class ParseInfo(object):
    """Collect errors from a parse"""

    def __init__(self):
        self.errors = []
        # warnings are currently unused by the parsers
        self.warnings = {}
        # the metadata fields are currently unused, i.e. the plain
        # text parser fills in some fields but they are not used
        # anywhere (instead the draft parser is used for .txt and the
        # other file types have no actual parsing at the moment)
        self.metadata = MetaData()

    def add_error(self, error_str):
        self.errors.append(error_str)

    def add_warning(self, warning_type, warning_str):
        warn_list = self.warnings.get(warning_type, [])
        self.warnings[warning_type] = warn_list + [warning_str]


class FileParser(object):
    ext = None
    mimetypes = []

    def __init__(self, fd):
        self.fd = fd
        self.parsed_info = ParseInfo()

    # If some error is found after this method invocation
    # no other file parsing is recommended
    def critical_parse(self):
        self.parse_invalid_chars_in_filename()
        self.parse_max_size();
        self.parse_filename_extension()
        self.parse_file_type()
        self.parsed_info.metadata.submission_date = datetime.date.today()
        return self.parsed_info

    def parse_invalid_chars_in_filename(self):
        name = self.fd.name
        regexp = re.compile(r'&|\|\/|;|\*|\s|\$')
        chars = regexp.findall(name)
        if chars:
            self.parsed_info.add_error(u'Invalid characters were found in the name of the file which was just submitted: %s' % ', '.join(set(chars)))

    def parse_max_size(self):
        max_size = settings.IDSUBMIT_MAX_DRAFT_SIZE[self.ext]
        if self.fd.size > max_size:
            self.parsed_info.add_error(u'File size is larger than the permitted maximum of %s' % filesizeformat(max_size))
        self.parsed_info.metadata.file_size = self.fd.size

    def parse_filename_extension(self):
        if not self.fd.name.lower().endswith('.'+self.ext):
            self.parsed_info.add_error(u'Expected the %s file to have extension ".%s", found the name "%s"' % (self.ext.upper(), self.ext, self.fd.name))

    def parse_file_type(self):
        self.fd.file.seek(0)
        content = self.fd.file.read(4096)
        mimetype = magic.from_buffer(content, mime=True)
        if not mimetype in self.mimetypes:
            self.parsed_info.add_error(u'Expected an %s file of type "%s", found one of type "%s"' % (self.ext.upper(), '" or "'.join(self.mimetypes), mimetype))
