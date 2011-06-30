#!/usr/bin/python

import sys, os, re, datetime

basedir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path = [ basedir ] + sys.path

from ietf import settings
settings.USE_DB_REDESIGN_PROXY_CLASSES = False

from django.core import management
management.setup_environ(settings)

from ietf.idtracker.models import AreaDirector, IETFWG
from redesign.person.models import *
from redesign.importing.utils import get_or_create_email

# creates system person and email

# imports AreaDirector persons that are connected to an IETFWG

# should probably also import the old person/email tables

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

for o in AreaDirector.objects.filter(ietfwg__in=IETFWG.objects.all()).exclude(area=None).distinct().order_by("pk").iterator():
    print "importing AreaDirector (from IETFWG) persons", o.pk
    
    get_or_create_email(o, create_fake=False)
