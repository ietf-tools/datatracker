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
from ietf.proceedings.models import IESGHistory
from ietf.utils.history import *


# assumptions:
#  - persons have been imported
#  - groups have been imported

# imports IESGLogin, AreaDirector, WGEditor, WGChair, IRTFChair,
# WGSecretary, WGTechAdvisor, NomCom chairs from ChairsHistory, IESGHistory

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

    try:
        group = Group.objects.get(acronym=acronym)
    except Group.DoesNotExist:
        print "SKIPPING WGChair", o.person, "with non-existing group", acronym
        continue

    print "importing WGChair", acronym, o.person

    email = get_or_create_email(o, create_fake=True)

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

# IESGHistory
emails_for_time = {}
for o in IESGHistory.objects.all().order_by('meeting__start_date', 'pk'):
    print "importing IESGHistory", o.pk, o.area, o.person, o.meeting
    email = get_or_create_email(o, create_fake=False)
    if not email:
        "SKIPPING IESGHistory with unknown email"
        continue

    # our job here is to make sure we either have the same AD today or
    # got proper GroupHistory and RoleHistory objects in the database;
    # there's only incomplete information available in the database so
    # the reconstructed history will necessarily not be entirely
    # accurate, just good enough to conclude who was AD
    area = Group.objects.get(acronym=o.area.area_acronym.acronym, type="area")
    meeting_time = datetime.datetime.combine(o.meeting.start_date, datetime.time(0, 0, 0))

    key = (area, meeting_time)
    if not key in emails_for_time:
        emails_for_time[key] = []
        
    emails_for_time[key].append(email)
    
    history = find_history_active_at(area, meeting_time)
    if (history and history.rolehistory_set.filter(email__person=email.person) or
        not history and area.role_set.filter(email__person=email.person)):
        continue

    if history and history.time == meeting_time:
        # add to existing GroupHistory
        RoleHistory.objects.create(name=area_director_role, group=history, email=email)
    else:
        existing = history if history else area
        
        h = GroupHistory(group=area,
                         charter=existing.charter,
                         time=meeting_time,
                         name=existing.name,
                         acronym=existing.acronym,
                         state=existing.state,
                         type=existing.type,
                         parent=existing.parent,
                         iesg_state=existing.iesg_state,
                         ad=existing.ad,
                         list_email=existing.list_email,
                         list_subscribe=existing.list_subscribe,
                         list_archive=existing.list_archive,
                         comments=existing.comments,
                         )
        h.save()

        # we need to add all emails for this area at this time
        # because the new GroupHistory resets the known roles
        for e in emails_for_time[key]:
            RoleHistory.objects.get_or_create(name=area_director_role, group=h, email=e)
        
