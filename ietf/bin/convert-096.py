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

from os.path import exists
import os
import re

def convert_py(file):
    print "  Converting ", file
    inf = open(file)
    outf_name = file+'.tmp~'
    outf = open(outf_name, "w")
    fixes = {}
    for line in inf:
        if re.search("Field.*maxlength=\d", line):
            line = line.replace("maxlength=", "max_length=")
            fixes['changed maxlength to max_length'] = True
        if re.search("^\s*from django import newforms as forms\s*$", line):
            line = "from django import forms\n"
            fixes['changed newforms to forms'] = True
        if re.search("^\s*import django.newforms as forms\s*$", line):
            line = "from django import forms\n"
            fixes['changed newforms to forms'] = True
        if re.search("^\s*from django.core.validators import email_re\s*$", line):
            line = "from django.forms.fields import email_re\n"
            fixes['changed email_re import'] = True
        if re.search("ForeignKey.*raw_id_admin=True", line):
            line = re.sub(",\s*raw_id_admin=True", "", line)
            fixes['removed raw_id_admin'] = True
        if re.search("ForeignKey.*edit_inline=True", line):
            line = re.sub(",\s*edit_inline=True", "", line)
            fixes['removed edit_inline'] = True
        if re.search("ForeignKey.*edit_inline=models\.\w+", line):
            line = re.sub(",\s*edit_inline=models\.\w+", "", line)
            fixes['removed edit_inline'] = True
        if re.search("ForeignKey.*num_in_admin=\d+", line):
            line = re.sub(",\s*num_in_admin=\d+", "", line)
            fixes['removed num_in_admin'] = True
        if re.search("ForeignKey.*max_num_in_admin=\d+", line):
            line = re.sub(",\s*max_num_in_admin=\d+", "", line)
            fixes['removed max_num_in_admin'] = True
        if re.search("ManyToManyField.*filter_interface=models\.\w+", line):
            line = re.sub(",\s*filter_interface=models\.\w+", "", line)
            fixes['removed filter_interface'] = True
        if re.search("(Field|ForeignKey).*core=True", line):
            line = re.sub(",\s*core=True", "", line)
            fixes['removed core'] = True
        if re.search("\.clean_data", line):
            line = re.sub("\.clean_data", ".cleaned_data", line)
            fixes['cleaned_data'] = True
        outf.write(line)
    inf.close()
    fixes_list = fixes.keys()
    fixes_list.sort()
    something_fixed = len(fixes_list) > 0
    if something_fixed:
        outf.write("\n# changes done by convert-096.py:")
        outf.write("\n# ".join(fixes_list))
        outf.write("\n")
    outf.close()
    if something_fixed:
        os.rename(file, file+'.backup~')
        os.rename(outf_name, file)
        print "  Fixes: "+", ".join(fixes_list)
    else:
        os.remove(outf_name)

if not exists("settings.py"):
    raise Exception("Please run this in directory containing settings.py")

for root, dirs, files in os.walk("."):
    if root.find(".svn") >= 0:
        continue
    print "Processing ", root
    for file in files:
        if file.endswith(".py"):
            convert_py(root+"/"+file)


