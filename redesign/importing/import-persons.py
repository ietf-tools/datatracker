#!/usr/bin/python

import sys, os, re, datetime

basedir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path = [ basedir ] + sys.path

from ietf import settings
settings.USE_DB_REDESIGN_PROXY_CLASSES = False

from django.core import management
management.setup_environ(settings)

from ietf.idtracker.models import AreaDirector, IETFWG, PersonOrOrgInfo, IDAuthor
from redesign.person.models import *
from redesign.importing.utils import clean_email_address, get_or_create_email

# creates system person and email

# imports AreaDirector persons that are connected to an IETFWG,
# persons from IDAuthor, announcement originators from Announcements,
# requesters from WgMeetingSession

# should probably import
# PersonOrOrgInfo/PostalAddress/EmailAddress/PhoneNumber fully

# make sure special system user/email is created 
print "creating (System) person and email"
try:
    system_person = Person.objects.get(name="(System)")
except Person.DoesNotExist:
    system_person = Person.objects.create(
        id=0, # special value
        name="(System)",
        ascii="(System)",
        address="",
        )
    
    system_person = Person.objects.get(name="(System)")
    
if system_person.id != 0: # work around bug in Django
    Person.objects.filter(id=system_person.id).update(id=0)
    system_person = Person.objects.get(id=0)
    
system_alias = Alias.objects.get_or_create(
    person=system_person,
    name=system_person.name
    )

system_email = Email.objects.get_or_create(
    address="",
    defaults=dict(active=True, person=system_person)
    )

# AreaDirector from IETFWG persons
for o in AreaDirector.objects.filter(ietfwg__in=IETFWG.objects.all()).exclude(area=None).distinct().order_by("pk").iterator():
    print "importing AreaDirector (from IETFWG) persons", o.pk
    
    get_or_create_email(o, create_fake=False)

# IESGHistory persons
for o in PersonOrOrgInfo.objects.filter(iesghistory__id__gte=1).order_by("pk").distinct():
    print "importing IESGHistory person", o.pk, o.first_name.encode('utf-8'), o.last_name.encode('utf-8')

    email = get_or_create_email(o, create_fake=False)
    
# WgMeetingSession persons
for o in PersonOrOrgInfo.objects.filter(wgmeetingsession__pk__gte=1).distinct().order_by("pk").iterator():
    print "importing WgMeetingSession persons", o.pk, o.first_name.encode('utf-8'), o.last_name.encode('utf-8')
    
    get_or_create_email(o, create_fake=False)
    
# Announcement persons
for o in PersonOrOrgInfo.objects.filter(announcement__announcement_id__gte=1).order_by("pk").distinct():
    print "importing Announcement originator", o.pk, o.first_name.encode('utf-8'), o.last_name.encode('utf-8')

    email = get_or_create_email(o, create_fake=False)
    
# Liaison submitter persons
for o in PersonOrOrgInfo.objects.filter(liaisondetail__pk__gte=1).order_by("pk").distinct():
    print "importing LiaisonDetail originator", o.pk, o.first_name.encode('utf-8'), o.last_name.encode('utf-8')

    email = get_or_create_email(o, create_fake=True)
    
# IDAuthor persons
for o in IDAuthor.objects.all().order_by('id').select_related('person').iterator():
    print "importing IDAuthor", o.id, o.person_id, o.person.first_name.encode('utf-8'), o.person.last_name.encode('utf-8')
    email = get_or_create_email(o, create_fake=True)

    # we may also need to import email address used specifically for
    # the document
    addr = clean_email_address(o.email() or "")
    if addr and addr.lower() != email.address.lower():
        try:
            e = Email.objects.get(address=addr)
            if e.person != email.person or e.active != False:
                e.person = email.person
                e.active = False
                e.save()
        except Email.DoesNotExist:
            Email.objects.create(address=addr, person=email.person, active=False)
    
