#!/usr/bin/python

import sys, os, re, datetime

basedir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path = [ basedir ] + sys.path

from ietf import settings
settings.USE_DB_REDESIGN_PROXY_CLASSES = False

from django.core import management
management.setup_environ(settings)

from ietf.idtracker.models import IESGLogin, AreaDirector, IETFWG, PersonOrOrgInfo, IDAuthor
from ietf.ietfauth.models import LegacyWgPassword, LegacyLiaisonUser
from ietf.liaisons.models import LiaisonDetail, LiaisonManagers, SDOAuthorizedIndividual
from redesign.person.models import *
from redesign.importing.utils import *

# creates system person and email

# imports AreaDirector persons that are connected to an IETFWG,
# persons from IDAuthor, announcement originators from Announcements,
# requesters from WgMeetingSession, LiaisonDetail persons,
# LiaisonManagers/SDOAuthorizedIndividual persons,
# WgProceedingsActivities persons

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
    address="(System)",
    defaults=dict(active=True, person=system_person)
    )

# LegacyWgPassword
for o in LegacyWgPassword.objects.all():
    print "importing LegacyWgPassword", o.pk, o.person.first_name.encode('utf-8'), o.person.last_name.encode('utf-8')
    
    email = get_or_create_email(o, create_fake=False)
    if not email:
        continue

    username = o.login_name[:30]
    persons = Person.objects.filter(user__username=username)
    if persons:
        if persons[0] != email.person:
            print "SKIPPING", o.login_name, "who is connected to another person "
        continue

    user, _ = User.objects.get_or_create(username=username)
    email.person.user = user
    email.person.save()

# LegacyLiaisonUser
for o in LegacyLiaisonUser.objects.all():
    print "importing LegacyLiaisonUser", o.pk, o.person.first_name.encode('utf-8'), o.person.last_name.encode('utf-8')
    
    email = get_or_create_email(o, create_fake=False)
    if not email:
        continue

    username = o.login_name[:30]
    persons = Person.objects.filter(user__username=username)
    if persons:
        if persons[0] != email.person:
            print "SKIPPING", o.login_name, "who is connected to another person "
        continue

    user, _ = User.objects.get_or_create(username=username)
    email.person.user = user
    email.person.save()

# IESGLogin
for o in IESGLogin.objects.all():
    print "importing IESGLogin", o.pk, o.first_name.encode('utf-8'), o.last_name.encode('utf-8')
    
    if not o.person:
        persons = PersonOrOrgInfo.objects.filter(first_name=o.first_name, last_name=o.last_name)
        if persons:
            o.person = persons[0]
        else:
            print "NO PERSON", o.person_id
            continue

    email = get_or_create_email(o, create_fake=False)
    if not email:
        continue

    user, _ = User.objects.get_or_create(username=o.login_name)
    email.person.user = user
    email.person.save()

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
    
# LiaisonManagers persons
for o in LiaisonManagers.objects.order_by("pk"):
    print "importing LiaisonManagers person", o.pk, o.person.first_name.encode('utf-8'), o.person.last_name.encode('utf-8')

    email = get_or_create_email(o, create_fake=False)
    possibly_import_other_priority_email(email, o.person.email(priority=o.email_priority)[1])
    
# SDOAuthorizedIndividual persons
for o in PersonOrOrgInfo.objects.filter(sdoauthorizedindividual__pk__gte=1).order_by("pk").distinct():
    print "importing SDOAuthorizedIndividual person", o.pk, o.first_name.encode('utf-8'), o.last_name.encode('utf-8')

    email = get_or_create_email(o, create_fake=False)
    
# Liaison persons (these are used as from contacts)
for o in LiaisonDetail.objects.exclude(person=None).order_by("pk"):
    print "importing LiaisonDetail person", o.pk, o.person.first_name.encode('utf-8'), o.person.last_name.encode('utf-8')

    email = get_or_create_email(o, create_fake=True)

    # we may also need to import email address used specifically for
    # the document
    if "@" in email.address:
        addr = o.from_email().address
        possibly_import_other_priority_email(email, addr)
    
# WgProceedingsActivities persons
for o in PersonOrOrgInfo.objects.filter(wgproceedingsactivities__id__gte=1).order_by("pk").distinct():
    print "importing WgProceedingsActivities person", o.pk, o.first_name.encode('utf-8'), o.last_name.encode('utf-8')

    email = get_or_create_email(o, create_fake=True)

# IDAuthor persons
for o in IDAuthor.objects.all().order_by('id').select_related('person').iterator():
    print "importing IDAuthor", o.id, o.person_id, o.person.first_name.encode('utf-8'), o.person.last_name.encode('utf-8')
    email = get_or_create_email(o, create_fake=True)

    # we may also need to import email address used specifically for
    # the document
    possibly_import_other_priority_email(email, o.email())
