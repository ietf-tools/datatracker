import re
import os
import magic
from pyquery import PyQuery

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.template.defaultfilters import filesizeformat

import debug                            # pyflakes:ignore

def get_cleaned_text_file_content(uploaded_file):
    """Read uploaded file, try to fix up encoding to UTF-8 and
    transform line endings into Unix style, then return the content as
    a UTF-8 string. Errors are reported as
    django.core.exceptions.ValidationError exceptions."""

    if not uploaded_file:
        return u""

    if uploaded_file.size and uploaded_file.size > 10 * 1000 * 1000:
        raise ValidationError("Text file too large (size %s)." % uploaded_file.size)

    content = "".join(uploaded_file.chunks())

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

    if not filetype.startswith("text"):
        raise ValidationError("Uploaded file does not appear to be a text file.")

    match = re.search("charset=([\w-]+)", filetype)
    if not match:
        raise ValidationError("File has unknown encoding.")

    encoding = match.group(1)
    if "ascii" not in encoding:
        try:
            content = content.decode(encoding)
        except Exception as e:
            raise ValidationError("Error decoding file (%s). Try submitting with UTF-8 encoding or remove non-ASCII characters." % str(e))

    # turn line-endings into Unix style
    content = content.replace("\r\n", "\n").replace("\r", "\n")

    return content.encode("utf-8")

def get_mime_type(content):
    # try to fixup encoding
    if hasattr(magic, "open"):
        m = magic.open(magic.MAGIC_MIME)
        m.load()
        filetype = m.buffer(content)
    else:
        m = magic.Magic()
        m.cookie = magic.magic_open(magic.MAGIC_NONE | magic.MAGIC_MIME | magic.MAGIC_MIME_ENCODING)
        magic.magic_load(m.cookie, None)
        filetype = m.from_buffer(content)
        
    return filetype.split('; ', 1)

def validate_file_size(size):
    if size > settings.SECR_MAX_UPLOAD_SIZE:
        raise forms.ValidationError('Please keep filesize under %s. Requested upload size was %s' % (filesizeformat(settings.SECR_MAX_UPLOAD_SIZE), filesizeformat(size)))

def validate_mime_type(content, valid):
    mime_type, encoding = get_mime_type(content)
    if not mime_type in valid:
        raise forms.ValidationError('Found content with unexpected mime type: %s.  Expected one of %s.' %
                                    (mime_type, ', '.join(valid) ))
    return mime_type, encoding

def validate_file_extension(name, valid):
    name, ext = os.path.splitext(name)
    if ext.lower() not in valid:
        raise forms.ValidationError('Found an unexpected extension: %s.  Expected one of %s' % (ext, ','.join(valid)))
    return ext

def validate_no_html_frame(content):
    q = PyQuery(content)
    if q("frameset") or q("frame") or q("iframe"):
        raise forms.ValidationError('Found content with html frames.  Please upload a file that does not use frames')
