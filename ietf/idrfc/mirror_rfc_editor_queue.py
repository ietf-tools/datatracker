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

    events = pulldom.parse(response)
    drafts = []
    refs = []
    for (event, node) in events:
        if event == pulldom.START_ELEMENT and node.tagName == "entry":
            events.expandNode(node)
            node.normalize()
            draft_name = getChildText(node, "draft").strip()
            draft_name = re.sub("(-\d\d)?(.txt){1,2}$", "", draft_name)
            date_received = getChildText(node, "date-received")
            
            states = []
            for child in node.childNodes:
                if child.nodeType == Node.ELEMENT_NODE and child.localName == "state":
                    states.append(child.firstChild.data)

            has_refs = False
            for child in node.childNodes:
                if child.nodeType == Node.ELEMENT_NODE and child.localName == "normRef":
                    ref_name = getChildText(child, "ref-name")
                    ref_state = getChildText(child, "ref-state")
                    in_queue = ref_state.startswith("IN-QUEUE")
                    refs.append([draft_name, ref_name, in_queue, True])
                    has_refs = True
            if has_refs and not "MISSREF" in states:
                states.append("REF")

            if len(states) == 0:
                state = "?"
            else:
                state = " ".join(states)
            drafts.append([draft_name, date_received, state, stream])
        
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
            # Remove self-reference
            ref_set.remove(draft_name)
            # Remove direct references
            for (source, destination, in_queue, direct) in refs:
                if source == draft_name:
                    if destination in ref_set:
                        ref_set.remove(destination)
            # The rest are indirect references
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

def parse_all(response):
    log("parsing...")
    (drafts, refs) = parse(response)
    log("got "+ str(len(drafts)) + " drafts and "+str(len(refs))+" direct refs")

    indirect_refs = find_indirect_refs(drafts, refs)
    log("found " + str(len(indirect_refs)) + " indirect refs")
    refs.extend(indirect_refs)
    del(indirect_refs)

    if settings.USE_DB_REDESIGN_PROXY_CLASSES: # note: return before id lookup
        return (drafts, refs)

    # convert filenames to id_document_tags
    log("connecting to database...")
    cursor = db.connection.cursor()
    log("finding id_document_tags...")
    (drafts, refs) = find_document_ids(cursor, drafts, refs)
    cursor.close()
    return (drafts, refs)

def insert_into_database(drafts, refs):
    log("connecting to database...")
    cursor = db.connection.cursor()
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

import django.db.transaction

def get_rfc_tag_mapping():
    """Return dict with RFC Editor state name -> DocTagName"""
    from name.models import DocTagName
    from name.utils import name
    
    return {
        'IANA': name(DocTagName, 'iana-crd', 'IANA coordination', "RFC-Editor/IANA Registration Coordination"),
        'REF': name(DocTagName, 'ref', 'Holding for references', "Holding for normative reference"),
        'MISSREF': name(DocTagName, 'missref', 'Missing references', "Awaiting missing normative reference"),
    }

def get_rfc_state_mapping():
    """Return dict with RFC Editor state name -> RfcDocStateName"""
    from name.models import RfcDocStateName
    from name.utils import name
    
    return {
        'AUTH': name(RfcDocStateName, 'auth', 'AUTH', "Awaiting author action"),
        'AUTH48': name(RfcDocStateName, 'auth48', "AUTH48", "Awaiting final author approval"),
        'EDIT': name(RfcDocStateName, 'edit', 'EDIT', "Approved by the stream manager (e.g., IESG, IAB, IRSG, ISE), awaiting processing and publishing"),
        'IANA': name(RfcDocStateName, 'iana-crd', 'IANA', "RFC-Editor/IANA Registration Coordination"),
        'IESG': name(RfcDocStateName, 'iesg', 'IESG', "Holding for IESG action"),
        'ISR': name(RfcDocStateName, 'isr', 'ISR', "Independent Submission Review by the ISE "),
        'ISR-AUTH': name(RfcDocStateName, 'isr-auth', 'ISR-AUTH', "Independent Submission awaiting author update, or in discussion between author and ISE"),
        'REF': name(RfcDocStateName, 'ref', 'REF', "Holding for normative reference"),
        'RFC-EDITOR': name(RfcDocStateName, 'rfc-edit', 'RFC-EDITOR', "Awaiting final RFC Editor review before AUTH48"),
        'TO': name(RfcDocStateName, 'timeout', 'TO', "Time-out period during which the IESG reviews document for conflict/concurrence with other IETF working group work"),
        'MISSREF': name(RfcDocStateName, 'missref', 'MISSREF', "Awaiting missing normative reference"),
    }


@django.db.transaction.commit_on_success
def insert_into_databaseREDESIGN(drafts, refs):
    from doc.models import Document
    from name.models import DocTagName

    tags = get_rfc_tag_mapping()
    states = get_rfc_state_mapping()

    rfc_editor_tags = tags.values()
    
    log("removing old data...")
    for d in Document.objects.exclude(rfc_state=None).filter(tags__in=rfc_editor_tags):
        d.tags.remove(*rfc_editor_tags)

    Document.objects.exclude(rfc_state=None).update(rfc_state=None)

    log("inserting new data...")

    for name, date_received, state, stream_id in drafts:
        try:
            d = Document.objects.get(name=name)
        except Document.DoesNotExist:
            log("unknown document %s" % name)
            continue

        s = state.split(" ")
        if s:
            # first is state
            d.rfc_state = states[s[0]]
            d.save()

            # remainding are tags
            for x in s[1:]:
                d.tags.add(tags[x])

if settings.USE_DB_REDESIGN_PROXY_CLASSES:
    insert_into_database = insert_into_databaseREDESIGN


if __name__ == '__main__':
    try:
        log("output from mirror_rfc_editor_queue.py:\n")
        log("time: "+str(datetime.now()))
        log("host: "+socket.gethostname())
        log("url: "+QUEUE_URL)
        
        log("downloading...")
        socket.setdefaulttimeout(30)
        response = urllib2.urlopen(QUEUE_URL)

        (drafts, refs) = parse_all(response)
        if len(drafts) < 10 or len(refs) < 10:
            raise Exception('not enough data')
    
        insert_into_database(drafts, refs)

        log("all done!")
        if log_data.find("WARNING") < 0:
            log_data = ""
    finally:
        if len(log_data) > 0:
            print log_data
