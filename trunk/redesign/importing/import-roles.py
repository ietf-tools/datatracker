#!/usr/bin/python

import sys, os, re, datetime

basedir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path = [ basedir ] + sys.path

from ietf import settings
settings.USE_DB_REDESIGN_PROXY_CLASSES = False

from django.core import management
management.setup_environ(settings)

from ietf.person.models import *
from ietf.group.models import *
from ietf.name.models import *
from ietf.name.utils import name
from redesign.importing.utils import get_or_create_email

from ietf.idtracker.models import IESGLogin, AreaDirector, PersonOrOrgInfo, WGChair, WGEditor, WGSecretary, WGTechAdvisor, ChairsHistory, Role as OldRole, Acronym, IRTFChair
from ietf.liaisons.models import LiaisonManagers, SDOAuthorizedIndividual
from ietf.wgchairs.models import WGDelegate
from ietf.proceedings.models import IESGHistory
from ietf.utils.history import *

# assumptions:
#  - persons have been imported
#  - groups have been imported

# imports roles from IESGLogin, AreaDirector, WGEditor, WGChair,
# IRTFChair, WGSecretary, WGTechAdvisor, NomCom chairs from
# ChairsHistory, IESGHistory, Role, LiaisonManagers,
# SDOAuthorizedIndividual, WGDelegate

area_director_role = name(RoleName, "ad", "Area Director")
pre_area_director_role = name(RoleName, "pre-ad", "Incoming Area Director")
chair_role = name(RoleName, "chair", "Chair")
editor_role = name(RoleName, "editor", "Editor")
secretary_role = name(RoleName, "secr", "Secretary")
techadvisor_role = name(RoleName, "techadv", "Tech Advisor")
exec_director_role = name(RoleName, "execdir", "Executive Director")
adm_director_role = name(RoleName, "admdir", "Administrative Director")
liaison_manager_role = name(RoleName, "liaiman", "Liaison Manager")
authorized_role = name(RoleName, "auth", "Authorized Individual")
delegate_role = name(RoleName, "delegate", "Delegate")

# import IANA authorized individuals
for o in User.objects.using("legacy").filter(groups__name="IANA"):
    print "Importing IANA group member", o

    if o.username == "amanda.barber@icann.org":
        o.username = "amanda.baber@icann.org"

    person = PersonOrOrgInfo.objects.filter(iesglogin__login_name=o.username)[0]

    group = Group.objects.get(acronym="iana")
    email = get_or_create_email(person, create_fake=False)

    Role.objects.get_or_create(name=authorized_role, group=group, person=email.person, email=email)

# WGDelegate
for o in WGDelegate.objects.all().order_by("pk"):
    print "importing WGDelegate", o.pk, unicode(o.wg).encode("utf-8"), unicode(o.person).encode("utf-8")

    group = Group.objects.get(acronym=o.wg.group_acronym.acronym)
    email = get_or_create_email(o, create_fake=False)

    Role.objects.get_or_create(name=delegate_role, group=group, person=email.person, email=email)
    
# SDOAuthorizedIndividual
for o in SDOAuthorizedIndividual.objects.all().order_by("pk"):
    print "importing SDOAuthorizedIndividual", o.pk, unicode(o.sdo).encode("utf-8"), unicode(o.person).encode("utf-8")

    group = Group.objects.get(name=o.sdo.sdo_name, type="sdo")
    email = get_or_create_email(o, create_fake=False)

    Role.objects.get_or_create(name=authorized_role, group=group, person=email.person, email=email)

# LiaisonManagers
for o in LiaisonManagers.objects.all().order_by("pk"):
    print "importing LiaisonManagers", o.pk, unicode(o.sdo).encode("utf-8"), unicode(o.person).encode("utf-8")

    group = Group.objects.get(name=o.sdo.sdo_name, type="sdo")
    email = Email.objects.get(address__iexact=o.person.email(priority=o.email_priority)[1])

    Role.objects.get_or_create(name=liaison_manager_role, group=group, person=email.person, email=email)

# Role
for o in OldRole.objects.all().order_by('pk'):
    acronym = o.role_name.lower()
    role = chair_role

    if o.id == OldRole.NOMCOM_CHAIR:
        continue # handled elsewhere

    print "importing Role", o.id, o.role_name, unicode(o.person).encode("utf-8")
    
    email = get_or_create_email(o, create_fake=False)
    official_email = email
    
    if o.role_name.endswith("Executive Director"):
        acronym = acronym[:-(len("Executive Director") + 1)]
        role = exec_director_role

    if o.id == OldRole.IAD_CHAIR:
        acronym = "ietf"
        role = adm_director_role
        official_email, _ = Email.objects.get_or_create(address="iad@ietf.org")

    if o.id == OldRole.IETF_CHAIR:
        official_email, _ = Email.objects.get_or_create(address="chair@ietf.org")

    if o.id == OldRole.IAB_CHAIR:
        official_email, _ = Email.objects.get_or_create(address="iab-chair@ietf.org")

    if o.id == OldRole.RSOC_CHAIR:
        official_email, _ = Email.objects.get_or_create(address="rsoc-chair@iab.org")

    if o.id == 9:
        official_email, _ = Email.objects.get_or_create(address="rfc-ise@rfc-editor.org")
        
    group = Group.objects.get(acronym=acronym)

    Role.objects.get_or_create(name=role, group=group, person=email.person, email=official_email)

