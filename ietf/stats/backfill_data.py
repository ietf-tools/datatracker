#!/usr/bin/env python
# Copyright The IETF Trust 2017-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import io
import sys
import os
import os.path
import argparse
import time

from typing import Set, Optional    # pyflakes:ignore

basedir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path = [ basedir ] + sys.path
os.environ["DJANGO_SETTINGS_MODULE"] = "ietf.settings"

virtualenv_activation = os.path.join(basedir, "env", "bin", "activate_this.py")
if os.path.exists(virtualenv_activation):
    exec(compile(io.open(virtualenv_activation, "rb").read(), virtualenv_activation, 'exec'), dict(__file__=virtualenv_activation))

import django
django.setup()

from django.conf import settings

import debug                            # pyflakes:ignore

from ietf.doc.models import Document
from ietf.name.models import FormalLanguageName
from ietf.utils.draft import Draft

parser = argparse.ArgumentParser()
parser.add_argument("--document", help="specific document name")
parser.add_argument("--words", action="store_true", help="fill in word count")
parser.add_argument("--formlang", action="store_true", help="fill in formal languages")
parser.add_argument("--authors", action="store_true", help="fill in author info")
args = parser.parse_args()

formal_language_dict = { l.pk: l for l in FormalLanguageName.objects.all() }

docs_qs = Document.objects.filter(type="draft")

if args.document:
    docs_qs = docs_qs.filter(docalias__name=args.document)

ts = time.strftime("%Y-%m-%d_%H:%M%z")
logfile = io.open('backfill-authorstats-%s.log'%ts, 'w')
print("Writing log to %s" % os.path.abspath(logfile.name))

def say(msg):
    msg = msg.encode('utf8')
    sys.stderr.write(msg)
    sys.stderr.write('\n')
    logfile.write(msg)
    logfile.write('\n')

def unicode(text):
    if text is None:
        return text
    # order matters here:
    for encoding in ['ascii', 'utf8', 'latin1', ]:
        try:
            utext = text.decode(encoding) 
#             if encoding == 'latin1':
#                 say("Warning: falling back to latin1 decoding for %s ..." % utext[:216]])
            return utext
        except UnicodeDecodeError:
            pass

start = time.time()
say("Running query for documents to process ...")
for doc in docs_qs.prefetch_related("docalias", "formal_languages", "documentauthor_set", "documentauthor_set__person", "documentauthor_set__person__alias_set"):
    canonical_name = doc.name
    for n in doc.docalias.all():
        if n.name.startswith("rfc"):
            canonical_name = n.name

    if canonical_name.startswith("rfc"):
        path = os.path.join(settings.RFC_PATH, canonical_name + ".txt")
    else:
        path = os.path.join(settings.INTERNET_ALL_DRAFTS_ARCHIVE_DIR, canonical_name + "-" + doc.rev + ".txt")

    if not os.path.exists(path):
        say("Skipping %s, no txt file found at %s" % (doc.name, path))
        continue

    with io.open(path, 'rb') as f:
        say("\nProcessing %s" % doc.name)
        sys.stdout.flush()
        d = Draft(unicode(f.read()), path)

        updated = False

        updates = {}

        if args.words:
            words = d.get_wordcount()
            if words != doc.words:
                updates["words"] = words

        if args.formlang:
            langs = d.get_formal_languages()

            new_formal_languages = set(formal_language_dict[l] for l in langs)
            old_formal_languages = set(doc.formal_languages.all())

            if new_formal_languages != old_formal_languages:
                for l in new_formal_languages - old_formal_languages:
                    doc.formal_languages.add(l)
                    updated = True
                for l in old_formal_languages - new_formal_languages:
                    doc.formal_languages.remove(l)
                    updated = True

        if args.authors:
            old_authors = doc.documentauthor_set.all()
            old_authors_by_name = {}
            old_authors_by_email = {}
            for author in old_authors:
                for alias in author.person.alias_set.all():
                    old_authors_by_name[alias.name] = author
                old_authors_by_name[author.person.plain_name()] = author

                if author.email_id:
                    old_authors_by_email[author.email_id] = author

            # the draft parser sometimes has a problem when
            # affiliation isn't in the second line and it then thinks
            # it's an extra author - skip those extra authors
            seen = set()                # type: Set[Optional[str]]
            for full, _, _, _, _, email, country, company in d.get_author_list():
                assert full is None or    isinstance(full,    str)
                assert email is None or   isinstance(email,   str)
                assert country is None or isinstance(country, str)
                assert                    isinstance(company, str)
                #full, email, country, company = [ unicode(s) for s in [full, email, country, company, ] ]
                if email in seen:
                    continue
                seen.add(email)

                old_author = None
                if email:
                    old_author = old_authors_by_email.get(email)
                if not old_author:
                    old_author = old_authors_by_name.get(full)

                if not old_author:
                    say("UNKNOWN AUTHOR: %s, %s, %s, %s, %s" % (doc.name, full, email, country, company))
                    continue

                if old_author.affiliation != company:
                    say("new affiliation: %s [ %s <%s> ] %s -> %s" % (canonical_name, full, email, old_author.affiliation, company))
                    old_author.affiliation = company
                    old_author.save(update_fields=["affiliation"])
                    updated = True

                if country is None:
                    country = ""

                if old_author.country != country:
                    say("new country: %s [ %s <%s> ] %s -> %s" % (canonical_name , full, email, old_author.country, country))
                    old_author.country = country
                    old_author.save(update_fields=["country"])
                    updated = True
                    

        if updates:
            Document.objects.filter(pk=doc.pk).update(**updates)
            updated = True

        if updated:
            say("updated: %s" % canonical_name)

stop = time.time()
dur = stop-start
sec = dur%60
min = dur//60
say("Processing time %d:%02d" % (min, sec))

print("\n\nWrote log to %s" % os.path.abspath(logfile.name))
logfile.close()

