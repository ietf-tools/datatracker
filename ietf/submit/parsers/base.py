import datetime
import re


CUTOFF_HOUR = 17


class MetaDataDraft(object):
    revision = None
    filename = None
    group = None


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

    def parse(self):
        if not self.fd:
            return self.parsed_info
        for attr in dir(self):
            if attr.startswith('parse_critical_'):
                method = getattr(self, attr, None)
                if callable(method):
                    method()
        # If some critical parsing has returned an error do not continue
        if self.parsed_info.errors:
            return self.parsed_info
        # Continue with non critical parsing, note that they also can return errors
        for attr in dir(self):
            if attr.startswith('parse_normal_'):
                method = getattr(self, attr, None)
                if callable(method):
                    method()
        if self.parsed_info.errors:
            return self.parsed_info

    def parse_critical_000_invalid_chars_in_filename(self):
        name = self.fd.name
        regexp = re.compile(r'&|\|\/|;|\*|\s|\$')
        chars = regexp.findall(name)
        if chars:
            self.parsed_info.add_error('Invalid characters were found in the name of the file which was just submitted: %s' % ', '.join(set(chars)))