# WGEditor
for o in WGEditor.objects.all():
    acronym = Acronym.objects.get(acronym_id=o.group_acronym_id).acronym
    print "importing WGEditor", acronym, o.person

    email = get_or_create_email(o, create_fake=True)
    group = Group.objects.get(acronym=acronym)

    Role.objects.get_or_create(name=editor_role, group=group, person=email.person, email=email)

# WGSecretary
for o in WGSecretary.objects.all():
    acronym = Acronym.objects.get(acronym_id=o.group_acronym_id).acronym
    print "importing WGSecretary", acronym, o.person

    email = get_or_create_email(o, create_fake=True)
    group = Group.objects.get(acronym=acronym)

    Role.objects.get_or_create(name=secretary_role, group=group, person=email.person, email=email)

# WGTechAdvisor
for o in WGTechAdvisor.objects.all():
    acronym = Acronym.objects.get(acronym_id=o.group_acronym_id).acronym
    print "importing WGTechAdvisor", acronym, o.person

    email = get_or_create_email(o, create_fake=True)
    group = Group.objects.get(acronym=acronym)

    Role.objects.get_or_create(name=techadvisor_role, group=group, person=email.person, email=email)

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

    if group.acronym == "none":
        print "SKIPPING WGChair", o.person, "with bogus group", group.acronym
        continue

    print "importing WGChair", acronym, o.person

    email = get_or_create_email(o, create_fake=True)

    Role.objects.get_or_create(name=chair_role, group=group, person=email.person, email=email)

# IRTFChair
for o in IRTFChair.objects.all():
    acronym = o.irtf.acronym.lower()
    if acronym == "irtf":
         # we already got the IRTF chair from Role, and the data in here is buggy
        continue

    print "importing IRTFChair", acronym, o.person

    email = get_or_create_email(o, create_fake=True)
    group = Group.objects.get(acronym=acronym)

    Role.objects.get_or_create(name=chair_role, group=group, person=email.person, email=email)

# NomCom chairs
official_email, _ = Email.objects.get_or_create(address="nomcom-chair@ietf.org")
nomcom_groups = list(Group.objects.filter(acronym__startswith="nomcom").exclude(acronym="nomcom"))
for o in ChairsHistory.objects.filter(chair_type=OldRole.NOMCOM_CHAIR):
    print "importing NOMCOM chair", o
    for g in nomcom_groups:
        if ("%s/%s" % (o.start_year, o.end_year)) in g.name:
            break

    email = get_or_create_email(o, create_fake=False)

    Role.objects.get_or_create(name=chair_role, group=g, person=email.person, email=official_email)

# IESGLogin
for o in IESGLogin.objects.all():
    print "importing IESGLogin", o.pk, o.first_name.encode("utf-8"), o.last_name.encode("utf-8")

    if not o.person:
        persons = PersonOrOrgInfo.objects.filter(first_name=o.first_name, last_name=o.last_name)
        if persons:
            o.person = persons[0]
        else:
            print "NO PERSON", o.person_id
            continue
    
    email = get_or_create_email(o, create_fake=False)
    # current ADs are imported below
    if email and o.user_level == IESGLogin.SECRETARIAT_LEVEL:
        if not Role.objects.filter(name=secretary_role, person=email.person):
            Role.objects.create(name=secretary_role, group=Group.objects.get(acronym="secretariat"), person=email.person, email=email)
        u = email.person.user
        if u:
            u.is_staff = True
            u.is_superuser = True
            u.save()

# AreaDirector
for o in AreaDirector.objects.all():
    if not o.area:
        print "NO AREA", o.person, o.area_id
        continue
    
    print "importing AreaDirector", o.area, o.person
    email = get_or_create_email(o, create_fake=False)
    
    area = Group.objects.get(acronym=o.area.area_acronym.acronym)

    role_type = area_director_role
    
    try:
        if IESGLogin.objects.get(person=o.person).user_level == 4:
            role_type = pre_area_director_role
    except IESGLogin.DoesNotExist:
        pass
    
    r = Role.objects.filter(name=role_type,
                            person=email.person)
    if r and r[0].group == "iesg":
        r[0].group = area
        r[0].name = role_type
        r[0].save()
    else:
        Role.objects.get_or_create(name=role_type, group=area, person=email.person, email=email)

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
    if (history and history.rolehistory_set.filter(person=email.person) or
        not history and area.role_set.filter(person=email.person)):
        continue

    if history and history.time == meeting_time:
        # add to existing GroupHistory
        RoleHistory.objects.create(name=area_director_role, group=history, person=email.person, email=email)
    else:
        existing = history if history else area
        
        h = GroupHistory(group=area,
                         time=meeting_time,
                         name=existing.name,
                         acronym=existing.acronym,
                         state=existing.state,
                         type=existing.type,
                         parent=existing.parent,
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
            RoleHistory.objects.get_or_create(name=area_director_role, group=h, person=e.person, email=e)
        
