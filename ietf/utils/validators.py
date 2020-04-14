# Copyright The IETF Trust 2016-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import os
import re
from pyquery import PyQuery

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.template.defaultfilters import filesizeformat
from django.utils.deconstruct import deconstructible

import debug                            # pyflakes:ignore

from ietf.utils.mime import get_mime_type

# Note that this is an instantiation of the regex validator, _not_ the
# regex-string validator defined right below
validate_no_control_chars = RegexValidator(
                                    regex="^[^\x00-\x1f]*$",
                                    message="Please enter a string without control characters." )


@deconstructible
class RegexStringValidator(object):
    "Validates that a given regular expression can be compiled."

    def __init__(self):
        pass

    def __call__(self, value):
        """
        Validates that the given regular expression can be compiled.
        """
        try:
            re.compile(value)
        except Exception as e:
            raise ValidationError('Please enter a valid regular expression.  '
                                    'Got an error when trying to compile this: "%s" : "%s"'
                                    % (value, e))
        if '-*' in value:
            raise ValidationError('Did you really mean that?  The regular expression '
                                    'contains "-*" which will match zero or more dashes.  '
                                    'Maybe you meant to write "-.*"?  If you actually meant "-*", '
                                    'you can use "[-]*" instead to get past this error.')

    def __eq__(self, other):
        return isinstance(other, RegexStringValidator)

    def __ne__(self, other):
        return not (self == other)

validate_regular_expression_string = RegexStringValidator()

def validate_file_size(file):
    if file._size > settings.SECR_MAX_UPLOAD_SIZE:
        raise ValidationError('Please keep filesize under %s. Requested upload size was %s' % (filesizeformat(settings.SECR_MAX_UPLOAD_SIZE), filesizeformat(file._size)))

def validate_mime_type(file, valid):
    file.open()
    raw = file.read()
    mime_type, encoding = get_mime_type(raw)
    # work around mis-identification of text where a line has 'virtual' as
    # the first word:
    if mime_type == 'text/x-c++' and re.search(br'(?m)^virtual\s', raw):
        mod = raw.replace(b'virtual', b' virtual')
        mime_type, encoding = get_mime_type(mod)
    if valid and not mime_type in valid:
        raise ValidationError('Found content with unexpected mime type: %s.  Expected one of %s.' %
                                    (mime_type, ', '.join(valid) ))
    return mime_type, encoding

def validate_file_extension(file, valid):
    name, ext = os.path.splitext(file.name)
    if ext.lower() not in valid:
        raise ValidationError('Found an unexpected extension: %s.  Expected one of %s' % (ext, ','.join(valid)))
    return ext

def validate_no_html_frame(file):
    file.open()
    q = PyQuery(file.read())
    if q("frameset") or q("frame") or q("iframe"):
        raise ValidationError('Found content with html frames.  Please upload a file that does not use frames')
