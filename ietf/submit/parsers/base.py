# Copyright The IETF Trust 2011-2023, All Rights Reserved
# -*- coding: utf-8 -*-


import re
import debug  # pyflakes:ignore

from typing import List, Optional  # pyflakes:ignore

from django.conf import settings
from django.template.defaultfilters import filesizeformat

from ietf.utils.timezone import date_today


class MetaData:
    rev = None
    name = None
    group = None
    file_size = None
    first_two_pages = None
    pages = None
    submission_date = None
    document_date = None
    authors = None


class ParseInfo:
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


class FileParser:
    ext: Optional[str] = None
    encoding = "utf8"

    def __init__(self, fd):
        self.fd = fd
        self.parsed_info = ParseInfo()

    # If some error is found after this method invocation
    # no other file parsing is recommended
    def critical_parse(self):
        self.parse_invalid_chars_in_filename()
        self.parse_max_size()
        self.parse_filename_extension()
        self.validate_encoding()
        self.parsed_info.metadata.submission_date = date_today()
        return self.parsed_info

    def parse_invalid_chars_in_filename(self):
        name = self.fd.name
        regexp = re.compile(r"&|\\|/|;|\*|\s|\$")
        chars = regexp.findall(name)
        if chars:
            self.parsed_info.add_error(
                "Invalid characters were found in the name of the file which was just submitted: %s"
                % ", ".join(set(chars))
            )

    def parse_max_size(self):
        max_size = settings.IDSUBMIT_MAX_DRAFT_SIZE[self.ext]
        if self.fd.size > max_size:
            self.parsed_info.add_error(
                "File size is larger than the permitted maximum of %s"
                % filesizeformat(max_size)
            )
        self.parsed_info.metadata.file_size = self.fd.size

    def parse_filename_extension(self):
        if not self.fd.name.lower().endswith("." + self.ext):
            self.parsed_info.add_error(
                'Expected the %s file to have extension ".%s", found the name "%s"'
                % (self.ext.upper(), self.ext, self.fd.name)
            )

    def validate_encoding(self):
        self.fd.seek(0)
        bytes = self.fd.read()
        try:
            bytes.decode(self.encoding)
        except UnicodeDecodeError as err:
            invalid_bytes = bytes[err.start : err.end]
            self.parsed_info.add_error(
                "Invalid {} byte(s) starting at byte {}: [{}]".format(
                    err.encoding,
                    err.start + 1,
                    ", ".join(f"0x{b:x}" for b in invalid_bytes)
                )
            )
