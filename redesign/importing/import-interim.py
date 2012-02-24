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
from ietf.person.models import *
from ietf.doc.models import Document, DocAlias, State, DocEvent
from redesign.importing.utils import old_person_to_person, dont_save_queries, make_revision_event
from redesign.interim.models import *
from ietf.name.models import *
from ietf.name.utils import name

dont_save_queries()

# assumptions:
#  - persons have been imported
#  - groups have been imported
#  - regular meetings have been imported

database = "ietf_ams"

system_person = Person.objects.get(name="(System)")

agenda_doctype = name(DocTypeName, "agenda", "Agenda")
minutes_doctype = name(DocTypeName, "minutes", "Minutes")
slides_doctype = name(DocTypeName, "slides", "Slides")

group_meetings_in_year = {}

for o in InterimMeetings.objects.using(database).order_by("start_date"):
    print "importing InterimMeeting", o.pk

    group = Group.objects.get(pk=o.group_acronym_id)
    meeting_key = "%s-%s" % (group.acronym, o.start_date.year)
    if not group.acronym in group_meetings_in_year:
        group_meetings_in_year[meeting_key] = 0

    group_meetings_in_year[meeting_key] += 1

    num = "interim-%s-%s-%s" % (o.start_date.year, group.acronym, group_meetings_in_year[meeting_key])

    try:
        m = Meeting.objects.get(number=num)
    except:
        m = Meeting(number=num)
        m.pk = o.pk

    m.type_id = "interim"
    m.date = o.start_date

    # we don't have any other fields

    m.save()

    if m.session_set.all():
        session = m.session_set.all()[0]
    else:
        session = Session()
        session.meeting = m

    session.group = group
    session.requested_by = system_person
    session.status_id = "appr"
    session.modified = datetime.datetime.combine(m.date, datetime.time(0, 0, 0))
    session.save()

    meeting = m
    interim_meeting = o

    def import_material_kind(kind, doctype):
        # import agendas
        found = kind.objects.filter(meeting_num=m.pk,
                                    group_acronym_id=interim_meeting.group_acronym_id,
                                    irtf=1 if session.group.parent.acronym == "irtf" else 0,
                                    interim=1).using(database)

        for o in found:
            name = "%s-%s" % (doctype.slug, m.number)
            if kind == InterimSlides:
                name += "-%s" % o.slide_num

            name = name.lower()

            try:
                d = Document.objects.get(type=doctype, docalias__name=name)
            except Document.DoesNotExist:
                d = Document(type=doctype, name=name)
                
            if kind == InterimSlides:
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
            d.time = datetime.datetime.combine(meeting.date, datetime.time(0, 0, 0)) # we may have better estimate below

            d.save()

            d.set_state(State.objects.get(type=doctype, slug="active"))
                
            DocAlias.objects.get_or_create(document=d, name=name)

            session.materials.add(d)

            # try to create a doc event to figure out who uploaded it
            e = make_revision_event(d, system_person)

            t = d.type_id
            if d.type_id == "slides":
                t = "slide, '%s" % d.title
            activities = InterimActivities.objects.filter(group_acronym_id=interim_meeting.group_acronym_id,
                                                          meeting_num=interim_meeting.meeting_num,
                                                          activity__startswith=t,
                                                          activity__endswith="was uploaded").using(database)[:1]

            if activities:
                a = activities[0]

                e.time = datetime.datetime.combine(a.act_date, a.act_time)
                try:
                    e.by = old_person_to_person(PersonOrOrgInfo.objects.get(pk=a.act_by)) or system_person
                except PersonOrOrgInfo.DoesNotExist:
                    pass

                d.time = e.time
                d.save()
            else:
                print "NO UPLOAD ACTIVITY RECORD for", d.name.encode("utf-8"), t.encode("utf-8"), interim_meeting.group_acronym_id, interim_meeting.meeting_num

            e.save()


    import_material_kind(InterimAgenda, agenda_doctype)
    import_material_kind(InterimMinutes, minutes_doctype)
    import_material_kind(InterimSlides, slides_doctype)

