#!/usr/bin/python

import sys, os, re, datetime

basedir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path = [ basedir ] + sys.path

from ietf import settings
settings.USE_DB_REDESIGN_PROXY_CLASSES = False

from django.core import management
management.setup_environ(settings)

from redesign.person.models import *

# creates system person and email

# should probably also import the old person/email tables

try:
    system_person = Person.objects.get(name="(System)")
except Person.DoesNotExist:
    system_person = Person.objects.create(
        id=0, # special value
        name="(System)",
        ascii="(System)",
        address="",
        )
    
    if system_person.id != 0: # work around bug in Django
        Person.objects.filter(id=system_person.id).update(id=0)
        system_person = Person.objects.get(id=0)
    

system_alias = Alias.objects.get_or_create(
    person=system_person,
    name=system_person.name
    )

system_email = Email.objects.get_or_create(
    address="",
    person=system_person,
    active=True
    )
