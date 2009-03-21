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

QUEUE_URL = "http://www.rfc-editor.org/queue2.xml"
TABLE = "rfc_editor_queue_mirror"
REF_TABLE = "rfc_editor_queue_mirror_refs"

log_data = ""
def log(line):
    global log_data
    if len(sys.argv) > 1:
        print line
    else:
        log_data += line + "\n"

def parse(response):
    def getChildText(parentNode, tagName):
        for node in parentNode.childNodes:
            if node.nodeType == Node.ELEMENT_NODE and node.localName == tagName:
                return node.firstChild.data
        return None

    events = pulldom.parse(response)
    drafts = []
    refs = []
    for (event, node) in events:
        if event == pulldom.START_ELEMENT and node.tagName == "entry":
            events.expandNode(node)
            node.normalize()
            draft_name = getChildText(node, "draft")
            if re.search("-\d\d\.txt$", draft_name):
                draft_name = draft_name[0:-7]
            date_received = getChildText(node, "date-received")
            
            states = []
            for child in node.childNodes:
                if child.nodeType == Node.ELEMENT_NODE and child.localName == "state":
                    states.append(child.firstChild.data)
            if len(states) == 0:
                state = "?"
            else:
                state = " ".join(states)
            
            drafts.append([draft_name, date_received, state, stream])

            for child in node.childNodes:
                if child.nodeType == Node.ELEMENT_NODE and child.localName == "normRef":
                    ref_name = getChildText(child, "ref-name")
                    ref_state = getChildText(child, "ref-state")
                    in_queue = ref_state.startswith("IN-QUEUE")
                    refs.append([draft_name, ref_name, in_queue, True])
        
        elif event == pulldom.START_ELEMENT and node.tagName == "section":
            name = node.getAttribute('name')
            if name.startswith("IETF"):
                stream = 1
            elif name.startswith("IAB"):
                stream = 2
            elif name.startswith("IRTF"):
                stream = 3
            elif name.startswith("INDEPENDENT"):
                stream = 4
            else:
                stream = 0
                log("WARNING: unrecognized section "+name)
    return (drafts, refs)

# Find set of all normative references (whether direct or via some
# other normative reference)
def find_indirect_refs(drafts, refs):
    result = []
    draft_names = set()
    for draft in drafts:
        draft_names.add(draft[0])

    def recurse(draft_name, ref_set, level):
        for (source, destination, in_queue, direct) in refs:
            if source == draft_name:
                if destination not in ref_set:
                    ref_set.add(destination)
                    recurse(destination, ref_set, level+1)
        if level == 0:
            for ref in ref_set:
                if draft_name != ref:
                    result.append([draft_name, ref, ref in draft_names, False])

    for draft_name in draft_names:
        recurse(draft_name, set([draft_name]), 0)
    return result

# Convert filenames to id_document_tags
def find_document_ids(cursor, drafts, refs):
    draft_ids = {}
    drafts2 = []
    for draft in drafts:
        cursor.execute("SELECT id_document_tag FROM internet_drafts WHERE filename=%s", [draft[0]])
        row = cursor.fetchone()
        if not row:
            log("WARNING: cannot find id for "+draft[0])
        else:
            draft_ids[draft[0]] = row[0]
            drafts2.append([row[0]]+draft[1:])
    refs2 = []
    for ref in refs:
        if ref[0] in draft_ids:
            refs2.append([draft_ids[ref[0]]]+ref[1:])
    return (drafts2, refs2)

try:
    log("output from mirror_rfc_editor_queue.py:\n")
    log("time: "+str(datetime.now()))
    log("host: "+socket.gethostname())
    log("url: "+QUEUE_URL)

    log("downloading...")
    response = urllib2.urlopen(QUEUE_URL)
    log("parsing...")
    (drafts, refs) = parse(response)
    log("got "+ str(len(drafts)) + " drafts and "+str(len(refs))+" direct refs")

    indirect_refs = find_indirect_refs(drafts, refs)
    log("found " + str(len(indirect_refs)) + " indirect refs")
    refs.extend(indirect_refs)
    del(indirect_refs)

    if len(drafts) < 10 or len(refs) < 10:
        raise Exception('not enough data')

    # convert filenames to id_document_tags
    log("connecting to database...")
    cursor = db.connection.cursor()
    log("finding id_document_tags...")
    (drafts, refs) = find_document_ids(cursor, drafts, refs)

    if len(drafts) < 10 or len(refs) < 10:
        raise Exception('not enough data')

    log("removing old data...")
    cursor.execute("DELETE FROM "+TABLE)
    cursor.execute("DELETE FROM "+REF_TABLE)
    log("inserting new data...")
    cursor.executemany("INSERT INTO "+TABLE+" (id_document_tag, date_received, state, stream) VALUES (%s, %s, %s, %s)", drafts)
    cursor.execute("DELETE FROM "+REF_TABLE)
    cursor.executemany("INSERT INTO "+REF_TABLE+" (source, destination, in_queue, direct) VALUES (%s, %s, %s, %s)", refs)
    cursor.close()
    db.connection._commit()
    db.connection.close()

    log("all done!")
    if log_data.find("WARNING") < 0:
        log_data = ""
finally:
    if len(log_data) > 0:
        print log_data
