#!/usr/bin/python

import sys, os, re, datetime

basedir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path = [ basedir ] + sys.path

from ietf import settings
settings.USE_DB_REDESIGN_PROXY_CLASSES = False
settings.IMPORTING_FROM_OLD_SCHEMA = True

from django.core import management
management.setup_environ(settings)

from ietf.person.models import *
from ietf.group.models import *
from ietf.name.utils import name
from ietf.message.models import Message, SendQueue
from redesign.importing.utils import old_person_to_person
from ietf.announcements.models import Announcement, PersonOrOrgInfo, AnnouncedTo, AnnouncedFrom, ScheduledAnnouncement
from ietf.idtracker.models import IESGLogin

# assumptions:
#  - nomcom groups have been imported
#  - persons have been imported (Announcement originators and IESGLogins)

# imports Announcement, ScheduledAnnouncement

system = Person.objects.get(name="(System)")

# Announcement
for o in Announcement.objects.all().select_related('announced_to', 'announced_from').order_by('announcement_id').iterator():
    print "importing Announcement", o.pk
    try:
        message = Message.objects.get(id=o.announcement_id)
    except Message.DoesNotExist:
        message = Message(id=o.announcement_id)

    message.time = datetime.datetime.combine(o.announced_date,
                                             datetime.time(*(int(x) for x in o.announced_time.split(":"))))

    try:
        x = o.announced_by
    except PersonOrOrgInfo.DoesNotExist:
        message.by = system
    else:
        if not o.announced_by.first_name and o.announced_by.last_name == 'None':
            message.by = system
        else:
            message.by = old_person_to_person(o.announced_by)

    message.subject = o.subject.strip()
    if o.announced_from_id == 99:
        message.frm = o.other_val or ""
    elif o.announced_from_id == 18 and o.nomcom_chair_id != 0:
        message.frm = u"%s <%s>" % o.nomcom_chair.person.email()
    else:
        if '<' in o.announced_from.announced_from:
            message.frm = o.announced_from.announced_from
        else:
            message.frm = u"%s <%s>" % (o.announced_from.announced_from, o.announced_from.email)
    if o.announced_to_id == 99:
        message.to = o.other_val or ""
    else:
        try:
            message.to = u"%s <%s>" % (o.announced_to.announced_to, o.announced_to.email)
        except AnnouncedTo.DoesNotExist:
            message.to = ""

    message.cc = o.cc or ""
    for l in (o.extra or "").strip().replace("^", "\n").replace("\r", "").split("\n"):
        l = l.strip()
        if l.lower().startswith("bcc:"):
            message.bcc = l[len("bcc:"):].strip()
        elif l.lower().startswith("reply-to:"):
            message.reply_to = l[len("reply-to:"):].strip()
    message.body = o.text
    message.save()

    message.related_groups.clear()

    if o.nomcom:
        nomcom = Group.objects.filter(role__name="chair",
                                      role__person=old_person_to_person(o.nomcom_chair.person),
                                      acronym__startswith="nomcom").exclude(acronym="nomcom").get()
        
        message.related_groups.add(nomcom)
        

# precompute scheduled_by's to speed up the loop a bit
scheduled_by_mapping = {}
for by in ScheduledAnnouncement.objects.all().values_list("scheduled_by", flat=True).distinct():
    logins = IESGLogin.objects.filter(login_name=by)
    if logins:
        l = logins[0]
        person = l.person
        if not person:
            person = PersonOrOrgInfo.objects.get(first_name=l.first_name, last_name=l.last_name)
        found = old_person_to_person(person)
    else:
        found = system

    print "mapping", by, "to", found
    scheduled_by_mapping[by] = found

# ScheduledAnnouncement
for o in ScheduledAnnouncement.objects.all().order_by('id').iterator():
    print "importing ScheduledAnnouncement", o.pk
    try:
        q = SendQueue.objects.get(id=o.id)
    except SendQueue.DoesNotExist:
        q = SendQueue(id=o.id)
        # make sure there's no id overlap with ordinary already-imported announcements
        q.message = Message(id=o.id + 4000)

    time = datetime.datetime.combine(o.scheduled_date,
                                     datetime.time(*(int(x) for x in o.scheduled_time.split(":"))))
    by = scheduled_by_mapping[o.scheduled_by]

    q.message.time = time
    q.message.by = by
    
    q.message.subject = (o.subject or "").strip()
    q.message.to = (o.to_val or "").strip()
    q.message.frm = (o.from_val or "").strip()
    q.message.cc = (o.cc_val or "").strip()
    q.message.bcc = (o.bcc_val or "").strip()
    q.message.reply_to = (o.replyto or "").strip()
    q.message.body = o.body or ""
    q.message.content_type = o.content_type or ""
    q.message.save()

    q.time = time
    q.by = by

    d = None
    if o.to_be_sent_date:
        try:
            t = datetime.time(*(int(x) for x in o.to_be_sent_time.split(":")))
        except ValueError:
            t = datetime.time(0, 0, 0)
        d = datetime.datetime.combine(o.to_be_sent_date, t)
    
    q.send_at = d

    d = None
    if o.actual_sent_date:
        try:
            t = datetime.time(*(int(x) for x in o.scheduled_time.split(":")))
        except ValueError:
            t = datetime.time(0, 0, 0)

        d = datetime.datetime.combine(o.actual_sent_date, t)

    q.sent_at = d

    n = (o.note or "").strip()
    if n.startswith("<br>"):
        n = n[len("<br>"):]
    q.note = n
    
    q.save()
