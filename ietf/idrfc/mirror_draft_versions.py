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

from ietf import settings
from django.core import management
management.setup_environ(settings)
from django import db

import re
import urllib2
from datetime import datetime
import socket
import sys

URL = "http://merlot.tools.ietf.org/~pasi/draft_versions.txt"
TABLE = "draft_versions_mirror"

log_data = ""
def log(line):
    global log_data
    if len(sys.argv) > 1:
        print line
    else:
        log_data += line + "\n"

try:
    log("output from mirror_draft_versions.py:\n")
    log("time: "+str(datetime.now()))
    log("host: "+socket.gethostname())
    log("url: "+URL)
                    
    log("downloading...")
    response = urllib2.urlopen(URL)
    #log("got \n"+str(response.info()))
    log("parsing...")
    data = []
    for line in response.readlines():
        rec = line[:-1].split("\t")
        data.append(rec)

    log("got " + str(len(data)) + " entries")
    if len(data) < 10000:
        raise Exception('not enough data')

    log("connecting to database...")
    cursor = db.connection.cursor()
    log("removing old data...")
    cursor.execute("DELETE FROM "+TABLE)
    log("inserting new data...")
    cursor.executemany("INSERT INTO "+TABLE+" (filename, revision, revision_date) VALUES (%s, %s, %s)", data)
    cursor.close()
    db.connection._commit()
    db.connection.close()

    log("all done!")
    log_data = ""
finally:
    if len(log_data) > 0:
        print log_data
