#!/usr/bin/python

import sys, os, re, datetime

basedir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path = [ basedir ] + sys.path

from ietf import settings
settings.USE_DB_REDESIGN_PROXY_CLASSES = False

from django.core import management
management.setup_environ(settings)

from redesign.person.models import *
from redesign.group.models import *
from redesign.name.models import *
from redesign.name.utils import name
from redesign.importing.utils import get_or_create_email

from ietf.idtracker.models import IESGLogin, AreaDirector, PersonOrOrgInfo, WGChair, WGEditor, WGSecretary, WGTechAdvisor, ChairsHistory, Role as OldRole, Acronym, IRTFChair


# assumptions:
#  - persons have been imported
#  - groups have been imported

# imports IESGLogin, AreaDirector, WGEditor, WGChair, IRTFChair,
# WGSecretary, WGTechAdvisor, NomCom chairs from ChairsHistory,

# FIXME: should probably import Role, LegacyWgPassword, LegacyLiaisonUser

area_director_role = name(RoleName, "ad", "Area Director")
inactive_area_director_role = name(RoleName, "ex-ad", "Ex-Area Director", desc="Inactive Area Director")
chair_role = name(RoleName, "chair", "Chair")
editor_role = name(RoleName, "editor", "Editor")
secretary_role = name(RoleName, "secr", "Secretary")
techadvisor_role = name(RoleName, "techadv", "Tech Advisor")


# WGEditor
for o in WGEditor.objects.all():
    acronym = Acronym.objects.get(acronym_id=o.group_acronym_id).acronym
    print "importing WGEditor", acronym, o.person

    email = get_or_create_email(o, create_fake=True)
    group = Group.objects.get(acronym=acronym)

    Role.objects.get_or_create(name=editor_role, group=group, email=email)

# WGSecretary
for o in WGSecretary.objects.all():
    acronym = Acronym.objects.get(acronym_id=o.group_acronym_id).acronym
    print "importing WGSecretary", acronym, o.person

    email = get_or_create_email(o, create_fake=True)
    group = Group.objects.get(acronym=acronym)

    Role.objects.get_or_create(name=secretary_role, group=group, email=email)

# WGTechAdvisor
for o in WGTechAdvisor.objects.all():
    acronym = Acronym.objects.get(acronym_id=o.group_acronym_id).acronym
    print "importing WGTechAdvisor", acronym, o.person

    email = get_or_create_email(o, create_fake=True)
    group = Group.objects.get(acronym=acronym)

    Role.objects.get_or_create(name=techadvisor_role, group=group, email=email)

# WGChair
for o in WGChair.objects.all():
    # there's some garbage in this table, so wear double safety belts
    try:
        acronym = Acronym.objects.get(acronym_id=o.group_acronym_id).acronym
    except Acronym.DoesNotExist:
        print "SKIPPING WGChair with unknown acronym id", o.group_acronym_id
        continue

    try:
        person = o.person
    except PersonOrOrgInfo.DoesNotExist:
        print "SKIPPING WGChair", acronym, "with invalid person id", o.person_id
        continue
    
    if acronym in ("apples", "apptsv", "usac", "null", "dirdir"):
        print "SKIPPING WGChair", acronym, o.person
        continue

    print "importing WGChair", acronym, o.person

    email = get_or_create_email(o, create_fake=True)
    group = Group.objects.get(acronym=acronym)

    Role.objects.get_or_create(name=chair_role, group=group, email=email)

# IRTFChair
for o in IRTFChair.objects.all():
    acronym = o.irtf.acronym.lower()
    print "importing IRTFChair", acronym, o.person

    email = get_or_create_email(o, create_fake=True)
    group = Group.objects.get(acronym=acronym)

    Role.objects.get_or_create(name=chair_role, group=group, email=email)

# NomCom chairs
nomcom_groups = list(Group.objects.filter(acronym__startswith="nomcom").exclude(acronym="nomcom"))
for o in ChairsHistory.objects.filter(chair_type=OldRole.NOMCOM_CHAIR):
    print "importing NOMCOM chair", o
    for g in nomcom_groups:
        if ("%s/%s" % (o.start_year, o.end_year)) in g.name:
            break

    email = get_or_create_email(o, create_fake=False)
    
    Role.objects.get_or_create(name=chair_role, group=g, email=email)

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

    email = get_or_create_email(o, create_fake=False)
    if not email:
        continue

    user, _ = User.objects.get_or_create(username=o.login_name)
    email.person.user = user
    email.person.save()

    # current ADs are imported below
    if o.user_level == IESGLogin.SECRETARIAT_LEVEL:
        if not Role.objects.filter(name=secretary_role, email=email):
            Role.objects.create(name=secretary_role, group=Group.objects.get(acronym="secretariat"), email=email)
    elif o.user_level == IESGLogin.INACTIVE_AD_LEVEL:
        if not Role.objects.filter(name=inactive_area_director_role, email=email):
            # connect them directly to the IESG as we don't really know where they belong
            Role.objects.create(name=inactive_area_director_role, group=Group.objects.get(acronym="iesg"), email=email)
    
# AreaDirector
for o in AreaDirector.objects.all():
    if not o.area:
        print "NO AREA", o.person, o.area_id
        continue
    
    print "importing AreaDirector", o.area, o.person
    email = get_or_create_email(o, create_fake=False)
    
    area = Group.objects.get(acronym=o.area.area_acronym.acronym)

    if area.state_id == "active":
        role_type = area_director_role
    else:
         # can't be active area director in an inactive area
        role_type = inactive_area_director_role
    
    r = Role.objects.filter(name__in=(area_director_role, inactive_area_director_role),
                            email=email)
    if r and r[0].group == "iesg":
        r[0].group = area
        r[0].name = role_type
        r[0].save()
    else:
        Role.objects.get_or_create(name=role_type, group=area, email=email)


