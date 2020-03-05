# Copyright The IETF Trust 2012-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import re

from django.conf import settings
from django.core.exceptions import ValidationError

import debug                            # pyflakes:ignore

def get_cleaned_text_file_content(uploaded_file):
    """Read uploaded file, try to fix up encoding to UTF-8 and
    transform line endings into Unix style, then return the content as
    a UTF-8 string. Errors are reported as
    django.core.exceptions.ValidationError exceptions."""

    if not uploaded_file:
        return ""

    if uploaded_file.size and uploaded_file.size > 10 * 1000 * 1000:
        raise ValidationError("Text file too large (size %s)." % uploaded_file.size)

    content = b"".join(uploaded_file.chunks())

    # try to fixup encoding
    import magic
    if hasattr(magic, "open"):
        m = magic.open(magic.MAGIC_MIME)
        m.load()
        filetype = m.buffer(content)
    else:
        m = magic.Magic()
        m.cookie = magic.magic_open(magic.MAGIC_NONE | magic.MAGIC_MIME | magic.MAGIC_MIME_ENCODING)
        magic.magic_load(m.cookie, None)
        filetype = m.from_buffer(content)

    if not filetype.startswith(settings.DOC_TEXT_FILE_VALID_UPLOAD_MIME_TYPES):
        raise ValidationError("Uploaded file does not appear to be a text file. "
                              "Permitted MIME types are {}, this file is {}"
                              .format(', '.join(settings.DOC_TEXT_FILE_VALID_UPLOAD_MIME_TYPES), filetype))

    match = re.search(r"charset=([\w-]+)", filetype)
    if not match:
        raise ValidationError("File has unknown encoding.")

    encoding = match.group(1)
    try:
        content = content.decode(encoding)
    except Exception as e:
        raise ValidationError("Error decoding file (%s). Try submitting with UTF-8 encoding or remove non-ASCII characters." % str(e))

    # turn line-endings into Unix style
    content = content.replace("\r\n", "\n").replace("\r", "\n")

    return content
