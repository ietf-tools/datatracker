#!/usr/bin/python

import sys, os, re, datetime, pytz

basedir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path = [ basedir ] + sys.path

from ietf import settings
settings.USE_DB_REDESIGN_PROXY_CLASSES = False

from django.core import management
management.setup_environ(settings)

from django.template.defaultfilters import slugify

import datetime

from ietf.idtracker.models import AreaDirector, IETFWG, Acronym, IRTF, PersonOrOrgInfo
from ietf.meeting.models import *
from ietf.proceedings.models import Meeting as MeetingOld, MeetingVenue, MeetingRoom, NonSession, WgMeetingSession, WgAgenda, Minute, Slide, WgProceedingsActivities, NotMeetingGroup
from ietf.person.models import *
from ietf.doc.models import Document, DocAlias, State, DocEvent
from redesign.importing.utils import old_person_to_person, dont_save_queries, make_revision_event
from ietf.name.models import *
from ietf.name.utils import name

import_meetings_from = None
if len(sys.argv) > 1:
    import_meetings_from = datetime.datetime.strptime(sys.argv[1], "%Y-%m-%d")


dont_save_queries()

# imports Meeting, MeetingVenue, MeetingRoom, NonSession,
# WgMeetingSession, WgAgenda, Minute, Slide, upload events from
# WgProceedingsActivities, NotMeetingGroup

# assumptions:
#  - persons have been imported
#  - groups have been imported

ietf_meeting = name(MeetingTypeName, "ietf", "IETF")
interim_meeting = name(MeetingTypeName, "interim", "Interim")

session_status_mapping = {
    1: name(SessionStatusName, "schedw", "Waiting for Scheduling"),
    2: name(SessionStatusName, "apprw", "Waiting for Approval"),
    3: name(SessionStatusName, "appr", "Approved"),
    4: name(SessionStatusName, "sched", "Scheduled"),
    5: name(SessionStatusName, "canceled", "Canceled"),
    6: name(SessionStatusName, "disappr", "Disapproved"),
    }

status_not_meeting = name(SessionStatusName, "notmeet", "Not meeting")
status_deleted = name(SessionStatusName, "deleted", "Deleted")

session_status_mapping[0] = session_status_mapping[1] # assume broken statuses of 0 are actually cancelled

other_slot = name(TimeSlotTypeName, "other", "Other")
session_slot = name(TimeSlotTypeName, "session", "Session")
break_slot = name(TimeSlotTypeName, "break", "Break")
registration_slot = name(TimeSlotTypeName, "reg", "Registration")
plenary_slot = name(TimeSlotTypeName, "plenary", "Plenary")

conflict_constraints = {
    1: name(ConstraintName, "conflict", "Conflicts with"),
    2: name(ConstraintName, "conflic2", "Conflicts with (secondary)"),
    3: name(ConstraintName, "conflic3", "Conflicts with (tertiary)"),
    }

agenda_doctype = name(DocTypeName, "agenda", "Agenda")
minutes_doctype = name(DocTypeName, "minutes", "Minutes")
slides_doctype = name(DocTypeName, "slides", "Slides")

system_person = Person.objects.get(name="(System)")
obviously_bogus_date = datetime.date(1970, 1, 1)

for o in MeetingOld.objects.all():
    print "importing Meeting", o.pk

    try:
        m = Meeting.objects.get(number=o.meeting_num)
    except:
        m = Meeting(number="%s" % o.meeting_num)
        m.pk = o.pk

    m.type = ietf_meeting
    m.date = o.start_date
    m.city = o.city

    # convert country to code
    country_code = None
    for k, v in pytz.country_names.iteritems():
        if v == o.country:
            country_code = k
            break

    if not country_code:
        country_fallbacks = {
            'USA': 'US'
            }
        
        country_code = country_fallbacks.get(o.country)

    if country_code:
        m.country = country_code
    else:
        print "unknown country", o.country


    time_zone_lookup = {
        ("IE", "Dublin"): "Europe/Dublin",
        ("FR", "Paris"): "Europe/Paris",
        ("CA", "Vancouver"): "America/Vancouver",
        ("CZ", "Prague"): "Europe/Prague",
        ("US", "Chicago"): "America/Chicago",
        ("US", "Anaheim"): "America/Los_Angeles",
        ("NL", "Maastricht"): "Europe/Amsterdam",
        ("CN", "Beijing"): "Asia/Shanghai",
        ("JP", "Hiroshima"): "Asia/Tokyo",
        ("SE", "Stockholm"): "Europe/Stockholm",
        ("US", "San Francisco"): "America/Los_Angeles",
        ("US", "Minneapolis"): "America/Menominee",
        }
    
    m.time_zone = time_zone_lookup.get((m.country, m.city), "")
    if not m.time_zone:
        print "unknown time zone for", m.get_country_display(), m.city

    m.venue_name = "" # no source for that in the old DB?
    m.venue_addr = "" # no source for that in the old DB?
    try:
        venue = o.meetingvenue_set.get()
        m.break_area = venue.break_area_name
        m.reg_area = venue.reg_area_name
    except MeetingVenue.DoesNotExist:
        pass

    # missing following semi-used fields from old Meeting: end_date,
    # ack, agenda_html/agenda_text, future_meeting
        
    m.save()

