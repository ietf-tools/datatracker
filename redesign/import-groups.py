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
from ietf.idtracker.models import AreaGroup, IETFWG, Area, AreaGroup, Acronym, AreaWGURL, IRTF, ChairsHistory, Role

# imports IETFWG, Area, AreaGroup, Acronym, IRTF

# also creates nomcom groups

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

system_email, _ = Email.objects.get_or_create(address="(System)")


# NomCom
Group.objects.filter(acronym="nominatingcom").delete()

for o in ChairsHistory.objects.filter(chair_type=Role.NOMCOM_CHAIR).order_by("start_year"):
    group = Group()
    group.acronym = "nominatingcom"
    group.name = "IAB/IESG Nominating Committee %s/%s" % (o.start_year, o.end_year)
    if o.chair_type.person == o.person:
        s = state_names["active"]
    else:
        s = state_names["conclude"]
    group.state = s
    group.type = type_names["ietf"]
    group.parent = None
    group.save()

    # we need start/end year so fudge events
    e = GroupEvent(group=group, type="started")
    e.time = datetime.datetime(o.start_year, 5, 1, 12, 0, 0)
    e.by = system_email
    e.desc = e.get_type_display()
    e.save()

    e = GroupEvent(group=group, type="concluded")
    e.time = datetime.datetime(o.end_year, 5, 1, 12, 0, 0)
    e.by = system_email
    e.desc = e.get_type_display()
    e.save()
    
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
    group.comments = o.comments.strip() if o.comments else ""

    group.save()

    # import events
    group.groupevent_set.all().delete()
    
    if o.concluded_date:
        e = GroupEvent(group=group, type="concluded")
        e.time = datetime.datetime.combine(o.concluded_date, datetime.time(12, 0, 0))
        e.by = system_email
        e.desc = e.get_type_display()
        e.save()

    # FIXME: missing fields from old: last_modified_date, extra_email_addresses

    
# IRTF
for o in IRTF.objects.all():
    try:
        group = Group.objects.get(acronym=o.acronym.lower())
    except Group.DoesNotExist:
        group = Group(acronym=o.acronym.lower())
        
    group.name = o.name
    group.state = state_names["active"] # we assume all to be active
    group.type = type_names["rg"]

    # FIXME: who is the parent?
    # group.parent = Group.objects.get(acronym=)
    print "no parent for", group.acronym, group.name, group.type, group.state

    group.comments = o.charter_text or ""
    
    group.save()

    # FIXME: missing fields from old: meeting_scheduled


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

    group.list_email = o.email_address if o.email_address else ""
    group.comments = o.comments.strip() if o.comments else ""
    
    group.save()

    # import events
    group.groupevent_set.all().delete()

    def import_date_event(name):
        d = getattr(o, "%s_date" % name)
        if d:
            e = GroupEvent(group=group, type=name)
            e.time = datetime.datetime.combine(d, datetime.time(12, 0, 0))
            e.by = system_email
            e.desc = e.get_type_display()
            e.save()

    import_date_event("proposed")
    import_date_event("start")
    import_date_event("concluded")
    # dormant_date is empty on all so don't bother with that
            
    # FIXME: missing fields from old: meeting_scheduled, email_subscribe, email_keyword, email_archive, last_modified_date, meeting_scheduled_old
