# Copyright The IETF Trust 2020, All Rights Reserved
# -*- coding: utf-8 -*-


import magic

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

