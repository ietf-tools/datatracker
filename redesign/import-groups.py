#!/usr/bin/python

import sys, os

basedir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path = [ basedir ] + sys.path

from ietf import settings
from django.core import management
management.setup_environ(settings)


from redesign.group.models import *
from redesign.name.models import *
from ietf.idtracker.models import AreaGroup, IETFWG, Area, AreaGroup, Acronym, AreaWGURL, IRTF

# Group replaces IETFWG, Area, AreaGroup, Acronym, IRTF

# make sure we got the names
GroupStateName.objects.get_or_create(slug="bof", name="BOF") # is this a state?
GroupStateName.objects.get_or_create(slug="proposed", name="Proposed")
GroupStateName.objects.get_or_create(slug="active", name="Active")
GroupStateName.objects.get_or_create(slug="dormant", name="Dormant")
GroupStateName.objects.get_or_create(slug="conclude", name="Concluded")
GroupStateName.objects.get_or_create(slug="unknown", name="Unknown")

GroupTypeName.objects.get_or_create(slug="ietf", name="IETF")
GroupTypeName.objects.get_or_create(slug="area", name="Area")
GroupTypeName.objects.get_or_create(slug="wg", name="WG")
GroupTypeName.objects.get_or_create(slug="rg", name="RG")
GroupTypeName.objects.get_or_create(slug="team", name="Team")

# FIXME: what about AG (area group?)?

    
# Area
for o in Area.objects.all():
    group, _ = Group.objects.get_or_create(acronym=o.area_acronym.acronym)
    group.name = o.area_acronym.name
    if o.status.status == "Active":
        s = GroupStateName.objects.get(slug="active")
    elif o.status.status == "Concluded":
        s = GroupStateName.objects.get(slug="conclude")
    elif o.status.status == "Unknown":
        s = GroupStateName.objects.get(slug="unknown")
    group.state = s
    group.type = GroupTypeName.objects.get(slug="area")

    # FIXME: missing fields from old: concluded_date, comments, last_modified_date, extra_email_addresses

    group.save()
    
# IETFWG, AreaGroup
for o in IETFWG.objects.all():
    group, _ = Group.objects.get_or_create(acronym=o.group_acronym.acronym)
    group.name = o.group_acronym.name
    # state
    if o.group_type.type == "BOF":
        s = GroupStateName.objects.get(slug="bof")
    elif o.group_type.type == "PWG": # FIXME: right?
        s = GroupStateName.objects.get(slug="proposed")
    elif o.status.status == "Active":
        s = GroupStateName.objects.get(slug="active")
    elif o.status.status == "Dormant":
        s = GroupStateName.objects.get(slug="dormant")
    elif o.status.status == "Concluded":
        s = GroupStateName.objects.get(slug="conclude")
    group.state = s
    # type
    if o.group_type.type == "team":
        group.type = GroupTypeName.objects.get(slug="team")
    else:
        group.type = GroupTypeName.objects.get(slug="wg")

    if o.area:
        print "no area for", group.acronym, group.name, group.type, group.state
        group.parent = Group.objects.get(acronym=o.area.area.area_acronym.acronym)
        
    # FIXME: missing fields from old: proposed_date, start_date, dormant_date, concluded_date, meeting_scheduled, email_address, email_subscribe, email_keyword, email_archive, comments, last_modified_date, meeting_scheduled_old
    
    group.save()

