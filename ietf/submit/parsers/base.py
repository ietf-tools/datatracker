import re


CUTOFF_HOUR = 17


class MetaDataDraft(object):
    revision = None
    filename = None
    group = None
    filesize = None
    first_two_pages = None
    page_count = None
    submission_date = None
    creation_date = None
    authors = None

class ParseInfo(object):

    def __init__(self):
        self.errors = []
        self.warnings = {}
        self.metadraft = MetaDataDraft()

    def add_error(self, error_str):
        self.errors.append(error_str)

    def add_warning(self, warning_type, warning_str):
        warn_list = self.warnings.get(warning_type, [])
        self.warnings[warning_type] = warn_list + [warning_str]


class FileParser(object):

    def __init__(self, fd):
        self.fd = fd
        self.parsed_info = ParseInfo()

    # If some error is found after this method invocation
    # no other file parsing is recommended
    def critical_parse(self):
        self.parse_invalid_chars_in_filename()
        return self.parsed_info

    def parse_invalid_chars_in_filename(self):
        name = self.fd.name
        regexp = re.compile(r'&|\|\/|;|\*|\s|\$')
        chars = regexp.findall(name)
        if chars:
            self.parsed_info.add_error('Invalid characters were found in the name of the file which was just submitted: %s' % ', '.join(set(chars)))
