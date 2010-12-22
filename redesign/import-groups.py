#!/usr/bin/python

import sys, os

basedir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path = [ basedir ] + sys.path

from ietf import settings
settings.USE_DB_REDESIGN_PROXY_CLASSES = False

from django.core import management
management.setup_environ(settings)


from redesign.group.models import *
from redesign.name.models import *
from ietf.idtracker.models import AreaGroup, IETFWG, Area, AreaGroup, Acronym, AreaWGURL, IRTF

# imports IETFWG, Area, AreaGroup, Acronym

# FIXME: should also import IRTF

# make sure we got the names
def name(name_class, slug, name, desc=""):
    # create if it doesn't exist, set name and desc
    obj, _ = name_class.objects.get_or_create(slug=slug)
    obj.name = name
    obj.desc = desc
    obj.save()
    return obj

state_names = dict(
    bof=name(GroupStateName, slug="bof", name="BOF"),
    proposed=name(GroupStateName, slug="proposed", name="Proposed"),
    active=name(GroupStateName, slug="active", name="Active"),
    dormant=name(GroupStateName, slug="dormant", name="Dormant"),
    conclude=name(GroupStateName, slug="conclude", name="Concluded"),
    unknown=name(GroupStateName, slug="unknown", name="Unknown"),
    )

type_names = dict(
    ietf=name(GroupTypeName, slug="ietf", name="IETF"),
    area=name(GroupTypeName, slug="area", name="Area"),
    wg=name(GroupTypeName, slug="wg", name="WG"),
    rg=name(GroupTypeName, slug="rg", name="RG"),
    team=name(GroupTypeName, slug="team", name="Team"),
    individ=name(GroupTypeName, slug="individ", name="Individual"),
    )

# make sure we got the IESG so we can use it as parent for areas
iesg_group, _ = Group.objects.get_or_create(acronym="iesg")
iesg_group.name = "IESG"
iesg_group.state = state_names["active"]
iesg_group.type = type_names["ietf"]
iesg_group.save()


# Area
for o in Area.objects.all():
    group, _ = Group.objects.get_or_create(acronym=o.area_acronym.acronym)
    group.name = o.area_acronym.name
    if o.status.status == "Active":
        s = state_names["active"]
    elif o.status.status == "Concluded":
        s = state_names["conclude"]
    elif o.status.status == "Unknown":
        s = state_names["unknown"]
    group.state = s
    group.type = type_names["area"]
    group.parent = iesg_group

    # FIXME: missing fields from old: concluded_date, comments, last_modified_date, extra_email_addresses

    group.save()
    
# IETFWG, AreaGroup
for o in IETFWG.objects.all():
    try:
        group = Group.objects.get(acronym=o.group_acronym.acronym)
    except Group.DoesNotExist:
        group = Group(acronym=o.group_acronym.acronym)
        
    group.name = o.group_acronym.name
    # state
    if o.group_type.type == "BOF":
        s = state_names["bof"]
    elif o.group_type.type == "PWG":
        s = state_names["proposed"]
    elif o.status.status == "Active":
        s = state_names["active"]
    elif o.status.status == "Dormant":
        s = state_names["dormant"]
    elif o.status.status == "Concluded":
        s = state_names["conclude"]
    group.state = s
    # type
    if o.group_type.type == "TEAM":
        group.type = type_names["team"]
    elif o.group_type.type == "AG":
        if o.group_acronym.acronym == "none":
            # none means individual
            group.type = type_names["individ"]
        elif o.group_acronym.acronym == "iab":
            group.type = type_names["ietf"]
            group.parent = None
        elif o.group_acronym.acronym in ("tsvdir", "secdir", "saag"):
            group.type = type_names["team"]
        elif o.group_acronym.acronym == "iesg":
            pass # we already treated iesg
        elif o.group_acronym.acronym in ('apparea', 'opsarea', 'rtgarea', 'usvarea', 'genarea', 'tsvarea', 'raiarea'):
            pass # we already treated areas
        else:
            # the remaining groups are
            #  apptsv, apples, usac, null, dirdir
            # for now, we don't transfer them
            if group.id:
                group.delete()
            print "not transferring", o.group_acronym.acronym, o.group_acronym.name
            continue
    else: # PWG/BOF/WG
        # some BOFs aren't WG-forming but we currently classify all as WGs
        group.type = type_names["wg"]

    if o.area:
        group.parent = Group.objects.get(acronym=o.area.area.area_acronym.acronym)
    elif not group.parent:
        print "no area/parent for", group.acronym, group.name, group.type, group.state
        
    # FIXME: missing fields from old: proposed_date, start_date, dormant_date, concluded_date, meeting_scheduled, email_address, email_subscribe, email_keyword, email_archive, comments, last_modified_date, meeting_scheduled_old
    
    group.save()

# FIXME: IRTF