meeting_cache = {}
def get_meeting(num):
    if not num in meeting_cache:
        meeting_cache[num] = Meeting.objects.get(number="%s" % num)
    return meeting_cache[num]

for o in MeetingRoom.objects.all():
    print "importing MeetingRoom", o.pk

    try:
        r = Room.objects.get(pk=o.pk)
    except Room.DoesNotExist:
        r = Room(pk=o.pk)

    r.meeting = get_meeting(o.meeting_id)
    r.name = o.room_name
    r.save()

def parse_time_desc(o):
    t = o.time_desc.replace(' ', '')
    
    start_time = datetime.time(int(t[0:2]), int(t[2:4]))
    end_time = datetime.time(int(t[5:7]), int(t[7:9]))

    d = o.meeting.start_date + datetime.timedelta(days=o.day_id)

    return (datetime.datetime.combine(d, start_time), datetime.datetime.combine(d, end_time))
    
requested_length_mapping = {
    None: 0, # assume NULL to mean nothing particular requested
    "1": 60 * 60,
    "2": 90 * 60,
    "3": 120 * 60,
    "4": 150 * 60,
    }

non_group_mapping = {
    "plenaryw": "ietf",
    "plenaryt": "ietf",
    "newcomer": "edu",
    "editor": "edu",
    "wgchair": "edu",
    "sectut": "edu",
    "protut": "edu",
    "iepg": "iepg",
    "rfc": "edu",
    "wgleader": "edu",
    "xml2rfc": "edu",
    "rbst": "edu",
    "recp": "ietf",
    "MIBDOC": "edu",
    "IE": "iepg",
    "newcomF": "edu",
    "WritRFC": "edu",
    "Orien": "edu",
    "newwork": "edu",
    "leadership": "edu",
    "ipv6spec": "edu",
    "Wel": "ietf",
    "IDRTut": "edu",
    "ToolsTut": "edu",
    "cosp": "tools",
    "doclife": "edu",
    "dnstut": "edu",
    "xmltut": "edu",
    "RFCEd": "edu",
    "IDRBasics": "edu",
    "newcomSWED": "edu",
    "MIBTut": "edu",
    "IDR75": "edu",
    "NewcomerJP": "edu",
    "MIBT": "edu",
    "DNSProg": "edu",
    "natTUT": "edu",
    "NewcomerCHINA": "edu",
    "CreatingID": "edu",
    "NewMeetGreet": "ietf",
    "appsprepmeeting": "edu",
    "NewcomersFrench": "edu",
    "NewComMandar": "edu",
    "AdminP": "ietf",
    }

