#!/usr/bin/env python
# Copyright The IETF Trust 2017-2019, All Rights Reserved

import datetime
import os
import sys
from pathlib2 import Path
from contextlib import closing

os.environ["DJANGO_SETTINGS_MODULE"] = "ietf.settings"

import django
django.setup()

from django.conf import settings
from django.core.validators import validate_email, ValidationError
from ietf.utils.draft import Draft
from ietf.submit.utils import update_authors

import debug                            # pyflakes:ignore

from ietf.doc.models import Document, NewRevisionDocEvent, DocEvent, State
from ietf.person.models import Person

system = Person.objects.get(name="(System)")
expired = State.objects.get(type='draft',slug='expired')

names = set()
print 'collecting draft names ...'
versions = 0
for p in Path(settings.INTERNET_DRAFT_PATH).glob('draft*.txt'):
    n = str(p).split('/')[-1].split('-')
    if n[-1][:2].isdigit():
        name = '-'.join(n[:-1])
        if '--' in name  or '.txt' in name or '[' in name or '=' in name or '&' in name:
            continue
        if name.startswith('draft-draft-'):
            continue
        if name == 'draft-ietf-trade-iotp-v1_0-dsig':
            continue
        if len(n[-1]) != 6:
            continue
        if name.startswith('draft-mlee-'):
            continue
        names.add('-'.join(n[:-1]))

count=0
print 'iterating through names ...'
for name in sorted(names):
    if not Document.objects.filter(name=name).exists():
        paths = list(Path(settings.INTERNET_DRAFT_PATH).glob('%s-??.txt'%name))
        paths.sort()
        doc = None
        for p in paths:
            n = str(p).split('/')[-1].split('-')
            rev = n[-1][:2]
            with open(str(p)) as txt_file:
                raw = txt_file.read()
                try:
                    text = raw.decode('utf8')
                except UnicodeDecodeError:
                    text = raw.decode('latin1')
                try:
                    draft = Draft(text, txt_file.name, name_from_source=True)
                except Exception as e:
                    print name, rev, "Can't parse", p,":",e
                    continue
            if draft.errors and draft.errors.keys()!=['draftname',]:
                print "Errors - could not process", name, rev, datetime.datetime.fromtimestamp(p.stat().st_mtime), draft.errors, draft.get_title().encode('utf8')
            else:
                time = datetime.datetime.fromtimestamp(p.stat().st_mtime)
                if not doc:
                    doc = Document.objects.create(name=name,
                                                  time=time,
                                                  type_id='draft',
                                                  title=draft.get_title(),
                                                  abstract=draft.get_abstract(),
                                                  rev = rev,
                                                  pages=draft.get_pagecount(),
                                                  words=draft.get_wordcount(),
                                                  expires=time+datetime.timedelta(settings.INTERNET_DRAFT_DAYS_TO_EXPIRE),
                                                 )
                    DocAlias.objects.create(name=doc.name).docs.add(doc)
                    doc.states.add(expired)
                # update authors
                authors = []
                for author in draft.get_author_list():
                    full_name, first_name, middle_initial, last_name, name_suffix, email, country, company = author

                    author_name = full_name.replace("\n", "").replace("\r", "").replace("<", "").replace(">", "").strip()

                    if email:
                        try:
                            validate_email(email)
                        except ValidationError:
                            email = ""

                    def turn_into_unicode(s):
                        if s is None:
                            return u""

                        if isinstance(s, unicode):
                            return s
                        else:
                            try:
                                return s.decode("utf-8")
                            except UnicodeDecodeError:
                                try:
                                    return s.decode("latin-1")
                                except UnicodeDecodeError:
                                    return ""

                    author_name = turn_into_unicode(author_name)
                    email = turn_into_unicode(email)
                    company = turn_into_unicode(company)

                    authors.append({
                        "name": author_name,
                        "email": email,
                        "affiliation": company,
                        "country": country
                    })
                dummysubmission=type('', (), {})() #https://stackoverflow.com/questions/19476816/creating-an-empty-object-in-python
                dummysubmission.authors = authors
                update_authors(doc,dummysubmission)
                
                # add a docevent with words explaining where this came from
                events = []
                e = NewRevisionDocEvent.objects.create(
                        type="new_revision",
                        doc=doc,
                        rev=rev,
                        by=system,
                        desc="New version available: <b>%s-%s.txt</b>" % (doc.name, doc.rev),
                        time=time,
                )
                events.append(e)
                e = DocEvent.objects.create(
                        type="comment",
                        doc = doc,
                        rev = rev,
                        by = system,
                        desc = "Revision added from id-archive on %s by %s"%(datetime.date.today(),sys.argv[0]),
                        time=time,
                )
                events.append(e)
                doc.time = time
                doc.rev = rev
                doc.save_with_history(events)
                print "Added",name, rev
