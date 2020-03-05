# Copyright The IETF Trust 2009-2020, All Rights Reserved
# -*- coding: utf-8 -*-
#
# Copyright (C) 2009 Nokia Corporation and/or its subsidiary(-ies).
# All rights reserved. Contact: Pasi Eronen <pasi.eronen@nokia.com>
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
#  * Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
#
#  * Redistributions in binary form must reproduce the above
#    copyright notice, this list of conditions and the following
#    disclaimer in the documentation and/or other materials provided
#    with the distribution.
#
#  * Neither the name of the Nokia Corporation and/or its
#    subsidiary(-ies) nor the names of its contributors may be used
#    to endorse or promote products derived from this software
#    without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.


import re

from django.utils.html import escape

from ietf.utils import log
from ietf.utils.text import wordwrap

def markup(content, width=None):
    log.assertion('isinstance(content, str)')
    # normalize line endings to LF only
    content = content.replace("\r\n", "\n")
    content = content.replace("\r", "\n")

    # remove leading white space
    content = content.lstrip()
    # remove runs of blank lines
    content = re.sub("\n\n\n+", "\n\n", content)

    # maybe wordwrap.  This must be done before the escaping below.
    if width:
        content = wordwrap(content, width)

    # expand tabs + escape 
    content = escape(content.expandtabs())

    content = re.sub(r"\n(.+\[Page \d+\])\n\f\n(.+)\n", r"""\n<span class="m_ftr">\g<1></span>\n<span class="m_hdr">\g<2></span>\n""", content)
    content = re.sub(r"\n(.+\[Page \d+\])\n\s*$", r"""\n<span class="m_ftr">\g<1></span>\n""", content)
    # remove remaining FFs (to be valid XHTML)
    content = content.replace("\f","\n")

    content = re.sub(r"\n\n([0-9]+\\.|[A-Z]\\.[0-9]|Appendix|Status of|Abstract|Table of|Full Copyright|Copyright|Intellectual Property|Acknowled|Author|Index)(.*)(?=\n\n)", r"""\n\n<span class="m_h">\g<1>\g<2></span>""", content)

    return "<pre>" + content + "</pre>\n"