def import_materials(wg_meeting_session, session):
    def import_material_kind(kind, doctype):
        # import agendas
        irtf = 0
        if wg_meeting_session.irtf:
            irtf = wg_meeting_session.group_acronym_id
        found = kind.objects.filter(meeting=wg_meeting_session.meeting_id,
                                    group_acronym_id=wg_meeting_session.group_acronym_id,
                                    irtf=irtf,
                                    interim=0)

        for o in found:
            name = "%s-%s-%s" % (doctype.slug, session.meeting.number, session.group.acronym)
            if kind == Slide:
                name += "-%s" % o.slide_num

            if session.name:
                name += "-%s" % slugify(session.name)

            name = name.lower()

            try:
                d = Document.objects.get(type=doctype, docalias__name=name)
            except Document.DoesNotExist:
                d = Document(type=doctype, name=name)
                
            if kind == Slide:
                d.title = o.slide_name.strip()
                l = o.file_loc()
                d.external_url = l[l.find("slides/") + len("slides/"):]
                d.order = o.order_num or 1
            else:
                session_name = session.name if session.name else session.group.acronym.upper()
                d.title = u"%s for %s at %s" % (doctype.name, session_name, session.meeting)
                d.external_url = o.filename # save filenames for now as they don't appear to be quite regular
            d.rev = "00"
            d.group = session.group
            d.time = datetime.datetime.combine(session.meeting.date, datetime.time(0, 0, 0)) # we may have better estimate below
            d.save()

            d.set_state(State.objects.get(type=doctype, slug="active"))
                
            DocAlias.objects.get_or_create(document=d, name=name)

            session.materials.add(d)

            # try to create a doc event to figure out who uploaded it
            e = make_revision_event(d, system_person)

            t = d.type_id
            if d.type_id == "slides":
                t = "slide, '%s" % d.title
            activities = WgProceedingsActivities.objects.filter(group_acronym=wg_meeting_session.group_acronym_id,
                                                                meeting=wg_meeting_session.meeting_id,
                                                                activity__startswith=t,
                                                                activity__endswith="was uploaded")[:1]
            if activities:
                a = activities[0]

                e.time = datetime.datetime.combine(a.act_date, datetime.time(*[int(s) for s in a.act_time.split(":")]))
                try:
                    e.by = old_person_to_person(a.act_by) or system_person
                except PersonOrOrgInfo.DoesNotExist:
                    pass

                d.time = e.time
                d.save()
            else:
                print "NO UPLOAD ACTIVITY RECORD for", d.name.encode("utf-8"), t.encode("utf-8"), wg_meeting_session.group_acronym_id, wg_meeting_session.meeting_id

            e.save()

    import_material_kind(WgAgenda, agenda_doctype)
    import_material_kind(Minute, minutes_doctype)
    import_material_kind(Slide, slides_doctype)

obviously_bogus_date = datetime.date(1970, 1, 1)

all_sessions = WgMeetingSession.objects.all().order_by("pk")
if import_meetings_from:
    all_sessions = all_sessions.filter(last_modified_date__gte=import_meetings_from)

