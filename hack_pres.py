#!/usr/bin/python

import os, sys
import django

#basedir = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
#sys.path.insert(0, basedir)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ietf.settings")

django.setup()

from django.db.utils import IntegrityError
from ietf.meeting.views import session_draft_list
from ietf.meeting.models import Meeting
from ietf.doc.models import Document

m93 = Meeting.objects.get(number=93)

for acronym in set(m93.agenda.scheduledsession_set.values_list('session__group__acronym',flat=True)):
    for namerev in session_draft_list(93,acronym):
        name=namerev[:-3]
        rev = namerev[-2:]
        doc = Document.objects.filter(docalias__name=name).first()
        if not doc:
          print "Can't find anything named",name
        else:
            for session in m93.session_set.filter(group__acronym=acronym):
                try:
                    session.sessionpresentation_set.get_or_create(document=doc,rev=rev)
                except IntegrityError:
                    print "No luck on ",acronym,"->",name,rev
