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

from xml.dom import pulldom, Node
import re
import urllib2
from datetime import datetime
import socket
import sys

INDEX_URL = "http://www.rfc-editor.org/rfc/rfc-index.xml"
TABLE = "rfc_index_mirror"

log_data = ""
def log(line):
    global log_data
    if __name__ == '__main__' and len(sys.argv) > 1:
        print line
    else:
        log_data += line + "\n"

def parse(response):
    def getChildText(parentNode, tagName):
        for node in parentNode.childNodes:
            if node.nodeType == Node.ELEMENT_NODE and node.localName == tagName:
                return node.firstChild.data
        return None

    def getDocList(parentNode, tagName):
        l = []
        for u in parentNode.getElementsByTagName(tagName):
            for d in u.getElementsByTagName("doc-id"):
                l.append(d.firstChild.data)
        if len(l) == 0:
            return None
        else:
            return ",".join(l)

    also_list = {}
    data = []
    events = pulldom.parse(response)
    for (event, node) in events:
        if event == pulldom.START_ELEMENT and node.tagName in ["bcp-entry", "fyi-entry", "std-entry"]:
            events.expandNode(node)
            node.normalize()
            bcpid = getChildText(node, "doc-id")
            doclist = getDocList(node, "is-also")
            if doclist:
                for docid in doclist.split(","):
                    if docid in also_list:
                        also_list[docid].append(bcpid)
                    else:
                        also_list[docid] = [bcpid]

        elif event == pulldom.START_ELEMENT and node.tagName == "rfc-entry":
            events.expandNode(node)
            node.normalize()
            rfc_number = int(getChildText(node, "doc-id")[3:])
            title = getChildText(node, "title")

            l = []
            for author in node.getElementsByTagName("author"):
                l.append(getChildText(author, "name"))
            authors = "; ".join(l)

            d = node.getElementsByTagName("date")[0]
            year = int(getChildText(d, "year"))
            month = getChildText(d, "month")
            month = ["January","February","March","April","May","June","July","August","September","October","November","December"].index(month)+1
            rfc_published_date = ("%d-%02d-01" % (year, month))

            current_status = getChildText(node, "current-status").title()

            updates = getDocList(node, "updates") 
            updated_by = getDocList(node, "updated-by")
            obsoletes = getDocList(node, "obsoletes") 
            obsoleted_by = getDocList(node, "obsoleted-by")

            draft = getChildText(node, "draft")
            if draft and re.search("-\d\d$", draft):
                draft = draft[0:-3]

            if len(node.getElementsByTagName("errata-url")) > 0:
                has_errata = 1
            else:
                has_errata = 0

            data.append([rfc_number,title,authors,rfc_published_date,current_status,updates,updated_by,obsoletes,obsoleted_by,None,draft,has_errata])

    for d in data:
        k = "RFC%04d" % d[0]
        if k in also_list:
            d[9] = ",".join(also_list[k])
    return data

def insert_to_database(data):
    log("connecting to database...")
    cursor = db.connection.cursor()
    log("removing old data...")
    cursor.execute("DELETE FROM "+TABLE)
    log("inserting new data...")
    cursor.executemany("INSERT INTO "+TABLE+" (rfc_number, title, authors, rfc_published_date, current_status,updates,updated_by,obsoletes,obsoleted_by,also,draft,has_errata) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)", data)
    cursor.close()
    db.connection._commit()
    db.connection.close()

if __name__ == '__main__':
    try:
        log("output from mirror_rfc_index.py:\n")
        log("time: "+str(datetime.now()))
        log("host: "+socket.gethostname())
        log("url: "+INDEX_URL)

        log("downloading...")
        response = urllib2.urlopen(INDEX_URL)
        log("parsing...")
        data = parse(response)

        log("got " + str(len(data)) + " entries")
        if len(data) < 5000:
            raise Exception('not enough data')

        insert_to_database(data)

        log("all done!")
        log_data = ""

    finally:
        if len(log_data) > 0:
            print log_data
