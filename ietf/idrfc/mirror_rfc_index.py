# Copyright (C) 2009-2010 Nokia Corporation and/or its subsidiary(-ies).
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
from datetime import datetime, date, timedelta
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
            stream = getChildText(node, "stream")
            wg = getChildText(node, "wg_acronym")
            if wg and ((wg == "NON WORKING GROUP") or len(wg) > 15):
                wg = None
           
            l = []
            for format in node.getElementsByTagName("format"):
                l.append(getChildText(format, "file-format"))
            file_formats = (",".join(l)).lower()

            draft = getChildText(node, "draft")
            if draft and re.search("-\d\d$", draft):
                draft = draft[0:-3]

            if len(node.getElementsByTagName("errata-url")) > 0:
                has_errata = 1
            else:
                has_errata = 0

            data.append([rfc_number,title,authors,rfc_published_date,current_status,updates,updated_by,obsoletes,obsoleted_by,None,draft,has_errata,stream,wg,file_formats])

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
    cursor.executemany("INSERT INTO "+TABLE+" (rfc_number, title, authors, rfc_published_date, current_status,updates,updated_by,obsoletes,obsoleted_by,also,draft,has_errata,stream,wg,file_formats) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)", data)
    cursor.close()
    db.connection._commit()
    db.connection.close()

def get_std_level_mapping():
    from name.models import StdLevelName
    from name.utils import name
    return {
        "Standard": name(StdLevelName, "std", "Standard"),
        "Draft Standard": name(StdLevelName, "ds", "Draft Standard"),
        "Proposed Standard": name(StdLevelName, "ps", "Proposed Standard"),
        "Informational": name(StdLevelName, "inf", "Informational"),
        "Experimental": name(StdLevelName, "exp", "Experimental"),
        "Best Current Practice": name(StdLevelName, "bcp", "Best Current Practice"),
        "Historic": name(StdLevelName, "hist", "Historic"),
        "Unknown": name(StdLevelName, "unkn", "Unknown"),
        }

def get_stream_mapping():
    from name.models import DocStreamName
    from name.utils import name

    return {
        "Legacy": name(DocStreamName, "legacy", "Legacy"),
        "IETF": name(DocStreamName, "ietf", "IETF"),
        "INDEPENDENT": name(DocStreamName, "ise", "ISE", desc="Independent submission editor stream"),
        "IAB": name(DocStreamName, "iab", "IAB"),
        "IRTF": name(DocStreamName, "irtf", "IRTF"),
    }


import django.db.transaction

@django.db.transaction.commit_on_success
def insert_to_databaseREDESIGN(data):
    from redesign.person.models import Person
    from redesign.doc.models import Document, DocAlias, DocEvent, RelatedDocument, State
    from redesign.group.models import Group
    from redesign.name.models import DocTagName, DocRelationshipName
    from redesign.name.utils import name
    
    system = Person.objects.get(name="(System)")
    std_level_mapping = get_std_level_mapping()
    stream_mapping = get_stream_mapping()
    tag_has_errata = name(DocTagName, 'errata', "Has errata")
    relationship_obsoletes = name(DocRelationshipName, "obs", "Obsoletes")
    relationship_updates = name(DocRelationshipName, "updates", "Updates")

    skip_older_than_date = (date.today() - timedelta(days=365)).strftime("%Y-%m-%d")

    log("updating data...")
    for d in data:
        rfc_number, title, authors, rfc_published_date, current_status, updates, updated_by, obsoletes, obsoleted_by, also, draft, has_errata, stream, wg, file_formats = d

        if rfc_published_date < skip_older_than_date:
            # speed up the process by skipping old entries
            continue

        # we assume two things can happen: we get a new RFC, or an
        # attribute has been updated at the RFC Editor (RFC Editor
        # attributes currently take precedence over our local
        # attributes)

        # make sure we got the document and alias
        created = False
        doc = None
        name = "rfc%s" % rfc_number
        a = DocAlias.objects.filter(name=name)
        if a:
            doc = a[0].document
        else:
            if draft:
                try:
                    doc = Document.objects.get(name=draft)
                except Document.DoesNotExist:
                    pass

            if not doc:
                created = True
                log("created document %s" % name)
                doc = Document.objects.create(name=name)

            # add alias
            DocAlias.objects.create(name=name, document=doc)
            if not created:
                created = True
                log("created alias %s to %s" % (name, doc.name))

                
        # check attributes
        changed = False
        if title != doc.title:
            doc.title = title
            changed = True

        if std_level_mapping[current_status] != doc.std_level:
            doc.std_level = std_level_mapping[current_status]
            changed = True

        if doc.get_state_slug() != "rfc":
            doc.set_state(State.objects.filter(type="draft", slug="rfc"))
            changed = True

        if doc.stream != stream_mapping[stream]:
            doc.stream = stream_mapping[stream]
            changed = True

        if not doc.group and wg:
            doc.group = Group.objects.get(acronym=wg)
            changed = True

        pubdate = datetime.strptime(rfc_published_date, "%Y-%m-%d")
        if not doc.latest_event(type="published_rfc", time=pubdate):
            e = DocEvent(doc=doc, type="published_rfc")
            e.time = pubdate
            e.by = system
            e.desc = "RFC published"
            e.save()
            changed = True

        def parse_relation_list(s):
            if not s:
                return []
            res = []
            for x in s.split(","):
                if x[:3] in ("NIC", "IEN", "STD", "RTR"):
                    # try translating this to RFCs that we can handle
                    # sensibly; otherwise we'll have to ignore them
                    l = DocAlias.objects.filter(name__startswith="rfc", document__docalias__name=x.lower())
                else:
                    l = DocAlias.objects.filter(name=x.lower())

                for a in l:
                    if a not in res:
                        res.append(a)
            return res

        for x in parse_relation_list(obsoletes):
            if not RelatedDocument.objects.filter(source=doc, target=x, relationship=relationship_obsoletes):
                RelatedDocument.objects.create(source=doc, target=x, relationship=relationship_obsoletes)
                changed = True
        
        for x in parse_relation_list(updates):
            if not RelatedDocument.objects.filter(source=doc, target=x, relationship=relationship_updates):
                RelatedDocument.objects.create(source=doc, target=x, relationship=relationship_updates)
                changed = True
        
        if also:
            for a in also.lower().split(","):
                if not DocAlias.objects.filter(name=a):
                    DocAlias.objects.create(name=a, document=doc)
                    changed = True

        if has_errata:
            if not doc.tags.filter(pk=tag_has_errata.pk):
                doc.tags.add(tag_has_errata)
                changed = True
        else:
            if doc.tags.filter(pk=tag_has_errata.pk):
                doc.tags.remove(tag_has_errata)
                changed = True

        if changed:
            if not created:
                log("%s changed" % name)
            doc.time = datetime.now()
            doc.save()
            

if settings.USE_DB_REDESIGN_PROXY_CLASSES:
    insert_to_database = insert_to_databaseREDESIGN
    
if __name__ == '__main__':
    try:
        log("output from mirror_rfc_index.py:\n")
        log("time: "+str(datetime.now()))
        log("host: "+socket.gethostname())
        log("url: "+INDEX_URL)

        log("downloading...")
        socket.setdefaulttimeout(30)
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
