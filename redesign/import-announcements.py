#!/usr/bin/python

import sys, os, re, datetime

basedir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path = [ basedir ] + sys.path

from ietf import settings
settings.USE_DB_REDESIGN_PROXY_CLASSES = False

from django.core import management
management.setup_environ(settings)

from redesign.person.models import *
from redesign.group.models import *
from redesign.announcements.models import *
from ietf.announcements.models import Announcement, PersonOrOrgInfo, AnnouncedTo, AnnouncedFrom
from importing.utils import *

# assumptions:
#  - nomcom groups have been imported
#  - persons have been imported

# imports Announcements

# FIXME: should import ScheduledAnnouncements

system_email, _ = Email.objects.get_or_create(address="(System)")

# Announcement
for o in Announcement.objects.all().select_related('announced_to', 'announced_from').order_by('announcement_id').iterator():
    try:
        message = Message.objects.get(id=o.announcement_id)
    except Message.DoesNotExist:
        message = Message(id=o.announcement_id)

    message.time = datetime.datetime.combine(o.announced_date,
                                             datetime.time(*(int(x) for x in o.announced_time.split(":"))))

    try:
        x = o.announced_by
    except PersonOrOrgInfo.DoesNotExist:
        message.by = system_email
    else:
        if not o.announced_by.first_name and o.announced_by.last_name == 'None':
            message.by = system_email
        else:
            message.by = Email.objects.get(address=person_email(o.announced_by))

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
    message.text = o.text
    message.save()

    message.related_groups.clear()

    if o.nomcom:
        nomcom = Group.objects.filter(role__name="chair",
                                      role__email__person__id=o.nomcom_chair.person.pk,
                                      acronym__startswith="nomcom").exclude(acronym="nomcom").get()
        
        message.related_groups.add(nomcom)
        
