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
from redesign.name.models import *
from ietf.idtracker.models import IESGLogin, AreaDirector, PersonOrOrgInfo

# assumptions:
#  - groups have been imported

# PersonOrOrgInfo/PostalAddress/EmailAddress/PhoneNumber are not imported

# imports IESGLogin, AreaDirector

# should import IDAuthor, WGChair, WGEditor,
#  WGSecretary, WGTechAdvisor, Role, ChairsHistory, IRTFChair

# make sure names exist
def name(name_class, slug, name, desc=""):
    # create if it doesn't exist, set name
    obj, _ = name_class.objects.get_or_create(slug=slug)
    obj.name = name
    obj.desc = desc
    obj.save()
    return obj

area_director_role = name(RoleName, "ad", "Area Director")


# helpers for creating the objects
def get_or_create_email(o):
    hardcoded_emails = { 'Dinara Suleymanova': "dinaras@ietf.org" }
    
    email = o.person.email()[1] or hardcoded_emails.get("%s %s" % (o.person.first_name, o.person.last_name))
    if not email:
        print "NO EMAIL FOR %s %s %s %s" % (o.__class__, o.id, o.person.first_name, o.person.last_name)
        return None
    
    e, _ = Email.objects.get_or_create(address=email)
    if not e.person:
        n = u"%s %s" % (o.person.first_name, o.person.last_name)
        aliases = Alias.objects.filter(name=n)
        if aliases:
            p = aliases[0].person
        else:
            p = Person.objects.create(name=n, ascii=n)
            Alias.objects.create(name=n, person=p)
            # FIXME: fill in address?
        
        e.person = p
        e.save()

    return e
    

# IESGLogin
for o in IESGLogin.objects.all():
    print "importing IESGLogin", o.id, o.first_name, o.last_name
    
    if not o.person:
        persons = PersonOrOrgInfo.objects.filter(first_name=o.first_name, last_name=o.last_name)
        if persons:
            o.person = persons[0]
        else:
            print "NO PERSON", o.person_id
            continue

    email = get_or_create_email(o)

    # FIXME: import o.user_level
    # FIXME: import o.login_name, o.user_level
    
    
# AreaDirector
Role.objects.filter(name=area_director_role).delete()
for o in AreaDirector.objects.all():
    print "importing AreaDirector", o.area, o.person
    email = get_or_create_email(o)
    if not o.area:
        print "NO AREA", o.area_id
        continue
    
    area = Group.objects.get(acronym=o.area.area_acronym.acronym)

    Role.objects.get_or_create(name=area_director_role, group=area, email=email)
    