for o in all_sessions.iterator():
    # num_session is unfortunately not quite reliable, seems to be
    # right for 1 or 2 but not 3 and it's sometimes null
    sessions = o.num_session or 1
    if o.sched_time_id3:
        sessions = 3
    
    print "importing WgMeetingSession", o.pk, "subsessions", sessions

    for i in range(1, 1 + sessions):
        pk = o.pk + (i - 1) * 10000 # move extra session out of the way
        try:
            s = Session.objects.get(pk=pk)
        except:
            s = Session(pk=pk)
        s.meeting = get_meeting(o.meeting_id)

        def get_timeslot(attr):
            meeting_time = getattr(o, attr)
            if not meeting_time:
                return None
            room = Room.objects.get(pk=getattr(o, attr.replace("time", "room") + "_id"))

            starts, ends = parse_time_desc(meeting_time)
    
            slots = TimeSlot.objects.filter(meeting=s.meeting, time=starts, location=room).filter(models.Q(session=s) | models.Q(session=None))
            if slots:
                slot = slots[0]
            else:
                slot = TimeSlot(meeting=s.meeting, time=starts, location=room)

                slot.type = session_slot
                slot.name = meeting_time.session_name.session_name if meeting_time.session_name_id else "Unknown"
                slot.duration = ends - starts

            return slot

        timeslot = get_timeslot("sched_time_id%s" % i)
        if o.irtf:
            s.group = Group.objects.get(acronym=IRTF.objects.get(pk=o.group_acronym_id).acronym.lower())
        else:
            acronym = Acronym.objects.get(pk=o.group_acronym_id)
            if o.group_acronym_id < 0:
                # this wasn't actually a WG session, but rather a tutorial
                # or similar
                a = non_group_mapping.get(acronym.acronym)
                if not a:
                    a = "ietf"
                    print "UNKNOWN phony group", o.group_acronym_id, acronym.acronym, "falling back to '%s'" % a
                s.group = Group.objects.get(acronym=a)
                s.name = acronym.name

                if timeslot:
                    if timeslot.name == "Unknown":
                        timeslot.name = acronym.name

                    if "Plenary" in timeslot.name:
                        timeslot.type = plenary_slot
                    else:
                        timeslot.type = other_slot
            else:
                s.group = Group.objects.get(acronym=acronym.acronym)
        s.attendees = o.number_attendee
        s.agenda_note = (o.special_agenda_note or "").strip()
        s.requested = o.requested_date or obviously_bogus_date
        s.requested_by = old_person_to_person(o.requested_by) if o.requested_by else system_person
        s.requested_duration = requested_length_mapping[getattr(o, "length_session%s" % i)]
        s.comments = (o.special_req or "").strip()
        conflict_other = (o.conflict_other or "").strip()
        if conflict_other:
            if s.comments:
                s.comments += " "
            s.comments += u"(other conflicts: %s)" % conflict_other
        s.status = session_status_mapping[o.status_id or 5]

        s.scheduled = o.scheduled_date
        s.modified = o.last_modified_date or obviously_bogus_date

        s.save()

        if timeslot:
            timeslot.session = s
            timeslot.modified = s.modified
            timeslot.save()
            
        import_materials(o, s)

        # some sessions have been scheduled over multiple time slots
        if i < 3:
            timeslot = get_timeslot("combined_time_id%s" % i)
            if timeslot:
                timeslot.session = s
                timeslot.modified = s.modified
                timeslot.save()


    for i in (1, 2, 3):
        conflict = (getattr(o, "conflict%s" % i) or "").replace(",", " ").lower()
        conflicting_groups = [g for g in conflict.split() if g]
        for target in Group.objects.filter(acronym__in=conflicting_groups):
            Constraint.objects.get_or_create(
                meeting=s.meeting,
                source=s.group,
                target=target,
                name=conflict_constraints[i])


    # missing following fields from old: ts_status_id (= third session
    # status id, third session required AD approval),
    # combined_room_id1/2, combined_time_id1/2

for o in NonSession.objects.all().order_by('pk').select_related("meeting").iterator():
    print "importing NonSession", o.pk

    if o.time_desc in ("", "0"):
        print "IGNORING non-scheduled NonSession", o.non_session_ref.name
        continue

    meeting = get_meeting(o.meeting_id)

    # some non-sessions are scheduled every day, but only if there's a
    # session nearby, figure out which days this corresponds to
    days = set()
    if o.day_id == None:
        t = datetime.time(int(o.time_desc[-4:][0:2]), int(o.time_desc[-4:][2:4]))
        
        for s in TimeSlot.objects.filter(meeting=meeting):
            if s.time.time() == t:
                days.add((s.time.date() - meeting.date).days)
    else:
        days.add(o.day_id)
        
    for day in days:
        o.day_id = day
        starts, ends = parse_time_desc(o)
        name = o.non_session_ref.name
    
        try:
            slot = TimeSlot.objects.get(meeting=meeting, time=starts, name=name)
        except TimeSlot.DoesNotExist:
            slot = TimeSlot(meeting=meeting, time=starts, name=name)

        slot.location = None
        if o.non_session_ref_id == 1:
            slot.type = registration_slot
        else:
            slot.type = break_slot
            
        slot.duration = ends - starts
        slot.show_location = o.show_break_location
        slot.save()


for o in NotMeetingGroup.objects.all().select_related('group_acronym'):
    if o.group_acronym_id == None or o.group_acronym == None:
        print "SKIPPING NotMeetingGroup with group_acronym_id", o.group_acronym_id
        continue # bogus data

    print "importing NotMeetingGroup", o.group_acronym.acronym, o.meeting_id
    try:
        group = Group.objects.get(acronym=o.group_acronym.acronym)
    except Group.DoesNotExist:
        print "SKIPPING", o.group_acronym.acronym
        continue
    meeting = get_meeting(o.meeting_id)

    if not Session.objects.filter(meeting=meeting, group=group):
        Session.objects.get_or_create(meeting=meeting,
                                      group=group,
                                      status=status_not_meeting,
                                      defaults=dict(requested_by=system_person,
                                                    requested_duration=0))

