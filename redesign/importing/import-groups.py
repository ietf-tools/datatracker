#!/usr/bin/python

import sys, os, datetime

basedir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path = [ basedir ] + sys.path

from ietf import settings
settings.USE_DB_REDESIGN_PROXY_CLASSES = False

from django.core import management
management.setup_environ(settings)


from redesign.group.models import *
from redesign.name.models import *
from redesign.doc.models import State, StateType
from redesign.doc.utils import get_tags_for_stream_id
from redesign.name.utils import name
from redesign.importing.utils import old_person_to_person
from ietf.idtracker.models import AreaGroup, IETFWG, Area, AreaGroup, Acronym, AreaWGURL, IRTF, ChairsHistory, Role, AreaDirector
from ietf.liaisons.models import SDOs
import workflows.utils

# imports IETFWG, Area, AreaGroup, Acronym, IRTF, AreaWGURL, SDOs

# also creates nomcom groups

# assumptions: persons and states have been imported

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
    ag=name(GroupTypeName, slug="ag", name="AG", desc="Area group"),
    wg=name(GroupTypeName, slug="wg", name="WG", desc="Working group"),
    rg=name(GroupTypeName, slug="rg", name="RG", desc="Research group"),
    team=name(GroupTypeName, slug="team", name="Team"),
    individ=name(GroupTypeName, slug="individ", name="Individual"),
    sdo=name(GroupTypeName, slug="sdo", name="SDO", desc="Standards organization"),
    )

# make sure we got the IETF as high-level parent
ietf_group, _ = Group.objects.get_or_create(acronym="ietf")
ietf_group.name = "IETF"
ietf_group.state = state_names["active"]
ietf_group.type = type_names["ietf"]
ietf_group.save()

# make sure we got the IESG so we can use it as parent for areas
iesg_group, _ = Group.objects.get_or_create(acronym="iesg")
iesg_group.name = "IESG"
iesg_group.state = state_names["active"]
iesg_group.type = type_names["ietf"]
iesg_group.parent = ietf_group
iesg_group.save()

# make sure we got the IRTF as parent for RGs
irtf_group, _ = Group.objects.get_or_create(acronym="irtf")
irtf_group.name = "IRTF"
irtf_group.state = state_names["active"]
irtf_group.type = type_names["ietf"]
irtf_group.save()

# create Secretariat for use with roles
secretariat_group, _ = Group.objects.get_or_create(acronym="secretariat")
secretariat_group.name = "IETF Secretariat"
secretariat_group.state = state_names["active"]
secretariat_group.type = type_names["ietf"]
secretariat_group.save()

# create ISE for use with streams
ise_group, _ = Group.objects.get_or_create(acronym="ise")
ise_group.name = "Independent Submission Editor"
ise_group.state = state_names["active"]
ise_group.type = type_names["ietf"]
ise_group.save()

# create RSOC for use with roles
rsoc_group, _ = Group.objects.get_or_create(acronym="rsoc")
rsoc_group.name = "RFC Series Oversight Committee"
rsoc_group.state = state_names["active"]
rsoc_group.type = type_names["ietf"]
rsoc_group.save()

# create IAB for use with liaison statements and streams
iab_group, _ = Group.objects.get_or_create(acronym="iab")
iab_group.name = "Internet Architecture Board"
iab_group.state = state_names["active"]
iab_group.type = type_names["ietf"]
iab_group.save()

# create IANA for use with roles for authorization
iana_group, _ = Group.objects.get_or_create(acronym="iana")
iana_group.name = "IANA"
iana_group.state = state_names["active"]
iana_group.type = type_names["ietf"]
iana_group.save()

system = Person.objects.get(name="(System)")

# NomCom
for o in ChairsHistory.objects.filter(chair_type=Role.NOMCOM_CHAIR).order_by("start_year"):
    print "importing ChairsHistory/Nomcom", o.pk, "nomcom%s" % o.start_year
    group, _ = Group.objects.get_or_create(acronym="nomcom%s" % o.start_year)
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
    group.groupevent_set.all().delete()
    
    e = GroupEvent(group=group, type="started")
    e.time = datetime.datetime(o.start_year, 5, 1, 12, 0, 0)
    e.by = system
    e.desc = e.get_type_display()
    e.save()

    e = GroupEvent(group=group, type="concluded")
    e.time = datetime.datetime(o.end_year, 5, 1, 12, 0, 0)
    e.by = system
    e.desc = e.get_type_display()
    e.save()
    
# IRTF
for o in IRTF.objects.all():
    print "importing IRTF", o.pk, o.acronym
    
    try:
        group = Group.objects.get(acronym=o.acronym.lower())
    except Group.DoesNotExist:
        group = Group(acronym=o.acronym.lower())
        
    group.name = o.name
    group.state = state_names["active"] # we assume all to be active
    group.type = type_names["rg"]
    group.parent = irtf_group

    group.comments = o.charter_text or ""
    
    group.save()

    # FIXME: missing fields from old: meeting_scheduled

# SDOs
for o in SDOs.objects.all().order_by("pk"):
    # we import SDOs as groups, this makes it easy to take advantage
    # of the rest of the role/person models for authentication and
    # authorization
    print "importing SDOs", o.pk, o.sdo_name
    try:
        group = Group.objects.get(name=o.sdo_name, type=type_names["sdo"])
    except Group.DoesNotExist:
        group = Group(name=o.sdo_name, type=type_names["sdo"])

    group.state_id = "active"
    group.save()

def import_date_event(group, name, type_name):
    d = getattr(o, "%s_date" % name)
    if d:
        e = GroupEvent(group=group, type=type_name)
        e.time = datetime.datetime.combine(d, datetime.time(12, 0, 0))
        e.by = system
        e.desc = e.get_type_display()
        e.save()

# Area
for o in Area.objects.all():
    print "importing Area", o.pk, o.area_acronym.acronym
    
    try:
        group = Group.objects.get(acronym=o.area_acronym.acronym)
    except Group.DoesNotExist:
        group = Group(acronym=o.area_acronym.acronym)
        group.id = o.area_acronym_id # transfer id

    # we could use last_modified_date for group.time, but in the new
    # schema, group.time is supposed to change when the roles change
    # too and some of the history logic depends on this, so it's going
    # to cause us too much trouble

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

    for u in o.additional_urls():
        url, _ = GroupURL.objects.get_or_create(group=group, url=u.url)
        url.name = u.description.strip()
        url.save()
    
    # import events
    group.groupevent_set.all().delete()

    import_date_event(group, "start", "started")
    import_date_event(group, "concluded", "concluded")

    # FIXME: missing fields from old: extra_email_addresses


# IETFWG, AreaGroup
for o in IETFWG.objects.all().order_by("pk"):
    print "importing IETFWG", o.pk, o.group_acronym.acronym
    
    try:
        group = Group.objects.get(acronym=o.group_acronym.acronym)
    except Group.DoesNotExist:
        group = Group(acronym=o.group_acronym.acronym)
        group.id = o.group_acronym_id # transfer id
        
    if o.last_modified_date:
        group.time = datetime.datetime.combine(o.last_modified_date, datetime.time(12, 0, 0))
    group.name = o.group_acronym.name
    # state
    if o.group_type.type == "BOF":
        s = state_names["bof"]
        if o.status.status == "Concluded":
            s = state_names["conclude"]
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
        elif o.group_acronym.acronym in ("tsvdir", "secdir", "saag", "usac"):
            group.type = type_names["team"]
        elif o.group_acronym.acronym == "iesg":
            pass # we already treated iesg
        elif o.group_acronym.acronym in ("apparea", "opsarea", "rtgarea", "usvarea", "genarea", "tsvarea", "raiarea", "apptsv"):
            group.type = type_names["ag"]
        else:
            # the remaining groups are
            #  apples, null, dirdir
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

    try:
        area_director = o.area_director
    except AreaDirector.DoesNotExist:
        area_director = None
    if area_director and not area_director.area_id:
        area_director = None # fake TBD guy
        
    group.ad = old_person_to_person(area_director.person) if area_director else None
    group.list_email = o.email_address if o.email_address else ""
    group.list_subscribe = (o.email_subscribe or "").replace("//listinfo", "/listinfo").strip()
    l = o.clean_email_archive().strip() if o.email_archive else ""
    if l in ("none", "not available"):
        l = ""
    group.list_archive = l
    group.comments = o.comments.strip() if o.comments else ""
    
    group.save()

    for u in o.additional_urls():
        url, _ = GroupURL.objects.get_or_create(group=group, url=u.url)
        url.name = u.description.strip()
        url.save()

    for m in o.milestones():
        desc = m.description.strip()
        try:
            milestone = GroupMilestone.objects.get(group=group, desc=desc)
        except GroupMilestone.DoesNotExist:
            milestone = GroupMilestone(group=group, desc=desc)
            
        milestone.expected_due_date = m.expected_due_date
        milestone.done = m.done == "Done"
        milestone.done_date = m.done_date
        milestone.time = datetime.datetime.combine(m.last_modified_date, datetime.time(12, 0, 0))
        milestone.save()

    # import workflow states and transitions
    w = workflows.utils.get_workflow_for_object(o)
    if w:
        try:
            w = w.wgworkflow
        except WGWorkflow.DoesNotExist:
            w = None
    if w:
        w.unused_states = State.objects.filter(type="draft-stream-ietf").exclude(name__in=[x.name for x in w.selected_states.all()])
        w.unused_tags = DocTagName.objects.filter(slug__in=get_tags_for_stream_id("draft-stream-ietf")).exclude(name__in=[x.name for x in w.selected_tags.all()])

        # custom transitions
        states = dict((s.name, s) for s in State.objects.filter(type="draft-stream-ietf"))
        old_states = dict((s.name, s) for s in w.states.filter(name__in=[name for name in states]).select_related('transitions'))
        for name in old_states:
            s = states[name]
            o = old_states[name]
            n = [states[t.destination.name] for t in o.transitions.filter(workflow=workflow)]
            if set(s.next_states) != set(n):
                g, _ = GroupStateTransitions.objects.get_or_create(group=group, state=s)
                g.next_states = n
    # import events
    group.groupevent_set.all().delete()

    import_date_event(group, "proposed", "proposed")
    import_date_event(group, "start", "started")
    import_date_event(group, "concluded", "concluded")
    # dormant_date is empty on all so don't bother with that
            
    # FIXME: missing fields from old: meeting_scheduled, email_keyword, meeting_scheduled_old

