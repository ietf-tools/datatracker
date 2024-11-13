# Copyright The IETF Trust 2009-2024, All Rights Reserved
# -*- coding: utf-8 -*-
import datetime
import io
import json
import os
import random
import re
import shutil
import pytz
import requests.exceptions
import requests_mock

from unittest import skipIf
from mock import call, patch, PropertyMock
from pyquery import PyQuery
from lxml.etree import tostring
from io import StringIO, BytesIO
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urlsplit
from PIL import Image
from pathlib import Path
from tempfile import NamedTemporaryFile
from zoneinfo import ZoneInfo

from django.urls import reverse as urlreverse
from django.conf import settings
from django.contrib.auth.models import User
from django.core.serializers.json import DjangoJSONEncoder
from django.test import Client, override_settings
from django.db.models import F, Max
from django.http import QueryDict, FileResponse
from django.template import Context, Template
from django.utils import timezone
from django.utils.text import slugify

import debug           # pyflakes:ignore

from ietf.doc.models import Document, NewRevisionDocEvent
from ietf.group.models import Group, Role, GroupFeatures
from ietf.group.utils import can_manage_group
from ietf.person.models import Person
from ietf.meeting.helpers import can_approve_interim_request, can_request_interim_meeting, can_view_interim_request, preprocess_assignments_for_agenda
from ietf.meeting.helpers import send_interim_approval_request, AgendaKeywordTagger
from ietf.meeting.helpers import send_interim_meeting_cancellation_notice, send_interim_session_cancellation_notice
from ietf.meeting.helpers import send_interim_minutes_reminder, populate_important_dates, update_important_dates
from ietf.meeting.models import Session, TimeSlot, Meeting, SchedTimeSessAssignment, Schedule, SessionPresentation, SlideSubmission, SchedulingEvent, Room, Constraint, ConstraintName
from ietf.meeting.test_data import make_meeting_test_data, make_interim_meeting, make_interim_test_data
from ietf.meeting.utils import condition_slide_order
from ietf.meeting.utils import add_event_info_to_session_qs, participants_for_meeting
from ietf.meeting.utils import create_recording, get_next_sequence, bluesheet_data
from ietf.meeting.views import session_draft_list, parse_agenda_filter_params, sessions_post_save, agenda_extract_schedule
from ietf.meeting.views import get_summary_by_area, get_summary_by_type, get_summary_by_purpose, generate_agenda_data
from ietf.name.models import SessionStatusName, ImportantDateName, RoleName, ProceedingsMaterialTypeName
from ietf.utils.decorators import skip_coverage
from ietf.utils.mail import outbox, empty_outbox, get_payload_text
from ietf.utils.test_utils import TestCase, login_testing_unauthorized, unicontent
from ietf.utils.timezone import date_today, time_now

from ietf.person.factories import PersonFactory, PersonalApiKeyFactory
from ietf.group.factories import GroupFactory, GroupEventFactory, RoleFactory
from ietf.meeting.factories import (SessionFactory, ScheduleFactory,
    SessionPresentationFactory, MeetingFactory, FloorPlanFactory,
    TimeSlotFactory, SlideSubmissionFactory, RoomFactory,
    ConstraintFactory, MeetingHostFactory, ProceedingsMaterialFactory,
    AttendedFactory)
from ietf.stats.factories import MeetingRegistrationFactory
from ietf.doc.factories import DocumentFactory, WgDraftFactory
from ietf.submit.tests import submission_file
from ietf.utils.test_utils import assert_ical_response_is_valid

if os.path.exists(settings.GHOSTSCRIPT_COMMAND):
    skip_pdf_tests = False
    skip_message = ""
else:
    skip_pdf_tests = True
    skip_message = ("Skipping pdf test: The binary for ghostscript wasn't found in the\n       "
                    "location indicated in settings.py.")
    print("     "+skip_message)


class BaseMeetingTestCase(TestCase):
    """Base class for meeting-related tests that need to set up temporary directories

    This creates temporary directories for meeting-related uploads, then updates settings
    to point to them. It also patches the Storage class to use the temporary directories.
    When done, removes its files, resets the settings, and shuts off the patched Storage.

    If subclasses have their own setUp/tearDown routines, they must remember to call the
    superclass methods.
    """
    def setUp(self):
        super().setUp()
        self.materials_dir = self.tempdir('materials')
        self.storage_dir = self.tempdir('storage')
        #
        archive_dir = Path(settings.INTERNET_DRAFT_ARCHIVE_DIR)
        (archive_dir / "unknown_ids").mkdir()
        (archive_dir / "deleted_tombstones").mkdir()
        (archive_dir / "expired_without_tombstone").mkdir()
        #
        self.saved_agenda_path = settings.AGENDA_PATH
        self.saved_meetinghost_logo_path = settings.MEETINGHOST_LOGO_PATH
        #
        settings.AGENDA_PATH = self.materials_dir
        settings.MEETINGHOST_LOGO_PATH = self.storage_dir

        # The FileSystemStorage has already set its location before
        # the settings were changed. Mock the method it uses to get the
        # location and fill in our temporary location. Without this, test
        # files will upload to the locations specified in settings.py.
        # Note that this will affect any use of the storage class in
        # meeting.models - i.e., FloorPlan.image and MeetingHost.logo
        self.patcher = patch('ietf.meeting.models.NoLocationMigrationFileSystemStorage.base_location',
                             new_callable=PropertyMock)
        mocked = self.patcher.start()
        mocked.return_value = self.storage_dir

    def tearDown(self):
        self.patcher.stop()
        #
        shutil.rmtree(self.storage_dir)
        shutil.rmtree(self.materials_dir)
        #
        settings.AGENDA_PATH = self.saved_agenda_path
        settings.MEETINGHOST_LOGO_PATH = self.saved_meetinghost_logo_path
        super().tearDown()

    def write_materials_file(self, meeting, doc, content, charset="utf-8", with_ext=None):
        if with_ext is None:
            filename = doc.uploaded_filename
        else:
            filename = Path(doc.uploaded_filename).with_suffix(with_ext)
        path = os.path.join(self.materials_dir, "%s/%s/%s" % (meeting.number, doc.type_id, filename))

        dirname = os.path.dirname(path)
        if not os.path.exists(dirname):
            os.makedirs(dirname)

        if isinstance(content, str):
            content = content.encode(charset)
        with io.open(path, "wb") as f:
            f.write(content)

    def write_materials_files(self, meeting, session):

        draft = Document.objects.filter(type="draft", group=session.group).first()

        self.write_materials_file(meeting, session.materials.get(type="agenda"),
                                  "1. WG status (15 minutes)\n\n2. Status of %s\n\n" % draft.name)

        self.write_materials_file(meeting, session.materials.get(type="minutes"),
                                  "1. More work items underway\n\n2. The draft will be finished before next meeting\n\n")

        self.write_materials_file(meeting, session.materials.filter(type="slides").exclude(states__type__slug='slides',states__slug='deleted').first(),
                                  "This is a slideshow")


class AgendaApiTests(TestCase):
    def test_agenda_extract_schedule_location(self):
        meeting = MeetingFactory(type_id='ietf')
        room = RoomFactory(meeting=meeting, floorplan=FloorPlanFactory(meeting=meeting))
        hidden_ts = TimeSlotFactory(meeting=meeting, location=room, show_location=False)
        shown_ts = TimeSlotFactory(meeting=meeting, location=room, show_location=True)
        hidden_sess = SessionFactory(meeting=meeting, add_to_schedule=False)
        shown_sess = SessionFactory(meeting=meeting, add_to_schedule=False)
        meeting.schedule.assignments.create(timeslot=hidden_ts, session=hidden_sess)
        meeting.schedule.assignments.create(timeslot=shown_ts, session=shown_sess)
        processed = preprocess_assignments_for_agenda(
            SchedTimeSessAssignment.objects.filter(session__in=[hidden_sess, shown_sess]),
            meeting
        )
        AgendaKeywordTagger(assignments=processed).apply()
        extracted = {item.session.pk: agenda_extract_schedule(item) for item in processed}

        hidden = extracted[hidden_sess.pk]
        self.assertIsNone(hidden['room'])
        self.assertEqual(hidden['location'], {})

        shown = extracted[shown_sess.pk]
        self.assertEqual(shown['room'], room.name)
        self.assertEqual(shown['location'], {'name': room.floorplan.name, 'short': room.floorplan.short})

    def test_agenda_extract_schedule_names(self):
        meeting = MeetingFactory(type_id='ietf')
        named_timeslots = TimeSlotFactory.create_batch(2, meeting=meeting, name='Timeslot Name')
        unnamed_timeslots = TimeSlotFactory.create_batch(2, meeting=meeting, name='')
        named_sessions = SessionFactory.create_batch(2, meeting=meeting, name='Session Name')
        unnamed_sessions = SessionFactory.create_batch(2, meeting=meeting, name='')
        pk_with = {
            'both named': named_sessions[0].timeslotassignments.create(
                schedule=meeting.schedule,
                timeslot=named_timeslots[0],
            ).pk,
            'session named': named_sessions[1].timeslotassignments.create(
                schedule=meeting.schedule,
                timeslot=unnamed_timeslots[0],
            ).pk,
            'timeslot named': unnamed_sessions[0].timeslotassignments.create(
                schedule=meeting.schedule,
                timeslot=named_timeslots[1],
            ).pk,
            'neither named': unnamed_sessions[1].timeslotassignments.create(
                schedule=meeting.schedule,
                timeslot=unnamed_timeslots[1],
            ).pk,
        }
        processed = preprocess_assignments_for_agenda(meeting.schedule.assignments.all(), meeting)
        AgendaKeywordTagger(assignments=processed).apply()
        extracted = {item.pk: agenda_extract_schedule(item) for item in processed}
        self.assertEqual(extracted[pk_with['both named']]['name'], 'Session Name')
        self.assertEqual(extracted[pk_with['both named']]['slotName'], 'Timeslot Name')
        self.assertEqual(extracted[pk_with['session named']]['name'], 'Session Name')
        self.assertEqual(extracted[pk_with['session named']]['slotName'], '')
        self.assertEqual(extracted[pk_with['timeslot named']]['name'], '')
        self.assertEqual(extracted[pk_with['timeslot named']]['slotName'], 'Timeslot Name')
        self.assertEqual(extracted[pk_with['neither named']]['name'], '')
        self.assertEqual(extracted[pk_with['neither named']]['slotName'], '')


class MeetingTests(BaseMeetingTestCase):
    @override_settings(
        MEETECHO_ONSITE_TOOL_URL="https://onsite.example.com",
        MEETECHO_VIDEO_STREAM_URL="https://meetecho.example.com",
    )
    def test_meeting_agenda(self):
        meeting = make_meeting_test_data()
        session = Session.objects.filter(meeting=meeting, group__acronym="mars").first()
        session.remote_instructions='https://remote.example.com'
        session.save()
        slot = TimeSlot.objects.get(sessionassignments__session=session,sessionassignments__schedule=meeting.schedule)
        meeting.timeslot_set.filter(type_id="break").update(show_location=False)
        #
        self.write_materials_files(meeting, session)
        #
        future_year = date_today().year+1
        future_num =  (future_year-1984)*3            # valid for the mid-year meeting
        future_meeting = Meeting.objects.create(date=datetime.date(future_year, 7, 22), number=future_num, type_id='ietf',
                                city="Panama City", country="PA", time_zone='America/Panama')

        registration_text = "Registration"

        # Extremely rudementary test of agenda-neue - to be replaced with back-end tests as the front-end tests are developed.
        r = self.client.get(urlreverse("agenda", kwargs=dict(num=meeting.number,utc='-utc')))
        self.assertEqual(r.status_code, 200)  

        # Agenda API tests
        # -> Meeting data
        # First, check that the generation function does the right thing
        generated_data = generate_agenda_data(meeting.number)
        self.assertEqual(
            generated_data,
            {
                "meeting": {
                    "number": meeting.number,
                    "city": meeting.city,
                    "startDate": meeting.date.isoformat(),
                    "endDate": meeting.end_date().isoformat(),
                    "updated": generated_data.get("meeting").get("updated"),  # Just expect the value to exist
                    "timezone": meeting.time_zone,
                    "infoNote": meeting.agenda_info_note,
                    "warningNote": meeting.agenda_warning_note
                },
                "categories": generated_data.get("categories"),  # Just expect the value to exist
                "isCurrentMeeting": True,
                "usesNotes": False,  # make_meeting_test_data sets number=72
                "schedule": generated_data.get("schedule"),  # Just expect the value to exist
                "floors": []
            }
        )
        with patch("ietf.meeting.views.generate_agenda_data", return_value=generated_data):
            r = self.client.get(urlreverse("ietf.meeting.views.api_get_agenda_data", kwargs=dict(num=meeting.number)))
        self.assertEqual(r.status_code, 200)  
        # json.dumps using the DjangoJSONEncoder to handle timestamps consistently
        self.assertJSONEqual(r.content.decode("utf8"), json.dumps(generated_data, cls=DjangoJSONEncoder))
        # -> Session MaterialM
        r = self.client.get(urlreverse("ietf.meeting.views.api_get_session_materials", kwargs=dict(session_id=session.id)))
        self.assertEqual(r.status_code, 200)  
        rjson = json.loads(r.content.decode("utf8"))
        minutes = session.minutes()
        self.assertJSONEqual(
            r.content.decode("utf8"),
            {
                "url": session.agenda().get_href(),
                "slides": rjson.get("slides"), # Just expect the value to exist
                "minutes": {
                    "id": minutes.id,
                    "title": minutes.title,
                    "url": minutes.get_href(),
                    "ext": minutes.file_extension()
                } if minutes is not None else None
            }
        )

        # text
        r = self.client.get(urlreverse("ietf.meeting.views.agenda_plain", kwargs=dict(num=meeting.number, ext=".txt")))
        self.assertContains(r, session.group.acronym)
        self.assertContains(r, session.group.name)
        self.assertContains(r, session.group.parent.acronym.upper())
        self.assertContains(r, slot.location.name)
        self.assertContains(r, "{}-{}".format(
            slot.time.astimezone(meeting.tz()).strftime("%H%M"),
            (slot.time + slot.duration).astimezone(meeting.tz()).strftime("%H%M"),
        ))
        self.assertContains(r, f"shown in the {meeting.tz()} time zone")
        updated = meeting.updated().astimezone(meeting.tz()).strftime("%Y-%m-%d %H:%M:%S %Z")
        self.assertContains(r, f"Updated {updated}")

        # text, UTC
        r = self.client.get(urlreverse(
            "ietf.meeting.views.agenda_plain",
            kwargs=dict(num=meeting.number, ext=".txt", utc="-utc"),
        ))
        self.assertContains(r, session.group.acronym)
        self.assertContains(r, session.group.name)
        self.assertContains(r, session.group.parent.acronym.upper())
        self.assertContains(r, slot.location.name)
        self.assertContains(r, "{}-{}".format(
            slot.time.astimezone(datetime.timezone.utc).strftime("%H%M"),
            (slot.time + slot.duration).astimezone(datetime.timezone.utc).strftime("%H%M"),
        ))
        self.assertContains(r, "shown in UTC")
        updated = meeting.updated().astimezone(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S %Z")
        self.assertContains(r, f"Updated {updated}")

        # text, invalid updated (none)
        with patch("ietf.meeting.models.Meeting.updated", return_value=None):
            r = self.client.get(urlreverse(
                "ietf.meeting.views.agenda_plain",
                kwargs=dict(num=meeting.number, ext=".txt", utc="-utc"),
            ))
            self.assertNotContains(r, "Updated ")

        # future meeting, no agenda
        r = self.client.get(urlreverse("ietf.meeting.views.agenda_plain", kwargs=dict(num=future_meeting.number, ext=".txt")))
        self.assertContains(r, "There is no agenda available yet.")
        self.assertTemplateUsed(r, 'meeting/no-agenda.txt')

        # CSV
        r = self.client.get(urlreverse("ietf.meeting.views.agenda_plain", kwargs=dict(num=meeting.number, ext=".csv")))
        self.assertContains(r, session.group.acronym)
        self.assertContains(r, session.group.name)
        self.assertContains(r, session.group.parent.acronym.upper())
        self.assertContains(r, slot.location.name)
        self.assertContains(r, registration_text)
        start_time = slot.time.astimezone(meeting.tz())
        end_time = slot.end_time().astimezone(meeting.tz())
        self.assertContains(r, '"{}","{}","{}"'.format(
            start_time.strftime("%Y-%m-%d"),
            start_time.strftime("%H%M"),
            end_time.strftime("%H%M"),
        ))
        self.assertContains(r, session.materials.get(type='agenda').uploaded_filename)
        self.assertContains(r, session.materials.filter(type='slides').exclude(states__type__slug='slides',states__slug='deleted').first().uploaded_filename)
        self.assertNotContains(r, session.materials.filter(type='slides',states__type__slug='slides',states__slug='deleted').first().uploaded_filename)

        # CSV, utc
        r = self.client.get(urlreverse(
            "ietf.meeting.views.agenda_plain",
            kwargs=dict(num=meeting.number, ext=".csv", utc="-utc"),
        ))
        self.assertContains(r, session.group.acronym)
        self.assertContains(r, session.group.name)
        self.assertContains(r, session.group.parent.acronym.upper())
        self.assertContains(r, slot.location.name)
        self.assertContains(r, registration_text)
        start_time = slot.time.astimezone(datetime.timezone.utc)
        end_time = slot.end_time().astimezone(datetime.timezone.utc)
        self.assertContains(r, '"{}","{}","{}"'.format(
            start_time.strftime("%Y-%m-%d"),
            start_time.strftime("%H%M"),
            end_time.strftime("%H%M"),
        ))
        self.assertContains(r, session.materials.get(type='agenda').uploaded_filename)
        self.assertContains(r, session.materials.filter(type='slides').exclude(states__type__slug='slides',states__slug='deleted').first().uploaded_filename)
        self.assertNotContains(r, session.materials.filter(type='slides',states__type__slug='slides',states__slug='deleted').first().uploaded_filename)

        # iCal, no session filtering
        ical_url = urlreverse("ietf.meeting.views.agenda_ical", kwargs=dict(num=meeting.number))
        r = self.client.get(ical_url)

        assert_ical_response_is_valid(self, r)
        self.assertContains(r, "BEGIN:VTIMEZONE")
        self.assertContains(r, "END:VTIMEZONE")

        # iCal, single group
        r = self.client.get(ical_url + "?show=" + session.group.parent.acronym.upper())
        assert_ical_response_is_valid(self, r)
        self.assertContains(r, session.group.acronym)
        self.assertContains(r, session.group.name)
        self.assertContains(r, session.remote_instructions)
        self.assertContains(r, slot.location.name)
        self.assertContains(r, 'https://onsite.example.com')
        self.assertContains(r, 'https://meetecho.example.com')
        self.assertContains(r, "BEGIN:VTIMEZONE")
        self.assertContains(r, "END:VTIMEZONE")        

        self.assertContains(r, session.agenda().get_href())
        self.assertContains(
            r,
            urlreverse(
                'ietf.meeting.views.session_details',
                kwargs=dict(num=meeting.number, acronym=session.group.acronym)),
            msg_prefix='ical should contain link to meeting materials page for session')

        # Floor Plan
        r = self.client.get(urlreverse('floor-plan', kwargs=dict(num=meeting.number)))
        self.assertEqual(r.status_code, 200)

    def test_session_recordings_via_factories(self):
        session = SessionFactory(meeting__type_id="ietf", meeting__date=date_today()-datetime.timedelta(days=180))
        self.assertEqual(session.meetecho_recording_name, "")
        self.assertEqual(len(session.recordings()), 0)
        url = urlreverse("ietf.meeting.views.session_details", kwargs=dict(num=session.meeting.number, acronym=session.group.acronym))
        r = self.client.get(url)
        q = PyQuery(r.content)
        # debug.show("q(f'#notes_and_recordings_{session.pk}')")
        self.assertEqual(len(q(f"#notes_and_recordings_{session.pk} tr")), 1)
        link = q(f"#notes_and_recordings_{session.pk} tr a")
        self.assertEqual(len(link), 1)
        self.assertEqual(link[0].attrib['href'], str(session.session_recording_url()))

        session.meetecho_recording_name = 'my_test_session_name'
        session.save()
        r = self.client.get(url)
        q = PyQuery(r.content)
        self.assertEqual(len(q(f"#notes_and_recordings_{session.pk} tr")), 1)
        links = q(f"#notes_and_recordings_{session.pk} tr a")
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0].attrib['href'], session.session_recording_url())

        new_recording_url = "https://www.youtube.com/watch?v=jNQXAC9IVRw"
        new_recording_title = "Me at the zoo"
        create_recording(session, new_recording_url, new_recording_title)
        r = self.client.get(url)
        q = PyQuery(r.content)
        self.assertEqual(len(q(f"#notes_and_recordings_{session.pk} tr")), 2)
        links = q(f"#notes_and_recordings_{session.pk} tr a")
        self.assertEqual(len(links), 2)
        self.assertEqual(links[0].attrib['href'], new_recording_url)
        self.assertIn(new_recording_title, links[0].text_content())
        #debug.show("q(f'#notes_and_recordings_{session_pk}')")

    def test_agenda_ical_next_meeting_type(self):
        # start with no upcoming IETF meetings, just an interim
        MeetingFactory(
            type_id="interim", date=date_today() + datetime.timedelta(days=15)
        )
        r = self.client.get(urlreverse("ietf.meeting.views.agenda_ical", kwargs={}))
        self.assertEqual(
            r.status_code, 404, "Should not return an interim meeting as next meeting"
        )
        # create an IETF meeting after the interim - it should be found as "next"
        ietf_meeting = MeetingFactory(
            type_id="ietf", date=date_today() + datetime.timedelta(days=30)
        )
        SessionFactory(meeting=ietf_meeting, name="Session at IETF meeting")
        r = self.client.get(urlreverse("ietf.meeting.views.agenda_ical", kwargs={}))
        self.assertContains(r, "Session at IETF meeting", status_code=200)

    def test_agenda_json_next_meeting_type(self):
        # start with no upcoming IETF meetings, just an interim
        MeetingFactory(
            type_id="interim", date=date_today() + datetime.timedelta(days=15)
        )
        r = self.client.get(urlreverse("ietf.meeting.views.agenda_json", kwargs={}))
        self.assertEqual(
            r.status_code, 404, "Should not return an interim meeting as next meeting"
        )
        # create an IETF meeting after the interim - it should be found as "next"
        ietf_meeting = MeetingFactory(
            type_id="ietf", date=date_today() + datetime.timedelta(days=30)
        )
        SessionFactory(meeting=ietf_meeting, name="Session at IETF meeting")
        r = self.client.get(urlreverse("ietf.meeting.views.agenda_json", kwargs={}))
        self.assertContains(r, "Session at IETF meeting", status_code=200)

    @override_settings(PROCEEDINGS_V1_BASE_URL='https://example.com/{meeting.number}')
    def test_agenda_redirects_for_old_meetings(self):
        """Meetings before 64 should be forwarded to their proceedings"""
        # meeting with record but no schedule
        MeetingFactory(type_id='ietf', number='35', populate_schedule=False)
        r = self.client.get(
            urlreverse(
                'agenda',
                kwargs={'num': '35', 'ext': '.html'},
            ))
        self.assertRedirects(r, 'https://example.com/35', fetch_redirect_response=False)

        # meeting with record and schedule but no assignments
        meeting_with_schedule = MeetingFactory(type_id='ietf', number='36', populate_schedule=True)
        r = self.client.get(
            urlreverse(
                'agenda',
                kwargs={'num': '36', 'ext': '.html'},
            ))
        self.assertRedirects(r, 'https://example.com/36', fetch_redirect_response=False)

        # meeting with an assignment
        SessionFactory(meeting=meeting_with_schedule)
        r = self.client.get(
                    urlreverse(
                        'agenda',
                        kwargs={'num': '36', 'ext': '.html'},
                    ))
        self.assertRedirects(r, 'https://example.com/36', fetch_redirect_response=False)

    def test_agenda_for_nonexistent_meeting(self):
        """Return a 404 for a bad IETF meeting number"""
        # Meetings pre-64 are redirected, but should be a 404 if there is no Meeting instance
        r = self.client.get(
            urlreverse(
                'agenda',
                kwargs={'num': '32', 'ext': '.html'},
            ))
        self.assertEqual(r.status_code, 404)

    @override_settings(MEETING_MATERIALS_SERVE_LOCALLY=False, MEETING_DOC_HREFS = settings.MEETING_DOC_CDN_HREFS)
    def test_materials_through_cdn(self):
        meeting = make_meeting_test_data(create_interims=True)

        session107 = SessionFactory(meeting__number='172',group__acronym='mars')
        doc = DocumentFactory.create(name='agenda-172-mars', type_id='agenda', title="Agenda",
            uploaded_filename="agenda-172-mars.txt", group=session107.group, rev='00', states=[('agenda','active')])
        pres = SessionPresentation.objects.create(session=session107,document=doc,rev=doc.rev)
        session107.presentations.add(pres) # 
        doc = DocumentFactory.create(name='minutes-172-mars', type_id='minutes', title="Minutes",
            uploaded_filename="minutes-172-mars.md", group=session107.group, rev='00', states=[('minutes','active')])
        pres = SessionPresentation.objects.create(session=session107,document=doc,rev=doc.rev)
        session107.presentations.add(pres)
        doc = DocumentFactory.create(name='slides-172-mars-1-active', type_id='slides', title="Slideshow",
            uploaded_filename="slides-172-mars.txt", group=session107.group, rev='00',
            states=[('slides','active'), ('reuse_policy', 'single')])
        pres = SessionPresentation.objects.create(session=session107,document=doc,rev=doc.rev)
        session107.presentations.add(pres)

        for session in (
            Session.objects.filter(meeting=meeting, group__acronym="mars").first(),
            session107,
            Session.objects.filter(meeting__type_id='interim', group__acronym='mars', schedulingevent__status='sched').first(),
        ):
            self.write_materials_files(session.meeting, session)
            for document in (session.agenda(),session.minutes(),session.slides()[0]):
                url = urlreverse("ietf.meeting.views.materials_document",
                                               kwargs=dict(num=session.meeting.number, document=document))
                r = self.client.get(url)
                if session.meeting.number.isdigit() and int(session.meeting.number)<=96:
                    self.assertEqual(r.status_code,200)
                else:
                    self.assertEqual(r.status_code,302)
                    self.assertEqual(r['Location'],document.get_href())
                    self.assertNotEqual(urlsplit(r['Location'])[2],url)

    def test_materials(self):
        meeting = make_meeting_test_data()
        session = Session.objects.filter(meeting=meeting, group__acronym="mars").first()
        self.do_test_materials(meeting, session)

    def test_interim_materials(self):
        make_meeting_test_data()
        group = Group.objects.get(acronym='mars')
        date = timezone.now() - datetime.timedelta(days=10)
        meeting = make_interim_meeting(group=group, date=date, status='sched')
        session = meeting.session_set.first()

        self.do_test_materials(meeting, session)

    def test_named_session(self):
        """Session with a name should appear separately in the materials"""
        meeting = MeetingFactory(type_id='ietf', number='100')
        meeting.importantdate_set.create(name_id='revsub',date=date_today() + datetime.timedelta(days=20))
        group = GroupFactory()
        plain_session = SessionFactory(meeting=meeting, group=group)
        named_session = SessionFactory(meeting=meeting, group=group, name='I Got a Name')
        for doc_type_id in ('agenda', 'minutes', 'slides', 'draft'):
            # Set up sessions materials that will have distinct URLs for each session.
            # This depends on settings.MEETING_DOC_HREFS and may need updating if that changes.
            SessionPresentationFactory(
                session=plain_session,
                document__type_id=doc_type_id,
                document__uploaded_filename=f'upload-{doc_type_id}-plain',
                document__external_url=f'external_url-{doc_type_id}-plain',
            )
            SessionPresentationFactory(
                session=named_session,
                document__type_id=doc_type_id,
                document__uploaded_filename=f'upload-{doc_type_id}-named',
                document__external_url=f'external_url-{doc_type_id}-named',
            )

        url = urlreverse('ietf.meeting.views.materials', kwargs={'num': meeting.number})
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)

        plain_label = q(f'div#{group.acronym}')
        self.assertEqual(plain_label.text(), group.acronym)
        plain_row = plain_label.closest('tr')
        self.assertTrue(plain_row)

        named_label = q(f'div#{slugify(named_session.name)}')
        self.assertEqual(named_label.text(), named_session.name)
        named_row = named_label.closest('tr')
        self.assertTrue(named_row)

        for material in (sp.document for sp in plain_session.presentations.all()):
            if material.type_id == 'draft':
                expected_url = urlreverse(
                    'ietf.doc.views_doc.document_main',
                    kwargs={'name': material.name},
                )
            else:
                expected_url = material.get_href(meeting)
            self.assertTrue(plain_row.find(f'a[href="{expected_url}"]'))
            self.assertFalse(named_row.find(f'a[href="{expected_url}"]'))

        for material in (sp.document for sp in named_session.presentations.all()):
            if material.type_id == 'draft':
                expected_url = urlreverse(
                    'ietf.doc.views_doc.document_main',
                    kwargs={'name': material.name},
                )
            else:
                expected_url = material.get_href(meeting)
            self.assertFalse(plain_row.find(f'a[href="{expected_url}"]'))
            self.assertTrue(named_row.find(f'a[href="{expected_url}"]'))

    @override_settings(MEETING_MATERIALS_SERVE_LOCALLY=True)
    def test_meeting_materials_non_utf8(self):
        meeting = make_meeting_test_data()
        session = Session.objects.filter(meeting=meeting, group__acronym="mars").first()
        doc = session.materials.get(type="minutes")
        self.write_materials_file(meeting,
                                  doc,
                                  "1. More work items underway\n\n2. The draft will be finished before next meeting\n\n - É",
                                  charset="iso-8859-1")
        url = urlreverse("ietf.meeting.views.materials_document",
                         kwargs=dict(num=meeting.number, document=session.minutes()))

        for accept, cont_type, content in [
                ('text/html,text/plain,text/markdown',  'text/html',     '<li>\n<p>More work items underway</p>\n</li>'),
                ('text/markdown,text/html,text/plain',  'text/markdown', '1. More work items underway'),
                ('text/plain,text/markdown, text/html', 'text/plain',    '1. More work items underway'),
                ('text/html',                           'text/html',     '<li>\n<p>More work items underway</p>\n</li>'),
                ('text/markdown',                       'text/markdown', '1. More work items underway'),
                ('text/plain',                          'text/plain',    '1. More work items underway'),
            ]:
            client = Client(HTTP_ACCEPT=accept)
            r = client.get(url)
            rtype = r['Content-Type'].split(';')[0]
            self.assertEqual(cont_type, rtype)
            self.assertContains(r, content)

    @override_settings(MEETING_MATERIALS_SERVE_LOCALLY=True)
    def do_test_materials(self, meeting, session):

        self.write_materials_files(meeting, session)
        
        # session agenda
        document = session.agenda()
        url = urlreverse("ietf.meeting.views.materials_document",
                                       kwargs=dict(num=meeting.number, document=document))
        r = self.client.get(url)
        if r.status_code != 200:
            q = PyQuery(r.content)
            debug.show('q(".alert").text()')
        self.assertContains(r, "1. WG status")

        # session minutes
        url = urlreverse("ietf.meeting.views.materials_document",
                         kwargs=dict(num=meeting.number, document=session.minutes()))
        r = self.client.get(url)
        self.assertContains(r, "1. More work items underway")
        
        
        cont_disp = r.headers.get('content-disposition', ('Content-Disposition', ''))[1]
        cont_disp = re.split('; ?', cont_disp)
        cont_disp_settings = dict( e.split('=', 1) for e in cont_disp if '=' in e )
        filename = cont_disp_settings.get('filename', '').strip('"')
        if filename.endswith('.md'):
            for accept, cont_type, content in [
                    ('text/html,text/plain,text/markdown',  'text/html',     '<li>\n<p>More work items underway</p>\n</li>'),
                    ('text/markdown,text/html,text/plain',  'text/markdown', '1. More work items underway'),
                    ('text/plain,text/markdown, text/html', 'text/plain',    '1. More work items underway'),
                    ('text/html',                           'text/html',     '<li>\n<p>More work items underway</p>\n</li>'),
                    ('text/markdown',                       'text/markdown', '1. More work items underway'),
                    ('text/plain',                          'text/plain',    '1. More work items underway'),
                ]:
                client = Client(HTTP_ACCEPT=accept)
                r = client.get(url)
                rtype = r['Content-Type'].split(';')[0]
                self.assertEqual(cont_type, rtype)
                self.assertContains(r, content)

        # test with explicit meeting number in url
        if meeting.number.isdigit():
            url = urlreverse("ietf.meeting.views.materials", kwargs=dict(num=meeting.number))
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)
            q = PyQuery(r.content)
            row = q('#content #%s' % str(session.group.acronym)).closest("tr")
            self.assertTrue(row.find('a:contains("Agenda")'))
            self.assertTrue(row.find('a:contains("Minutes")'))
            self.assertTrue(row.find('a:contains("Slideshow")'))
            self.assertFalse(row.find("a:contains(\"Bad Slideshow\")"))

            # test with no meeting number in url
            # Add various group sessions
            groups = []
            parent_groups = [
                    GroupFactory.create(type_id="area", acronym="gen"),
                    GroupFactory.create(acronym="iab"),
                    GroupFactory.create(acronym="irtf"),
                    ]
            for parent in parent_groups:
                groups.append(GroupFactory.create(parent=parent))
            for acronym in ["rsab", "edu"]:
                groups.append(GroupFactory.create(acronym=acronym))
            for group in groups:
                SessionFactory(meeting=meeting, group=group)
            self.write_materials_files(meeting, session)
            url = urlreverse("ietf.meeting.views.materials", kwargs=dict())
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)
            q = PyQuery(r.content)
            row = q('#content #%s' % str(session.group.acronym)).closest("tr")
            self.assertTrue(row.find('a:contains("Agenda")'))
            self.assertTrue(row.find('a:contains("Minutes")'))
            self.assertTrue(row.find('a:contains("Slideshow")'))
            self.assertFalse(row.find("a:contains(\"Bad Slideshow\")"))
            # test for different sections
            sections = ["plenaries", "gen", "iab", "editorial", "irtf", "training"]
            for section in sections:
                self.assertEqual(len(q(f"#{section}")), 1, f"{section} section should exists in proceedings")

            # test with a loggged-in wg chair
            self.client.login(username="marschairman", password="marschairman+password")
            url = urlreverse("ietf.meeting.views.materials", kwargs=dict(num=meeting.number))
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)
            q = PyQuery(r.content)
            row = q('#content #%s' % str(session.group.acronym)).closest("tr")
            self.assertTrue(row.find('a:contains("Agenda")'))
            self.assertTrue(row.find('a:contains("Minutes")'))
            self.assertTrue(row.find('a:contains("Slideshow")'))
            self.assertFalse(row.find("a:contains(\"Bad Slideshow\")"))
            self.assertTrue(row.find('a:contains("Edit materials")'))
            # FIXME: missing tests of .pdf/.tar generation (some code can
            # probably be lifted from similar tests in iesg/tests.py)

            # document-specific urls
            for doc in session.materials.exclude(states__slug='deleted'):
                url = urlreverse('ietf.meeting.views.materials_document', kwargs=dict(num=meeting.number, document=doc.name))
                r = self.client.get(url)
                self.assertEqual(unicontent(r), doc.text())

    def test_materials_has_edit_links(self):
        meeting = make_meeting_test_data()
        url = urlreverse("ietf.meeting.views.materials", kwargs=dict(num=meeting.number))
        r = self.client.get(url)
        self.assertNotContains(r, 'Edit materials', status_code=200)

        # mars chairman can edit materials for mars group
        self.client.login(username='marschairman', password='marschairman+password')
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content.decode())
        edit_url = urlreverse(
            'ietf.meeting.views.session_details',
            kwargs={'num': meeting.number, 'acronym': 'mars'},
        )
        self.assertEqual(len(q(f'a[href^="{edit_url}"]')), 1, 'Link to mars session_details for mars chairman')
        for acro in ['ietf', 'ames']:  # other groups with materials
            edit_url = urlreverse(
                'ietf.meeting.views.session_details',
                kwargs={'num': meeting.number, 'acronym': acro},
            )
            self.assertEqual(len(q(f'a[href^="{edit_url}"]')), 0, f'No link to {acro} session_details for mars chairman')

        # secretary can edit all groups
        self.client.login(username='secretary', password='secretary+password')
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content.decode())
        for acro in ['mars', 'ames']:  # wgs
            edit_url = urlreverse(
                'ietf.meeting.views.session_details',
                kwargs={'num': meeting.number, 'acronym': acro},
            )
            self.assertEqual(len(q(f'a[href^="{edit_url}"]')), 1, f'Link to session_details page for {acro}')
        # The IETF Plenary has a "#sessionX" tacked on to the edit url to differentiate from other sessions,
        # so test it separately. Not bothering to check the exact session pk in detail.
        edit_url = urlreverse(
            'ietf.meeting.views.session_details',
            kwargs={'num': meeting.number, 'acronym': 'ietf'},
        )
        self.assertEqual(len(q(f'a[href^="{edit_url}#session"]')), 1, f'Link to session_details page for {acro}')

    def test_materials_document_extension_choice(self):
        def _url(**kwargs):
            return urlreverse("ietf.meeting.views.materials_document", kwargs=kwargs)

        presentation = SessionPresentationFactory(
            document__rev="00",
            document__name="slides-whatever",
            document__uploaded_filename="slides-whatever-00.txt",
            document__type_id="slides",
            document__states=(("reuse_policy", "single"),)
        )
        session = presentation.session
        meeting = session.meeting
        # This is not a realistic set of files to exist, but is useful for testing. Normally,
        # we'd have _either_ txt, pdf, or pptx + pdf.
        self.write_materials_file(meeting, presentation.document, "Hi I'm a txt", with_ext=".txt")
        self.write_materials_file(meeting, presentation.document, "Hi I'm a pptx", with_ext=".pptx")

        # with no rev, prefers the uploaded_filename
        r = self.client.get(_url(document="slides-whatever", num=meeting.number))  # no rev
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content.decode(), "Hi I'm a txt")
        
        # with a rev, prefers pptx because it comes first alphabetically
        r = self.client.get(_url(document="slides-whatever-00", num=meeting.number))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content.decode(), "Hi I'm a pptx")

        # now create a pdf
        self.write_materials_file(meeting, presentation.document, "Hi I'm a pdf", with_ext=".pdf")

        # with no rev, still prefers uploaded_filename
        r = self.client.get(_url(document="slides-whatever", num=meeting.number))  # no rev
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content.decode(), "Hi I'm a txt")

        # pdf should be preferred with a rev
        r = self.client.get(_url(document="slides-whatever-00", num=meeting.number))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content.decode(), "Hi I'm a pdf")
        
        # and explicit extensions should, of course, be respected
        for ext in ["pdf", "pptx", "txt"]:
            r = self.client.get(_url(document="slides-whatever-00", num=meeting.number, ext=f".{ext}"))
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.content.decode(), f"Hi I'm a {ext}")
        
        # and 404 should come up if the ext is not found
        r = self.client.get(_url(document="slides-whatever-00", num=meeting.number, ext=".docx"))
        self.assertEqual(r.status_code, 404)

    def test_materials_editable_groups(self):
        meeting = make_meeting_test_data()
        
        self.client.login(username="marschairman", password="marschairman+password")
        r = self.client.get(urlreverse("ietf.meeting.views.materials_editable_groups", kwargs={'num':meeting.number}))
        self.assertContains(r, meeting.number)
        self.assertContains(r, "mars")
        self.assertNotContains(r, "No session requested")

        self.client.login(username="ad", password="ad+password")
        r = self.client.get(urlreverse("ietf.meeting.views.materials_editable_groups", kwargs={'num':meeting.number}))
        self.assertContains(r, meeting.number)
        self.assertContains(r, "frfarea")
        self.assertContains(r, "No session requested")

        self.client.login(username="plain",password="plain+password")
        r = self.client.get(urlreverse("ietf.meeting.views.materials_editable_groups", kwargs={'num':meeting.number}))
        self.assertContains(r, meeting.number)
        self.assertContains(r, "You cannot manage the meeting materials for any groups")

    @override_settings(MEETING_MATERIALS_SERVE_LOCALLY=True)
    def test_materials_name_endswith_hyphen_number_number(self):
        # be sure a shadowed filename without the hyphen does not interfere
        shadow = SessionPresentationFactory(
            document__name="slides-115-junk",
            document__type_id="slides",
            document__states=[("reuse_policy", "single")],
        )
        shadow.document.uploaded_filename = (
            f"{shadow.document.name}-{shadow.document.rev}.pdf"
        )
        shadow.document.save()
        # create the material we want to find for the test
        sp = SessionPresentationFactory(
            document__name="slides-115-junk-15",
            document__type_id="slides",
            document__states=[("reuse_policy", "single")],
        )
        sp.document.uploaded_filename = f"{sp.document.name}-{sp.document.rev}.pdf"
        sp.document.save()
        self.write_materials_file(
            sp.session.meeting, sp.document, "Fake slide contents rev 00"
        )

        # create rev 01
        sp.document.rev = "01"
        sp.document.uploaded_filename = f"{sp.document.name}-{sp.document.rev}.pdf"
        sp.document.save_with_history(
            [
                NewRevisionDocEvent.objects.create(
                    type="new_revision",
                    doc=sp.document,
                    rev=sp.document.rev,
                    by=Person.objects.get(name="(System)"),
                    desc=f"New version available: <b>{sp.document.name}-{sp.document.rev}.txt</b>",
                )
            ]
        )
        self.write_materials_file(
            sp.session.meeting, sp.document, "Fake slide contents rev 01"
        )
        url = urlreverse(
            "ietf.meeting.views.materials_document",
            kwargs=dict(document=sp.document.name, num=sp.session.meeting.number),
        )
        r = self.client.get(url)
        self.assertContains(
            r,
            "Fake slide contents rev 01",
            status_code=200,
            msg_prefix="Should return latest rev by default",
        )
        url = urlreverse(
            "ietf.meeting.views.materials_document",
            kwargs=dict(document=sp.document.name + "-00", num=sp.session.meeting.number),
        )
        r = self.client.get(url)
        self.assertContains(
            r,
            "Fake slide contents rev 00",
            status_code=200,
            msg_prefix="Should return existing version on request",
        )
        url = urlreverse(
            "ietf.meeting.views.materials_document",
            kwargs=dict(document=sp.document.name + "-02", num=sp.session.meeting.number),
        )
        r = self.client.get(url)
        self.assertEqual(r.status_code, 404, "Should not find nonexistent version")

    def test_important_dates(self):
        meeting=MeetingFactory(type_id='ietf')
        meeting.show_important_dates = True
        meeting.save()
        populate_important_dates(meeting)
        url = urlreverse('ietf.meeting.views.important_dates',kwargs={'num':meeting.number})
        r = self.client.get(url)
        self.assertContains(r, str(meeting.importantdate_set.first().date))
        idn = ImportantDateName.objects.filter(used=True).first()
        pre_date = meeting.importantdate_set.get(name=idn).date
        idn.default_offset_days -= 1
        idn.save()
        update_important_dates(meeting)
        post_date =  meeting.importantdate_set.get(name=idn).date
        self.assertEqual(pre_date, post_date+datetime.timedelta(days=1))

    def test_important_dates_ical(self):
        meeting = MeetingFactory(type_id='ietf')
        meeting.show_important_dates = True
        meeting.save()
        populate_important_dates(meeting)
        url = urlreverse('ietf.meeting.views.important_dates', kwargs={'num': meeting.number, 'output_format': 'ics'})
        r = self.client.get(url)
        for d in meeting.importantdate_set.all():
            self.assertContains(r, d.date.isoformat())

        updated = meeting.updated()
        self.assertIsNotNone(updated)
        expected_updated = updated.astimezone(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.assertContains(r, f"DTSTAMP:{expected_updated}")
        dtstamps_count = r.content.decode("utf-8").count(f"DTSTAMP:{expected_updated}")
        self.assertEqual(dtstamps_count, meeting.importantdate_set.count())

        # With default cached_updated, 1970-01-01
        with patch("ietf.meeting.models.Meeting.updated", return_value=None):
            r = self.client.get(url)
            for d in meeting.importantdate_set.all():
                self.assertContains(r, d.date.isoformat())

            expected_updated = "19700101T000000Z"
            self.assertContains(r, f"DTSTAMP:{expected_updated}")
            dtstamps_count = r.content.decode("utf-8").count(f"DTSTAMP:{expected_updated}")
            self.assertEqual(dtstamps_count, meeting.importantdate_set.count())

    def test_group_ical(self):
        meeting = make_meeting_test_data()
        s1 = Session.objects.filter(meeting=meeting, group__acronym="mars").first()
        a1 = s1.official_timeslotassignment()
        t1 = a1.timeslot
        # Create an extra session
        t2 = TimeSlotFactory.create(
            meeting=meeting,
            time=meeting.tz().localize(
                datetime.datetime.combine(meeting.date, datetime.time(11, 30))
            )
        )
        s2 = SessionFactory.create(meeting=meeting, group=s1.group, add_to_schedule=False)
        SchedTimeSessAssignment.objects.create(timeslot=t2, session=s2, schedule=meeting.schedule)
        #
        url = urlreverse('ietf.meeting.views.agenda_ical', kwargs={'num':meeting.number, 'acronym':s1.group.acronym, })
        r = self.client.get(url)
        assert_ical_response_is_valid(self,
                                      r,
                                      expected_event_summaries=['mars - Martian Special Interest Group'],
                                      expected_event_count=2)
        self.assertContains(r, t1.local_start_time().strftime('%Y%m%dT%H%M%S'))
        self.assertContains(r, t2.local_start_time().strftime('%Y%m%dT%H%M%S'))
        #
        url = urlreverse('ietf.meeting.views.agenda_ical', kwargs={'num':meeting.number, 'session_id':s1.id, })
        r = self.client.get(url)
        assert_ical_response_is_valid(self, r,
                                      expected_event_summaries=['mars - Martian Special Interest Group'],
                                      expected_event_count=1)
        self.assertContains(r, t1.local_start_time().strftime('%Y%m%dT%H%M%S'))
        self.assertNotContains(r, t2.local_start_time().strftime('%Y%m%dT%H%M%S'))

    def test_parse_agenda_filter_params(self):
        def _r(show=(), hide=(), showtypes=(), hidetypes=()):
            """Helper to create expected result dict"""
            return dict(show=set(show), hide=set(hide), showtypes=set(showtypes), hidetypes=set(hidetypes))

        self.assertIsNone(parse_agenda_filter_params(QueryDict('')))

        # test valid combos (not exhaustive)
        for qstr, expected in (
            ('show=', _r()), ('hide=', _r()), ('showtypes=', _r()), ('hidetypes=', _r()),
            ('show=x', _r(show=['x'])), ('hide=x', _r(hide=['x'])),
            ('showtypes=x', _r(showtypes=['x'])), ('hidetypes=x', _r(hidetypes=['x'])),
            ('show=x,y,z', _r(show=['x','y','z'])),
            ('hide=x,y,z', _r(hide=['x','y','z'])),
            ('showtypes=x,y,z', _r(showtypes=['x','y','z'])),
            ('hidetypes=x,y,z', _r(hidetypes=['x','y','z'])),
            ('show=a&hide=a', _r(show=['a'], hide=['a'])),
            ('show=a&hide=b', _r(show=['a'], hide=['b'])),
            ('show=a&hide=b&showtypes=c&hidetypes=d', _r(show=['a'], hide=['b'], showtypes=['c'], hidetypes=['d'])),
        ):
            self.assertEqual(
                parse_agenda_filter_params(QueryDict(qstr)),
                expected,
                'Parsed "%s" incorrectly' % qstr,
            )

    def do_ical_filter_test(self, meeting, querystring, expected_session_summaries):
        url = urlreverse('ietf.meeting.views.agenda_ical', kwargs={'num':meeting.number})
        r = self.client.get(url + querystring)
        self.assertEqual(r.status_code, 200)
        assert_ical_response_is_valid(self,
                                      r,
                                      expected_event_summaries=expected_session_summaries,
                                      expected_event_count=len(expected_session_summaries))

    def test_ical_filter(self):
        # Just a quick check of functionality - permutations tested via tests_js.AgendaTests
        meeting = make_meeting_test_data()
        self.do_ical_filter_test(
            meeting,
            querystring='',
            expected_session_summaries=[
                'Morning Break',
                'Registration',
                'IETF Plenary',
                'ames - Asteroid Mining Equipment Standardization Group',
                'mars - Martian Special Interest Group',
            ]
        )
        self.do_ical_filter_test(
            meeting,
            querystring='?show=plenary,secretariat,ames&hide=admin',
            expected_session_summaries=[
                'Morning Break',
                'IETF Plenary',
                'ames - Asteroid Mining Equipment Standardization Group',
            ]
        )

    def build_session_setup(self):
        # This setup is intentionally unusual - the session has one draft attached as a session presentation,
        # but lists a different on in its agenda. The expectation is that the pdf and tgz views will return both.
        session = SessionFactory(group__type_id='wg',meeting__type_id='ietf')
        draft1 = WgDraftFactory(group=session.group)
        session.presentations.create(document=draft1)
        draft2 = WgDraftFactory(group=session.group)
        agenda = DocumentFactory(type_id='agenda',group=session.group, uploaded_filename='agenda-%s-%s' % (session.meeting.number,session.group.acronym), states=[('agenda','active')])
        session.presentations.create(document=agenda)
        self.write_materials_file(session.meeting, session.materials.get(type="agenda"),
                                  "1. WG status (15 minutes)\n\n2. Status of %s\n\n" % draft2.name)
        filenames = []
        for d in (draft1, draft2):
            file,_ = submission_file(name_in_doc=f'{d.name}-00',name_in_post=f'{d.name}-00.txt',templatename='test_submission.txt',group=session.group)
            filename = os.path.join(d.get_file_path(),file.name)
            with io.open(filename,'w') as draftbits:
                draftbits.write(file.getvalue())
            filenames.append(filename)
        self.assertEqual( len(session_draft_list(session.meeting.number,session.group.acronym)), 2)
        return (session, filenames)

    def test_session_draft_tarfile(self):
        session, filenames = self.build_session_setup()
        try:
            url = urlreverse('ietf.meeting.views.session_draft_tarfile', kwargs={'num':session.meeting.number,'acronym':session.group.acronym})
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get('Content-Type'), 'application/octet-stream')
        finally:
            for filename in filenames:
                os.unlink(filename)

    @skipIf(skip_pdf_tests, skip_message)
    @skip_coverage
    def test_session_draft_pdf(self):
        session, filenames = self.build_session_setup()
        try:
            url = urlreverse('ietf.meeting.views.session_draft_pdf', kwargs={'num':session.meeting.number,'acronym':session.group.acronym})
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get('Content-Type'), 'application/pdf')
        finally:
            for filename in filenames:
                os.unlink(filename)

    def test_current_materials(self):
        url = urlreverse('ietf.meeting.views.current_materials')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)
        MeetingFactory(type_id='ietf', date=date_today())
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)

    def test_edit_schedule_properties(self):
        self.client.login(username='secretary',password='secretary+password')
        url = urlreverse('ietf.meeting.views.edit_schedule_properties',kwargs={'owner':'does@notexist.example','name':'doesnotexist','num':00})
        response = self.client.get(url)
        self.assertEqual(response.status_code,404)
        self.client.logout()
        schedule = ScheduleFactory(meeting__type_id='ietf',visible=False,public=False)
        url = urlreverse('ietf.meeting.views.edit_schedule_properties',kwargs={'owner':schedule.owner.email(),'name':schedule.name,'num':schedule.meeting.number})
        response = self.client.get(url)
        self.assertEqual(response.status_code,302)
        self.client.login(username='secretary',password='secretary+password')
        response = self.client.get(url)
        self.assertEqual(response.status_code,200)

        new_base = Schedule.objects.create(name="newbase", owner=schedule.owner, meeting=schedule.meeting)
        response = self.client.post(url, {
                'name': 'some-other-name',
                'visible':True,
                'public':True,
                'notes': "New Notes",
                'base': new_base.pk,
            }
        )
        self.assertNoFormPostErrors(response)
        self.assertRedirects(
            response,
            urlreverse(
                'ietf.meeting.views.edit_meeting_schedule',
                kwargs={'num': schedule.meeting.number, 'owner': schedule.owner.email(), 'name': 'some-other-name'}
            ),
        )
        schedule.refresh_from_db()
        self.assertTrue(schedule.visible)
        self.assertTrue(schedule.public)
        self.assertEqual(schedule.notes, "New Notes")
        self.assertEqual(schedule.base_id, new_base.pk)
        self.assertEqual(schedule.name, 'some-other-name')

    def test_agenda_by_type_ics(self):
        session=SessionFactory(meeting__type_id='ietf',type_id='lead')
        url = urlreverse('ietf.meeting.views.agenda_by_type_ics',kwargs={'num':session.meeting.number,'type':'lead'})
        login_testing_unauthorized(self,"secretary",url)
        response = self.client.get(url)
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.get('Content-Type'), 'text/calendar')

    def test_cancelled_ics(self):
        session=SessionFactory(meeting__type_id='ietf',status_id='canceled')
        url = urlreverse('ietf.meeting.views.agenda_ical', kwargs=dict(num=session.meeting.number))
        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        self.assertIn('STATUS:CANCELLED',unicontent(r))
        self.assertNotIn('STATUS:CONFIRMED',unicontent(r))

    def test_session_materials(self):
        meeting = make_meeting_test_data()
        session = Session.objects.filter(meeting=meeting, group__acronym="mars").first()

        url = urlreverse('ietf.meeting.views.session_materials', kwargs=dict(session_id=session.pk))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)

        agenda_div = q('div.agenda-frame')
        self.assertIsNotNone(agenda_div)
        self.assertEqual(agenda_div.attr('data-src'), session.agenda().get_href())

        minutes_div = q('div.minutes-frame')
        self.assertIsNotNone(minutes_div)
        self.assertEqual(minutes_div.attr('data-src'), session.minutes().get_href())

        # Make sure undeleted slides are present and deleted slides are not
        not_deleted_slides = session.materials.filter(
            type='slides'
        ).exclude(
            states__type__slug='slides',states__slug='deleted'
        )
        self.assertGreater(not_deleted_slides.count(), 0)  # make sure this isn't a pointless test

        deleted_slides = session.materials.filter(
            type='slides', states__type__slug='slides', states__slug='deleted'
        )
        self.assertGreater(deleted_slides.count(), 0)  # make sure this isn't a pointless test

        # live slides should be found
        for slide in not_deleted_slides:
            self.assertTrue(q('ul li a:contains("%s")' % slide.title))

        # deleted slides should not be found
        for slide in deleted_slides:
            self.assertFalse(q('ul li a:contains("%s")' % slide.title))

    def test_meetinghost_logo(self):
        host = MeetingHostFactory()
        url = urlreverse('ietf.meeting.views_proceedings.meetinghost_logo',kwargs=dict(host_id=host.pk,num=host.meeting.number))
        r = self.client.get(url)
        self.assertIs(type(r),FileResponse)


@override_settings(MEETING_SESSION_LOCK_TIME=datetime.timedelta(minutes=10))
class EditMeetingScheduleTests(TestCase):
    """Tests of the meeting editor view

    This has tests in tests_js.py as well.
    """
    def test_room_grouping(self):
        """Blocks of rooms in the editor should have identical timeslots"""
        # set up a meeting, but we'll construct our own timeslots/rooms
        meeting = MeetingFactory(type_id='ietf', populate_schedule=False)
        sched = ScheduleFactory(meeting=meeting)

        # Make groups of rooms with timeslots identical within a group, distinct between groups
        times = [
            [datetime.time(11,0), datetime.time(12,0), datetime.time(13,0)],
            [datetime.time(11,0), datetime.time(12,0), datetime.time(13,0)],  # same times, but durations will differ
            [datetime.time(11,30), datetime.time(12, 0), datetime.time(13,0)],  # different time
            [datetime.time(12,0)],  # different number of timeslots
        ]
        durations = [
            [30, 60, 90],
            [60, 60, 90],
            [30, 60, 90],
            [60],
        ]
        # check that times and durations are same-sized arrays
        self.assertEqual(len(times), len(durations))
        for time_row, duration_row in zip(times, durations):
            self.assertEqual(len(time_row), len(duration_row))

        # Create an array of room groups, each with rooms_per_group Rooms in it.
        # Assign TimeSlots according to the times/durations above to each Room.
        room_groups = []
        rooms_in_group = 1  # will be incremented with each group
        for time_row, duration_row in zip(times, durations):
            room_groups.append(RoomFactory.create_batch(rooms_in_group, meeting=meeting))
            rooms_in_group += 1  # put a different number of rooms in each group to help identify errors in grouping
            for time, duration in zip(time_row, duration_row):
                for room in room_groups[-1]:
                    TimeSlotFactory(
                        meeting=meeting,
                        location=room,
                        time=meeting.tz().localize(
                            datetime.datetime.combine(meeting.date, time)
                        ),
                        duration=datetime.timedelta(minutes=duration),
                    )

        # Now retrieve the edit meeting schedule page
        url = urlreverse('ietf.meeting.views.edit_meeting_schedule',
                         kwargs=dict(num=meeting.number, owner=sched.owner.email(), name=sched.name))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        q = PyQuery(r.content)
        day_divs = q('div.day')
        # There's only one day with TimeSlots. This means there will be two divs with class 'day':
        # the first is the room label column, the second is the TimeSlot grid.
        # Using eq() instead of [] gives us PyQuery objects instead of Elements
        label_divs = day_divs.eq(0).find('div.room-group')
        self.assertEqual(len(label_divs), len(room_groups))
        room_group_divs = day_divs.eq(1).find('div.room-group')
        self.assertEqual(len(room_group_divs), len(room_groups))
        for rg, l_div, rg_div in zip(
                room_groups,
                label_divs.items(),  # items() gives us PyQuery objects
                room_group_divs.items(),  # items() gives us PyQuery objects
        ):
            # Check that room labels are correctly grouped
            self.assertCountEqual(
                [div.text() for div in l_div.find('div.room-name').items()],
                [room.name for room in rg],
            )

            # And that the time labels are correct. Just check that the individual timeslot labels agree with
            # the time-header above each room group.
            time_header_labels = rg_div.find('div.time-header div.time-label').text()
            timeslot_rows = rg_div.find('div.timeslots')
            for row in timeslot_rows.items():
                time_labels = row.find('div.time-label div:not(.past-flag)').text()
                self.assertEqual(time_labels, time_header_labels)

    def test_bof_session_tag(self):
        """Sessions for BOF groups should be marked as such"""
        meeting = MeetingFactory(type_id='ietf')

        non_bof_session = SessionFactory(meeting=meeting)
        bof_session = SessionFactory(meeting=meeting, group__state_id='bof')

        url = urlreverse('ietf.meeting.views.edit_meeting_schedule',
                         kwargs=dict(num=meeting.number))

        self.client.login(username='secretary', password='secretary+password')
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        q = PyQuery(r.content)
        self.assertEqual(len(q('#session{} .bof-tag'.format(non_bof_session.pk))), 0,
                         'Non-BOF session should not be tagged as a BOF session')

        bof_tags = q('#session{} .bof-tag'.format(bof_session.pk))
        self.assertEqual(len(bof_tags), 1,
                         'BOF session should have one BOF session tag')
        self.assertIn('BOF', bof_tags.eq(0).text(),
                      'BOF tag should contain text "BOF"')

    def _setup_for_swap_timeslots(self):
        """Create a meeting, rooms, and schedule for swap_timeslots testing

        Creates two groups of rooms with disjoint timeslot sets, modeling the room grouping in
        the edit_meeting_schedule view.
        """
        # Meeting must be in the future so it can be edited
        meeting = MeetingFactory(
            type_id='ietf',
            date=date_today() + datetime.timedelta(days=7),
            populate_schedule=False,
        )
        meeting.schedule = ScheduleFactory(meeting=meeting)
        meeting.save()

        # Create room groups
        room_groups = [
            RoomFactory.create_batch(2, meeting=meeting),
            RoomFactory.create_batch(2, meeting=meeting),
        ]

        # Set up different sets of timeslots
        # Work with t0 in UTC for arithmetic. This does not change the results but is cleaner if someone looks
        # at intermediate results which may be misleading until passed through tz.normalize().
        t0 = meeting.tz().localize(
            datetime.datetime.combine(meeting.date, datetime.time(11, 0))
        ).astimezone(pytz.utc)
        dur = datetime.timedelta(hours=2)
        for room in room_groups[0]:
            TimeSlotFactory(meeting=meeting, location=room, duration=dur, time=t0)
            TimeSlotFactory(meeting=meeting, location=room, duration=dur, time=t0 + datetime.timedelta(days=1, hours=2))
            TimeSlotFactory(meeting=meeting, location=room, duration=dur, time=t0 + datetime.timedelta(days=2, hours=4))

        for room in room_groups[1]:
            TimeSlotFactory(meeting=meeting, location=room, duration=dur, time=t0 + datetime.timedelta(hours=1))
            TimeSlotFactory(meeting=meeting, location=room, duration=dur, time=t0 + datetime.timedelta(days=1, hours=3))
            TimeSlotFactory(meeting=meeting, location=room, duration=dur, time=t0 + datetime.timedelta(days=2, hours=5))

        # And now put sessions in the timeslots
        for ts in meeting.timeslot_set.all():
            SessionFactory(
                meeting=meeting,
                name=str(ts.pk),  # label to identify where it started
                add_to_schedule=False,
            ).timeslotassignments.create(
                timeslot=ts,
                schedule=meeting.schedule,
            )
        return meeting, room_groups

    def test_swap_timeslots(self):
        """Schedule timeslot groups should swap properly

        This tests the case currently exercised by the UI - where the rooms are grouped according to
        entirely equivalent sets of timeslots. Thus, there is always a matching timeslot for every (or no)
        room as long as the rooms parameter to the ajax call includes only one group.
        """
        meeting, room_groups = self._setup_for_swap_timeslots()

        url = urlreverse('ietf.meeting.views.edit_meeting_schedule', kwargs=dict(num=meeting.number))
        username = meeting.schedule.owner.user.username
        self.client.login(username=username, password=username + '+password')

        # Swap group 0's first and last sessions
        r = self.client.post(
            url,
            dict(
                action='swaptimeslots',
                origin_timeslot=str(room_groups[0][0].timeslot_set.first().pk),
                target_timeslot=str(room_groups[0][0].timeslot_set.last().pk),
                rooms=','.join([str(room.pk) for room in room_groups[0]]),
            )
        )
        self.assertEqual(r.status_code, 302)

        # Validate results
        for index, room in enumerate(room_groups[0]):
            timeslots = list(room.timeslot_set.all())
            self.assertEqual(timeslots[0].session.name, str(timeslots[-1].pk),
                             'Session from last timeslot in room (0, {}) should now be in first'.format(index))
            self.assertEqual(timeslots[-1].session.name, str(timeslots[0].pk),
                             'Session from first timeslot in room (0, {}) should now be in last'.format(index))
            self.assertEqual(
                [ts.session.name for ts in timeslots[1:-1]],
                [str(ts.pk) for ts in timeslots[1:-1]],
                'Sessions in middle timeslots should be unchanged'
            )
        for index, room in enumerate(room_groups[1]):
            timeslots = list(room.timeslot_set.all())
            self.assertFalse(
                any(ts.session is None for ts in timeslots),
                "Sessions in other room group's timeslots should still be assigned"
            )
            self.assertEqual(
                [ts.session.name for ts in timeslots],
                [str(ts.pk) for ts in timeslots],
                "Sessions in other room group's timeslots should be unchanged"
            )

    def test_swap_timeslots_denies_past(self):
        """Swapping past timeslots is not allowed for an official schedule"""
        meeting, room_groups = self._setup_for_swap_timeslots()
        # clone official schedule as an unofficial schedule
        Schedule.objects.create(
            name='unofficial',
            owner=meeting.schedule.owner,
            meeting=meeting,
            base=meeting.schedule.base,
            origin=meeting.schedule,
        )


        official_url = urlreverse('ietf.meeting.views.edit_meeting_schedule', kwargs=dict(num=meeting.number))
        unofficial_url = urlreverse('ietf.meeting.views.edit_meeting_schedule',
                                    kwargs=dict(num=meeting.number,
                                                owner=str(meeting.schedule.owner.email()),
                                                name='unofficial'))
        username = meeting.schedule.owner.user.username
        self.client.login(username=username, password=username + '+password')

        # Swap group 0's first and last sessions, first in the past
        right_now = self._right_now_in(meeting.tz())
        for room in room_groups[0]:
            ts = room.timeslot_set.last()
            ts.time = right_now - datetime.timedelta(minutes=5)
            ts.save()
        # timeslot_set is ordered by -time, so check that we know which is past/future
        self.assertTrue(room_groups[0][0].timeslot_set.last().time < right_now)
        self.assertTrue(room_groups[0][0].timeslot_set.first().time > right_now)
        post_data = dict(
            action='swaptimeslots',
            origin_timeslot=str(room_groups[0][0].timeslot_set.first().pk),
            target_timeslot=str(room_groups[0][0].timeslot_set.last().pk),
            rooms=','.join([str(room.pk) for room in room_groups[0]]),
        )
        r = self.client.post(official_url, post_data)
        self.assertContains(r, "Can't swap these timeslots.", status_code=400)

        # same request should succeed for an unofficial schedule
        r = self.client.post(unofficial_url, post_data)
        self.assertEqual(r.status_code, 302)

        # now with origin/target reversed
        post_data = dict(
            action='swaptimeslots',
            origin_timeslot=str(room_groups[0][0].timeslot_set.last().pk),
            target_timeslot=str(room_groups[0][0].timeslot_set.first().pk),
            rooms=','.join([str(room.pk) for room in room_groups[0]]),
        )
        r = self.client.post(official_url, post_data)
        self.assertContains(r, "Can't swap these timeslots.", status_code=400)

        # same request should succeed for an unofficial schedule
        r = self.client.post(unofficial_url, post_data)
        self.assertEqual(r.status_code, 302)

        # now with the "past" timeslot less than MEETING_SESSION_LOCK_TIME in the future
        for room in room_groups[0]:
            ts = room.timeslot_set.last()
            ts.time = right_now + datetime.timedelta(minutes=9)  # must be < MEETING_SESSION_LOCK_TIME
            ts.save()
        self.assertTrue(room_groups[0][0].timeslot_set.last().time < right_now + settings.MEETING_SESSION_LOCK_TIME)
        self.assertTrue(room_groups[0][0].timeslot_set.first().time > right_now + settings.MEETING_SESSION_LOCK_TIME)
        post_data = dict(
            action='swaptimeslots',
            origin_timeslot=str(room_groups[0][0].timeslot_set.first().pk),
            target_timeslot=str(room_groups[0][0].timeslot_set.last().pk),
            rooms=','.join([str(room.pk) for room in room_groups[0]]),
        )
        r = self.client.post(official_url, post_data)
        self.assertContains(r, "Can't swap these timeslots.", status_code=400)

        # now with both in the past
        for room in room_groups[0]:
            ts = room.timeslot_set.last()
            ts.time = right_now - datetime.timedelta(minutes=5)
            ts.save()
            ts = room.timeslot_set.first()
            ts.time = right_now - datetime.timedelta(hours=1)
            ts.save()
        past_slots = room_groups[0][0].timeslot_set.filter(time__lt=right_now)
        self.assertEqual(len(past_slots), 2, 'Need two timeslots in the past!')
        post_data = dict(
            action='swaptimeslots',
            origin_timeslot=str(past_slots[0].pk),
            target_timeslot=str(past_slots[1].pk),
            rooms=','.join([str(room.pk) for room in room_groups[0]]),
        )
        r = self.client.post(official_url, post_data)
        self.assertContains(r, "Can't swap these timeslots.", status_code=400)

        # same request should succeed for an unofficial schedule
        r = self.client.post(unofficial_url, post_data)
        self.assertEqual(r.status_code, 302)

    def test_swap_timeslots_handles_unmatched(self):
        """Sessions in unmatched timeslots should be unassigned when swapped

        This more generally tests the back end by exercising the situation where a timeslot in the
        affected rooms does not have an equivalent timeslot target. This is not used by the UI as of
        now (2021-06-22), but should function correctly.
        """
        meeting, room_groups = self._setup_for_swap_timeslots()

        # Remove a timeslot and session from only one room in group 0
        ts_to_remove = room_groups[0][1].timeslot_set.last()
        ts_to_remove.session.delete()
        ts_to_remove.delete()  # our object still exists but has no db object

        # Add a matching timeslot to group 1 so we can be sure it's being ignored.
        # If not, this session will be unassigned when we swap timeslots on group 0.
        new_ts = TimeSlotFactory(
            meeting=meeting,
            location=room_groups[1][0],
            duration=ts_to_remove.duration,
            time=ts_to_remove.time,
        )
        SessionFactory(
            meeting=meeting,
            name=str(new_ts.pk),
            add_to_schedule=False,
        ).timeslotassignments.create(
            timeslot=new_ts,
            schedule=meeting.schedule,
        )

        url = urlreverse('ietf.meeting.views.edit_meeting_schedule', kwargs=dict(num=meeting.number))
        username = meeting.schedule.owner.user.username
        self.client.login(username=username, password=username + '+password')

        # Now swap between first and last timeslots in group 0
        r = self.client.post(
            url,
            dict(
                action='swaptimeslots',
                origin_timeslot=str(room_groups[0][0].timeslot_set.first().pk),
                target_timeslot=str(room_groups[0][0].timeslot_set.last().pk),
                rooms=','.join([str(room.pk) for room in room_groups[0]]),
            )
        )
        self.assertEqual(r.status_code, 302)

        # Validate results
        for index, room in enumerate(room_groups[0]):
            timeslots = list(room.timeslot_set.all())
            if index == 1:
                # special case - this has no matching timeslot because we deleted it above
                self.assertIsNone(timeslots[0].session, 'Unmatched timeslot should be empty after swap')
                session_that_should_be_unassigned = Session.objects.get(name=str(timeslots[0].pk))
                self.assertEqual(session_that_should_be_unassigned.timeslotassignments.count(), 0,
                                 'Session that was in an unmatched timeslot should now be unassigned')
                # check from 2nd timeslot to the last since we deleted the original last timeslot
                self.assertEqual(
                    [ts.session.name for ts in timeslots[1:]],
                    [str(ts.pk) for ts in timeslots[1:]],
                    'Sessions in middle timeslots should be unchanged'
                )
            else:
                self.assertEqual(timeslots[0].session.name, str(timeslots[-1].pk),
                                 'Session from last timeslot in room (0, {}) should now be in first'.format(index))
                self.assertEqual(timeslots[-1].session.name, str(timeslots[0].pk),
                                 'Session from first timeslot in room (0, {}) should now be in last'.format(index))
                self.assertEqual(
                    [ts.session.name for ts in timeslots[1:-1]],
                    [str(ts.pk) for ts in timeslots[1:-1]],
                    'Sessions in middle timeslots should be unchanged'
                )

        # Still should have no effect on other rooms, even if they matched a timeslot
        for index, room in enumerate(room_groups[1]):
            timeslots = list(room.timeslot_set.all())
            self.assertFalse(
                any(ts.session is None for ts in timeslots),
                "Sessions in other room group's timeslots should still be assigned"
            )
            self.assertEqual(
                [ts.session.name for ts in timeslots],
                [str(ts.pk) for ts in timeslots],
                "Sessions in other room group's timeslots should be unchanged"
            )

    def test_swap_days_denies_past(self):
        """Swapping past days is not allowed for an official schedule"""
        meeting, room_groups = self._setup_for_swap_timeslots()
        # clone official schedule as an unofficial schedule
        Schedule.objects.create(
            name='unofficial',
            owner=meeting.schedule.owner,
            meeting=meeting,
            base=meeting.schedule.base,
            origin=meeting.schedule,
        )


        official_url = urlreverse('ietf.meeting.views.edit_meeting_schedule', kwargs=dict(num=meeting.number))
        unofficial_url = urlreverse('ietf.meeting.views.edit_meeting_schedule',
                                    kwargs=dict(num=meeting.number,
                                                owner=str(meeting.schedule.owner.email()),
                                                name='unofficial'))
        username = meeting.schedule.owner.user.username
        self.client.login(username=username, password=username + '+password')

        # Swap group 0's first and last sessions, first in the past
        right_now = self._right_now_in(meeting.tz())
        yesterday = right_now.date() - datetime.timedelta(days=1)
        day_before = right_now.date() - datetime.timedelta(days=2)
        for room in room_groups[0]:
            ts = room.timeslot_set.last()
            # Calculation keeps local clock time, shifted to a different day.
            ts.time = meeting.tz().localize(
                datetime.datetime.combine(
                    yesterday,
                    ts.time.astimezone(meeting.tz()).time()
                ),
            )
            ts.save()
        # timeslot_set is ordered by -time, so check that we know which is past/future
        self.assertTrue(room_groups[0][0].timeslot_set.last().time < right_now)
        self.assertTrue(room_groups[0][0].timeslot_set.first().time > right_now)
        post_data = dict(
            action='swapdays',
            source_day=yesterday.isoformat(),
            target_day=room_groups[0][0].timeslot_set.first().time.date().isoformat(),
        )
        r = self.client.post(official_url, post_data)
        self.assertContains(r, "Can't swap these days.", status_code=400)

        # same request should succeed for an unofficial schedule
        r = self.client.post(unofficial_url, post_data)
        self.assertEqual(r.status_code, 302)

        # now with origin/target reversed
        post_data = dict(
            action='swapdays',
            source_day=room_groups[0][0].timeslot_set.first().time.date().isoformat(),
            target_day=yesterday.isoformat(),
            rooms=','.join([str(room.pk) for room in room_groups[0]]),
        )
        r = self.client.post(official_url, post_data)
        self.assertContains(r, "Can't swap these days.", status_code=400)

        # same request should succeed for an unofficial schedule
        r = self.client.post(unofficial_url, post_data)
        self.assertEqual(r.status_code, 302)

        # now with both in the past
        for room in room_groups[0]:
            ts = room.timeslot_set.first()
            ts.time = meeting.tz().localize(
                datetime.datetime.combine(
                    day_before,
                    ts.time.astimezone(meeting.tz()).time(),
                )
            )
            ts.save()
        past_slots = room_groups[0][0].timeslot_set.filter(time__lt=right_now)
        self.assertEqual(len(past_slots), 2, 'Need two timeslots in the past!')
        post_data = dict(
            action='swapdays',
            source_day=yesterday.isoformat(),
            target_day=day_before.isoformat(),
        )
        r = self.client.post(official_url, post_data)
        self.assertContains(r, "Can't swap these days.", status_code=400)

        # same request should succeed for an unofficial schedule
        r = self.client.post(unofficial_url, post_data)
        self.assertEqual(r.status_code, 302)

    def _decode_json_response(self, r):
        try:
            return json.loads(r.content.decode())
        except json.JSONDecodeError as err:
            self.fail('Response was not valid JSON: {}'.format(err))

    @staticmethod
    def _right_now_in(tzinfo):
        right_now = timezone.now().astimezone(tzinfo)
        return right_now

    def test_assign_session(self):
        """Allow assignment to future timeslots only for official schedule"""
        meeting = MeetingFactory(
            type_id='ietf',
            date=(timezone.now() - datetime.timedelta(days=1)).date(),
            days=3,
        )
        right_now = self._right_now_in(meeting.tz())

        schedules = dict(
            official=meeting.schedule,
            unofficial=ScheduleFactory(meeting=meeting, owner=meeting.schedule.owner),
        )

        timeslots = dict(
            past=TimeSlotFactory(meeting=meeting, time=right_now - datetime.timedelta(hours=1)),
            future=TimeSlotFactory(meeting=meeting, time=right_now + datetime.timedelta(hours=1)),
        )

        url_for = lambda sched: urlreverse(
            'ietf.meeting.views.edit_meeting_schedule',
            kwargs=dict(
                num=meeting.number,
                owner=str(sched.owner.email()),
                name=sched.name,
            )
        )

        post_data = lambda ts: dict(
            action='assign',
            session=str(SessionFactory(meeting=meeting, add_to_schedule=False).pk),
            timeslot=str(ts.pk),
        )

        username = meeting.schedule.owner.user.username
        self.assertTrue(self.client.login(username=username, password=username + '+password'))

        # past timeslot, official schedule: reject
        r = self.client.post(url_for(schedules['official']), post_data(timeslots['past']))
        self.assertEqual(r.status_code, 400)
        self.assertEqual(
            self._decode_json_response(r),
            dict(success=False, error="Can't assign to this timeslot."),
        )

        # past timeslot, unofficial schedule: allow
        r = self.client.post(url_for(schedules['unofficial']), post_data(timeslots['past']))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(self._decode_json_response(r)['success'])

        # future timeslot, official schedule: allow
        r = self.client.post(url_for(schedules['official']), post_data(timeslots['future']))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(self._decode_json_response(r)['success'])

        # future timeslot, unofficial schedule: allow
        r = self.client.post(url_for(schedules['unofficial']), post_data(timeslots['future']))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(self._decode_json_response(r)['success'])

    def test_reassign_session(self):
        """Do not allow assignment of past sessions for official schedule"""
        meeting = MeetingFactory(
            type_id='ietf',
            date=(timezone.now() - datetime.timedelta(days=1)).date(),
            days=3,
        )
        right_now = self._right_now_in(meeting.tz())

        schedules = dict(
            official=meeting.schedule,
            unofficial=ScheduleFactory(meeting=meeting, owner=meeting.schedule.owner),
        )

        timeslots = dict(
            past=TimeSlotFactory(meeting=meeting, time=right_now - datetime.timedelta(hours=1)),
            other_past=TimeSlotFactory(meeting=meeting, time=right_now - datetime.timedelta(hours=2)),
            barely_future=TimeSlotFactory(meeting=meeting, time=right_now + datetime.timedelta(minutes=9)),
            future=TimeSlotFactory(meeting=meeting, time=right_now + datetime.timedelta(hours=1)),
            other_future=TimeSlotFactory(meeting=meeting, time=right_now + datetime.timedelta(hours=2)),
        )

        self.assertLess(
            timeslots['barely_future'].time - right_now,
            settings.MEETING_SESSION_LOCK_TIME,
            '"barely_future" timeslot is too far in the future. Check MEETING_SESSION_LOCK_TIME settings',
        )

        url_for = lambda sched: urlreverse(
            'ietf.meeting.views.edit_meeting_schedule',
            kwargs=dict(
                num=meeting.number,
                owner=str(sched.owner.email()),
                name=sched.name,
            )
        )

        def _new_session_in(timeslot, schedule):
            return SchedTimeSessAssignment.objects.create(
                schedule=schedule,
                session=SessionFactory(meeting=meeting, add_to_schedule=False),
                timeslot=timeslot,
            ).session

        post_data = lambda session, new_ts: dict(
            action='assign',
            session=str(session.pk),
            timeslot=str(new_ts.pk),
        )

        username = meeting.schedule.owner.user.username
        self.assertTrue(self.client.login(username=username, password=username + '+password'))

        # past session to past timeslot, official: not allowed
        session = _new_session_in(timeslots['past'], schedules['official'])
        r = self.client.post(url_for(schedules['official']), post_data(session, timeslots['other_past']))
        self.assertEqual(r.status_code, 400)
        self.assertEqual(
            self._decode_json_response(r),
            dict(success=False, error="Can't assign to this timeslot."),
        )
        session.delete()  # takes the SchedTimeSessAssignment with it

        # past session to future timeslot, official: not allowed
        session = _new_session_in(timeslots['past'], schedules['official'])
        r = self.client.post(url_for(schedules['official']), post_data(session, timeslots['future']))
        self.assertEqual(r.status_code, 400)
        self.assertEqual(
            self._decode_json_response(r),
            dict(success=False, error="Can't reassign this session."),
        )
        session.delete()  # takes the SchedTimeSessAssignment with it

        # future session to past, timeslot, official: not allowed
        session = _new_session_in(timeslots['future'], schedules['official'])
        r = self.client.post(url_for(schedules['official']), post_data(session, timeslots['past']))
        self.assertEqual(r.status_code, 400)
        self.assertEqual(
            self._decode_json_response(r),
            dict(success=False, error="Can't assign to this timeslot."),
        )
        session.delete()  # takes the SchedTimeSessAssignment with it

        # future session to future timeslot, unofficial: allowed
        session = _new_session_in(timeslots['future'], schedules['unofficial'])
        r = self.client.post(url_for(schedules['unofficial']), post_data(session, timeslots['other_future']))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(self._decode_json_response(r)['success'])
        session.delete()  # takes the SchedTimeSessAssignment with it

        # future session to barely future timeslot, official: not allowed
        session = _new_session_in(timeslots['future'], schedules['official'])
        r = self.client.post(url_for(schedules['official']), post_data(session, timeslots['barely_future']))
        self.assertEqual(r.status_code, 400)
        self.assertEqual(
            self._decode_json_response(r),
            dict(success=False, error="Can't assign to this timeslot."),
        )
        session.delete()  # takes the SchedTimeSessAssignment with it

        # future session to future timeslot, unofficial: allowed
        session = _new_session_in(timeslots['future'], schedules['unofficial'])
        r = self.client.post(url_for(schedules['unofficial']), post_data(session, timeslots['barely_future']))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(self._decode_json_response(r)['success'])
        session.delete()  # takes the SchedTimeSessAssignment with it

        # past session to past timeslot, unofficial: allowed
        session = _new_session_in(timeslots['past'], schedules['unofficial'])
        r = self.client.post(url_for(schedules['unofficial']), post_data(session, timeslots['other_past']))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(self._decode_json_response(r)['success'])
        session.delete()  # takes the SchedTimeSessAssignment with it

        # past session to future timeslot, unofficial: allowed
        session = _new_session_in(timeslots['past'], schedules['unofficial'])
        r = self.client.post(url_for(schedules['unofficial']), post_data(session, timeslots['future']))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(self._decode_json_response(r)['success'])
        session.delete()  # takes the SchedTimeSessAssignment with it

        # future session to past timeslot, unofficial: allowed
        session = _new_session_in(timeslots['future'], schedules['unofficial'])
        r = self.client.post(url_for(schedules['unofficial']), post_data(session, timeslots['past']))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(self._decode_json_response(r)['success'])
        session.delete()  # takes the SchedTimeSessAssignment with it

        # future session to future timeslot, unofficial: allowed
        session = _new_session_in(timeslots['future'], schedules['unofficial'])
        r = self.client.post(url_for(schedules['unofficial']), post_data(session, timeslots['other_future']))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(self._decode_json_response(r)['success'])
        session.delete()  # takes the SchedTimeSessAssignment with it

    def test_unassign_session(self):
        """Allow unassignment only of future timeslots for official schedule"""
        meeting = MeetingFactory(
            type_id='ietf',
            date=(timezone.now() - datetime.timedelta(days=1)).date(),
            days=3,
        )
        right_now = self._right_now_in(meeting.tz())

        schedules = dict(
            official=meeting.schedule,
            unofficial=ScheduleFactory(meeting=meeting, owner=meeting.schedule.owner),
        )

        timeslots = dict(
            past=TimeSlotFactory(meeting=meeting, time=right_now - datetime.timedelta(hours=1)),
            future=TimeSlotFactory(meeting=meeting, time=right_now + datetime.timedelta(hours=1)),
            barely_future=TimeSlotFactory(meeting=meeting, time=right_now + datetime.timedelta(minutes=9)),
        )

        self.assertLess(
            timeslots['barely_future'].time - right_now,
            settings.MEETING_SESSION_LOCK_TIME,
            '"barely_future" timeslot is too far in the future. Check MEETING_SESSION_LOCK_TIME settings',
        )

        url_for = lambda sched: urlreverse(
            'ietf.meeting.views.edit_meeting_schedule',
            kwargs=dict(
                num=meeting.number,
                owner=str(sched.owner.email()),
                name=sched.name,
            )
        )

        post_data = lambda ts, sched: dict(
            action='unassign',
            session=str(
                SchedTimeSessAssignment.objects.create(
                    schedule=sched,
                    timeslot=ts,
                    session=SessionFactory(meeting=meeting, add_to_schedule=False),
                ).session.pk
            ),
        )

        username = meeting.schedule.owner.user.username
        self.assertTrue(self.client.login(username=username, password=username + '+password'))

        # past session, official schedule: reject
        r = self.client.post(url_for(schedules['official']), post_data(timeslots['past'], schedules['official']))
        self.assertEqual(r.status_code, 400)
        self.assertEqual(
            self._decode_json_response(r),
            dict(success=False, error="Can't unassign this session."),
        )

        # past timeslot, unofficial schedule: allow
        r = self.client.post(url_for(schedules['unofficial']), post_data(timeslots['past'], schedules['unofficial']))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(self._decode_json_response(r)['success'])

        # barely future session, official schedule: reject
        r = self.client.post(url_for(schedules['official']), post_data(timeslots['barely_future'], schedules['official']))
        self.assertEqual(r.status_code, 400)
        self.assertEqual(
            self._decode_json_response(r),
            dict(success=False, error="Can't unassign this session."),
        )

        # barely future timeslot, unofficial schedule: allow
        r = self.client.post(url_for(schedules['unofficial']), post_data(timeslots['barely_future'], schedules['unofficial']))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(self._decode_json_response(r)['success'])

        # future timeslot, official schedule: allow
        r = self.client.post(url_for(schedules['official']), post_data(timeslots['future'], schedules['official']))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(self._decode_json_response(r)['success'])

        # future timeslot, unofficial schedule: allow
        r = self.client.post(url_for(schedules['unofficial']), post_data(timeslots['future'], schedules['unofficial']))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(self._decode_json_response(r)['success'])

    def test_editor_with_no_timeslots(self):
        """Schedule editor should not crash when there are no timeslots"""
        meeting = MeetingFactory(
            type_id='ietf',
            date=date_today() + datetime.timedelta(days=7),
            populate_schedule=False,
        )
        meeting.schedule = ScheduleFactory(meeting=meeting)
        meeting.save()
        SessionFactory(meeting=meeting, add_to_schedule=False)
        self.assertEqual(meeting.timeslot_set.count(), 0, 'Test problem - meeting should not have any timeslots')
        url = urlreverse('ietf.meeting.views.edit_meeting_schedule', kwargs={'num': meeting.number})
        self.assertTrue(self.client.login(username='secretary', password='secretary+password'))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'No timeslots exist')
        self.assertContains(r, urlreverse('ietf.meeting.views.edit_timeslots', kwargs={'num': meeting.number}))

    def test_editor_time_zone(self):
        """Agenda editor should show meeting time zone"""
        time_zone = 'Etc/GMT+8'
        meeting_tz = ZoneInfo(time_zone)
        meeting = MeetingFactory(
            type_id='ietf',
            date=date_today(meeting_tz) + datetime.timedelta(days=7),
            populate_schedule=False,
            time_zone=time_zone,
        )
        meeting.schedule = ScheduleFactory(meeting=meeting)
        meeting.save()
        timeslot = TimeSlotFactory(meeting=meeting)
        ts_start = timeslot.time.astimezone(meeting_tz)
        ts_end = timeslot.end_time().astimezone(meeting_tz)
        url = urlreverse('ietf.meeting.views.edit_meeting_schedule', kwargs={'num': meeting.number})
        self.assertTrue(self.client.login(username='secretary', password='secretary+password'))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        pq = PyQuery(r.content)

        day_header = pq('.day-flow .day-label')
        self.assertIn(ts_start.strftime('%A'), day_header.text())

        day_swap = day_header.find('.swap-days')
        self.assertEqual(day_swap.attr('data-dayid'), ts_start.date().isoformat())
        self.assertEqual(day_swap.attr('data-start'), ts_start.date().isoformat())

        time_label = pq('.day-flow .time-header .time-label')
        self.assertEqual(len(time_label), 1)
        # strftime() does not seem to support hours without leading 0, so do this manually
        time_label_string = f'{ts_start.hour:d}:{ts_start.minute:02d} - {ts_end.hour:d}:{ts_end.minute:02d}'
        self.assertIn(time_label_string, time_label.text())
        self.assertEqual(time_label.attr('data-start'), ts_start.astimezone(datetime.timezone.utc).isoformat())
        self.assertEqual(time_label.attr('data-end'), ts_end.astimezone(datetime.timezone.utc).isoformat())

        ts_swap = time_label.find('.swap-timeslot-col')
        origin_label = ts_swap.attr('data-origin-label')
        # testing the exact date in origin_label is hard because Django's date filter uses
        # different month formats than Python's strftime, so just check a couple parts.
        self.assertIn(ts_start.strftime('%A'), origin_label)
        self.assertIn(f'{ts_start.hour:d}:{ts_start.minute:02d}-{ts_end.hour:d}:{ts_end.minute:02d}', origin_label)

        timeslot_elt = pq(f'#timeslot{timeslot.pk}')
        self.assertEqual(len(timeslot_elt), 1)
        self.assertEqual(timeslot_elt.attr('data-start'), ts_start.astimezone(datetime.timezone.utc).isoformat())
        self.assertEqual(timeslot_elt.attr('data-end'), ts_end.astimezone(datetime.timezone.utc).isoformat())

        timeslot_label = pq(f'#timeslot{timeslot.pk} .time-label')
        self.assertEqual(len(timeslot_label), 1)
        self.assertIn(time_label_string, timeslot_label.text())


class EditTimeslotsTests(TestCase):
    def login(self, username='secretary'):
        """Log in with permission to edit timeslots"""
        self.client.login(username=username, password='{}+password'.format(username))

    @staticmethod
    def edit_timeslots_url(meeting):
        return urlreverse('ietf.meeting.views.edit_timeslots', kwargs={'num': meeting.number})

    @staticmethod
    def edit_timeslot_url(ts: TimeSlot):
        return urlreverse('ietf.meeting.views.edit_timeslot',
                          kwargs={'num': ts.meeting.number, 'slot_id': ts.pk})

    @staticmethod
    def create_timeslots_url(meeting):
        return urlreverse('ietf.meeting.views.create_timeslot', kwargs={'num': meeting.number})

    @staticmethod
    def create_bare_meeting(number=120) -> Meeting:
        """Create a basic IETF meeting"""
        return MeetingFactory(
            type_id='ietf',
            number=number,
            date=date_today() + datetime.timedelta(days=10),
            populate_schedule=False,
        )

    @staticmethod
    def create_initial_schedule(meeting):
        """Create initial / base schedule in the same manner as through the UI"""
        owner = User.objects.get(username='secretary').person
        base_schedule = Schedule.objects.create(
            meeting=meeting,
            name='base',
            owner=owner,
            visible=True,
            public=True,
        )

        schedule = Schedule.objects.create(meeting = meeting,
                                           name    = "%s-1" % slugify(owner.plain_name()),
                                           owner   = owner,
                                           visible = True,
                                           public  = True,
                                           base    = base_schedule,
        )

        meeting.schedule = schedule
        meeting.save()

    def create_meeting(self, number=120):
        """Create a meeting ready for adding timeslots in the usual workflow"""
        meeting = self.create_bare_meeting(number=number)
        RoomFactory.create_batch(8, meeting=meeting)
        self.create_initial_schedule(meeting)
        # retrieve meeting from DB so it goes through Django's processing
        return Meeting.objects.get(pk=meeting.pk)

    def test_view_permissions(self):
        """Only the secretary should be able to edit timeslots"""
        # test prep and helper method
        usernames_to_reject = [
            'plain',
            RoleFactory(name_id='chair').person.user.username,
            RoleFactory(name_id='ad', group__type_id='area').person.user.username,
        ]
        meeting = self.create_bare_meeting()
        url = self.edit_timeslots_url(meeting)

        def _assert_permissions(comment):
            self.client.logout()
            logged_in_username = '<nobody>'
            try:
                # loop through all the usernames that should be rejected
                for username in usernames_to_reject:
                    login_testing_unauthorized(self, username, url)
                    logged_in_username = username
                # test the last username to reject and log in as secretary
                login_testing_unauthorized(self, 'secretary', url)
            except AssertionError:
                # give a better failure message
                self.fail(
                    '{} should not be able to access the edit timeslots page {}'.format(
                        logged_in_username,
                        comment,
                    )
                )
            r = self.client.get(url)  # confirm secretary can retrieve the page
            self.assertEqual(r.status_code, 200,
                             'secretary should be able to access the edit timeslots page {}'.format(comment))

        # Actual tests here
        _assert_permissions('without schedule')  # first test without a meeting schedule
        self.create_initial_schedule(meeting)
        _assert_permissions('with schedule')  # then test with a meeting schedule

    def test_linked_from_agenda_list(self):
        """The edit timeslots view should be linked from the agenda list view"""
        ad = RoleFactory(name_id='ad', group__type_id='area').person

        meeting = self.create_bare_meeting()
        self.create_initial_schedule(meeting)

        url = urlreverse('ietf.meeting.views.list_schedules', kwargs={'num': meeting.number})

        # Should have no link when logged in as area director
        self.login(ad.user.username)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(
            len(q('a[href="{}"]'.format(self.edit_timeslots_url(meeting)))),
            0,
            'User who cannot edit timeslots should not see a link to the edit timeslots page'
        )

        # Should have a link when logged in as secretary
        self.login()
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertGreaterEqual(
            len(q('a[href="{}"]'.format(self.edit_timeslots_url(meeting)))),
            1,
            'Must be at least one link from the agenda list page to the edit timeslots page'
        )

    def assert_helpful_url(self, response, helpful_url, message):
        q = PyQuery(response.content)
        self.assertGreaterEqual(
            len(q('.timeslot-edit a[href="{}"]'.format(helpful_url))),
            1,
            message,
        )

    def test_with_no_rooms(self):
        """Editor should be helpful when there are no rooms yet"""
        meeting = self.create_bare_meeting()
        self.login()

        # with no schedule, should get a link to the meeting page in the secr app until we can
        # handle this situation in the meeting app
        r = self.client.get(self.edit_timeslots_url(meeting))
        self.assertEqual(r.status_code, 200)
        self.assert_helpful_url(
            r,
            urlreverse('ietf.secr.meetings.views.view', kwargs={'meeting_id': meeting.number}),
            'Must be a link to a helpful URL when there are no rooms and no schedule'
        )

        # with a schedule, should get a link to the create rooms page in the secr app
        self.create_initial_schedule(meeting)
        r = self.client.get(self.edit_timeslots_url(meeting))
        self.assertEqual(r.status_code, 200)
        self.assert_helpful_url(
            r,
            urlreverse('ietf.secr.meetings.views.rooms',
                       kwargs={'meeting_id': meeting.number, 'schedule_name': meeting.schedule.name}),
            'Must be a link to a helpful URL when there are no rooms'
        )

    def test_with_no_timeslots(self):
        """Editor should be helpful when there are rooms but no timeslots yet"""
        meeting = self.create_bare_meeting()
        RoomFactory(meeting=meeting)
        self.login()
        helpful_url = self.create_timeslots_url(meeting)

        # with no schedule, should get a link to the meeting page in the secr app until we can
        # handle this situation in the meeting app
        r = self.client.get(self.edit_timeslots_url(meeting))
        self.assertEqual(r.status_code, 200)
        self.assert_helpful_url(r, helpful_url,
                                 'Must be a link to a helpful URL when there are no timeslots and no schedule')

        # with a schedule, should get a link to the create rooms page in the secr app
        self.create_initial_schedule(meeting)
        r = self.client.get(self.edit_timeslots_url(meeting))
        self.assertEqual(r.status_code, 200)
        self.assert_helpful_url(r, helpful_url,
                                 'Must be a link to a helpful URL when there are no timeslots')

    def assert_required_links_present(self, response, meeting):
        """Assert that required links on the editor page are present"""
        q = PyQuery(response.content)
        self.assertGreaterEqual(
            len(q('a[href="{}"]'.format(self.create_timeslots_url(meeting)))),
            1,
            'Timeslot edit page should have a link to create timeslots'
        )
        self.assertGreaterEqual(
            len(q('a[href="{}"]'.format(urlreverse('ietf.secr.meetings.views.rooms',
                                                   kwargs={'meeting_id': meeting.number,
                                                           'schedule_name': meeting.schedule.name}))
                  )),
            1,
            'Timeslot edit page should have a link to edit rooms'
        )

    def test_required_links_present(self):
        """Editor should have links to create timeslots and edit rooms"""
        meeting = self.create_meeting()
        self.create_initial_schedule(meeting)
        RoomFactory.create_batch(8, meeting=meeting)

        self.login()
        r = self.client.get(self.edit_timeslots_url(meeting))
        self.assertEqual(r.status_code, 200)
        self.assert_required_links_present(r, meeting)

    def test_shows_timeslots(self):
        """Timeslots should be displayed properly"""
        def _col_index(elt):
            """Find the column index of an element in its table row

            First column is 1
            """
            selector = 'td, th'  # accept both td and th elements
            col_elt = elt.closest(selector)
            tr = col_elt.parent('tr')
            return 1 + tr.children(selector).index(col_elt[0])  # [0] gets bare element

        meeting = self.create_meeting()
        # add some timeslots
        times = [datetime.time(hour=h) for h in (11, 14)]
        days = [meeting.get_meeting_date(ii) for ii in range(meeting.days)]

        timeslots = []
        duration = datetime.timedelta(minutes=90)
        for room in meeting.room_set.all():
            for day in days:
                timeslots.extend(
                    TimeSlotFactory(
                        meeting=meeting,
                        location=room,
                        time=meeting.tz().localize(datetime.datetime.combine(day, t)),
                        duration=duration,
                    )
                    for t in times
                )

        # get the page under test
        self.login()
        r = self.client.get(self.edit_timeslots_url(meeting))
        self.assertEqual(r.status_code, 200)

        q = PyQuery(r.content)
        table = q('#timeslot-table')
        self.assertEqual(len(table), 1, 'Exactly one timeslot-table required')
        table = table.eq(0)

        # check the day super-column headings
        day_headings = table.find('.day-label')
        self.assertEqual(len(day_headings), len(days))
        day_columns = dict()  # map datetime to iterable with table col indices for that day
        next_col = _col_index(day_headings.eq(0))  # find column of the first day
        for day, heading in zip(days, day_headings.items()):
            self.assertIn(day.strftime('%a'), heading.text(),
                          'Weekday abbrev for {} not found in heading'.format(day))
            self.assertIn(day.strftime('%Y-%m-%d'), heading.text(),
                          'Numeric date for {} not found in heading'.format(day))
            cols = int(heading.attr('colspan'))  # columns spanned by day header
            day_columns[day] = range(next_col, next_col + cols)
            next_col += cols

        # check the timeslot time headings
        time_headings = table.find('.time-label')
        self.assertEqual(len(time_headings), len(times) * len(days))

        expected_columns = dict()  # [date][time] element is expected column for a timeslot
        for day, columns in day_columns.items():
            headings = time_headings.filter(
                # selector for children in any of the day's columns
                ','.join(
                    ':nth-child({})'.format(col)
                    for col in columns
                )
            )
            expected_columns[day] = dict()
            for time, heading in zip(times, headings.items()):
                self.assertIn(time.strftime('%H:%M'), heading.text(),
                              'Timeslot start {} not found for day {}'.format(time, day))
                expected_columns[day][time] = _col_index(heading)

        # check that the expected timeslots are shown with expected info / ui features
        timeslot_elts = table.find('.timeslot')
        self.assertEqual(len(timeslot_elts), len(timeslots), 'Unexpected or missing timeslot elements')
        for ts in timeslots:
            pk_elts = timeslot_elts.filter('#timeslot{}'.format(ts.pk))
            self.assertEqual(len(pk_elts), 1, 'Expect exactly one element for each timeslot')
            elt = pk_elts.eq(0)
            self.assertIn(ts.name, elt.text(), 'Timeslot name should appear in the element for {}'.format(ts))
            self.assertIn(str(ts.type), elt.text(), 'Timeslot type should appear in the element for {}'.format(ts))
            self.assertEqual(_col_index(elt), expected_columns[ts.time.date()][ts.time.time()],
                             'Timeslot {} is in the wrong column'.format(ts))
            delete_btn = elt.find('.delete-button[data-delete-scope="timeslot"]')
            self.assertEqual(len(delete_btn), 1,
                             'Timeslot {} should have one delete button'.format(ts))
            edit_btn = elt.find('a[href="{}"]'.format(
                urlreverse('ietf.meeting.views.edit_timeslot',
                           kwargs=dict(num=meeting.number, slot_id=ts.pk))
            ))
            self.assertEqual(len(edit_btn), 1,
                             'Timeslot {} should have one edit button'.format(ts))
            # find the room heading for the row
            tr = elt.closest('tr')
            self.assertIn(ts.location.name, tr.children('th').eq(0).text(),
                          'Timeslot {} is not shown in the correct row'.format(ts))

    def test_bulk_delete_buttons_exist(self):
        """Delete buttons for days and columns should be shown"""
        meeting = self.create_meeting()
        for day in range(meeting.days):
            TimeSlotFactory(
                meeting=meeting,
                location=meeting.room_set.first(),
                time=meeting.tz().localize(
                    datetime.datetime.combine(
                        meeting.get_meeting_date(day),
                        datetime.time(hour=11),
                    )
                ),
            )
            TimeSlotFactory(
                meeting=meeting,
                location=meeting.room_set.first(),
                time=meeting.tz().localize(
                    datetime.datetime.combine(
                        meeting.get_meeting_date(day),
                        datetime.time(hour=14),
                    )
                ),
            )

        self.login()
        r = self.client.get(self.edit_timeslots_url(meeting))
        self.assertEqual(r.status_code, 200)

        q = PyQuery(r.content)
        table = q('#timeslot-table')
        days = table.find('.day-label')
        self.assertEqual(len(days), meeting.days, 'Wrong number of day labels')
        for day_label in days.items():
            self.assertEqual(len(day_label.find('.delete-button[data-delete-scope="day"]')), 1,
                             'No delete button for day {}'.format(day_label.text()))

        slots = table.find('.time-label')
        self.assertEqual(len(slots), 2 * meeting.days, 'Wrong number of slot labels')
        for slot_label in slots.items():
            self.assertEqual(len(slot_label.find('.delete-button[data-delete-scope="column"]')), 1,
                             'No delete button for slot {}'.format(slot_label.text()))

    def test_timeslot_collision_flag(self):
        """Overlapping timeslots in a room should be flagged

        Only checks exact overlap because that is all we currently handle. The display puts
        overlapping but not exactly matching timeslots in separate columns which must be
        manually checked.
        """
        meeting = self.create_bare_meeting()

        t1 = TimeSlotFactory(meeting=meeting)
        TimeSlotFactory(meeting=meeting, time=t1.time, duration=t1.duration, location=t1.location)
        TimeSlotFactory(meeting=meeting, time=t1.time, duration=t1.duration)  # other location
        TimeSlotFactory(meeting=meeting, time=t1.time.replace(hour=t1.time.hour + 1), location=t1.location)  # other time

        self.login()
        r = self.client.get(self.edit_timeslots_url(meeting))
        self.assertEqual(r.status_code, 200)

        q = PyQuery(r.content)
        slots = q('#timeslot-table .tscell')
        self.assertEqual(len(slots), 4)  # one per location per distinct time
        collision = slots.filter('.timeslot-collision')
        no_collision = slots.filter(':not(.timeslot-collision)')
        self.assertEqual(len(collision), 1, 'Wrong number of timeslot collisions flagged')
        self.assertEqual(len(no_collision), 3, 'Wrong number of non-colliding timeslots')
        # check that the cell containing t1 is the one flagged as a conflict
        self.assertEqual(len(collision.find('#timeslot{}'.format(t1.pk))), 1,
                         'Wrong timeslot cell flagged as having a collision')

    def test_timeslot_in_use_flag(self):
        """Timeslots that are in use should be flagged"""
        meeting = self.create_meeting()

        # assign sessions to some timeslots
        empty, has_official, has_other = TimeSlotFactory.create_batch(3, meeting=meeting, location=meeting.room_set.first())
        SchedTimeSessAssignment.objects.create(
            timeslot=has_official,
            session=SessionFactory(meeting=meeting, add_to_schedule=False),
            schedule=meeting.schedule,  # official schedule
        )

        SchedTimeSessAssignment.objects.create(
            timeslot=has_other,
            session=SessionFactory(meeting=meeting, add_to_schedule=False),
            schedule=ScheduleFactory(meeting=meeting),  # not the official schedule
        )

        # get the page
        self.login()
        r = self.client.get(self.edit_timeslots_url(meeting))
        self.assertEqual(r.status_code, 200)

        # now check that all timeslots appear, flagged appropriately
        q = PyQuery(r.content)
        empty_elt = q('#timeslot{}'.format(empty.pk))
        has_official_elt = q('#timeslot{}'.format(has_official.pk))
        has_other_elt = q('#timeslot{}'.format(has_other.pk))

        self.assertEqual(empty_elt.attr('data-unofficial-use'), 'false', 'Unused timeslot should not be in use')
        self.assertEqual(empty_elt.attr('data-official-use'), 'false', 'Unused timeslot should not be in use')

        self.assertEqual(has_other_elt.attr('data-unofficial-use'), 'true',
                         'Unofficially used timeslot should be flagged')
        self.assertEqual(has_other_elt.attr('data-official-use'), 'false',
                         'Unofficially used timeslot is not in official use')

        self.assertEqual(has_official_elt.attr('data-unofficial-use'), 'false',
                         'Officially used timeslot not in unofficial use')
        self.assertEqual(has_official_elt.attr('data-official-use'), 'true',
                         'Officially used timeslot should be flagged')

    def test_edit_timeslot(self):
        """Edit page should work as expected"""
        meeting = self.create_meeting()

        name_before = 'Name Classic (tm)'
        type_before = 'regular'
        time_utc = pytz.utc.localize(datetime.datetime.combine(meeting.date, datetime.time(hour=10)))
        time_before = time_utc.astimezone(meeting.tz())
        duration_before = datetime.timedelta(minutes=60)
        show_location_before = True
        location_before = meeting.room_set.first()
        ts = TimeSlotFactory(
            meeting=meeting,
            name=name_before,
            type_id=type_before,
            time=time_before,
            duration=duration_before,
            show_location=show_location_before,
            location=location_before,
        )

        self.login()
        url = self.edit_timeslot_url(ts)

        # check that sched parameter is preserved
        r = self.client.get(url)
        self.assertNotContains(r, '?sched=', status_code=200)
        r = self.client.get(url + '?sched=1234')
        self.assertContains(r, '?sched=1234', status_code=200)  # could check in more detail

        name_after = 'New Name (tm)'
        type_after = 'plenary'
        time_after = (time_utc + datetime.timedelta(days=1, hours=2)).astimezone(meeting.tz())
        duration_after = duration_before * 2
        show_location_after = False
        location_after = meeting.room_set.last()
        post_data = dict(
            name=name_after,
            type=type_after,
            time_0=time_after.strftime('%Y-%m-%d'),  # date for SplitDateTimeField
            time_1=time_after.strftime('%H:%M'),  # time for SplitDateTimeField
            duration=str(duration_after),
            # show_location=show_location_after,  # False values are omitted from form
            location=location_after.pk,
        )
        r = self.client.post(url, data=post_data)
        self.assertEqual(r.status_code, 302)  # expect redirect to timeslot edit url
        self.assertEqual(r['Location'], self.edit_timeslots_url(meeting),
                         'Expected to be redirected to meeting timeslots edit page')

        # check that we changed things
        self.assertNotEqual(name_before, name_after)
        self.assertNotEqual(type_before, type_after)
        self.assertNotEqual(time_before, time_after)
        self.assertNotEqual(duration_before, duration_after)
        self.assertNotEqual(location_before, location_after)

        # and that we have the new values
        ts = TimeSlot.objects.get(pk=ts.pk)
        self.assertEqual(ts.name, name_after)
        self.assertEqual(ts.type_id, type_after)
        self.assertEqual(ts.time, time_after)
        self.assertEqual(ts.duration, duration_after)
        self.assertEqual(ts.show_location, show_location_after)
        self.assertEqual(ts.location, location_after)

        # and check with sched param set
        r = self.client.post(url + '?sched=1234', data=post_data)
        self.assertEqual(r.status_code, 302)  # expect redirect to timeslot edit url
        self.assertEqual(r['Location'], self.edit_timeslots_url(meeting) + '?sched=1234',
                         'Expected to be redirected to meeting timeslots edit page with sched param set')

    def test_invalid_edit_timeslot(self):
        meeting = self.create_bare_meeting()
        ts: TimeSlot = TimeSlotFactory(meeting=meeting, name='slot')  # type: ignore[annotation-unchecked]
        self.login()
        r = self.client.post(
            self.edit_timeslot_url(ts),
            data=dict(
                name='',
                type=ts.type.pk,
                time_0=ts.time.strftime('%Y-%m-%d'),
                time_1=ts.time.strftime('%H:%M'),
                duration=str(ts.duration),
                show_location=ts.show_location,
                location=str(ts.location.pk),
            )
        )
        self.assertContains(r, 'This field is required', status_code=400,
                            msg_prefix='Missing name not properly rejected')

        r = self.client.post(
            self.edit_timeslot_url(ts),
            data=dict(
                name='different name',
                type='this is not a type id',
                time_0=ts.time.strftime('%Y-%m-%d'),
                time_1=ts.time.strftime('%H:%M'),
                duration=str(ts.duration),
                show_location=ts.show_location,
                location=str(ts.location.pk),
            )
        )
        self.assertContains(r, 'Select a valid choice', status_code=400,
                            msg_prefix='Invalid type not properly rejected')

        r = self.client.post(
            self.edit_timeslot_url(ts),
            data=dict(
                name='different name',
                type=ts.type.pk,
                time_0='this is not a date',
                time_1=ts.time.strftime('%H:%M'),
                duration=str(ts.duration),
                show_location=ts.show_location,
                location=str(ts.location.pk),
            )
        )
        self.assertContains(r, 'Enter a valid date', status_code=400,
                            msg_prefix='Invalid date not properly rejected')

        r = self.client.post(
            self.edit_timeslot_url(ts),
            data=dict(
                name='different name',
                type=ts.type.pk,
                time_0=ts.time.strftime('%Y-%m-%d'),
                time_1='this is not a time',
                duration=str(ts.duration),
                show_location=ts.show_location,
                location=str(ts.location.pk),
            )
        )
        self.assertContains(r, 'Enter a valid time', status_code=400,
                            msg_prefix='Invalid time not properly rejected')

        r = self.client.post(
            self.edit_timeslot_url(ts),
            data=dict(
                name='different name',
                type=ts.type.pk,
                time_0=ts.time.strftime('%Y-%m-%d'),
                time_1=ts.time.strftime('%H:%M'),
                duration='this is not a duration',
                show_location=ts.show_location,
                location=str(ts.location.pk),
            )
        )
        self.assertContains(r, 'Enter a valid duration', status_code=400,
                            msg_prefix='Invalid duration not properly rejected')

        r = self.client.post(
            self.edit_timeslot_url(ts),
            data=dict(
                name='different name',
                type=ts.type.pk,
                time_0=ts.time.strftime('%Y-%m-%d'),
                time_1=ts.time.strftime('%H:%M'),
                duration='26:00',  # longer than 12 hours,
                show_location=ts.show_location,
                location=str(ts.location.pk),
            )
        )
        self.assertContains(r, 'Ensure this value is less than or equal to', status_code=400,
                            msg_prefix='Overlong duration not properly rejected')

        r = self.client.post(
            self.edit_timeslot_url(ts),
            data=dict(
                name='different name',
                type=str(ts.type.pk),
                time_0=ts.time.strftime('%Y-%m-%d'),
                time_1=ts.time.strftime('%H:%M'),
                duration=str(ts.duration),
                show_location=ts.show_location,
                location='this is not a location',
            )
        )
        self.assertContains(r, 'Select a valid choice', status_code=400,
                            msg_prefix='Invalid location not properly rejected')

        ts_after = meeting.timeslot_set.get(pk=ts.pk)
        self.assertEqual(ts.name, ts_after.name)
        self.assertEqual(ts.type, ts_after.type)
        self.assertEqual(ts.time, ts_after.time)
        self.assertEqual(ts.duration, ts_after.duration)
        self.assertEqual(ts.show_location, ts_after.show_location)
        self.assertEqual(ts.location, ts_after.location)

    def test_create_single_timeslot(self):
        """Creating a single timeslot should work"""
        meeting = self.create_meeting()
        timeslots_before = set(ts.pk for ts in meeting.timeslot_set.all())

        url = self.create_timeslots_url(meeting)
        post_data = dict(
            name='some name',
            type='regular',
            days=str(meeting.date.toordinal()),
            time='14:37',
            duration='1:13',  # does not include seconds
            show_location=True,
            locations=str(meeting.room_set.first().pk),
        )
        self.login()

        # check that sched parameter is preserved
        r = self.client.get(url)
        self.assertNotContains(r, '?sched=', status_code=200)
        r = self.client.get(url + '?sched=1234')
        self.assertContains(r, '?sched=1234', status_code=200)  # could check in more detail

        r = self.client.post(url, data=post_data)
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r['Location'], self.edit_timeslots_url(meeting),
                         'Expected to be redirected to meeting timeslots edit page')

        self.assertEqual(meeting.timeslot_set.count(), len(timeslots_before) + 1)
        ts = meeting.timeslot_set.exclude(pk__in=timeslots_before).first()  # only 1
        self.assertEqual(ts.name, post_data['name'])
        self.assertEqual(ts.type_id, post_data['type'])
        self.assertEqual(str(ts.local_start_time().date().toordinal()), post_data['days'])
        self.assertEqual(ts.local_start_time().strftime('%H:%M'), post_data['time'])
        self.assertEqual(str(ts.duration), '{}:00'.format(post_data['duration']))  # add seconds
        self.assertEqual(ts.show_location, post_data['show_location'])
        self.assertEqual(str(ts.location.pk), post_data['locations'])

        # check again with sched parameter
        r = self.client.post(url + '?sched=1234', data=post_data)
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r['Location'], self.edit_timeslots_url(meeting) + '?sched=1234',
                         'Expected to be redirected to meeting timeslots edit page with sched parameter set')

    def test_create_single_timeslot_outside_meeting_days(self):
        """Creating a single timeslot outside the official meeting days should work"""
        meeting = self.create_meeting()
        timeslots_before = set(ts.pk for ts in meeting.timeslot_set.all())
        other_date = meeting.get_meeting_date(-7)
        post_data = dict(
            name='some name',
            type='regular',
            other_date=other_date.strftime('%Y-%m-%d'),
            time='14:37',
            duration='1:13',  # does not include seconds
            show_location=True,
            locations=str(meeting.room_set.first().pk),
        )
        self.login()
        r = self.client.post(
            self.create_timeslots_url(meeting),
            data=post_data,
        )
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r['Location'], self.edit_timeslots_url(meeting),
                         'Expected to be redirected to meeting timeslots edit page')

        self.assertEqual(meeting.timeslot_set.count(), len(timeslots_before) + 1)
        ts = meeting.timeslot_set.exclude(pk__in=timeslots_before).first()  # only 1
        self.assertEqual(ts.name, post_data['name'])
        self.assertEqual(ts.type_id, post_data['type'])
        self.assertEqual(ts.local_start_time().date(), other_date)
        self.assertEqual(ts.local_start_time().strftime('%H:%M'), post_data['time'])
        self.assertEqual(str(ts.duration), '{}:00'.format(post_data['duration']))  # add seconds
        self.assertEqual(ts.show_location, post_data['show_location'])
        self.assertEqual(str(ts.location.pk), post_data['locations'])


    def test_invalid_create_timeslot(self):
        meeting = self.create_bare_meeting()
        room_pk = str(RoomFactory(meeting=meeting).pk)
        timeslot_count = TimeSlot.objects.count()

        self.login()
        r = self.client.post(
            self.create_timeslots_url(meeting),
            data=dict(
                name='',
                type='regular',
                days=str(meeting.date.toordinal()),
                time='14:37',
                duration='1:13',  # does not include seconds
                show_location=True,
                locations=room_pk,
            )
        )
        self.assertContains(r, 'This field is required', status_code=400,
                            msg_prefix='Empty name not rejected properly')

        r = self.client.post(
            self.create_timeslots_url(meeting),
            data=dict(
                name='this is a name',
                type='this is not a type',
                days=str(meeting.date.toordinal()),
                time='14:37',
                duration='1:13',  # does not include seconds
                show_location=True,
                locations=room_pk,
            )
        )
        self.assertContains(r, 'Select a valid choice', status_code=400,
                            msg_prefix='Invalid type not rejected properly')

        r = self.client.post(
            self.create_timeslots_url(meeting),
            data=dict(
                name='this is a name',
                type='regular',
                # days='',
                time='14:37',
                duration='1:13',  # does not include seconds
                show_location=True,
                locations=room_pk,
            )
        )
        self.assertContains(r, 'Please select a day or specify a date', status_code=400,
                            msg_prefix='Missing date not rejected properly')

        r = self.client.post(
            self.create_timeslots_url(meeting),
            data=dict(
                name='this is a name',
                type='regular',
                days='this is not an ordinal date',
                time='14:37',
                duration='1:13',  # does not include seconds
                show_location=True,
                locations=room_pk,
            )
        )
        self.assertContains(r, 'Select a valid choice', status_code=400,
                            msg_prefix='Invalid day not rejected properly')

        r = self.client.post(
            self.create_timeslots_url(meeting),
            data=dict(
                name='this is a name',
                type='regular',
                days=[str(meeting.date.toordinal()), 'this is not an ordinal date'],
                time='14:37',
                duration='1:13',  # does not include seconds
                show_location=True,
                locations=room_pk,
            )
        )
        self.assertContains(r, 'Select a valid choice', status_code=400,
                            msg_prefix='Invalid day with valid day not rejected properly')

        r = self.client.post(
            self.create_timeslots_url(meeting),
            data=dict(
                name='this is a name',
                type='regular',
                days=str(meeting.date.toordinal()),
                other_date='this is not a date',
                time='14:37',
                duration='1:13',  # does not include seconds
                show_location=True,
                locations=room_pk,
            )
        )
        self.assertContains(r, 'Enter a valid date', status_code=400,
                            msg_prefix='Invalid other_date with valid days not rejected properly')

        r = self.client.post(
            self.create_timeslots_url(meeting),
            data=dict(
                name='this is a name',
                type='regular',
                days='this is not an ordinal date',
                other_date='2021-07-13',
                time='14:37',
                duration='1:13',  # does not include seconds
                show_location=True,
                locations=room_pk,
            )
        )
        self.assertContains(r, 'Select a valid choice', status_code=400,
                            msg_prefix='Invalid day with valid other_date not rejected properly')

        r = self.client.post(
            self.create_timeslots_url(meeting),
            data=dict(
                name='this is a name',
                type='regular',
                other_date='this is not a date',
                time='14:37',
                duration='1:13',  # does not include seconds
                show_location=True,
                locations=room_pk,
            )
        )
        self.assertContains(r, 'Enter a valid date', status_code=400,
                            msg_prefix='Invalid other_date not rejected properly')
        r = self.client.post(
            self.create_timeslots_url(meeting),
            data=dict(
                name='this is a name',
                type='regular',
                days=str(meeting.date.toordinal()),
                time='14:37',
                duration="ceci n'est pas une duree",
                show_location=True,
                locations=room_pk,
            )
        )
        self.assertContains(r, 'Enter a valid duration', status_code=400,
                            msg_prefix='Invalid duration not rejected properly')

        r = self.client.post(
            self.create_timeslots_url(meeting),
            data=dict(
                name='this is a name',
                type='regular',
                days=str(meeting.date.toordinal()),
                time='14:37',
                duration="26:00",
                show_location=True,
                locations=room_pk,
            )
        )
        self.assertContains(r, 'Ensure this value is less than or equal to', status_code=400,
                            msg_prefix='Overlong duration not rejected properly')

        r = self.client.post(
            self.create_timeslots_url(meeting),
            data=dict(
                name='this is a name',
                type='regular',
                days=str(meeting.date.toordinal()),
                time='14:37',
                duration="1:13",
                show_location=True,
                locations='this is not a room',
            )
        )
        self.assertContains(r, 'is not a valid value', status_code=400,
                            msg_prefix='Invalid location not rejected properly')

        r = self.client.post(
            self.create_timeslots_url(meeting),
            data=dict(
                name='this is a name',
                type='regular',
                days=str(meeting.date.toordinal()),
                time='14:37',
                duration="1:13",
                show_location=True,
                locations=[room_pk, 'this is not a room'],
            )
        )
        self.assertContains(r, 'is not a valid value', status_code=400,
                            msg_prefix='Invalid location with valid location not rejected properly')

        r = self.client.post(
            self.create_timeslots_url(meeting),
            data=dict(
                name='this is a name',
                type='regular',
                days=str(meeting.date.toordinal()),
                time='14:37',
                duration="1:13",
                show_location=True,
            )
        )
        self.assertContains(r, 'This field is required', status_code=400,
                            msg_prefix='Missing location not rejected properly')

        self.assertEqual(TimeSlot.objects.count(), timeslot_count,
                         'TimeSlot unexpectedly created')

    def test_create_bulk_timeslots(self):
        """Creating multiple timeslots should work"""
        meeting = self.create_meeting()
        timeslots_before = set(ts.pk for ts in meeting.timeslot_set.all())
        days = [meeting.get_meeting_date(n) for n in range(meeting.days)]
        other_date = meeting.get_meeting_date(-1)  # date before start of meeting
        self.assertNotIn(other_date, days)
        locations = meeting.room_set.all()
        post_data = dict(
            name='some name',
            type='regular',
            days=[str(d.toordinal()) for d in days],
            other_date=other_date.strftime('%Y-%m-%d'),
            time='14:37',
            duration='1:13',  # does not include seconds
            show_location=True,
            locations=[str(loc.pk) for loc in locations],
        )
        self.login()
        r = self.client.post(
            self.create_timeslots_url(meeting),
            data=post_data,
        )
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r['Location'], self.edit_timeslots_url(meeting),
                         'Expected to be redirected to meeting timeslots edit page')

        days.append(other_date)
        new_slot_count = len(days) * len(locations)
        self.assertEqual(meeting.timeslot_set.count(), len(timeslots_before) + new_slot_count)

        day_locs = set((day, loc) for day in days for loc in locations)  # cartesian product
        for ts in meeting.timeslot_set.exclude(pk__in=timeslots_before):
            self.assertEqual(ts.name, post_data['name'])
            self.assertEqual(ts.type_id, post_data['type'])
            self.assertEqual(ts.local_start_time().strftime('%H:%M'), post_data['time'])
            self.assertEqual(str(ts.duration), '{}:00'.format(post_data['duration']))  # add seconds
            self.assertEqual(ts.show_location, post_data['show_location'])
            self.assertIn(ts.local_start_time().date(), days)
            self.assertIn(ts.location, locations)
            self.assertIn((ts.time.date(), ts.location), day_locs,
                          'Duplicated day / location found')
            day_locs.discard((ts.time.date(), ts.location))
        self.assertEqual(day_locs, set(), 'Not all day/location combinations created')

    def test_sched_param_preserved(self):
        meeting = MeetingFactory(type_id='ietf')
        url = urlreverse('ietf.meeting.views.edit_timeslots', kwargs={'num': meeting.number})
        self.client.login(username='secretary', password='secretary+password')
        r = self.client.get(url)
        self.assertNotContains(r, '?sched=', status_code=200)
        self.assertNotContains(r, "Back to agenda")
        r = self.client.get(url + '?sched=1234')
        self.assertContains(r, '?sched=1234', status_code=200)  # could check in more detail
        self.assertContains(r, "Back to agenda")

    def test_ajax_delete_timeslot(self):
        """AJAX call to delete timeslot should work"""
        meeting = self.create_bare_meeting()
        ts_to_del, ts_to_keep = TimeSlotFactory.create_batch(2, meeting=meeting)

        self.login()
        r = self.client.post(
            self.edit_timeslots_url(meeting),
            data=dict(
                action='delete',
                slot_id=str(ts_to_del.pk),
            )
        )
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Deleted TimeSlot {}'.format(ts_to_del.pk))
        self.assertNotContains(r, 'Deleted TimeSlot {}'.format(ts_to_keep.pk))
        self.assertEqual(meeting.timeslot_set.filter(pk=ts_to_del.pk).count(), 0,
                         'Timeslot not deleted')
        self.assertEqual(meeting.timeslot_set.filter(pk=ts_to_keep.pk).count(), 1,
                         'Extra timeslot deleted')

    def test_ajax_delete_timeslots(self):
        """AJAX call to delete several timeslots should work"""
        meeting = self.create_bare_meeting()
        ts_to_del = TimeSlotFactory.create_batch(5, meeting=meeting)
        ts_to_keep = TimeSlotFactory(meeting=meeting)

        self.login()
        r = self.client.post(
            self.edit_timeslots_url(meeting),
            data=dict(
                action='delete',
                slot_id=','.join(str(ts.pk) for ts in ts_to_del),
            )
        )
        self.assertEqual(r.status_code, 200)
        for ts in ts_to_del:
            self.assertContains(r, 'Deleted TimeSlot {}'.format(ts.pk))
        self.assertNotContains(r, 'Deleted TimeSlot {}'.format(ts_to_keep.pk))
        self.assertEqual(
            meeting.timeslot_set.filter(pk__in=(ts.pk for ts in ts_to_del)).count(),
            0,
            'Timeslots not deleted',
        )
        self.assertEqual(meeting.timeslot_set.filter(pk=ts_to_keep.pk).count(), 1,
                         'Extra timeslot deleted')

    def test_ajax_delete_timeslots_invalid(self):
        meeting = self.create_bare_meeting()
        ts = TimeSlotFactory(meeting=meeting)
        self.login()
        r = self.client.post(
            self.edit_timeslots_url(meeting),
        )
        self.assertEqual(r.status_code, 400, 'Missing POST data not handled')

        r = self.client.post(
            self.edit_timeslots_url(meeting),
            data=dict()
        )
        self.assertEqual(r.status_code, 400, 'Empty POST data not handled')

        r = self.client.post(
            self.edit_timeslots_url(meeting),
            data=dict(
                slot_id=str(ts.pk),
            )
        )
        self.assertEqual(r.status_code, 400, 'Missing action not handled')

        r = self.client.post(
            self.edit_timeslots_url(meeting),
            data=dict(
                action='deletify',
                slot_id=str(ts.pk),
            )
        )
        self.assertEqual(r.status_code, 400, 'Invalid action not handled')

        r = self.client.post(
            self.edit_timeslots_url(meeting),
            data=dict(
                action='delete',
            )
        )
        self.assertEqual(r.status_code, 400, 'Missing slot_id not handled')

        r = self.client.post(
            self.edit_timeslots_url(meeting),
            data=dict(
                action='delete',
                slot_id='not an id',
            )
        )
        self.assertEqual(r.status_code, 400, 'Invalid slot_id not handled')

        r = self.client.post(
            self.edit_timeslots_url(meeting),
            data=dict(
                action='delete',
                slot_id='{}, not an id'.format(ts.pk),
            )
        )
        self.assertEqual(r.status_code, 400, 'Invalid slot_id not handled in bulk')

        nonexistent_id = TimeSlot.objects.all().aggregate(Max('id'))['id__max'] + 1
        r = self.client.post(
            self.edit_timeslots_url(meeting),
            data=dict(
                action='delete',
                slot_id=str(nonexistent_id),
            )
        )
        self.assertEqual(r.status_code, 404, 'Nonexistent slot_id not handled in bulk')

        r = self.client.post(
            self.edit_timeslots_url(meeting),
            data=dict(
                action='delete',
                slot_id='{},{}'.format(nonexistent_id, ts.pk),
            )
        )
        self.assertEqual(r.status_code, 404, 'Nonexistent slot_id not handled in bulk')

        self.assertEqual(meeting.timeslot_set.filter(pk=ts.pk).count(), 1,
                         'TimeSlot unexpectedly deleted')


class ReorderSlidesTests(TestCase):

    @override_settings(MEETECHO_API_CONFIG="fake settings")  # enough to trigger API calls
    @patch("ietf.meeting.views.SlidesManager")
    def test_add_slides_to_session(self, mock_slides_manager_cls):
        for type_id in ('ietf','interim'):
            chair_role = RoleFactory(name_id='chair')
            session = SessionFactory(group=chair_role.group, meeting__date=date_today() - datetime.timedelta(days=90), meeting__type_id=type_id)
            slides = DocumentFactory(type_id='slides')
            url = urlreverse('ietf.meeting.views.ajax_add_slides_to_session', kwargs={'session_id':session.pk, 'num':session.meeting.number})

            # Not a valid user
            r = self.client.post(url, {'order':1, 'name':slides.name })
            self.assertEqual(r.status_code, 403)
            self.assertIn('have permission', unicontent(r))
            self.assertFalse(mock_slides_manager_cls.called)

            self.client.login(username=chair_role.person.user.username, password=chair_role.person.user.username+"+password")

            # Past submission cutoff
            r = self.client.post(url, {'order':0, 'name':slides.name })
            self.assertEqual(r.status_code, 403)
            self.assertIn('materials cutoff', unicontent(r))
            self.assertFalse(mock_slides_manager_cls.called)

            session.meeting.date = date_today()
            session.meeting.save()

            # Invalid order
            r = self.client.post(url, {})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()['success'],False)
            self.assertIn('No data',r.json()['error'])
            self.assertFalse(mock_slides_manager_cls.called)

            r = self.client.post(url, {'garbage':'garbage'})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()['success'],False)
            self.assertIn('order is not valid',r.json()['error'])
            self.assertFalse(mock_slides_manager_cls.called)

            r = self.client.post(url, {'order':0, 'name':slides.name })
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()['success'],False)
            self.assertIn('order is not valid',r.json()['error'])
            self.assertFalse(mock_slides_manager_cls.called)

            r = self.client.post(url, {'order':2, 'name':slides.name })
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()['success'],False)
            self.assertIn('order is not valid',r.json()['error'])
            self.assertFalse(mock_slides_manager_cls.called)

            r = self.client.post(url, {'order':'garbage', 'name':slides.name })
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()['success'],False)
            self.assertIn('order is not valid',r.json()['error'])
            self.assertFalse(mock_slides_manager_cls.called)

            # Invalid name
            r = self.client.post(url, {'order':1 })
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()['success'],False)
            self.assertIn('name is not valid',r.json()['error'])
            self.assertFalse(mock_slides_manager_cls.called)

            r = self.client.post(url, {'order':1, 'name':'garbage' })
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()['success'],False)
            self.assertIn('name is not valid',r.json()['error'])
            self.assertFalse(mock_slides_manager_cls.called)

            # Valid post
            r = self.client.post(url, {'order':1, 'name':slides.name })
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()['success'],True)
            self.assertEqual(session.presentations.count(),1)
            self.assertTrue(mock_slides_manager_cls.called)
            self.assertEqual(mock_slides_manager_cls.call_args, call(api_config="fake settings"))
            self.assertTrue(mock_slides_manager_cls.return_value.add.called)
            self.assertEqual(mock_slides_manager_cls.return_value.add.call_args, call(session=session, slides=slides, order=1))
            mock_slides_manager_cls.reset_mock()

            # Ignore a request to add slides that are already in a session
            r = self.client.post(url, {'order':1, 'name':slides.name })
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()['success'],True)
            self.assertEqual(session.presentations.count(),1)
            self.assertFalse(mock_slides_manager_cls.called)


            session2 = SessionFactory(group=session.group, meeting=session.meeting)
            SessionPresentationFactory.create_batch(3, document__type_id='slides', session=session2)
            for num, sp in enumerate(session2.presentations.filter(document__type_id='slides'),start=1):
                sp.order = num
                sp.save()

            url = urlreverse('ietf.meeting.views.ajax_add_slides_to_session', kwargs={'session_id':session2.pk, 'num':session2.meeting.number})

            more_slides = DocumentFactory.create_batch(3, type_id='slides')

            # Insert at beginning
            r = self.client.post(url, {'order':1, 'name':more_slides[0].name})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()['success'],True)
            self.assertEqual(session2.presentations.get(document=more_slides[0]).order,1)
            self.assertEqual(list(session2.presentations.order_by('order').values_list('order',flat=True)), list(range(1,5)))
            self.assertTrue(mock_slides_manager_cls.called)
            self.assertEqual(mock_slides_manager_cls.call_args, call(api_config="fake settings"))
            self.assertTrue(mock_slides_manager_cls.return_value.add.called)
            self.assertEqual(mock_slides_manager_cls.return_value.add.call_args, call(session=session2, slides=more_slides[0], order=1))
            mock_slides_manager_cls.reset_mock()

            # Insert at end
            r = self.client.post(url, {'order':5, 'name':more_slides[1].name})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()['success'],True)
            self.assertEqual(session2.presentations.get(document=more_slides[1]).order,5)
            self.assertEqual(list(session2.presentations.order_by('order').values_list('order',flat=True)), list(range(1,6)))
            self.assertTrue(mock_slides_manager_cls.called)
            self.assertEqual(mock_slides_manager_cls.call_args, call(api_config="fake settings"))
            self.assertTrue(mock_slides_manager_cls.return_value.add.called)
            self.assertEqual(mock_slides_manager_cls.return_value.add.call_args, call(session=session2, slides=more_slides[1], order=5))
            mock_slides_manager_cls.reset_mock()

            # Insert in middle
            r = self.client.post(url, {'order':3, 'name':more_slides[2].name})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()['success'],True)
            self.assertEqual(session2.presentations.get(document=more_slides[2]).order,3)
            self.assertEqual(list(session2.presentations.order_by('order').values_list('order',flat=True)), list(range(1,7)))
            self.assertTrue(mock_slides_manager_cls.called)
            self.assertEqual(mock_slides_manager_cls.call_args, call(api_config="fake settings"))
            self.assertTrue(mock_slides_manager_cls.return_value.add.called)
            self.assertEqual(mock_slides_manager_cls.return_value.add.call_args, call(session=session2, slides=more_slides[2], order=3))
            mock_slides_manager_cls.reset_mock()

    @override_settings(MEETECHO_API_CONFIG="fake settings")  # enough to trigger API calls
    @patch("ietf.meeting.views.SlidesManager")
    def test_remove_slides_from_session(self, mock_slides_manager_cls):
        for type_id in ['ietf','interim']:
            chair_role = RoleFactory(name_id='chair')
            session = SessionFactory(group=chair_role.group, meeting__date=date_today()-datetime.timedelta(days=90), meeting__type_id=type_id)
            slides = DocumentFactory(type_id='slides')
            url = urlreverse('ietf.meeting.views.ajax_remove_slides_from_session', kwargs={'session_id':session.pk, 'num':session.meeting.number})

            # Not a valid user
            r = self.client.post(url, {'oldIndex':1, 'name':slides.name })
            self.assertEqual(r.status_code, 403)
            self.assertIn('have permission', unicontent(r))
            self.assertFalse(mock_slides_manager_cls.called)

            self.client.login(username=chair_role.person.user.username, password=chair_role.person.user.username+"+password")
            
            # Past submission cutoff
            r = self.client.post(url, {'oldIndex':0, 'name':slides.name })
            self.assertEqual(r.status_code, 403)
            self.assertIn('materials cutoff', unicontent(r))
            self.assertFalse(mock_slides_manager_cls.called)

            session.meeting.date = date_today()
            session.meeting.save()

            # Invalid order
            r = self.client.post(url, {})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()['success'],False)
            self.assertIn('No data',r.json()['error'])
            self.assertFalse(mock_slides_manager_cls.called)

            r = self.client.post(url, {'garbage':'garbage'})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()['success'],False)
            self.assertIn('index is not valid',r.json()['error'])
            self.assertFalse(mock_slides_manager_cls.called)

            r = self.client.post(url, {'oldIndex':0, 'name':slides.name })
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()['success'],False)
            self.assertIn('index is not valid',r.json()['error'])
            self.assertFalse(mock_slides_manager_cls.called)

            r = self.client.post(url, {'oldIndex':'garbage', 'name':slides.name })
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()['success'],False)
            self.assertIn('index is not valid',r.json()['error'])
            self.assertFalse(mock_slides_manager_cls.called)

            # No matching thing to delete
            r = self.client.post(url, {'oldIndex':1, 'name':slides.name })
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()['success'],False)
            self.assertIn('index is not valid',r.json()['error'])
            self.assertFalse(mock_slides_manager_cls.called)

            session.presentations.create(document=slides, rev=slides.rev, order=1)

            # Bad names
            r = self.client.post(url, {'oldIndex':1})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()['success'],False)
            self.assertIn('name is not valid',r.json()['error'])
            self.assertFalse(mock_slides_manager_cls.called)

            r = self.client.post(url, {'oldIndex':1, 'name':'garbage' })
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()['success'],False)
            self.assertIn('name is not valid',r.json()['error'])
            self.assertFalse(mock_slides_manager_cls.called)

            slides2 = DocumentFactory(type_id='slides')

            # index/name mismatch
            r = self.client.post(url, {'oldIndex':1, 'name':slides2.name })
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()['success'],False)
            self.assertIn('SessionPresentation not found',r.json()['error'])
            self.assertFalse(mock_slides_manager_cls.called)

            session.presentations.create(document=slides2, rev=slides2.rev, order=2)
            r = self.client.post(url, {'oldIndex':1, 'name':slides2.name })
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()['success'],False)
            self.assertIn('Name does not match index',r.json()['error'])
            self.assertFalse(mock_slides_manager_cls.called)

            # valid removal
            r = self.client.post(url, {'oldIndex':1, 'name':slides.name })
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()['success'],True)
            self.assertEqual(session.presentations.count(),1)
            self.assertTrue(mock_slides_manager_cls.called)
            self.assertEqual(mock_slides_manager_cls.call_args, call(api_config="fake settings"))
            self.assertTrue(mock_slides_manager_cls.return_value.delete.called)
            self.assertEqual(mock_slides_manager_cls.return_value.delete.call_args, call(session=session, slides=slides))
            mock_slides_manager_cls.reset_mock()

            session2 = SessionFactory(group=session.group, meeting=session.meeting)
            sp_list = SessionPresentationFactory.create_batch(5, document__type_id='slides', session=session2)
            for num, sp in enumerate(session2.presentations.filter(document__type_id='slides'),start=1):
                sp.order = num
                sp.save()

            url = urlreverse('ietf.meeting.views.ajax_remove_slides_from_session', kwargs={'session_id':session2.pk, 'num':session2.meeting.number})

            # delete at first of list
            r = self.client.post(url, {'oldIndex':1, 'name':sp_list[0].document.name })
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()['success'],True)
            self.assertFalse(session2.presentations.filter(pk=sp_list[0].pk).exists())
            self.assertEqual(list(session2.presentations.order_by('order').values_list('order',flat=True)), list(range(1,5)))
            self.assertTrue(mock_slides_manager_cls.called)
            self.assertEqual(mock_slides_manager_cls.call_args, call(api_config="fake settings"))
            self.assertTrue(mock_slides_manager_cls.return_value.delete.called)
            self.assertEqual(mock_slides_manager_cls.return_value.delete.call_args, call(session=session2, slides=sp_list[0].document))
            mock_slides_manager_cls.reset_mock()

            # delete in middle of list
            r = self.client.post(url, {'oldIndex':4, 'name':sp_list[4].document.name })
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()['success'],True)
            self.assertFalse(session2.presentations.filter(pk=sp_list[4].pk).exists())
            self.assertEqual(list(session2.presentations.order_by('order').values_list('order',flat=True)), list(range(1,4)))
            self.assertTrue(mock_slides_manager_cls.called)
            self.assertEqual(mock_slides_manager_cls.call_args, call(api_config="fake settings"))
            self.assertTrue(mock_slides_manager_cls.return_value.delete.called)
            self.assertEqual(mock_slides_manager_cls.return_value.delete.call_args, call(session=session2, slides=sp_list[4].document))
            mock_slides_manager_cls.reset_mock()

            # delete at end of list
            r = self.client.post(url, {'oldIndex':2, 'name':sp_list[2].document.name })
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()['success'],True)
            self.assertFalse(session2.presentations.filter(pk=sp_list[2].pk).exists())
            self.assertEqual(list(session2.presentations.order_by('order').values_list('order',flat=True)), list(range(1,3)))
            self.assertTrue(mock_slides_manager_cls.called)
            self.assertEqual(mock_slides_manager_cls.call_args, call(api_config="fake settings"))
            self.assertTrue(mock_slides_manager_cls.return_value.delete.called)
            self.assertEqual(mock_slides_manager_cls.return_value.delete.call_args, call(session=session2, slides=sp_list[2].document))
            mock_slides_manager_cls.reset_mock()

    @override_settings(MEETECHO_API_CONFIG="fake settings")  # enough to trigger API calls
    @patch("ietf.meeting.views.SlidesManager")
    def test_reorder_slides_in_session(self, mock_slides_manager_cls):
        def _sppk_at(sppk, positions):
            return [sppk[p-1] for p in positions]
        chair_role = RoleFactory(name_id='chair')
        session = SessionFactory(group=chair_role.group, meeting__date=date_today() - datetime.timedelta(days=90))
        sp_list = SessionPresentationFactory.create_batch(5, document__type_id='slides', session=session)
        sppk = [o.pk for o in sp_list]
        for num, sp in enumerate(sp_list, start=1):
            sp.order = num
            sp.save()
        url = urlreverse('ietf.meeting.views.ajax_reorder_slides_in_session', kwargs={'session_id':session.pk, 'num':session.meeting.number})

        for type_id in ['ietf','interim']:
            
            session.meeting.type_id = type_id
            session.meeting.date = date_today()-datetime.timedelta(days=90)
            session.meeting.save()

            # Not a valid user
            r = self.client.post(url, {'oldIndex':1, 'newIndex':2 })
            self.assertEqual(r.status_code, 403)
            self.assertIn('have permission', unicontent(r))
            self.assertFalse(mock_slides_manager_cls.called)

            self.client.login(username=chair_role.person.user.username, password=chair_role.person.user.username+"+password")

            # Past submission cutoff
            r = self.client.post(url, {'oldIndex':1, 'newIndex':2 })
            self.assertEqual(r.status_code, 403)
            self.assertIn('materials cutoff', unicontent(r))
            self.assertFalse(mock_slides_manager_cls.called)

            session.meeting.date = date_today()
            session.meeting.save()

            # Bad index values
            r = self.client.post(url, {'oldIndex':0, 'newIndex':2 })
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()['success'],False)
            self.assertIn('index is not valid',r.json()['error'])
            self.assertFalse(mock_slides_manager_cls.called)

            r = self.client.post(url, {'oldIndex':2, 'newIndex':6 })
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()['success'],False)
            self.assertIn('index is not valid',r.json()['error'])
            self.assertFalse(mock_slides_manager_cls.called)

            r = self.client.post(url, {'oldIndex':2, 'newIndex':2 })
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()['success'],False)
            self.assertIn('index is not valid',r.json()['error'])
            self.assertFalse(mock_slides_manager_cls.called)

            # Move from beginning
            r = self.client.post(url, {'oldIndex':1, 'newIndex':3})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()['success'],True)
            self.assertEqual(list(session.presentations.order_by('order').values_list('pk',flat=True)),_sppk_at(sppk,[2,3,1,4,5]))
            self.assertTrue(mock_slides_manager_cls.called)
            self.assertEqual(mock_slides_manager_cls.call_args, call(api_config="fake settings"))
            self.assertTrue(mock_slides_manager_cls.return_value.send_update.called)
            self.assertEqual(mock_slides_manager_cls.return_value.send_update.call_args, call(session))
            mock_slides_manager_cls.reset_mock()

            # Move to beginning
            r = self.client.post(url, {'oldIndex':3, 'newIndex':1})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()['success'],True)
            self.assertEqual(list(session.presentations.order_by('order').values_list('pk',flat=True)),_sppk_at(sppk,[1,2,3,4,5]))
            self.assertTrue(mock_slides_manager_cls.called)
            self.assertEqual(mock_slides_manager_cls.call_args, call(api_config="fake settings"))
            self.assertTrue(mock_slides_manager_cls.return_value.send_update.called)
            self.assertEqual(mock_slides_manager_cls.return_value.send_update.call_args, call(session))
            mock_slides_manager_cls.reset_mock()

            # Move from end
            r = self.client.post(url, {'oldIndex':5, 'newIndex':3})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()['success'],True)
            self.assertEqual(list(session.presentations.order_by('order').values_list('pk',flat=True)),_sppk_at(sppk,[1,2,5,3,4]))
            self.assertTrue(mock_slides_manager_cls.called)
            self.assertEqual(mock_slides_manager_cls.call_args, call(api_config="fake settings"))
            self.assertTrue(mock_slides_manager_cls.return_value.send_update.called)
            self.assertEqual(mock_slides_manager_cls.return_value.send_update.call_args, call(session))
            mock_slides_manager_cls.reset_mock()

            # Move to end
            r = self.client.post(url, {'oldIndex':3, 'newIndex':5})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()['success'],True)
            self.assertEqual(list(session.presentations.order_by('order').values_list('pk',flat=True)),_sppk_at(sppk,[1,2,3,4,5]))
            self.assertTrue(mock_slides_manager_cls.called)
            self.assertEqual(mock_slides_manager_cls.call_args, call(api_config="fake settings"))
            self.assertTrue(mock_slides_manager_cls.return_value.send_update.called)
            self.assertEqual(mock_slides_manager_cls.return_value.send_update.call_args, call(session))
            mock_slides_manager_cls.reset_mock()

            # Move beginning to end
            r = self.client.post(url, {'oldIndex':1, 'newIndex':5})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()['success'],True)
            self.assertEqual(list(session.presentations.order_by('order').values_list('pk',flat=True)),_sppk_at(sppk,[2,3,4,5,1]))
            self.assertTrue(mock_slides_manager_cls.called)
            self.assertEqual(mock_slides_manager_cls.call_args, call(api_config="fake settings"))
            self.assertTrue(mock_slides_manager_cls.return_value.send_update.called)
            self.assertEqual(mock_slides_manager_cls.return_value.send_update.call_args, call(session))
            mock_slides_manager_cls.reset_mock()

            # Move middle to middle 
            r = self.client.post(url, {'oldIndex':3, 'newIndex':4})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()['success'],True)
            self.assertEqual(list(session.presentations.order_by('order').values_list('pk',flat=True)),_sppk_at(sppk,[2,3,5,4,1]))
            self.assertTrue(mock_slides_manager_cls.called)
            self.assertEqual(mock_slides_manager_cls.call_args, call(api_config="fake settings"))
            self.assertTrue(mock_slides_manager_cls.return_value.send_update.called)
            self.assertEqual(mock_slides_manager_cls.return_value.send_update.call_args, call(session))
            mock_slides_manager_cls.reset_mock()

            r = self.client.post(url, {'oldIndex':3, 'newIndex':2})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()['success'],True)
            self.assertEqual(list(session.presentations.order_by('order').values_list('pk',flat=True)),_sppk_at(sppk,[2,5,3,4,1]))
            self.assertTrue(mock_slides_manager_cls.called)
            self.assertEqual(mock_slides_manager_cls.call_args, call(api_config="fake settings"))
            self.assertTrue(mock_slides_manager_cls.return_value.send_update.called)
            self.assertEqual(mock_slides_manager_cls.return_value.send_update.call_args, call(session))
            mock_slides_manager_cls.reset_mock()

            # Reset for next iteration in the loop
            session.presentations.update(order=F('pk'))
            self.client.logout()


    def test_slide_order_reconditioning(self):
        chair_role = RoleFactory(name_id='chair')
        session = SessionFactory(group=chair_role.group, meeting__date=date_today() - datetime.timedelta(days=90))
        sp_list = SessionPresentationFactory.create_batch(5, document__type_id='slides', session=session)
        for num, sp in enumerate(sp_list, start=1):
            sp.order = 2*num
            sp.save()

        try:
            condition_slide_order(session)
        except AssertionError:
            pass

        self.assertEqual(list(session.presentations.order_by('order').values_list('order',flat=True)),list(range(1,6)))


class EditTests(TestCase):
    """Test schedule edit operations"""

    def test_official_record_schedule_is_read_only(self):
        def _set_date_offset_and_retrieve_page(meeting, days_offset, client):
            meeting.date = date_today() + datetime.timedelta(days=days_offset)
            meeting.save()
            client.login(username="secretary", password="secretary+password")
            url = urlreverse("ietf.meeting.views.edit_meeting_schedule", kwargs=dict(num=meeting.number))
            r = client.get(url)
            q = PyQuery(r.content)
            return(r, q)

        # Setup
        ####################################################################################

        # Basic test data
        meeting = make_meeting_test_data()

        # Set the secretary as the owner of the schedule
        schedule = meeting.schedule
        schedule.owner = Person.objects.get(user__username="secretary")
        schedule.save()

        # Tests
        ####################################################################################

        # 1) Check that we get told the page is not editable
        #######################################################
        r, q = _set_date_offset_and_retrieve_page(meeting,
                                                  0 - 2 - meeting.days, # Meeting ended 2 days ago
                                                  self.client)
        self.assertTrue(q(""".alert:contains("You can't edit this schedule")"""))
        self.assertTrue(q(""".alert:contains("This is the official schedule for a meeting in the past")"""))

        # 2) An ongoing meeting
        #######################################################
        r, q = _set_date_offset_and_retrieve_page(meeting,
                                                  0, # Meeting starts today
                                                  self.client)
        self.assertFalse(q(""".alert:contains("You can't edit this schedule")"""))
        self.assertFalse(q(""".alert:contains("This is the official schedule for a meeting in the past")"""))

        # 3) A meeting in the future
        #######################################################
        r, q = _set_date_offset_and_retrieve_page(meeting,
                                                  7, # Meeting starts next week
                                                  self.client)
        self.assertFalse(q(""".alert:contains("You can't edit this schedule")"""))
        self.assertFalse(q(""".alert:contains("This is the official schedule for a meeting in the past")"""))

    def test_edit_meeting_schedule(self):
        meeting = make_meeting_test_data()

        self.client.login(username="secretary", password="secretary+password")

        s1 = Session.objects.filter(meeting=meeting, type='regular').first()
        s2 = Session.objects.filter(meeting=meeting, type='regular').exclude(group=s1.group).first()
        s1.comments = "Hello world!"
        s1.attendees = 1234
        s1.save()

        Constraint.objects.create(
            meeting=meeting,
            source=s1.group,
            target=s2.group,
            name=ConstraintName.objects.get(slug="conflict"),
        )

        p = Person.objects.order_by('pk')[1]

        Constraint.objects.create(
            meeting=meeting,
            source=s1.group,
            person=p,
            name=ConstraintName.objects.get(slug="bethere"),
        )
        
        Constraint.objects.create(
            meeting=meeting,
            source=s2.group,
            person=p,
            name=ConstraintName.objects.get(slug="bethere"),
        )

        room = Room.objects.get(meeting=meeting, session_types='regular')
        base_timeslot = TimeSlot.objects.create(meeting=meeting, type_id='regular', location=room,
                                                duration=datetime.timedelta(minutes=50),
                                                time=meeting.tz().localize(
                                                    datetime.datetime.combine(meeting.date + datetime.timedelta(days=2), datetime.time(9, 30))
                                                ))

        timeslots = list(TimeSlot.objects.filter(meeting=meeting, type='regular').order_by('time'))

        base_session = SessionFactory(meeting=meeting, group=Group.objects.get(acronym="irg"),
                                      attendees=20, requested_duration=datetime.timedelta(minutes=30),
                                      add_to_schedule=False)
        SchedulingEvent.objects.create(session=base_session, status_id='schedw', by=Person.objects.get(user__username='secretary'))
        SchedTimeSessAssignment.objects.create(timeslot=base_timeslot, session=base_session, schedule=meeting.schedule.base)


        # check we have the grid and everything set up as a baseline -
        # the Javascript tests check that the Javascript can work with
        # it
        url = urlreverse("ietf.meeting.views.edit_meeting_schedule", kwargs=dict(num=meeting.number))
        r = self.client.get(url)
        q = PyQuery(r.content)

        self.assertTrue(q(".room-name:contains(\"{}\")".format(room.name)))
        self.assertTrue(q(".room-name:contains(\"{}\")".format(room.capacity)))

        self.assertTrue(q("#timeslot{}".format(timeslots[0].pk)))

        for s in [s1, s2]:
            e = q("#session{}".format(s.pk))

            # should be link to edit/cancel session
            edit_session_url = urlreverse(
                'ietf.meeting.views.edit_session', kwargs={'session_id': s.pk}
            ) + f'?sched={meeting.schedule.pk}'
            self.assertTrue(
                e.find(f'a[href="{edit_session_url}"]')
            )
            self.assertTrue(
                e.find('a[href="{}?sched={}"]'.format(
                    urlreverse('ietf.meeting.views.cancel_session', kwargs={'session_id': s.pk}),
                    meeting.schedule.pk,
                ))
            )

            # info in the item representing the session that can be moved around
            self.assertIn(s.group.acronym, e.find(".session-label").text())
            if s.comments:
                self.assertTrue(e.find(".comments"))
            if s.attendees is not None:
                self.assertIn(str(s.attendees), e.find(".attendees").text())
            self.assertTrue(e.hasClass("parent-{}".format(s.group.parent.acronym)))

            constraints = e.find(".constraints > span")
            s_other = s2 if s == s1 else s1
            self.assertEqual(len(constraints), 3)
            self.assertEqual(constraints.eq(0).attr("data-sessions"), str(s_other.pk))
            self.assertEqual(constraints.eq(0).find(".bi-people-fill").parent().text(), "1") # 1 person in the constraint
            self.assertEqual(constraints.eq(1).attr("data-sessions"), str(s_other.pk))
            self.assertEqual(constraints.eq(1).find(".encircled").text(), "1" if s_other == s2 else "-1")
            self.assertEqual(constraints.eq(2).attr("data-sessions"), str(s_other.pk))
            self.assertEqual(constraints.eq(2).find(".encircled").text(), "AD")

            # session info for the panel
            self.assertIn(str(round(s.requested_duration.total_seconds() / 60.0 / 60, 1)), e.find(".session-info .title").text())

            event = SchedulingEvent.objects.filter(session=s).order_by("id").first()
            if event:
                self.assertTrue(e.find("div:contains(\"{}\")".format(event.by.name)))

            if s.comments:
                self.assertIn(s.comments, e.find(".comments").text())

        formatted_constraints1 = q("#session{} .session-info .formatted-constraints > *".format(s1.pk))
        self.assertIn(s2.group.acronym, formatted_constraints1.eq(0).html())
        self.assertIn(p.name, formatted_constraints1.eq(1).html())

        formatted_constraints2 = q("#session{} .session-info .formatted-constraints > *".format(s2.pk))
        self.assertIn(p.name, formatted_constraints2.eq(0).html())

        self.assertEqual(len(q("#session{}.readonly".format(base_session.pk))), 1)

        self.assertTrue(q(".alert:contains(\"You can't edit this schedule\")"))

        # can't change anything
        r = self.client.post(url, {
            'action': 'assign',
            'timeslot': timeslots[0].pk,
            'session': s1.pk,
        })
        self.assertEqual(r.status_code, 403)
        
        # turn us into owner
        schedule = meeting.schedule
        schedule.owner = Person.objects.get(user__username="secretary")
        schedule.save()

        meeting.schedule = None
        meeting.save()

        url = urlreverse("ietf.meeting.views.edit_meeting_schedule", kwargs=dict(num=meeting.number, owner=schedule.owner_email(), name=schedule.name))
        r = self.client.get(url)
        q = PyQuery(r.content)
        self.assertTrue(not q("em:contains(\"You can't edit this schedule\")"))

        SchedTimeSessAssignment.objects.filter(session=s1).delete()

        # assign
        r = self.client.post(url, {
            'action': 'assign',
            'timeslot': timeslots[0].pk,
            'session': s1.pk,
        })
        self.assertEqual(json.loads(r.content)['success'], True)
        self.assertEqual(SchedTimeSessAssignment.objects.get(schedule=schedule, session=s1).timeslot, timeslots[0])

        # move assignment on unofficial schedule
        r = self.client.post(url, {
            'action': 'assign',
            'timeslot': timeslots[1].pk,
            'session': s1.pk,
        })
        self.assertEqual(json.loads(r.content)['success'], True)
        self.assertEqual(SchedTimeSessAssignment.objects.get(schedule=schedule, session=s1).timeslot, timeslots[1])

        # move assignment on official schedule, leaving tombstone
        meeting.schedule = schedule
        meeting.save()
        SchedulingEvent.objects.create(
            session=s1,
            status=SessionStatusName.objects.get(slug='sched'),
            by=Person.objects.get(name='(System)')
        )
        r = self.client.post(url, {
            'action': 'assign',
            'timeslot': timeslots[0].pk,
            'session': s1.pk,
        })
        json_content = json.loads(r.content)
        self.assertEqual(json_content['success'], True)
        self.assertEqual(SchedTimeSessAssignment.objects.get(schedule=schedule, session=s1).timeslot, timeslots[0])

        sessions_for_group = Session.objects.filter(group=s1.group, meeting=meeting)
        self.assertEqual(len(sessions_for_group), 2)
        s_tombstone = [s for s in sessions_for_group if s != s1][0]
        self.assertEqual(s_tombstone.tombstone_for, s1)
        tombstone_event = SchedulingEvent.objects.get(session=s_tombstone)
        self.assertEqual(tombstone_event.status_id, 'resched')

        self.assertEqual(SchedTimeSessAssignment.objects.get(schedule=schedule, session=s_tombstone).timeslot, timeslots[1])
        self.assertTrue(PyQuery(json_content['tombstone'])("#session{}.readonly".format(s_tombstone.pk)).html())

        # unassign
        r = self.client.post(url, {
            'action': 'unassign',
            'session': s1.pk,
        })
        self.assertEqual(json.loads(r.content)['success'], True)
        self.assertEqual(list(SchedTimeSessAssignment.objects.filter(schedule=schedule, session=s1)), [])

        # try swapping days
        SchedTimeSessAssignment.objects.create(schedule=schedule, session=s1, timeslot=timeslots[0])
        self.assertEqual(len(SchedTimeSessAssignment.objects.filter(schedule=schedule, session=s1, timeslot=timeslots[0])), 1)
        self.assertEqual(len(SchedTimeSessAssignment.objects.filter(schedule=schedule, session=s2, timeslot=timeslots[1])), 1)
        self.assertEqual(list(SchedTimeSessAssignment.objects.filter(schedule=schedule, timeslot=timeslots[2])), [])

        r = self.client.post(url, {
            'action': 'swapdays',
            'source_day': timeslots[0].time.date().isoformat(),
            'target_day': timeslots[2].time.date().isoformat(),
        })
        self.assertEqual(r.status_code, 302)

        self.assertEqual(list(SchedTimeSessAssignment.objects.filter(schedule=schedule, timeslot=timeslots[0])), [])
        self.assertEqual(list(SchedTimeSessAssignment.objects.filter(schedule=schedule, timeslot=timeslots[1])), [])
        self.assertEqual(len(SchedTimeSessAssignment.objects.filter(schedule=schedule, session=s1, timeslot=timeslots[2])), 1)
        self.assertEqual(list(SchedTimeSessAssignment.objects.filter(schedule=schedule, session=s2)), [])

        # swap back
        r = self.client.post(url, {
            'action': 'swapdays',
            'source_day': timeslots[2].time.date().isoformat(),
            'target_day': timeslots[0].time.date().isoformat(),
        })
        self.assertEqual(r.status_code, 302)

        self.assertEqual(len(SchedTimeSessAssignment.objects.filter(schedule=schedule, session=s1, timeslot=timeslots[0])), 1)
        self.assertEqual(list(SchedTimeSessAssignment.objects.filter(schedule=schedule, timeslot=timeslots[1])), [])
        self.assertEqual(list(SchedTimeSessAssignment.objects.filter(schedule=schedule, timeslot=timeslots[2])), [])
        
    def test_edit_meeting_timeslots_and_misc_sessions(self):
        meeting = make_meeting_test_data()

        self.client.login(username="secretary", password="secretary+password")

        # check we have the grid and everything set up as a baseline -
        # the Javascript tests check that the Javascript can work with
        # it
        url = urlreverse("ietf.meeting.views.edit_meeting_timeslots_and_misc_sessions", kwargs=dict(num=meeting.number, owner=meeting.schedule.base.owner_email(), name=meeting.schedule.base.name))
        r = self.client.get(url)
        q = PyQuery(r.content)

        breakfast_room = Room.objects.get(meeting=meeting, name="Breakfast Room")
        break_room = Room.objects.get(meeting=meeting, name="Break Area")
        reg_room = Room.objects.get(meeting=meeting, name="Registration Area")

        for i in range(meeting.days):
            self.assertTrue(q("[data-day=\"{}\"]".format((meeting.date + datetime.timedelta(days=i)).isoformat())))

        self.assertTrue(q(".room-label:contains(\"{}\")".format(breakfast_room.name)))
        self.assertTrue(q(".room-label:contains(\"{}\")".format(break_room.name)))
        self.assertTrue(q(".room-label:contains(\"{}\")".format(reg_room.name)))

        break_slot = TimeSlot.objects.get(location=break_room, type='break')

        room_row = q(".room-row[data-day=\"{}\"][data-room=\"{}\"]".format(break_slot.time.date().isoformat(), break_slot.location_id))
        self.assertTrue(room_row)
        self.assertTrue(room_row.find("#timeslot{}".format(break_slot.pk)))

        self.assertTrue(q(".timeslot-form"))

        # add timeslot
        ietf_group = Group.objects.get(acronym='ietf')

        r = self.client.post(url, {
            'day': meeting.date,
            'time': '08:30',
            'duration': '1:30',
            'location': break_room.pk,
            'show_location': 'on',
            'type': 'other',
            'group': ietf_group.pk,
            'name': "IETF Testing",
            'short': "ietf-testing",
            'scroll': 1234,
            'action': 'add-timeslot',
        })
        self.assertNoFormPostErrors(r)
        self.assertIn("#scroll=1234", r['Location'])

        test_timeslot = TimeSlot.objects.get(meeting=meeting, name="IETF Testing")
        self.assertEqual(
            test_timeslot.time,
            meeting.tz().localize(
                datetime.datetime.combine(meeting.date, datetime.time(8, 30))
            ),
        )
        self.assertEqual(test_timeslot.duration, datetime.timedelta(hours=1, minutes=30))
        self.assertEqual(test_timeslot.location_id, break_room.pk)
        self.assertEqual(test_timeslot.show_location, True)
        self.assertEqual(test_timeslot.type_id, 'other')

        test_session = Session.objects.get(meeting=meeting, timeslotassignments__timeslot=test_timeslot)
        self.assertEqual(test_session.short, 'ietf-testing')
        self.assertEqual(test_session.group, ietf_group)

        self.assertTrue(SchedulingEvent.objects.filter(session=test_session, status='sched'))

        # edit timeslot
        r = self.client.get(url, {
            'timeslot': test_timeslot.pk,
            'action': 'edit-timeslot',
        })
        self.assertEqual(r.status_code, 200)
        edit_form_html = json.loads(r.content)['form']
        q = PyQuery(edit_form_html)
        self.assertEqual(q("[name=name]").val(), test_timeslot.name)
        self.assertEqual(q("[name=location]").val(), str(test_timeslot.location_id))
        self.assertEqual(q("[name=timeslot]").val(), str(test_timeslot.pk))
        self.assertEqual(q("[name=type]").val(), str(test_timeslot.type_id))
        self.assertEqual(q("[name=group]").val(), str(ietf_group.pk))

        iab_group = Group.objects.get(acronym='iab')

        r = self.client.post(url, {
            'timeslot': test_timeslot.pk,
            'day': meeting.date,
            'time': '09:30',
            'duration': '1:00',
            'location': breakfast_room.pk,
            'type': 'other',
            'group': iab_group.pk,
            'name': "IETF Testing 2",
            'short': "ietf-testing2",
            'action': 'edit-timeslot',
        })
        self.assertNoFormPostErrors(r)
        test_timeslot.refresh_from_db()
        self.assertEqual(
            test_timeslot.time,
            meeting.tz().localize(
                datetime.datetime.combine(meeting.date, datetime.time(9, 30))
            ),
        )
        self.assertEqual(test_timeslot.duration, datetime.timedelta(hours=1))
        self.assertEqual(test_timeslot.location_id, breakfast_room.pk)
        self.assertEqual(test_timeslot.show_location, False)
        self.assertEqual(test_timeslot.type_id, 'other')

        test_session.refresh_from_db()
        self.assertEqual(test_session.short, 'ietf-testing2')
        self.assertEqual(test_session.group, iab_group)

        # cancel timeslot
        r = self.client.post(url, {
            'timeslot': test_timeslot.pk,
            'action': 'cancel-timeslot',
        })
        self.assertNoFormPostErrors(r)

        event = SchedulingEvent.objects.filter(
            session__timeslotassignments__timeslot=test_timeslot
        ).order_by('-id').first()
        self.assertEqual(event.status_id, 'canceled')

        # delete timeslot
        test_presentation = Document.objects.create(name='slides-test', type_id='slides')
        SessionPresentation.objects.create(
            document=test_presentation,
            rev='1',
            session=test_session
        )

        r = self.client.post(url, {
            'timeslot': test_timeslot.pk,
            'action': 'delete-timeslot',
        })
        self.assertNoFormPostErrors(r)

        self.assertEqual(list(TimeSlot.objects.filter(pk=test_timeslot.pk)), [])
        self.assertEqual(list(Session.objects.filter(pk=test_session.pk)), [])
        self.assertEqual(test_presentation.get_state_slug(), 'deleted')

        # set agenda note
        assignment = SchedTimeSessAssignment.objects.filter(session__group__acronym='mars', schedule=meeting.schedule).first()

        url = urlreverse("ietf.meeting.views.edit_meeting_timeslots_and_misc_sessions", kwargs=dict(num=meeting.number, owner=meeting.schedule.owner_email(), name=meeting.schedule.name))

        r = self.client.post(url, {
            'timeslot': assignment.timeslot_id,
            'day': assignment.timeslot.time.date().isoformat(),
            'time': assignment.timeslot.time.time().isoformat(),
            'duration': assignment.timeslot.duration,
            'location': assignment.timeslot.location_id,
            'type': assignment.slot_type().slug,
            'name': assignment.timeslot.name,
            'agenda_note': "New Test Note",
            'action': 'edit-timeslot',
        })
        self.assertNoFormPostErrors(r)

        assignment.session.refresh_from_db()
        self.assertEqual(assignment.session.agenda_note, "New Test Note")

    def test_edit_meeting_schedule_conflict_types(self):
        """The meeting schedule editor should show the constraint types enabled for the meeting"""
        meeting = MeetingFactory(
            type_id='ietf',
            group_conflicts=[],  # show none to start with
        )
        s1 = SessionFactory(
            meeting=meeting,
            type_id='regular',
            attendees=12,
            comments='chair conflict',
        )

        s2 = SessionFactory(
            meeting=meeting,
            type_id='regular',
            attendees=34,
            comments='old-fashioned conflict',
        )

        Constraint.objects.create(
            meeting=meeting,
            source=s1.group,
            target=s2.group,
            name=ConstraintName.objects.get(slug="chair_conflict"),
        )

        Constraint.objects.create(
            meeting=meeting,
            source=s2.group,
            target=s1.group,
            name=ConstraintName.objects.get(slug="conflict"),
        )


        # log in as secretary so we have access
        self.client.login(username="secretary", password="secretary+password")

        url = urlreverse("ietf.meeting.views.edit_meeting_schedule", kwargs=dict(num=meeting.number))

        # Should have no conflict constraints listed because the meeting has all disabled
        r = self.client.get(url)
        q = PyQuery(r.content)

        self.assertEqual(len(q('#session{} span.constraints > span'.format(s1.pk))), 0)
        self.assertEqual(len(q('#session{} span.constraints > span'.format(s2.pk))), 0)

        # Now enable the 'chair_conflict' constraint only
        chair_conflict = ConstraintName.objects.get(slug='chair_conflict')
        chair_conf_label = b'<i class="bi bi-circle-fill"/>'  # result of etree.tostring(etree.fromstring(editor_label))
        meeting.group_conflict_types.add(chair_conflict)
        r = self.client.get(url)
        q = PyQuery(r.content)

        # verify that there is a constraint pointing from 1 to 2
        #
        # The constraint is represented in the HTML as
        # <div id="session<pk>">
        #   [...]
        #   <span class="constraints">
        #     <span data-sessions="<other pk>">[constraint label]</span>
        #   </span>
        # </div>
        #
        # Where the constraint label is the editor_label for the ConstraintName.
        # If this pk is the constraint target, the editor_label includes a
        # '-' prefix, which may be before the editor_label or inserted inside
        # it.
        #
        # For simplicity, this test is tied to the current values of editor_label.
        # It also assumes the order of constraints will be constant.
        # If those change, the test will need to be updated.
        s1_constraints = q('#session{} span.constraints > span'.format(s1.pk))
        s2_constraints = q('#session{} span.constraints > span'.format(s2.pk))

        # Check the forward constraint
        self.assertEqual(len(s1_constraints), 1)
        self.assertEqual(s1_constraints[0].attrib['data-sessions'], str(s2.pk))
        self.assertEqual(s1_constraints[0].text, None)  # no '-' prefix on the source
        self.assertEqual(tostring(s1_constraints[0][0]), chair_conf_label)  # [0][0] is the innermost <span>

        # And the reverse constraint
        self.assertEqual(len(s2_constraints), 1)
        self.assertEqual(s2_constraints[0].attrib['data-sessions'], str(s1.pk))
        self.assertEqual(s2_constraints[0].text, '-')  # '-' prefix on the target
        self.assertEqual(tostring(s2_constraints[0][0]), chair_conf_label)  # [0][0] is the innermost <span>

        # Now also enable the 'conflict' constraint
        conflict = ConstraintName.objects.get(slug='conflict')
        conf_label = b'<span class="encircled">1</span>'
        conf_label_reversed = b'<span class="encircled">-1</span>'  # the '-' is inside the span!
        meeting.group_conflict_types.add(conflict)
        r = self.client.get(url)
        q = PyQuery(r.content)

        s1_constraints = q('#session{} span.constraints > span'.format(s1.pk))
        s2_constraints = q('#session{} span.constraints > span'.format(s2.pk))

        # Check the forward constraint
        self.assertEqual(len(s1_constraints), 2)
        self.assertEqual(s1_constraints[0].attrib['data-sessions'], str(s2.pk))
        self.assertEqual(s1_constraints[0].text, None)  # no '-' prefix on the source
        self.assertEqual(tostring(s1_constraints[0][0]), chair_conf_label)  # [0][0] is the innermost <span>

        self.assertEqual(s1_constraints[1].attrib['data-sessions'], str(s2.pk))
        self.assertEqual(tostring(s1_constraints[1][0]), conf_label_reversed)  # [0][0] is the innermost <span>

        # And the reverse constraint
        self.assertEqual(len(s2_constraints), 2)
        self.assertEqual(s2_constraints[0].attrib['data-sessions'], str(s1.pk))
        self.assertEqual(s2_constraints[0].text, '-')  # '-' prefix on the target
        self.assertEqual(tostring(s2_constraints[0][0]), chair_conf_label)  # [0][0] is the innermost <span>

        self.assertEqual(s2_constraints[1].attrib['data-sessions'], str(s1.pk))
        self.assertEqual(tostring(s2_constraints[1][0]), conf_label)  # [0][0] is the innermost <span>

    def test_new_meeting_schedule(self):
        """Can create a meeting schedule from scratch"""
        meeting = make_meeting_test_data()
        self.client.login(username="secretary", password="secretary+password")

        # new from scratch
        url = urlreverse("ietf.meeting.views.new_meeting_schedule", kwargs=dict(num=meeting.number))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        r = self.client.post(url, {
            'name': "scratch",
            'public': "on",
            'visible': "on",
            'notes': "New scratch",
            'base': meeting.schedule.base_id,
        })
        self.assertNoFormPostErrors(r)

        new_schedule = Schedule.objects.get(meeting=meeting, owner__user__username='secretary', name='scratch')
        self.assertEqual(new_schedule.public, True)
        self.assertEqual(new_schedule.visible, True)
        self.assertEqual(new_schedule.notes, "New scratch")
        self.assertEqual(new_schedule.origin, None)
        self.assertEqual(new_schedule.base_id, meeting.schedule.base_id)

    def test_copy_meeting_schedule(self):
        """Can create a copy of an existing meeting schedule"""
        meeting = make_meeting_test_data()
        self.client.login(username="secretary", password="secretary+password")

        url = urlreverse("ietf.meeting.views.new_meeting_schedule", kwargs=dict(num=meeting.number, owner=meeting.schedule.owner_email(), name=meeting.schedule.name))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        r = self.client.post(url, {
            'name': "copy",
            'public': "on",
            'notes': "New copy",
            'base': meeting.schedule.base_id,
        })
        self.assertNoFormPostErrors(r)

        new_schedule = Schedule.objects.get(meeting=meeting, owner__user__username='secretary', name='copy')
        self.assertEqual(new_schedule.public, True)
        self.assertEqual(new_schedule.visible, False)
        self.assertEqual(new_schedule.notes, "New copy")
        self.assertEqual(new_schedule.origin, meeting.schedule)
        self.assertEqual(new_schedule.base_id, meeting.schedule.base_id)

        old_assignments = {(a.session_id, a.timeslot_id) for a in SchedTimeSessAssignment.objects.filter(schedule=meeting.schedule)}
        for a in SchedTimeSessAssignment.objects.filter(schedule=new_schedule):
            self.assertIn((a.session_id, a.timeslot_id), old_assignments)

    def test_schedule_read_permissions(self):
        meeting = make_meeting_test_data()
        schedule = meeting.schedule

        # try to get non-existing agenda
        url = urlreverse("ietf.meeting.views.edit_meeting_schedule", kwargs=dict(num=meeting.number,
                                                                                 owner=schedule.owner_email(),
                                                                                 name="foo"))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 404)

        url = urlreverse("ietf.meeting.views.edit_meeting_schedule", kwargs=dict(num=meeting.number,
                                                                                 owner=schedule.owner_email(),
                                                                                 name=schedule.name))
        self.client.login(username='ad', password='ad+password')
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        schedule.visible = True
        schedule.public = False
        schedule.save()

        # get as anonymous doesn't work
        self.client.logout()
        r = self.client.get(url)
        self.assertEqual(r.status_code, 403)

        # public, now anonymous works
        schedule.public = True
        schedule.save()
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        # Secretariat can always see it
        schedule.visible = False
        schedule.public = False
        schedule.save()
        self.client.login(username="secretary", password="secretary+password")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

    def test_new_meeting_schedule_rejects_invalid_names(self):
        meeting = make_meeting_test_data()

        orig_schedule_count = meeting.schedule_set.count()
        self.client.login(username="ad", password="ad+password")
        url = urlreverse("ietf.meeting.views.new_meeting_schedule", kwargs=dict(num=meeting.number))
        r = self.client.post(url, {
            'name': "/no/this/should/not/work/it/is/too/long",
            'public': "on",
            'notes': "Name too long",
            'base': meeting.schedule.base_id,
        })
        self.assertEqual(r.status_code, 200)
        self.assertFormError(r.context["form"], 'name', 'Enter a valid value.')
        self.assertEqual(meeting.schedule_set.count(), orig_schedule_count, 'Schedule should not be created')

        r = self.client.post(url, {
            'name': "/invalid/chars/",
            'public': "on",
            'notes': "Name too long",
            'base': meeting.schedule.base_id,
        })
        self.assertEqual(r.status_code, 200)
        self.assertFormError(r.context["form"], 'name', 'Enter a valid value.')
        self.assertEqual(meeting.schedule_set.count(), orig_schedule_count, 'Schedule should not be created')

        # Non-ASCII alphanumeric characters
        r = self.client.post(url, {
            'name': "f\u00E9ling",
            'public': "on",
            'notes': "Name too long",
            'base': meeting.schedule.base_id,
        })
        self.assertEqual(r.status_code, 200)
        self.assertFormError(r.context["form"], 'name', 'Enter a valid value.')
        self.assertEqual(meeting.schedule_set.count(), orig_schedule_count, 'Schedule should not be created')

    def test_edit_session(self):
        session = SessionFactory(meeting__type_id='ietf', group__type_id='team')  # type determines allowed session purposes
        edit_meeting_url = urlreverse('ietf.meeting.views.edit_meeting_schedule', kwargs={'num': session.meeting.number})
        self.client.login(username='secretary', password='secretary+password')
        url = urlreverse('ietf.meeting.views.edit_session', kwargs={'session_id': session.pk})
        r = self.client.get(url)
        self.assertContains(r, 'Edit session', status_code=200)
        pq = PyQuery(r.content)
        back_button = pq(f'a[href="{edit_meeting_url}"]')
        self.assertEqual(len(back_button), 1)
        post_data = {
            'name': 'this is a name',
            'short': 'tian',
            'purpose': 'coding',
            'type': 'other',
            'requested_duration': '3600',
            'on_agenda': True,
            'remote_instructions': 'Do this do that',
            'attendees': '103',
            'comments': 'So much to say',
            'chat_room': 'xyzzy',
        }
        r = self.client.post(url, post_data)
        self.assertNoFormPostErrors(r)
        self.assertRedirects(r, edit_meeting_url)
        session = Session.objects.get(pk=session.pk)  # refresh objects from DB
        self.assertEqual(session.name, 'this is a name')
        self.assertEqual(session.short, 'tian')
        self.assertEqual(session.purpose_id, 'coding')
        self.assertEqual(session.type_id, 'other')
        self.assertEqual(session.requested_duration, datetime.timedelta(hours=1))
        self.assertEqual(session.on_agenda, True)
        self.assertEqual(session.remote_instructions, 'Do this do that')
        self.assertEqual(session.attendees, 103)
        self.assertEqual(session.comments, 'So much to say')
        self.assertEqual(session.chat_room, 'xyzzy')

        # Verify return to correct schedule when sched query parameter is present
        other_schedule = ScheduleFactory(meeting=session.meeting)
        r = self.client.get(url + f'?sched={other_schedule.pk}')
        edit_meeting_url = urlreverse(
            'ietf.meeting.views.edit_meeting_schedule',
            kwargs={
                'num': session.meeting.number,
                'owner': other_schedule.owner.email(),
                'name': other_schedule.name,
            },
        )
        pq = PyQuery(r.content)
        back_button = pq(f'a[href="{edit_meeting_url}"]')
        self.assertEqual(len(back_button), 1)
        r = self.client.post(url + f'?sched={other_schedule.pk}', post_data)
        self.assertRedirects(r, edit_meeting_url)

    def test_cancel_session(self):
        # session for testing with official schedule
        session = SessionFactory(meeting__type_id='ietf')
        url = urlreverse('ietf.meeting.views.cancel_session', kwargs={'session_id': session.pk})
        return_url = urlreverse('ietf.meeting.views.edit_meeting_schedule', kwargs={'num': session.meeting.number})
        # session for testing with unofficial schedule
        other_session = SessionFactory(meeting=session.meeting)
        unofficial_schedule = ScheduleFactory(meeting=other_session.meeting)
        url_unofficial = urlreverse(
            'ietf.meeting.views.cancel_session',
            kwargs={'session_id': other_session.pk},
        ) + f'?sched={unofficial_schedule.pk}'
        return_url_unofficial = urlreverse(
            'ietf.meeting.views.edit_meeting_schedule',
            kwargs={
                'num': other_session.meeting.number,
                'name': unofficial_schedule.name,
                'owner': unofficial_schedule.owner_email(),
            },
        )

        login_testing_unauthorized(self, 'secretary', url)
        r = self.client.get(url)
        self.assertContains(r, 'Cancel session', status_code=200)
        self.assertIn(return_url, r.content.decode())
        r = self.client.get(url_unofficial)
        self.assertContains(r, 'Cancel session', status_code=200)
        self.assertIn(return_url_unofficial, r.content.decode())

        r = self.client.post(url, {})
        self.assertFormError(r.context["form"], 'confirmed', 'This field is required.')
        r = self.client.post(url_unofficial, {})
        self.assertFormError(r.context["form"], 'confirmed', 'This field is required.')

        r = self.client.post(url, {'confirmed': 'on'})
        self.assertRedirects(r, return_url)
        session = Session.objects.with_current_status().get(pk=session.pk)
        self.assertEqual(session.current_status, 'canceled')
        r = self.client.get(url)
        self.assertRedirects(r, return_url)  # should redirect immediately when session is already canceled

        r = self.client.post(url_unofficial, {'confirmed': 'on'})
        self.assertRedirects(r, return_url_unofficial)
        other_session = Session.objects.with_current_status().get(pk=other_session.pk)
        self.assertEqual(other_session.current_status, 'canceled')
        r = self.client.get(url_unofficial)
        self.assertRedirects(r, return_url_unofficial)  # should redirect immediately when session is already canceled

    def test_edit_timeslots(self):
        meeting = make_meeting_test_data()

        self.client.login(username="secretary", password="secretary+password")
        r = self.client.get(urlreverse("ietf.meeting.views.edit_timeslots", kwargs=dict(num=meeting.number)))
        self.assertContains(r, meeting.room_set.all().first().name)

    def test_edit_timeslot_type(self):
        timeslot = TimeSlotFactory(meeting__type_id='ietf')
        url = urlreverse('ietf.meeting.views.edit_timeslot_type', kwargs=dict(num=timeslot.meeting.number,slot_id=timeslot.id))
        login_testing_unauthorized(self,"secretary",url)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        r = self.client.post(url,{'type':'other',})
        self.assertEqual(r.status_code, 302)
        timeslot = TimeSlot.objects.get(id=timeslot.id)
        self.assertEqual(timeslot.type.slug,'other')

    def test_slot_to_the_right(self):
        meeting = make_meeting_test_data()
        session = Session.objects.filter(meeting=meeting, group__acronym="mars").first()
        mars_scheduled = session.timeslotassignments.get(schedule__name='test-schedule')
        mars_slot = TimeSlot.objects.get(sessionassignments__session=session,sessionassignments__schedule__name='test-schedule')
        mars_ends = mars_slot.time + mars_slot.duration

        session = Session.objects.filter(meeting=meeting, group__acronym="ames").first()
        ames_slot_qs = TimeSlot.objects.filter(sessionassignments__session=session,sessionassignments__schedule__name='test-schedule')

        ames_slot_qs.update(time=mars_ends + datetime.timedelta(seconds=11 * 60))
        self.assertTrue(not mars_slot.slot_to_the_right)
        self.assertTrue(not mars_scheduled.slot_to_the_right)

        ames_slot_qs.update(time=mars_ends + datetime.timedelta(seconds=10 * 60))
        self.assertTrue(mars_slot.slot_to_the_right)
        self.assertTrue(mars_scheduled.slot_to_the_right)

    def test_updateview(self):
        """The updateview action should set visible timeslot types in the session"""
        meeting = MeetingFactory(type_id='ietf')
        url = urlreverse('ietf.meeting.views.edit_meeting_schedule', kwargs={'num': meeting.number})
        types_to_enable = ['regular', 'reg', 'other']
        r = self.client.post(
            url,
            {
                'action': 'updateview',
                'enabled_timeslot_types[]': types_to_enable,
            },
        )
        self.assertEqual(r.status_code, 200)
        session_data = self.client.session
        self.assertIn('edit_meeting_schedule', session_data)
        self.assertCountEqual(
            session_data['edit_meeting_schedule']['enabled_timeslot_types'],
            types_to_enable,
            'Should set types requested',
        )

        r = self.client.post(
            url,
            {
                'action': 'updateview',
                'enabled_timeslot_types[]': types_to_enable + ['faketype'],
            },
        )
        self.assertEqual(r.status_code, 200)
        session_data = self.client.session
        self.assertIn('edit_meeting_schedule', session_data)
        self.assertCountEqual(
            session_data['edit_meeting_schedule']['enabled_timeslot_types'],
            types_to_enable,
            'Should ignore unknown types',
        )

    def test_persistent_enabled_timeslot_types(self):
        meeting = MeetingFactory(type_id='ietf')
        TimeSlotFactory(meeting=meeting, type_id='other')
        TimeSlotFactory(meeting=meeting, type_id='reg')

        # test default behavior (only 'regular' enabled)
        r = self.client.get(urlreverse('ietf.meeting.views.edit_meeting_schedule', kwargs={'num': meeting.number}))
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('#timeslot-type-toggles-modal input[value="regular"][checked]')), 1)
        self.assertEqual(len(q('#timeslot-type-toggles-modal input[value="other"]:not([checked])')), 1)
        self.assertEqual(len(q('#timeslot-type-toggles-modal input[value="reg"]:not([checked])')), 1)

        # test with 'regular' and 'other' enabled via session store
        client_session = self.client.session  # must store as var, new session is created on access
        client_session['edit_meeting_schedule'] = {
            'enabled_timeslot_types': ['regular', 'other']
        }
        client_session.save()
        r = self.client.get(urlreverse('ietf.meeting.views.edit_meeting_schedule', kwargs={'num': meeting.number}))
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('#timeslot-type-toggles-modal input[value="regular"][checked]')), 1)
        self.assertEqual(len(q('#timeslot-type-toggles-modal input[value="other"][checked]')), 1)
        self.assertEqual(len(q('#timeslot-type-toggles-modal input[value="reg"]:not([checked])')), 1)


class SessionDetailsTests(TestCase):

    def test_session_details(self):

        group = GroupFactory.create(type_id='wg',state_id='active')
        session = SessionFactory.create(meeting__type_id='ietf',group=group, meeting__date=date_today() + datetime.timedelta(days=90))
        SessionPresentationFactory.create(session=session,document__type_id='draft',rev=None)
        SessionPresentationFactory.create(session=session,document__type_id='minutes')
        SessionPresentationFactory.create(session=session,document__type_id='slides')
        SessionPresentationFactory.create(session=session,document__type_id='agenda')

        url = urlreverse('ietf.meeting.views.session_details', kwargs=dict(num=session.meeting.number, acronym=group.acronym))
        r = self.client.get(url)
        self.assertTrue(all([x in unicontent(r) for x in ('slides','agenda','minutes','draft')]))
        self.assertNotContains(r, 'deleted')

    def test_session_details_has_import_minutes_buttons(self):
        group = GroupFactory.create(
            type_id='wg',
            state_id='active',
        )
        session = SessionFactory.create(
            meeting__type_id='ietf',
            group=group,
            meeting__date=date_today() + datetime.timedelta(days=90),
        )
        session_details_url = urlreverse(
            'ietf.meeting.views.session_details',
            kwargs={'num': session.meeting.number, 'acronym': group.acronym},
        )
        import_minutes_url = urlreverse(
            'ietf.meeting.views.import_session_minutes',
            kwargs={'num': session.meeting.number, 'session_id': session.pk},
        )

        # test without existing minutes
        with patch('ietf.meeting.views.can_manage_session_materials', return_value=False):
            r = self.client.get(session_details_url)
            self.assertEqual(r.status_code, 200)
            q = PyQuery(r.content)
            self.assertEqual(
                len(q(f'a[href="{import_minutes_url}"]')), 0,
                'Do not show import new minutes buttons to non-materials manager',
            )
        with patch('ietf.meeting.views.can_manage_session_materials', return_value=True):
            r = self.client.get(session_details_url)
            self.assertEqual(r.status_code, 200)
            q = PyQuery(r.content)
            self.assertGreater(
                len(q(f'a[href="{import_minutes_url}"]')), 0,
                'Show import new minutes buttons to materials manager',
            )

        # now create minutes and test that we can still have the import button
        SessionPresentationFactory.create(session=session,document__type_id='minutes')
        with patch('ietf.meeting.views.can_manage_session_materials', return_value=False):
            r = self.client.get(session_details_url)
            self.assertEqual(r.status_code, 200)
            q = PyQuery(r.content)
            self.assertEqual(
                len(q(f'a[href="{import_minutes_url}"]')), 0,
                'Do not show import revised minutes buttons to non-materials manager',
            )

        with patch('ietf.meeting.views.can_manage_session_materials', return_value=True):
            r = self.client.get(session_details_url)
            self.assertEqual(r.status_code, 200)
            q = PyQuery(r.content)
            self.assertGreater(
                len(q(f'a[href="{import_minutes_url}"]')), 0,
                'Show import revised minutes buttons to materials manager',
            )

    def test_session_details_past_interim(self):
        group = GroupFactory.create(type_id='wg',state_id='active')
        chair = RoleFactory(name_id='chair',group=group)
        session = SessionFactory.create(meeting__type_id='interim',group=group, meeting__date=date_today() - datetime.timedelta(days=90))
        SessionPresentationFactory.create(session=session,document__type_id='draft',rev=None)
        SessionPresentationFactory.create(session=session,document__type_id='minutes')
        SessionPresentationFactory.create(session=session,document__type_id='slides')
        SessionPresentationFactory.create(session=session,document__type_id='agenda')

        url = urlreverse('ietf.meeting.views.session_details', kwargs=dict(num=session.meeting.number, acronym=group.acronym))
        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        self.assertNotIn('The materials upload cutoff date for this session has passed', unicontent(r))
        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        self.client.login(username=chair.person.user.username,password=chair.person.user.username+'+password')
        self.assertTrue(all([x in unicontent(r) for x in ('slides','agenda','minutes','draft')]))
        
    def test_add_session_drafts(self):
        group = GroupFactory.create(type_id='wg',state_id='active')
        group_chair = PersonFactory.create()
        group.role_set.create(name_id='chair',person = group_chair, email = group_chair.email())
        session = SessionFactory.create(meeting__type_id='ietf',group=group, meeting__date=date_today() + datetime.timedelta(days=90))
        SessionPresentationFactory.create(session=session,document__type_id='draft',rev=None)
        old_draft = session.presentations.filter(document__type='draft').first().document
        new_draft = DocumentFactory(type_id='draft')

        url = urlreverse('ietf.meeting.views.add_session_drafts', kwargs=dict(num=session.meeting.number, session_id=session.pk))

        r = self.client.get(url)
        self.assertEqual(r.status_code, 404)

        self.client.login(username="plain",password="plain+password")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 404)

        self.client.login(username=group_chair.user.username, password='%s+password'%group_chair.user.username)
        r = self.client.get(url)
        self.assertContains(r, old_draft.name)

        r = self.client.post(url,dict(drafts=[new_draft.pk, old_draft.pk]))
        self.assertTrue(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertIn("Already linked:", q('form .text-danger').text())

        self.assertEqual(1,session.presentations.count())
        r = self.client.post(url,dict(drafts=[new_draft.pk,]))
        self.assertTrue(r.status_code, 302)
        self.assertEqual(2,session.presentations.count())

        session.meeting.date -= datetime.timedelta(days=180)
        session.meeting.save()
        r = self.client.get(url)
        self.assertEqual(r.status_code,404)
        self.client.login(username='secretary',password='secretary+password')
        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        q = PyQuery(r.content)
        self.assertEqual(1,len(q(".alert-warning:contains('may affect published proceedings')")))

class EditScheduleListTests(TestCase):
    def setUp(self):
        super().setUp()
        self.mtg = MeetingFactory(type_id='ietf')
        ScheduleFactory(meeting=self.mtg, name='secretary1')

    def test_list_schedules(self):
        url = urlreverse('ietf.meeting.views.list_schedules',kwargs={'num':self.mtg.number})
        login_testing_unauthorized(self,"secretary",url)
        r = self.client.get(url)
        self.assertTrue(r.status_code, 200)

    def test_diff_schedules(self):
        meeting = make_meeting_test_data()

        url = urlreverse('ietf.meeting.views.diff_schedules',kwargs={'num':meeting.number})
        login_testing_unauthorized(self,"secretary", url)
        r = self.client.get(url)
        self.assertTrue(r.status_code, 200)

        from_schedule = Schedule.objects.get(meeting=meeting, name="test-unofficial-schedule")

        session1 = Session.objects.filter(meeting=meeting, group__acronym='mars').first()
        session2 = Session.objects.filter(meeting=meeting, group__acronym='ames').first()
        session3 = SessionFactory(meeting=meeting, group=Group.objects.get(acronym='mars'),
                                  attendees=10, requested_duration=datetime.timedelta(minutes=70),
                                  add_to_schedule=False)
        SchedulingEvent.objects.create(session=session3, status_id='schedw', by=Person.objects.first())

        slot2 = TimeSlot.objects.filter(meeting=meeting, type='regular').order_by('-time').first()
        slot3 = TimeSlot.objects.create(
            meeting=meeting, type_id='regular', location=slot2.location,
            duration=datetime.timedelta(minutes=60),
            time=slot2.time + datetime.timedelta(minutes=60),
        )

        # copy
        new_url = urlreverse("ietf.meeting.views.new_meeting_schedule", kwargs=dict(num=meeting.number, owner=from_schedule.owner_email(), name=from_schedule.name))
        r = self.client.post(new_url, {
            'name': "newtest",
            'public': "on",
        })
        self.assertNoFormPostErrors(r)

        to_schedule = Schedule.objects.get(meeting=meeting, name='newtest')

        # make some changes

        edit_url = urlreverse("ietf.meeting.views.edit_meeting_schedule", kwargs=dict(num=meeting.number, owner=to_schedule.owner_email(), name=to_schedule.name))

        # schedule session
        r = self.client.post(edit_url, {
            'action': 'assign',
            'timeslot': slot3.pk,
            'session': session3.pk,
        })
        self.assertEqual(json.loads(r.content)['success'], True)
        # unschedule session
        r = self.client.post(edit_url, {
            'action': 'unassign',
            'session': session1.pk,
        })
        self.assertEqual(json.loads(r.content)['success'], True)
        # move session
        r = self.client.post(edit_url, {
            'action': 'assign',
            'timeslot': slot2.pk,
            'session': session2.pk,
        })
        self.assertEqual(json.loads(r.content)['success'], True)

        # now get differences
        r = self.client.get(url, {
            'from_schedule': from_schedule.name,
            'to_schedule': to_schedule.name,
        })
        self.assertTrue(r.status_code, 200)

        q = PyQuery(r.content)
        self.assertEqual(len(q(".schedule-diffs tr")), 3+1)

    def test_delete_schedule(self):
        url = urlreverse('ietf.meeting.views.delete_schedule',
                         kwargs={'num':self.mtg.number,
                                 'owner':self.mtg.schedule.owner.email_address(),
                                 'name':self.mtg.schedule.name,
                         })
        login_testing_unauthorized(self,"secretary",url)
        r = self.client.get(url)
        self.assertTrue(r.status_code, 403)
        r = self.client.post(url,{'save':1})
        self.assertTrue(r.status_code, 403)
        self.assertEqual(self.mtg.schedule_set.count(),2)
        self.mtg.schedule=None
        self.mtg.save()
        r = self.client.get(url)
        self.assertTrue(r.status_code, 200)
        r = self.client.post(url,{'save':1})
        self.assertTrue(r.status_code, 302)
        self.assertEqual(self.mtg.schedule_set.count(),1)

    def test_make_schedule_official(self):
        schedule = self.mtg.schedule_set.exclude(id=self.mtg.schedule.id).first()
        url = urlreverse('ietf.meeting.views.make_schedule_official',
                         kwargs={'num':self.mtg.number,
                                 'owner':schedule.owner.email_address(),
                                 'name':schedule.name,
                         })
        login_testing_unauthorized(self,"secretary",url)
        r = self.client.get(url)
        self.assertTrue(r.status_code, 200)
        r = self.client.post(url,{'save':1})
        self.assertTrue(r.status_code, 302)
        mtg = Meeting.objects.get(number=self.mtg.number)
        self.assertEqual(mtg.schedule,schedule)

# -------------------------------------------------
# Interim Meeting Tests
# -------------------------------------------------

class InterimTests(TestCase):
    settings_temp_path_overrides = TestCase.settings_temp_path_overrides + ['AGENDA_PATH']

    # test_interim_announce subsumed by test_appears_on_announce

    def do_interim_skip_announcement_test(self, base_session=False, extra_session=False, canceled_session=False):
        make_meeting_test_data()
        group = Group.objects.get(acronym='irg')
        date = date_today() + datetime.timedelta(days=30)
        meeting = make_interim_meeting(group=group, date=date, status='scheda')
        session = meeting.session_set.first()
        if base_session:
            base_session = SessionFactory(meeting=meeting, status_id='apprw', add_to_schedule=False)
            meeting.schedule.base = Schedule.objects.create(
                meeting=meeting, owner=PersonFactory(), name="base", visible=True, public=True
            )
            SchedTimeSessAssignment.objects.create(
                timeslot=TimeSlotFactory.create(meeting=meeting),
                session=base_session,
                schedule=meeting.schedule.base,
            )
            meeting.schedule.save()
        if extra_session:
            extra_session = SessionFactory(meeting=meeting, status_id='scheda')
        if canceled_session:
            canceled_session = SessionFactory(meeting=meeting, status_id='canceledpa')
        url = urlreverse("ietf.meeting.views.interim_skip_announcement", kwargs={'number': meeting.number})
        login_testing_unauthorized(self, "secretary", url)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        # check post
        len_before = len(outbox)
        r = self.client.post(url)
        self.assertRedirects(r, urlreverse('ietf.meeting.views.interim_announce'))
        meeting_sessions = meeting.session_set.with_current_status()
        self.assertEqual(meeting_sessions.get(pk=session.pk).current_status, 'sched')
        if base_session:
            self.assertEqual(meeting_sessions.get(pk=base_session.pk).current_status, 'sched')            
        if extra_session:
            self.assertEqual(meeting_sessions.get(pk=extra_session.pk).current_status, 'sched')
        if canceled_session:
            self.assertEqual(meeting_sessions.get(pk=canceled_session.pk).current_status, 'canceledpa')
        self.assertEqual(len(outbox), len_before)

    def test_interim_skip_announcement(self):
        """skip_announcement should move single session to sched state"""
        self.do_interim_skip_announcement_test()

    def test_interim_skip_announcement_with_base_sched(self):
        """skip_announcement should move single session to sched state"""
        self.do_interim_skip_announcement_test(base_session=True)

    def test_interim_skip_announcement_with_extra_session(self):
        """skip_announcement should move multiple sessions to sched state"""
        self.do_interim_skip_announcement_test(extra_session=True)

    def test_interim_skip_announcement_with_extra_session_and_base_sched(self):
        """skip_announcement should move multiple sessions to sched state"""
        self.do_interim_skip_announcement_test(extra_session=True, base_session=True)

    def test_interim_skip_announcement_with_canceled_session(self):
        """skip_announcement should not schedule a canceled session"""
        self.do_interim_skip_announcement_test(canceled_session=True)

    def test_interim_skip_announcement_with_canceled_session_and_base_sched(self):
        """skip_announcement should not schedule a canceled session"""
        self.do_interim_skip_announcement_test(canceled_session=True, base_session=True)

    def test_interim_skip_announcement_with_extra_and_canceled_sessions(self):
        """skip_announcement should schedule multiple sessions and leave canceled session alone"""
        self.do_interim_skip_announcement_test(extra_session=True, canceled_session=True)

    def test_interim_skip_announcement_with_extra_and_canceled_sessions_and_base_sched(self):
        """skip_announcement should schedule multiple sessions and leave canceled session alone"""
        self.do_interim_skip_announcement_test(extra_session=True, canceled_session=True, base_session=True)

    def do_interim_send_announcement_test(self, base_session=False, extra_session=False, canceled_session=False):
        make_interim_test_data(meeting_tz='America/Los_Angeles')
        session = Session.objects.with_current_status().filter(
            meeting__type='interim', group__acronym='mars', current_status='apprw').first()
        meeting = session.meeting

        if base_session:
            base_session = SessionFactory(meeting=meeting, status_id='apprw', add_to_schedule=False)
            meeting.schedule.base = Schedule.objects.create(
                meeting=meeting, owner=PersonFactory(), name="base", visible=True, public=True
            )
            SchedTimeSessAssignment.objects.create(
                timeslot=TimeSlotFactory.create(meeting=meeting),
                session=base_session,
                schedule=meeting.schedule.base,
            )
            meeting.schedule.save()
        if extra_session:
            extra_session = SessionFactory(meeting=meeting, status_id='apprw')
        if canceled_session:
            canceled_session = SessionFactory(meeting=meeting, status_id='canceledpa')

        url = urlreverse("ietf.meeting.views.interim_send_announcement", kwargs={'number': meeting.number})
        login_testing_unauthorized(self, "secretary", url)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        initial = r.context['form'].initial

        # send announcement
        len_before = len(outbox)
        r = self.client.post(url, initial)
        self.assertRedirects(r, urlreverse('ietf.meeting.views.interim_announce'))
        self.assertEqual(len(outbox), len_before + 1)
        announcement_msg = outbox[-1]
        announcement_text = get_payload_text(announcement_msg)
        self.assertIn('WG Virtual Meeting', announcement_msg['Subject'])
        self.assertIn('09:00 to 09:20 America/Los_Angeles', announcement_text)
        for sess in [session, base_session, extra_session]:
            if sess:
                timeslot = sess.official_timeslotassignment().timeslot
                self.assertIn(timeslot.time.strftime('%Y-%m-%d'), announcement_text)
                self.assertRegex(
                    announcement_text,
                    r'(%s\s+to\s+%s\s+UTC)' % (
                        timeslot.utc_start_time().strftime('%H:%M'),timeslot.utc_end_time().strftime('%H:%M')
                    ))
        # Count number of sessions listed
        if base_session and extra_session:
            expected_session_matches = 3
        elif base_session or extra_session:
            expected_session_matches = 2
        else:
            expected_session_matches = 0  # no session list when only one session
        session_matches = re.findall(r'Session \d+:', announcement_text)
        self.assertEqual(len(session_matches), expected_session_matches) 

        meeting_sessions = meeting.session_set.with_current_status()
        self.assertEqual(meeting_sessions.get(pk=session.pk).current_status, 'sched')
        if base_session:
            self.assertEqual(meeting_sessions.get(pk=base_session.pk).current_status, 'sched')
        if extra_session:
            self.assertEqual(meeting_sessions.get(pk=extra_session.pk).current_status, 'sched')
        if canceled_session:
            self.assertEqual(meeting_sessions.get(pk=canceled_session.pk).current_status, 'canceledpa')

    def test_interim_send_announcement(self):
        self.do_interim_send_announcement_test()

    def test_interim_send_announcement_with_base_sched(self):
        self.do_interim_send_announcement_test(base_session=True)

    def test_interim_send_announcement_with_extra_session(self):
        self.do_interim_send_announcement_test(extra_session=True)

    def test_interim_send_announcement_with_extra_session_and_base_sched(self):
        self.do_interim_send_announcement_test(extra_session=True, base_session=True)

    def test_interim_send_announcement_with_canceled_session(self):
        self.do_interim_send_announcement_test(canceled_session=True)

    def test_interim_send_announcement_with_canceled_session_and_base_sched(self):
        self.do_interim_send_announcement_test(canceled_session=True, base_session=True)

    def test_interim_send_announcement_with_extra_and_canceled_sessions(self):
        self.do_interim_send_announcement_test(extra_session=True, canceled_session=True)

    def test_interim_send_announcement_with_extra_and_canceled_sessions_and_base_sched(self):
        self.do_interim_send_announcement_test(extra_session=True, canceled_session=True, base_session=True)

    def do_interim_approve_by_ad_test(self, base_session=False, extra_session=False, canceled_session=False):
        make_interim_test_data()
        session = Session.objects.with_current_status().filter(
            meeting__type='interim', group__acronym='mars', current_status='apprw').first()
        meeting = session.meeting

        if base_session:
            base_session = SessionFactory(meeting=meeting, status_id='apprw', add_to_schedule=False)
            meeting.schedule.base = Schedule.objects.create(
                meeting=meeting, owner=PersonFactory(), name="base", visible=True, public=True
            )
            SchedTimeSessAssignment.objects.create(
                timeslot=TimeSlotFactory.create(meeting=meeting),
                session=base_session,
                schedule=meeting.schedule.base,
            )
            meeting.schedule.save()
        if extra_session:
            extra_session = SessionFactory(meeting=meeting, status_id='apprw')
        if canceled_session:
            canceled_session = SessionFactory(meeting=meeting, status_id='canceledpa')

        url = urlreverse('ietf.meeting.views.interim_request_details', kwargs={'number': meeting.number})
        length_before = len(outbox)
        login_testing_unauthorized(self, "ad", url)
        r = self.client.post(url, {'approve': 'approve'})
        self.assertRedirects(r, urlreverse('ietf.meeting.views.interim_pending'))

        for sess in [session, base_session, extra_session]:
            if sess:
                self.assertEqual(Session.objects.with_current_status().get(pk=sess.pk).current_status,
                                 'scheda')
        if canceled_session:
            self.assertEqual(Session.objects.with_current_status().get(pk=canceled_session.pk).current_status,
                             'canceledpa')
        self.assertEqual(len(outbox), length_before + 1)
        self.assertIn('ready for announcement', outbox[-1]['Subject'])

    def test_interim_approve_by_ad(self):
        self.do_interim_approve_by_ad_test()

    def test_interim_approve_by_ad_with_base_sched(self):
        self.do_interim_approve_by_ad_test(base_session=True)

    def test_interim_approve_by_ad_with_extra_session(self):
        self.do_interim_approve_by_ad_test(extra_session=True)

    def test_interim_approve_by_ad_with_extra_session_and_base_sched(self):
        self.do_interim_approve_by_ad_test(extra_session=True, base_session=True)

    def test_interim_approve_by_ad_with_canceled_session(self):
        self.do_interim_approve_by_ad_test(canceled_session=True)

    def test_interim_approve_by_ad_with_canceled_session_and_base_sched(self):
        self.do_interim_approve_by_ad_test(canceled_session=True, base_session=True)

    def test_interim_approve_by_ad_with_extra_and_canceled_sessions(self):
        self.do_interim_approve_by_ad_test(extra_session=True, canceled_session=True)

    def test_interim_approve_by_ad_with_extra_and_canceled_sessions_and_base_sched(self):
        self.do_interim_approve_by_ad_test(extra_session=True, canceled_session=True, base_session=True)

    def do_interim_approve_by_secretariat_test(self, base_session=False, extra_session=False, canceled_session=False):
        make_interim_test_data()
        session = Session.objects.with_current_status().filter(
            meeting__type='interim', group__acronym='mars', current_status='apprw').first()
        meeting = session.meeting
        if base_session:
            base_session = SessionFactory(meeting=meeting, status_id='apprw', add_to_schedule=False)
            meeting.schedule.base = Schedule.objects.create(
                meeting=meeting, owner=PersonFactory(), name="base", visible=True, public=True
            )
            SchedTimeSessAssignment.objects.create(
                timeslot=TimeSlotFactory.create(meeting=meeting),
                session=base_session,
                schedule=meeting.schedule.base,
            )
            meeting.schedule.save()
        if extra_session:
            extra_session = SessionFactory(meeting=meeting, status_id='apprw')
        if canceled_session:
            canceled_session = SessionFactory(meeting=meeting, status_id='canceledpa')

        url = urlreverse('ietf.meeting.views.interim_request_details', kwargs={'number': meeting.number})
        length_before = len(outbox)
        login_testing_unauthorized(self, "secretary", url)
        r = self.client.post(url, {'approve': 'approve'})
        self.assertRedirects(r, urlreverse('ietf.meeting.views.interim_send_announcement', kwargs={'number': meeting.number}))
        for sess in [session, base_session, extra_session]:
            if sess:
                self.assertEqual(Session.objects.with_current_status().get(pk=sess.pk).current_status,
                                 'scheda')
        if canceled_session:
            self.assertEqual(Session.objects.with_current_status().get(pk=canceled_session.pk).current_status,
                             'canceledpa')
        self.assertEqual(len(outbox), length_before)

    def test_interim_approve_by_secretariat(self):
        self.do_interim_approve_by_secretariat_test()

    def test_interim_approve_by_secretariat_with_base_sched(self):
        self.do_interim_approve_by_secretariat_test(base_session=True)

    def test_interim_approve_by_secretariat_with_extra_session(self):
        self.do_interim_approve_by_secretariat_test(extra_session=True)

    def test_interim_approve_by_secretariat_with_extra_session_and_base_sched(self):
        self.do_interim_approve_by_secretariat_test(extra_session=True, base_session=True)

    def test_interim_approve_by_secretariat_with_canceled_session(self):
        self.do_interim_approve_by_secretariat_test(canceled_session=True)

    def test_interim_approve_by_secretariat_with_canceled_session_and_base_sched(self):
        self.do_interim_approve_by_secretariat_test(canceled_session=True, base_session=True)

    def test_interim_approve_by_secretariat_with_extra_and_canceled_sessions(self):
        self.do_interim_approve_by_secretariat_test(extra_session=True, canceled_session=True)

    def test_interim_approve_by_secretariat_with_extra_and_canceled_sessions_and_base_sched(self):
        self.do_interim_approve_by_secretariat_test(extra_session=True, canceled_session=True, base_session=True)

    def test_past(self):
        today = date_today()
        last_week = today - datetime.timedelta(days=7)
        ietf = SessionFactory(meeting__type_id='ietf',meeting__date=last_week,group__state_id='active',group__parent=GroupFactory(state_id='active'))
        SessionFactory(meeting__type_id='interim',meeting__date=last_week,status_id='canceled',group__state_id='active',group__parent=GroupFactory(state_id='active'))
        url = urlreverse('ietf.meeting.views.past')
        r = self.client.get(url)
        self.assertContains(r, 'IETF-%02d'%int(ietf.meeting.number))
        q = PyQuery(r.content)
        #id="-%s" % interim.group.acronym
        #self.assertIn('Cancelled', q('[id*="'+id+'"]').text())
        self.assertIn('Cancelled', q('tr>td>a+span').text())

    def do_upcoming_test(self, querystring=None, create_meeting=True):
        if create_meeting:
            make_meeting_test_data(create_interims=True)
        url = urlreverse("ietf.meeting.views.upcoming")
        if querystring is not None:
            url += '?' + querystring

        today = date_today()
        interims = dict(
            mars=add_event_info_to_session_qs(Session.objects.filter(meeting__type='interim', meeting__date__gt=today, group__acronym='mars')).filter(current_status='sched').first().meeting,
            ames=add_event_info_to_session_qs(Session.objects.filter(meeting__type='interim', meeting__date__gt=today, group__acronym='ames')).filter(current_status='canceled').first().meeting,
        )
        return self.client.get(url), interims

    def test_upcoming(self):
        r, interims = self.do_upcoming_test()
        self.assertContains(r, interims['mars'].number)
        self.assertContains(r, interims['ames'].number)
        self.assertContains(r, 'IETF 72')
        # cancelled session
        q = PyQuery(r.content)
        self.assertIn('Cancelled', q('tr>td.text-end>span').text())

    # test_upcoming_filters_ignored removed - we _don't_ want to ignore filters now, and the test passed because it wasn't testing the filtering anyhow (which requires testing the js).

    def test_upcoming_ical(self):
        meeting = make_meeting_test_data(create_interims=True)
        populate_important_dates(meeting)
        url = urlreverse("ietf.meeting.views.upcoming_ical")

        # Expect events 3 sessions - one for each WG and one for the IETF meeting
        expected_event_summaries = [
            'ames - Asteroid Mining Equipment Standardization Group',
            'mars - Martian Special Interest Group',
            'IETF 72',
        ]

        Session.objects.filter(
            meeting__type_id='interim',
            group__acronym="mars",
        ).update(
            remote_instructions='https://someurl.example.com',
        )
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        assert_ical_response_is_valid(self, r,
                                      expected_event_summaries=expected_event_summaries,
                                      expected_event_count=len(expected_event_summaries))
        self.assertContains(r, 'Remote instructions: https://someurl.example.com')

        Session.objects.filter(meeting__type_id='interim').update(remote_instructions='')
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        assert_ical_response_is_valid(self, r,
                                      expected_event_summaries=expected_event_summaries,
                                      expected_event_count=len(expected_event_summaries))
        self.assertNotContains(r, 'Remote instructions:')

        updated = meeting.updated()
        self.assertIsNotNone(updated)
        expected_updated = updated.astimezone(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.assertContains(r, f"DTSTAMP:{expected_updated}")

        # With default cached_updated, 1970-01-01
        with patch("ietf.meeting.models.Meeting.updated", return_value=None):
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)

            self.assertEqual(meeting.type_id, "ietf")

            expected_updated = "19700101T000000Z"
            self.assertEqual(1, r.content.decode("utf-8").count(f"DTSTAMP:{expected_updated}"))

    @patch("ietf.meeting.utils.preprocess_meeting_important_dates")
    def test_upcoming_ical_filter(self, mock_preprocess_meeting_important_dates):
        # Just a quick check of functionality - details tested by test_js.InterimTests
        make_meeting_test_data(create_interims=True)
        url = urlreverse("ietf.meeting.views.upcoming_ical")

        r = self.client.get(url + '?show=mars')
        self.assertEqual(r.status_code, 200)
        assert_ical_response_is_valid(self, r,
                                      expected_event_summaries=[
                                          'mars - Martian Special Interest Group',
                                      ],
                                      expected_event_count=1)

        r = self.client.get(url + '?show=mars,ietf-meetings')
        self.assertEqual(r.status_code, 200)
        assert_ical_response_is_valid(self, r,
                                      expected_event_summaries=[
                                          'mars - Martian Special Interest Group',
                                          'IETF 72',
                                      ],
                                      expected_event_count=2)

        # Verify preprocess_meeting_important_dates isn't being called
        mock_preprocess_meeting_important_dates.assert_not_called()

    def test_upcoming_json(self):
        make_meeting_test_data(create_interims=True)
        url = urlreverse("ietf.meeting.views.upcoming_json")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get('Content-Type'), "application/json;charset=utf-8")
        data = r.json()
        self.assertEqual(len(data), 3)

    def test_interim_request_permissions(self):
        '''Ensure only authorized users see link to request interim meeting'''
        make_meeting_test_data()

        # test unauthorized not logged in
        upcoming_url = urlreverse("ietf.meeting.views.upcoming")
        request_url = urlreverse("ietf.meeting.views.interim_request")
        r = self.client.get(upcoming_url)
        self.assertNotContains(r,'Request new interim meeting')

        # test unauthorized user
        login_testing_unauthorized(self,"plain",request_url)
        r = self.client.get(upcoming_url)
        self.assertNotContains(r,'Request new interim meeting')
        r = self.client.get(request_url)
        self.assertEqual(r.status_code, 403) 
        self.client.logout()

        # test authorized
        for username in ('secretary','ad','marschairman','irtf-chair','irgchairman'):
            self.client.login(username=username, password= username + "+password")
            r = self.client.get(upcoming_url)
            self.assertContains(r,'Request new interim meeting')
            r = self.client.get(request_url)
            self.assertEqual(r.status_code, 200)
            self.client.logout()

    def test_interim_request_options(self):
        make_meeting_test_data()

        # secretariat can request for any group
        self.client.login(username="secretary", password="secretary+password")
        r = self.client.get("/meeting/interim/request/")
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(Group.objects.with_meetings().filter(state__in=('active', 'proposed', 'bof')).count(),
            len(q("#id_group option")) - 1)  # -1 for options placeholder
        self.client.logout()

        # wg chair
        self.client.login(username="marschairman", password="marschairman+password")
        r = self.client.get("/meeting/interim/request/")
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        user = User.objects.get(username='marschairman')
        person = user.person
        count = person.role_set.filter(name='chair',group__type__in=('wg', 'rg'), group__state__in=('active', 'proposed')).count()
        self.assertEqual(count, len(q("#id_group option")) - 1)  # -1 for options placeholder
        
        # wg AND rg chair
        group = Group.objects.get(acronym='irg')
        Role.objects.create(name_id='chair',group=group,person=person,email=person.email())
        r = self.client.get("/meeting/interim/request/")
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        count = person.role_set.filter(name='chair',group__type__in=('wg', 'rg'), group__state__in=('active', 'proposed')).count()
        self.assertEqual(count, len(q("#id_group option")) - 1)  # -1 for options placeholder

    def do_interim_request_single_virtual(self, emails_expected):
        make_meeting_test_data()
        group = Group.objects.get(acronym='mars')
        date = date_today() + datetime.timedelta(days=30)
        time = time_now().replace(microsecond=0,second=0)
        dt = pytz.utc.localize(datetime.datetime.combine(date, time))
        duration = datetime.timedelta(hours=3)
        remote_instructions = 'Use webex'
        agenda = 'Intro. Slides. Discuss.'
        agenda_note = 'On second level'
        length_before = len(outbox)
        meeting_count = Meeting.objects.filter(number__contains='-%s-'%group.acronym, date__year=date.year).count()
        next_num = "%02d" % (meeting_count+1)
        self.client.login(username="marschairman", password="marschairman+password")
        data = {'group':group.pk,
                'meeting_type':'single',
                'city':'',
                'country':'',
                'time_zone':'UTC',
                'session_set-0-date':date.strftime("%Y-%m-%d"),
                'session_set-0-time':time.strftime('%H:%M'),
                'session_set-0-requested_duration':'03:00:00',
                'session_set-0-remote_instructions':remote_instructions,
                'session_set-0-agenda':agenda,
                'session_set-0-agenda_note':agenda_note,
                'session_set-TOTAL_FORMS':1,
                'session_set-INITIAL_FORMS':0,
                'session_set-MIN_NUM_FORMS':0,
                'session_set-MAX_NUM_FORMS':1000}

        with patch('ietf.meeting.views.sessions_post_save', wraps=sessions_post_save) as mock:
            r = self.client.post(urlreverse("ietf.meeting.views.interim_request"),data)
        self.assertTrue(mock.called)
        self.assertRedirects(r,urlreverse('ietf.meeting.views.upcoming'))
        meeting = Meeting.objects.order_by('id').last()
        self.assertEqual(meeting.type_id,'interim')
        self.assertEqual(meeting.date,date)
        self.assertEqual(meeting.number,'interim-%s-%s-%s' % (date.year, group.acronym, next_num))
        self.assertEqual(meeting.city,'')
        self.assertEqual(meeting.country,'')
        self.assertEqual(meeting.time_zone,'UTC')
        session = meeting.session_set.first()
        self.assertEqual(session.remote_instructions,remote_instructions)
        self.assertEqual(session.agenda_note,agenda_note)
        timeslot = session.official_timeslotassignment().timeslot
        self.assertEqual(timeslot.time,dt)
        self.assertEqual(timeslot.duration,duration)
        # ensure agenda document was created
        self.assertEqual(session.materials.count(),1)
        doc = session.materials.first()
        path = os.path.join(doc.get_file_path(),doc.filename_with_rev())
        self.assertTrue(os.path.exists(path))
        # check notices to secretariat and chairs
        self.assertEqual(len(outbox), length_before + emails_expected)
        return meeting

    @override_settings(VIRTUAL_INTERIMS_REQUIRE_APPROVAL = True)
    def test_interim_request_single_virtual_settings_approval_required(self):
        meeting = self.do_interim_request_single_virtual(emails_expected=1)
        self.assertEqual(meeting.session_set.last().schedulingevent_set.last().status_id,'apprw')
        self.assertIn('New Interim Meeting Request', outbox[-1]['Subject'])
        self.assertIn('session-request@ietf.org', outbox[-1]['To'])
        self.assertIn('aread@example.org', outbox[-1]['Cc'])

    @override_settings(VIRTUAL_INTERIMS_REQUIRE_APPROVAL = False)
    def test_interim_request_single_virtual_settings_approval_not_required(self):
        meeting = self.do_interim_request_single_virtual(emails_expected=2)
        self.assertEqual(meeting.session_set.last().schedulingevent_set.last().status_id,'scheda')
        self.assertIn('iesg-secretary@ietf.org', outbox[-1]['To'])
        self.assertIn('interim meeting ready for announcement', outbox[-1]['Subject'])

    def test_interim_request_single_in_person(self):
        make_meeting_test_data()
        group = Group.objects.get(acronym='mars')
        date = date_today() + datetime.timedelta(days=30)
        time = time_now().replace(microsecond=0,second=0)
        time_zone = 'America/Los_Angeles'
        tz = pytz.timezone(time_zone)
        dt = tz.localize(datetime.datetime.combine(date, time))
        duration = datetime.timedelta(hours=3)
        city = 'San Francisco'
        country = 'US'
        remote_instructions = 'Use webex'
        agenda = 'Intro. Slides. Discuss.'
        agenda_note = 'On second level'
        meeting_count = Meeting.objects.filter(number__contains='-%s-'%group.acronym, date__year=date.year).count()
        next_num = "%02d" % (meeting_count+1)
        self.client.login(username="secretary", password="secretary+password")
        data = {'group':group.pk,
                'meeting_type':'single',
                'city':city,
                'country':country,
                'time_zone':time_zone,
                'session_set-0-date':date.strftime("%Y-%m-%d"),
                'session_set-0-time':time.strftime('%H:%M'),
                'session_set-0-requested_duration':'03:00:00',
                'session_set-0-remote_instructions':remote_instructions,
                'session_set-0-agenda':agenda,
                'session_set-0-agenda_note':agenda_note,
                'session_set-TOTAL_FORMS':1,
                'session_set-INITIAL_FORMS':0}

        with patch('ietf.meeting.views.sessions_post_save', wraps=sessions_post_save) as mock:
            r = self.client.post(urlreverse("ietf.meeting.views.interim_request"),data)
        self.assertTrue(mock.called)
        self.assertRedirects(r,urlreverse('ietf.meeting.views.upcoming'))
        meeting = Meeting.objects.order_by('id').last()
        self.assertEqual(meeting.type_id,'interim')
        self.assertEqual(meeting.date,date)
        self.assertEqual(meeting.number,'interim-%s-%s-%s' % (date.year, group.acronym, next_num))
        self.assertEqual(meeting.city,city)
        self.assertEqual(meeting.country,country)
        self.assertEqual(meeting.time_zone,time_zone)
        session = meeting.session_set.first()
        self.assertEqual(session.remote_instructions,remote_instructions)
        self.assertEqual(session.agenda_note,agenda_note)
        timeslot = session.official_timeslotassignment().timeslot
        self.assertEqual(timeslot.time,dt)
        self.assertEqual(timeslot.duration,duration)

    def test_interim_request_multi_day(self):
        make_meeting_test_data()
        date = date_today() + datetime.timedelta(days=30)
        date2 = date + datetime.timedelta(days=1)
        time = time_now().replace(microsecond=0,second=0)
        time_zone = 'America/Los_Angeles'
        tz = pytz.timezone(time_zone)
        dt = tz.localize(datetime.datetime.combine(date, time))
        dt2 = tz.localize(datetime.datetime.combine(date2, time))
        duration = datetime.timedelta(hours=3)
        group = Group.objects.get(acronym='mars')
        city = 'San Francisco'
        country = 'US'
        remote_instructions = 'Use webex'
        agenda = 'Intro. Slides. Discuss.'
        agenda_note = 'On second level'
        meeting_count = Meeting.objects.filter(number__contains='-%s-'%group.acronym, date__year=date.year).count()
        next_num = "%02d" % (meeting_count+1)
        self.client.login(username="secretary", password="secretary+password")
        data = {'group':group.pk,
                'meeting_type':'multi-day',
                'city':city,
                'country':country,
                'time_zone':time_zone,
                'session_set-0-date':date.strftime("%Y-%m-%d"),
                'session_set-0-time':time.strftime('%H:%M'),
                'session_set-0-requested_duration':'03:00:00',
                'session_set-0-remote_instructions':remote_instructions,
                'session_set-0-agenda':agenda,
                'session_set-0-agenda_note':agenda_note,
                'session_set-1-date':date2.strftime("%Y-%m-%d"),
                'session_set-1-time':time.strftime('%H:%M'),
                'session_set-1-requested_duration':'03:00:00',
                'session_set-1-remote_instructions':remote_instructions,
                'session_set-1-agenda':agenda,
                'session_set-1-agenda_note':agenda_note,
                'session_set-TOTAL_FORMS':2,
                'session_set-INITIAL_FORMS':0}

        with patch('ietf.meeting.views.sessions_post_save', wraps=sessions_post_save) as mock:
            r = self.client.post(urlreverse("ietf.meeting.views.interim_request"),data)
        self.assertTrue(mock.called)

        self.assertRedirects(r,urlreverse('ietf.meeting.views.upcoming'))
        meeting = Meeting.objects.order_by('id').last()
        self.assertEqual(meeting.type_id,'interim')
        self.assertEqual(meeting.date,date)
        self.assertEqual(meeting.number,'interim-%s-%s-%s' % (date.year, group.acronym, next_num))
        self.assertEqual(meeting.city,city)
        self.assertEqual(meeting.country,country)
        self.assertEqual(meeting.time_zone,time_zone)
        self.assertEqual(meeting.session_set.count(),2)
        # first sesstion
        session = meeting.session_set.all()[0]
        self.assertEqual(session.remote_instructions,remote_instructions)
        timeslot = session.official_timeslotassignment().timeslot
        self.assertEqual(timeslot.time,dt)
        self.assertEqual(timeslot.duration,duration)
        self.assertEqual(session.agenda_note,agenda_note)
        # second sesstion
        session = meeting.session_set.all()[1]
        self.assertEqual(session.remote_instructions,remote_instructions)
        timeslot = session.official_timeslotassignment().timeslot
        self.assertEqual(timeslot.time,dt2)
        self.assertEqual(timeslot.duration,duration)
        self.assertEqual(session.agenda_note,agenda_note)

    def test_interim_request_multi_day_non_consecutive(self):
        make_meeting_test_data()
        date = date_today() + datetime.timedelta(days=30)
        date2 = date + datetime.timedelta(days=2)
        time = timezone.now().time().replace(microsecond=0,second=0)
        group = Group.objects.get(acronym='mars')
        city = 'San Francisco'
        country = 'US'
        time_zone = 'America/Los_Angeles'
        remote_instructions = 'Use webex'
        agenda = 'Intro. Slides. Discuss.'
        agenda_note = 'On second level'
        self.client.login(username="secretary", password="secretary+password")
        data = {'group':group.pk,
                'meeting_type':'multi-day',
                'city':city,
                'country':country,
                'time_zone':time_zone,
                'session_set-0-date':date.strftime("%Y-%m-%d"),
                'session_set-0-time':time.strftime('%H:%M'),
                'session_set-0-requested_duration':'03:00:00',
                'session_set-0-remote_instructions':remote_instructions,
                'session_set-0-agenda':agenda,
                'session_set-0-agenda_note':agenda_note,
                'session_set-1-date':date2.strftime("%Y-%m-%d"),
                'session_set-1-time':time.strftime('%H:%M'),
                'session_set-1-requested_duration':'03:00:00',
                'session_set-1-remote_instructions':remote_instructions,
                'session_set-1-agenda':agenda,
                'session_set-1-agenda_note':agenda_note,
                'session_set-TOTAL_FORMS':2,
                'session_set-INITIAL_FORMS':0}

        r = self.client.post(urlreverse("ietf.meeting.views.interim_request"),data)
        self.assertContains(r, 'days must be consecutive')

    def test_interim_request_multi_day_cancel(self):
        """All sessions of a multi-day interim request should be canceled"""
        length_before = len(outbox)
        date = date_today() + datetime.timedelta(days=15)

        # Set up an interim request with several sessions 
        num_sessions = 3
        meeting = MeetingFactory(type_id='interim', date=date)
        for _ in range(num_sessions):
            SessionFactory(meeting=meeting)

        # Cancel the interim request
        url = urlreverse('ietf.meeting.views.interim_request_cancel', kwargs={'number': meeting.number})
        self.client.login(username="secretary", password="secretary+password")
        r = self.client.post(url)
        
        # Verify results
        self.assertRedirects(r, urlreverse('ietf.meeting.views.upcoming'))
        for session in add_event_info_to_session_qs(meeting.session_set.all()):
            self.assertEqual(session.current_status, 'canceled')
        self.assertEqual(len(outbox), length_before + 1)
        self.assertIn('Interim Meeting Cancelled', outbox[-1]['Subject'])

    def test_interim_request_series(self):
        make_meeting_test_data()
        meeting_count_before = Meeting.objects.filter(type='interim').count()
        date = date_today() + datetime.timedelta(days=30)
        if (date.month, date.day) == (12, 31):
            # Avoid date and date2 in separate years
            # (otherwise the test will fail if run on December 1st)
            date += datetime.timedelta(days=1)
        date2 = date + datetime.timedelta(days=1)
        # ensure dates are in the same year
        if date.year != date2.year:
            date += datetime.timedelta(days=1)
            date2 += datetime.timedelta(days=1)
        time = time_now().replace(microsecond=0,second=0)
        time_zone = 'America/Los_Angeles'
        tz = pytz.timezone(time_zone)
        dt = tz.localize(datetime.datetime.combine(date, time))
        dt2 = tz.localize(datetime.datetime.combine(date2, time))
        duration = datetime.timedelta(hours=3)
        group = Group.objects.get(acronym='mars')
        city = ''
        country = ''
        remote_instructions = 'Use webex'
        agenda = 'Intro. Slides. Discuss.'
        agenda_note = 'On second level'
        meeting_count = Meeting.objects.filter(number__contains='-%s-'%group.acronym, date__year=date.year).count()
        next_num = "%02d" % (meeting_count+1)
        next_num2 = "%02d" % (meeting_count+2)
        self.client.login(username="secretary", password="secretary+password")
        r = self.client.get(urlreverse("ietf.meeting.views.interim_request"))
        self.assertEqual(r.status_code, 200)

        data = {'group':group.pk,
                'meeting_type':'series',
                'city':city,
                'country':country,
                'time_zone':time_zone,
                'session_set-0-date':date.strftime("%Y-%m-%d"),
                'session_set-0-time':time.strftime('%H:%M'),
                'session_set-0-requested_duration':'03:00:00',
                'session_set-0-remote_instructions':remote_instructions,
                'session_set-0-agenda':agenda,
                'session_set-0-agenda_note':agenda_note,
                'session_set-1-date':date2.strftime("%Y-%m-%d"),
                'session_set-1-time':time.strftime('%H:%M'),
                'session_set-1-requested_duration':'03:00:00',
                'session_set-1-remote_instructions':remote_instructions,
                'session_set-1-agenda':agenda,
                'session_set-1-agenda_note':agenda_note,
                'session_set-TOTAL_FORMS':2,
                'session_set-INITIAL_FORMS':0}

        with patch('ietf.meeting.views.sessions_post_save', wraps=sessions_post_save) as mock:
            r = self.client.post(urlreverse("ietf.meeting.views.interim_request"),data)
        self.assertTrue(mock.called)
        self.assertRedirects(r,urlreverse('ietf.meeting.views.upcoming'))
        meeting_count_after = Meeting.objects.filter(type='interim').count()
        self.assertEqual(meeting_count_after,meeting_count_before + 2)
        meetings = Meeting.objects.order_by('-id')[:2]
        # first meeting
        meeting = meetings[1]
        self.assertEqual(meeting.type_id,'interim')
        self.assertEqual(meeting.date,date)
        self.assertEqual(meeting.number,'interim-%s-%s-%s' % (date.year, group.acronym, next_num))
        self.assertEqual(meeting.city,city)
        self.assertEqual(meeting.country,country)
        self.assertEqual(meeting.time_zone,time_zone)
        self.assertEqual(meeting.session_set.count(),1)
        session = meeting.session_set.first()
        self.assertEqual(session.remote_instructions,remote_instructions)
        timeslot = session.official_timeslotassignment().timeslot
        self.assertEqual(timeslot.time,dt)
        self.assertEqual(timeslot.duration,duration)
        self.assertEqual(session.agenda_note,agenda_note)
        # second meeting
        meeting = meetings[0]
        self.assertEqual(meeting.type_id,'interim')
        self.assertEqual(meeting.date,date2)
        self.assertEqual(meeting.number,'interim-%s-%s-%s' % (date2.year, group.acronym, next_num2))
        self.assertEqual(meeting.city,city)
        self.assertEqual(meeting.country,country)
        self.assertEqual(meeting.time_zone,time_zone)
        self.assertEqual(meeting.session_set.count(),1)
        session = meeting.session_set.first()
        self.assertEqual(session.remote_instructions,remote_instructions)
        timeslot = session.official_timeslotassignment().timeslot
        self.assertEqual(timeslot.time,dt2)
        self.assertEqual(timeslot.duration,duration)
        self.assertEqual(session.agenda_note,agenda_note)


    # test_interim_pending subsumed by test_appears_on_pending


    def test_can_approve_interim_request(self):
        make_interim_test_data()
        # unprivileged user
        user = User.objects.get(username='plain')
        group = Group.objects.get(acronym='mars')
        meeting = add_event_info_to_session_qs(Session.objects.filter(meeting__type='interim', group=group)).filter(current_status='apprw').first().meeting
        self.assertFalse(can_approve_interim_request(meeting=meeting,user=user))
        # Secretariat
        user = User.objects.get(username='secretary')
        self.assertTrue(can_approve_interim_request(meeting=meeting,user=user))
        # related AD
        user = User.objects.get(username='ad')
        self.assertTrue(can_approve_interim_request(meeting=meeting,user=user))
        # AD from other area
        user = User.objects.get(username='ops-ad')
        self.assertFalse(can_approve_interim_request(meeting=meeting,user=user))
        # AD from other area assigned as the WG AD anyhow (cross-area AD)
        user = RoleFactory(name_id='ad',group=group).person.user
        self.assertTrue(can_approve_interim_request(meeting=meeting,user=user))
        # WG Chair
        user = User.objects.get(username='marschairman')
        self.assertFalse(can_approve_interim_request(meeting=meeting,user=user))

    def test_can_view_interim_request(self):
        make_interim_test_data()
        # unprivileged user
        user = User.objects.get(username='plain')
        group = Group.objects.get(acronym='mars')
        meeting = add_event_info_to_session_qs(Session.objects.filter(meeting__type='interim', group=group)).filter(current_status='apprw').first().meeting
        self.assertFalse(can_view_interim_request(meeting=meeting,user=user))
        # Secretariat
        user = User.objects.get(username='secretary')
        self.assertTrue(can_view_interim_request(meeting=meeting,user=user))
        # related AD
        user = User.objects.get(username='ad')
        self.assertTrue(can_view_interim_request(meeting=meeting,user=user))
        # other AD
        user = User.objects.get(username='ops-ad')
        self.assertTrue(can_view_interim_request(meeting=meeting,user=user))
        # WG Chair
        user = User.objects.get(username='marschairman')
        self.assertTrue(can_view_interim_request(meeting=meeting,user=user))
        # Other WG Chair
        user = User.objects.get(username='ameschairman')
        self.assertFalse(can_view_interim_request(meeting=meeting,user=user))

    def test_can_manage_group(self):
        make_meeting_test_data()
        # unprivileged user
        user = User.objects.get(username='plain')
        group = Group.objects.get(acronym='mars')
        self.assertFalse(can_manage_group(user=user,group=group))
        # Secretariat
        user = User.objects.get(username='secretary')
        self.assertTrue(can_manage_group(user=user,group=group))
        # related AD
        user = User.objects.get(username='ad')
        self.assertTrue(can_manage_group(user=user,group=group))
        # other AD
        user = User.objects.get(username='ops-ad')
        self.assertTrue(can_manage_group(user=user,group=group))
        # WG Chair
        user = User.objects.get(username='marschairman')
        self.assertTrue(can_manage_group(user=user,group=group))
        # Other WG Chair
        user = User.objects.get(username='ameschairman')
        self.assertFalse(can_manage_group(user=user,group=group))

    def test_interim_request_details(self):
        make_interim_test_data(meeting_tz='America/Chicago')
        meeting = Session.objects.with_current_status().filter(
            meeting__type='interim', group__acronym='mars', current_status='apprw').first().meeting
        url = urlreverse('ietf.meeting.views.interim_request_details',kwargs={'number':meeting.number})
        login_testing_unauthorized(self,"secretary",url)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        start_time = meeting.session_set.first().official_timeslotassignment().timeslot.local_start_time().strftime('%H:%M')
        utc_start_time = meeting.session_set.first().official_timeslotassignment().timeslot.utc_start_time().strftime('%H:%M')
        self.assertIn(start_time, unicontent(r))
        self.assertIn(utc_start_time, unicontent(r))

    def test_interim_request_details_announcement(self):
        '''Test access to Announce / Skip Announce features'''
        make_meeting_test_data()
        date = date_today() + datetime.timedelta(days=30)
        group = Group.objects.get(acronym='mars')
        meeting = make_interim_meeting(group=group, date=date, status='scheda')
        url = urlreverse('ietf.meeting.views.interim_request_details',kwargs={'number':meeting.number})

        # Chair, no access
        self.client.login(username="marschairman", password="marschairman+password")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q("a.btn:contains('Announce')")),0)

        # Secretariat has access
        self.client.login(username="secretary", password="secretary+password")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q("a.btn:contains('nnounce')")),2)

    def test_interim_request_details_cancel(self):
        """Test access to cancel meeting / session features"""
        make_interim_test_data()
        mars_sessions = Session.objects.with_current_status(
        ).filter(
            meeting__type='interim',
            group__acronym='mars',
        )
        meeting_apprw = mars_sessions.filter(current_status='apprw').first().meeting
        meeting_sched = mars_sessions.filter(current_status='sched').first().meeting
        # All these roles should have access to cancel the request
        usernames_and_passwords = (
            ('marschairman', 'marschairman+password'),
            ('secretary', 'secretary+password')
        )
        
        # Start with one session - there should not be any cancel session buttons
        for meeting in (meeting_apprw, meeting_sched):
            url = urlreverse('ietf.meeting.views.interim_request_details', 
                             kwargs={'number': meeting.number})

            for username, password in usernames_and_passwords:
                self.client.login(username=username, password=password)
                r = self.client.get(url)
                self.assertEqual(r.status_code, 200)
                q = PyQuery(r.content)
                cancel_meeting_btns = q("a.btn:contains('Cancel meeting')")
                self.assertEqual(len(cancel_meeting_btns), 1,
                                 'Should be exactly one cancel meeting button for user %s' % username)
                self.assertEqual(cancel_meeting_btns.eq(0).attr('href'),
                                 urlreverse('ietf.meeting.views.interim_request_cancel',
                                            kwargs={'number': meeting.number}),
                                 'Cancel meeting points to wrong URL')

                self.assertEqual(len(q("a.btn:contains('Cancel Session')")), 0,
                                 'Should be no cancel session buttons for user %s' % username)

        # Add a second session
        SessionFactory(meeting=meeting_apprw, status_id='apprw')
        SessionFactory(meeting=meeting_sched, status_id='sched')

        for meeting in (meeting_apprw, meeting_sched):
            url = urlreverse('ietf.meeting.views.interim_request_details',
                             kwargs={'number': meeting.number})

            for username, password in usernames_and_passwords:
                self.client.login(username=username, password=password)
                r = self.client.get(url)
                self.assertEqual(r.status_code, 200)
                q = PyQuery(r.content)
                cancel_meeting_btns = q("a.btn:contains('Cancel meeting')")
                self.assertEqual(len(cancel_meeting_btns), 1,
                                 'Should be exactly one cancel meeting button for user %s' % username)
                self.assertEqual(cancel_meeting_btns.eq(0).attr('href'),
                                 urlreverse('ietf.meeting.views.interim_request_cancel',
                                            kwargs={'number': meeting.number}),
                                 'Cancel meeting button points to wrong URL')

                cancel_session_btns = q("a.btn:contains('Cancel session')")
                self.assertEqual(len(cancel_session_btns), 2,
                                 'Should be two cancel session buttons for user %s' % username)
                hrefs = [btn.attr('href') for btn in cancel_session_btns.items()]
                for index, session in enumerate(meeting.session_set.all()):
                    self.assertIn(urlreverse('ietf.meeting.views.interim_request_session_cancel',
                                             kwargs={'sessionid': session.pk}),
                                  hrefs,
                                  'Session missing a link to its cancel URL')

    def test_interim_request_details_status(self):
        """Test statuses on the interim request details page"""
        make_interim_test_data()
        some_person = PersonFactory()
        self.client.login(username='marschairman', password='marschairman+password')
        # These are the first sessions for each meeting - hang on to them
        sessions = list(
            Session.objects.with_current_status().filter(meeting__type='interim', group__acronym='mars')
        )

        # Hack: change the name for the 'canceled' session status so we can tell it apart
        # from the 'canceledpa' session status more easily
        canceled_status = SessionStatusName.objects.get(slug='canceled')
        canceled_status.name = 'This is cancelled'
        canceled_status.save()
        canceledpa_status = SessionStatusName.objects.get(slug='canceledpa')
        notmeet_status = SessionStatusName.objects.get(slug='notmeet')

        # Simplest case - single session for each meeting
        for session in [Session.objects.with_current_status().get(pk=s.pk) for s in sessions]:
            url = urlreverse('ietf.meeting.views.interim_request_details',
                             kwargs={'number': session.meeting.number})
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)
            q = PyQuery(r.content)
            status = SessionStatusName.objects.get(slug=session.current_status)
            self.assertEqual(
                len(q("dd:contains('%s')" % status.name)),
                1  # once - for the meeting status, no session status shown when only one session
            )

        # Now add a second session with a different status - it should not change meeting status
        for session in [Session.objects.with_current_status().get(pk=s.pk) for s in sessions]:
            SessionFactory(meeting=session.meeting, status_id=notmeet_status.pk)
            url = urlreverse('ietf.meeting.views.interim_request_details',
                             kwargs={'number': session.meeting.number})
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)
            q = PyQuery(r.content)
            status = SessionStatusName.objects.get(slug=session.current_status)
            self.assertEqual(
                len(q("dd:contains('%s')" % status.name)),
                2  # twice - once as the meeting status, once as the session status
            )
            self.assertEqual(
                len(q("dd:contains('%s')" % notmeet_status.name)),
                1  # only for the session status
            )

        # Now cancel the first session - second meeting status should be shown for meeting
        for session in [Session.objects.with_current_status().get(pk=s.pk) for s in sessions]:
            # Use 'canceledpa' here and 'canceled' later
            SchedulingEvent.objects.create(session=session,
                                           status=canceledpa_status,
                                           by=some_person)
            url = urlreverse('ietf.meeting.views.interim_request_details',
                             kwargs={'number': session.meeting.number})
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)
            q = PyQuery(r.content)
            self.assertEqual(
                len(q("dd:contains('%s')" % canceledpa_status.name)),
                1  # only for the session status
            )
            self.assertEqual(
                len(q("dd:contains('%s')" % notmeet_status.name)),
                2  # twice - once as the meeting status, once as the session status
            )

        # Now cancel the second session - first meeting status should be shown for meeting again
        for session in [Session.objects.with_current_status().get(pk=s.pk) for s in sessions]:
            second_session = session.meeting.session_set.exclude(pk=session.pk).first()
            # use canceled so we can differentiate between the first and second session statuses
            SchedulingEvent.objects.create(session=second_session,
                                           status=canceled_status,
                                           by=some_person)
            url = urlreverse('ietf.meeting.views.interim_request_details',
                             kwargs={'number': session.meeting.number})
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)
            q = PyQuery(r.content)
            self.assertEqual(
                len(q("dd:contains('%s')" % canceledpa_status.name)),
                2  # twice - once as the meeting status, once as the session status
            )
            self.assertEqual(
                len(q("dd:contains('%s')" % canceled_status.name)),
                1  # only as the session status
            )

    def do_interim_request_disapprove_test(self, extra_session=False, canceled_session=False):
        make_interim_test_data()
        session = Session.objects.with_current_status().filter(
            meeting__type='interim', group__acronym='mars', current_status='apprw').first()
        meeting = session.meeting
        if extra_session:
            extra_session = SessionFactory(meeting=meeting, status_id='apprw')
        if canceled_session:
            canceled_session = SessionFactory(meeting=meeting, status_id='canceledpa')

        url = urlreverse('ietf.meeting.views.interim_request_details',kwargs={'number':meeting.number})
        login_testing_unauthorized(self,"secretary",url)
        r = self.client.post(url,{'disapprove':'Disapprove'})
        self.assertRedirects(r, urlreverse('ietf.meeting.views.interim_pending'))
        for sess in [session, extra_session]:
            if sess:
                self.assertEqual(Session.objects.with_current_status().get(pk=sess.pk).current_status,
                                 'disappr')
        if canceled_session:
            self.assertEqual(Session.objects.with_current_status().get(pk=canceled_session.pk).current_status,
                             'canceledpa')

    def test_interim_request_disapprove(self):
        self.do_interim_request_disapprove_test()

    def test_interim_request_disapprove_with_extra_session(self):
        self.do_interim_request_disapprove_test(extra_session=True)

    def test_interim_request_disapprove_with_canceled_session(self):
        self.do_interim_request_disapprove_test(canceled_session=True)

    def test_interim_request_disapprove_with_extra_and_canceled_sessions(self):
        self.do_interim_request_disapprove_test(extra_session=True, canceled_session=True)

    @patch('ietf.meeting.views.sessions_post_cancel')
    def test_interim_request_cancel(self, mock):
        """Test that interim request cancel function works
        
        Does not test that UI buttons are present, that is handled elsewhere.
        """
        make_interim_test_data()
        meeting = Session.objects.with_current_status(
        ).filter(
            meeting__type='interim',
            group__acronym='mars',
            current_status='apprw',
        ).first().meeting

        # ensure fail unauthorized
        url = urlreverse('ietf.meeting.views.interim_request_cancel', kwargs={'number': meeting.number})
        comments = 'Bob cannot make it'
        self.client.login(username="ameschairman", password="ameschairman+password")
        r = self.client.post(url, {'comments': comments})
        self.assertEqual(r.status_code, 403)
        self.assertFalse(mock.called, 'Should not cancel sessions if request rejected')

        # test with overly-long comments
        comments += '0123456789abcdef'*32
        self.client.login(username="marschairman", password="marschairman+password")
        r = self.client.post(url, {'comments': comments})
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(q('form .is-invalid'))
        # truncate to max_length
        comments = comments[:512]

        # test cancelling before announcement
        length_before = len(outbox)
        r = self.client.post(url, {'comments': comments})
        self.assertRedirects(r, urlreverse('ietf.meeting.views.upcoming'))
        for session in meeting.session_set.with_current_status():
            self.assertEqual(session.current_status,'canceledpa')
            self.assertEqual(session.agenda_note, comments)
        self.assertEqual(len(outbox), length_before)     # no email notice
        self.assertTrue(mock.called, 'Should cancel sessions if request handled')
        self.assertCountEqual(mock.call_args[0][1], meeting.session_set.all())

        # test cancelling after announcement
        mock.reset_mock()
        meeting = add_event_info_to_session_qs(Session.objects.filter(meeting__type='interim', group__acronym='mars')).filter(current_status='sched').first().meeting
        url = urlreverse('ietf.meeting.views.interim_request_cancel', kwargs={'number': meeting.number})
        r = self.client.post(url, {'comments': comments})
        self.assertRedirects(r, urlreverse('ietf.meeting.views.upcoming'))
        for session in meeting.session_set.with_current_status():
            self.assertEqual(session.current_status,'canceled')
            self.assertEqual(session.agenda_note, comments)
        self.assertEqual(len(outbox), length_before + 1)
        self.assertIn('Interim Meeting Cancelled', outbox[-1]['Subject'])
        self.assertIn(comments, get_payload_text(outbox[-1]))
        self.assertTrue(mock.called, 'Should cancel sessions if request handled')
        self.assertCountEqual(mock.call_args[0][1], meeting.session_set.all())

    @patch('ietf.meeting.views.sessions_post_cancel')
    def test_interim_request_session_cancel(self, mock):
        """Test that interim meeting session cancellation functions

        Does not test that UI buttons are present, that is handled elsewhere.
        """
        make_interim_test_data()
        session = Session.objects.with_current_status().filter(
            meeting__type='interim', group__acronym='mars', current_status='apprw',).first()
        meeting = session.meeting
        comments = 'Bob cannot make it'
        
        # Should not be able to cancel when there is only one session
        self.client.login(username="marschairman", password="marschairman+password")
        url = urlreverse('ietf.meeting.views.interim_request_session_cancel', kwargs={'sessionid': session.pk})
        r = self.client.post(url, {'comments': comments})
        self.assertEqual(r.status_code, 409)
        self.assertFalse(mock.called, 'Should not cancel sessions if request rejected')

        # Add a second session
        SessionFactory(meeting=meeting, status_id='apprw')

        # ensure fail unauthorized
        url = urlreverse('ietf.meeting.views.interim_request_session_cancel', kwargs={'sessionid': session.pk})
        self.client.login(username="ameschairman", password="ameschairman+password")
        r = self.client.post(url, {'comments': comments})
        self.assertEqual(r.status_code, 403)
        self.assertFalse(mock.called, 'Should not cancel sessions if request rejected')

        # test cancelling before announcement
        self.client.login(username="marschairman", password="marschairman+password")
        length_before = len(outbox)
        canceled_count_before = meeting.session_set.with_current_status().filter(
            current_status__in=['canceled', 'canceledpa']).count()
        r = self.client.post(url, {'comments': comments})
        self.assertRedirects(r, urlreverse('ietf.meeting.views.interim_request_details', 
                                           kwargs={'number': meeting.number}))
        self.assertTrue(mock.called, 'Should cancel sessions if request handled')
        self.assertCountEqual(mock.call_args[0][1], [session])

        # This session should be canceled...
        sessions = meeting.session_set.with_current_status()
        session = sessions.filter(id=session.pk).first()  # reload our session info
        self.assertEqual(session.current_status, 'canceledpa')
        self.assertEqual(session.agenda_note, comments)
        # But others should not - count should have changed by only 1
        self.assertEqual(
            sessions.filter(current_status__in=['canceled', 'canceledpa']).count(),
            canceled_count_before + 1
        )
        self.assertEqual(len(outbox), length_before)     # no email notice

        # test cancelling after announcement
        mock.reset_mock()
        session = Session.objects.with_current_status().filter(
            meeting__type='interim', group__acronym='mars', current_status='sched').first()
        meeting = session.meeting
        
        # Try to cancel when there's only one session in the meeting
        url = urlreverse('ietf.meeting.views.interim_request_session_cancel', kwargs={'sessionid': session.pk})
        r = self.client.post(url, {'comments': comments})
        self.assertEqual(r.status_code, 409)
        self.assertFalse(mock.called, 'Should not cancel sessions if request rejected')

        # Add another session
        SessionFactory(meeting=meeting, status_id='sched')  # two sessions so canceling a session makes sense

        canceled_count_before = meeting.session_set.with_current_status().filter(
            current_status__in=['canceled', 'canceledpa']).count()
        r = self.client.post(url, {'comments': comments})
        self.assertRedirects(r, urlreverse('ietf.meeting.views.interim_request_details',
                                           kwargs={'number': meeting.number}))
        self.assertTrue(mock.called, 'Should cancel sessions if request handled')
        self.assertCountEqual(mock.call_args[0][1], [session])

        # This session should be canceled...
        sessions = meeting.session_set.with_current_status()
        session = sessions.filter(id=session.pk).first()  # reload our session info
        self.assertEqual(session.current_status, 'canceled')
        self.assertEqual(session.agenda_note, comments)
        # But others should not - count should have changed by only 1
        self.assertEqual(
            sessions.filter(current_status__in=['canceled', 'canceledpa']).count(),
            canceled_count_before + 1
        )
        self.assertEqual(len(outbox), length_before + 1)     # email notice sent
        self.assertIn('session cancelled', outbox[-1]['Subject'])

    def test_interim_request_edit_no_notice(self):
        '''Edit a request.  No notice should go out if it hasn't been announced yet'''
        make_interim_test_data()
        meeting = add_event_info_to_session_qs(Session.objects.filter(meeting__type='interim', group__acronym='mars')).filter(current_status='apprw').first().meeting
        group = meeting.session_set.first().group
        url = urlreverse('ietf.meeting.views.interim_request_edit', kwargs={'number': meeting.number})
        # test unauthorized access
        self.client.login(username="ameschairman", password="ameschairman+password")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 403)
        # test authorized use
        login_testing_unauthorized(self, "secretary", url)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        # post changes
        length_before = len(outbox)
        form_initial = r.context['form'].initial
        formset_initial =  r.context['formset'].forms[0].initial
        data = {'group':group.pk,
                'meeting_type':'single',
                'session_set-0-id':meeting.session_set.first().id,
                'session_set-0-date':formset_initial['date'].strftime('%Y-%m-%d'),
                'session_set-0-time':'12:34',
                'session_set-0-requested_duration': '00:30',
                'session_set-0-remote_instructions':formset_initial['remote_instructions'],
                #'session_set-0-agenda':formset_initial['agenda'],
                'session_set-0-agenda_note':formset_initial['agenda_note'],
                'session_set-TOTAL_FORMS':1,
                'session_set-INITIAL_FORMS':1}
        data.update(form_initial)
        r = self.client.post(url, data)
        self.assertRedirects(r, urlreverse('ietf.meeting.views.interim_request_details', kwargs={'number': meeting.number}))
        self.assertEqual(len(outbox),length_before)
        session = meeting.session_set.first()
        timeslot = session.official_timeslotassignment().timeslot
        self.assertEqual(
            timeslot.time,
            meeting.tz().localize(datetime.datetime.combine(formset_initial['date'], datetime.time(12, 34))),
        )
        
    def test_interim_request_edit(self):
        '''Edit request.  Send notice of change'''
        make_interim_test_data()
        meeting = add_event_info_to_session_qs(Session.objects.filter(meeting__type='interim', group__acronym='mars')).filter(current_status='sched').first().meeting
        group = meeting.session_set.first().group
        url = urlreverse('ietf.meeting.views.interim_request_edit', kwargs={'number': meeting.number})
        # test unauthorized access
        self.client.login(username="ameschairman", password="ameschairman+password")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 403)
        # test authorized use
        login_testing_unauthorized(self, "secretary", url)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        # post changes
        length_before = len(outbox)
        form_initial = r.context['form'].initial
        formset_initial =  r.context['formset'].forms[0].initial
        new_duration = formset_initial['requested_duration'] + datetime.timedelta(hours=1)
        data = {'group':group.pk,
                'meeting_type':'single',
                'session_set-0-id':meeting.session_set.first().id,
                'session_set-0-date':formset_initial['date'].strftime('%Y-%m-%d'),
                'session_set-0-time': '12:34',
                'session_set-0-requested_duration':self.strfdelta(new_duration, '{hours}:{minutes}'),
                'session_set-0-remote_instructions':formset_initial['remote_instructions'],
                #'session_set-0-agenda':formset_initial['agenda'],
                'session_set-0-agenda_note':formset_initial['agenda_note'],
                'session_set-TOTAL_FORMS':1,
                'session_set-INITIAL_FORMS':1}
        data.update(form_initial)
        r = self.client.post(url, data)
        self.assertRedirects(r, urlreverse('ietf.meeting.views.interim_request_details', kwargs={'number': meeting.number}))
        self.assertEqual(len(outbox),length_before+1)
        self.assertIn('CHANGED', outbox[-1]['Subject'])
        session = meeting.session_set.first()
        timeslot = session.official_timeslotassignment().timeslot
        self.assertEqual(
            timeslot.time,
            meeting.tz().localize(datetime.datetime.combine(formset_initial['date'], datetime.time(12, 34))),
        )
        self.assertEqual(timeslot.duration,new_duration)
    
    def strfdelta(self, tdelta, fmt):
        d = {"days": tdelta.days}
        d["hours"], rem = divmod(tdelta.seconds, 3600)
        d["minutes"], d["seconds"] = divmod(rem, 60)
        return fmt.format(**d)

    def test_interim_request_edit_agenda_updates_doc(self):
        """Updating the agenda through the request edit form should update the doc correctly"""
        make_interim_test_data()
        meeting = add_event_info_to_session_qs(Session.objects.filter(meeting__type='interim', group__acronym='mars')).filter(current_status='sched').first().meeting
        group = meeting.session_set.first().group
        url = urlreverse('ietf.meeting.views.interim_request_edit', kwargs={'number': meeting.number})
        session = meeting.session_set.first()
        agenda_doc = session.agenda()
        rev_before = agenda_doc.rev
        uploaded_filename_before = agenda_doc.uploaded_filename

        self.client.login(username='secretary', password='secretary+password')
        r = self.client.get(url)
        form_initial = r.context['form'].initial
        formset_initial = r.context['formset'].forms[0].initial
        data = {
            'group': group.pk,
            'meeting_type': 'single',
            'session_set-0-id': session.id,
            'session_set-0-date': formset_initial['date'].strftime('%Y-%m-%d'),
            'session_set-0-time': formset_initial['time'].strftime('%H:%M'),
            'session_set-0-requested_duration': '00:30',
            'session_set-0-remote_instructions': formset_initial['remote_instructions'],
            'session_set-0-agenda': 'modified agenda contents',
            'session_set-0-agenda_note': formset_initial['agenda_note'],
            'session_set-TOTAL_FORMS': 1,
            'session_set-INITIAL_FORMS': 1,
        }
        data.update(form_initial)
        r = self.client.post(url, data)
        self.assertRedirects(r, urlreverse('ietf.meeting.views.interim_request_details', kwargs={'number': meeting.number}))

        session = Session.objects.get(pk=session.pk)  # refresh
        agenda_doc = session.agenda()
        self.assertEqual(agenda_doc.rev, f'{int(rev_before) + 1:02}', 'Revision of agenda should increase')
        self.assertNotEqual(agenda_doc.uploaded_filename, uploaded_filename_before, 'Uploaded filename should be updated')
        with (Path(agenda_doc.get_file_path()) / agenda_doc.uploaded_filename).open() as f:
            self.assertEqual(f.read(), 'modified agenda contents', 'New agenda contents should be saved')

    def test_interim_request_details_permissions(self):
        make_interim_test_data()
        meeting = add_event_info_to_session_qs(Session.objects.filter(meeting__type='interim', group__acronym='mars')).filter(current_status='apprw').first().meeting
        url = urlreverse('ietf.meeting.views.interim_request_details',kwargs={'number':meeting.number})

        # unprivileged user
        login_testing_unauthorized(self,"plain",url)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 403)

    def test_send_interim_approval_request(self):
        make_interim_test_data()
        meeting = add_event_info_to_session_qs(Session.objects.filter(meeting__type='interim', group__acronym='mars')).filter(current_status='apprw').first().meeting
        length_before = len(outbox)
        send_interim_approval_request(meetings=[meeting])
        self.assertEqual(len(outbox),length_before+1)
        self.assertIn('New Interim Meeting Request', outbox[-1]['Subject'])

    def test_send_interim_meeting_cancellation_notice(self):
        make_interim_test_data()
        meeting = Session.objects.with_current_status(
        ).filter(
            meeting__type='interim',
            group__acronym='mars',
            current_status='sched',
        ).first().meeting
        length_before = len(outbox)
        send_interim_meeting_cancellation_notice(meeting)
        self.assertEqual(len(outbox),length_before + 1)
        self.assertIn('Interim Meeting Cancelled', outbox[-1]['Subject'])

    def test_send_interim_session_cancellation_notice(self):
        make_interim_test_data()
        session = Session.objects.with_current_status(
        ).filter(
            meeting__type='interim',
            group__acronym='mars',
            current_status='sched',
        ).first()
        length_before = len(outbox)
        send_interim_session_cancellation_notice(session)
        self.assertEqual(len(outbox), length_before + 1)
        self.assertIn('session cancelled', outbox[-1]['Subject'])

    def test_send_interim_minutes_reminder(self):
        make_meeting_test_data()
        group = Group.objects.get(acronym='mars')
        date = timezone.now() - datetime.timedelta(days=10)
        meeting = make_interim_meeting(group=group, date=date, status='sched')
        length_before = len(outbox)
        send_interim_minutes_reminder(meeting=meeting)
        self.assertEqual(len(outbox),length_before+1)
        self.assertIn('Action Required: Minutes', outbox[-1]['Subject'])


    def test_group_ical(self):
        make_interim_test_data()
        meeting = Meeting.objects.filter(type='interim', session__group__acronym='mars').first()
        s1 = Session.objects.filter(meeting=meeting, group__acronym="mars").first()
        self.assertGreater(len(s1.remote_instructions), 0, 'Expected remote_instructions to be set')
        a1 = s1.official_timeslotassignment()
        t1 = a1.timeslot
        # Create an extra session
        t2 = TimeSlotFactory.create(
            meeting=meeting,
            time=meeting.tz().localize(
                datetime.datetime.combine(meeting.date, datetime.time(11, 30))
            ))
        s2 = SessionFactory.create(meeting=meeting, group=s1.group, add_to_schedule=False)
        SchedTimeSessAssignment.objects.create(timeslot=t2, session=s2, schedule=meeting.schedule)
        #
        url = urlreverse('ietf.meeting.views.agenda_ical', kwargs={'num':meeting.number, 'acronym':s1.group.acronym, })
        r = self.client.get(url)
        self.assertEqual(r.get('Content-Type'), "text/calendar")
        self.assertContains(r, 'BEGIN:VEVENT')
        self.assertEqual(r.content.count(b'UID'), 2)
        self.assertContains(r, 'SUMMARY:mars - Martian Special Interest Group')
        self.assertContains(r, t1.local_start_time().strftime('%Y%m%dT%H%M%S'))
        self.assertContains(r, s1.remote_instructions)
        self.assertContains(r, t2.local_start_time().strftime('%Y%m%dT%H%M%S'))
        self.assertContains(r, 'END:VEVENT')
        #
        url = urlreverse('ietf.meeting.views.agenda_ical', kwargs={'num':meeting.number, 'session_id':s1.id, })
        r = self.client.get(url)
        self.assertEqual(r.get('Content-Type'), "text/calendar")
        self.assertContains(r, 'BEGIN:VEVENT')
        self.assertEqual(r.content.count(b'UID'), 1)
        self.assertContains(r, 'SUMMARY:mars - Martian Special Interest Group')
        self.assertContains(r, t1.time.strftime('%Y%m%dT%H%M%S'))
        self.assertContains(r, s1.remote_instructions)
        self.assertNotContains(r, t2.time.strftime('%Y%m%dT%H%M%S'))
        self.assertContains(r, 'END:VEVENT')


class IphoneAppJsonTests(TestCase):
    def test_iphone_app_json_interim(self):
        make_interim_test_data()
        meeting = Meeting.objects.filter(type_id='interim').order_by('id').last()
        url = urlreverse('ietf.meeting.views.agenda_json',kwargs={'num':meeting.number})
        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        data = r.json()
        self.assertIn(meeting.number, data.keys())
        jsessions = [ s for s in data[meeting.number] if s['objtype'] == 'session' ]
        msessions = meeting.session_set.exclude(type__in=['lead','offagenda','break','reg'])
        self.assertEqual(len(jsessions), msessions.count())
        for s in jsessions:
            self.assertTrue(msessions.filter(group__acronym=s['group']['acronym']).exists())

    def test_iphone_app_json(self):
        make_meeting_test_data()
        meeting = Meeting.objects.filter(type_id='ietf').order_by('id').last()
        floorplan = FloorPlanFactory.create(meeting=meeting)
        for room in meeting.room_set.all():
            room.floorplan = floorplan
            room.x1 = random.randint(0,100)
            room.y1 = random.randint(0,100)
            room.x2 = random.randint(0,100)
            room.y2 = random.randint(0,100)
            room.save()
        url = urlreverse('ietf.meeting.views.agenda_json',kwargs={'num':meeting.number})
        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        data = r.json()
        self.assertIn(meeting.number, data.keys())
        jsessions = [ s for s in data[meeting.number] if s['objtype'] == 'session' ]
        msessions = meeting.session_set.exclude(type__in=['lead','offagenda','break','reg'])
        self.assertEqual(len(jsessions), msessions.count())
        for s in jsessions:
            self.assertTrue(msessions.filter(group__acronym=s['group']['acronym']).exists())

class FinalizeProceedingsTests(TestCase):
    def test_finalize_proceedings(self):
        make_meeting_test_data()
        meeting = Meeting.objects.filter(type_id='ietf').order_by('id').last()
        meeting.session_set.filter(group__acronym='mars').first().presentations.create(document=Document.objects.filter(type='draft').first(),rev=None)

        url = urlreverse('ietf.meeting.views.finalize_proceedings',kwargs={'num':meeting.number})
        login_testing_unauthorized(self,"secretary",url)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        self.assertEqual(meeting.proceedings_final,False)
        self.assertEqual(meeting.session_set.filter(group__acronym="mars").first().presentations.filter(document__type="draft").first().rev,None)
        r = self.client.post(url,{'finalize':1})
        self.assertEqual(r.status_code, 302)
        meeting = Meeting.objects.get(pk=meeting.pk)
        self.assertEqual(meeting.proceedings_final,True)
        self.assertEqual(meeting.session_set.filter(group__acronym="mars").first().presentations.filter(document__type="draft").first().rev,'00')
 
    @patch("ietf.meeting.utils.generate_bluesheet")
    def test_bluesheet_generation(self, mock):
        meeting = MeetingFactory(type_id="ietf", number="107")  # number where generate_bluesheets should not be called
        SessionFactory.create_batch(5, meeting=meeting)
        url = urlreverse("ietf.meeting.views.finalize_proceedings", kwargs={"num": meeting.number})
        self.client.login(username="secretary", password="secretary+password")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertFalse(mock.called)
        r = self.client.post(url,{'finalize': 1})
        self.assertEqual(r.status_code, 302)
        self.assertFalse(mock.called)

        meeting = MeetingFactory(type_id="ietf", number="108")  # number where generate_bluesheets should be called
        SessionFactory.create_batch(5, meeting=meeting)
        url = urlreverse("ietf.meeting.views.finalize_proceedings", kwargs={"num": meeting.number})
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertFalse(mock.called)
        r = self.client.post(url,{'finalize': 1})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(mock.called)
        self.assertCountEqual(
            [call_args[0][1] for call_args in mock.call_args_list],
            [sess for sess in meeting.session_set.all()],
        )


class MaterialsTests(TestCase):
    settings_temp_path_overrides = TestCase.settings_temp_path_overrides + [
        'AGENDA_PATH',
        'SLIDE_STAGING_PATH'
    ]
    def setUp(self):
        super().setUp()
        self.materials_dir = self.tempdir('materials')
        if not os.path.exists(self.materials_dir):
            os.mkdir(self.materials_dir)

    def tearDown(self):
        shutil.rmtree(self.materials_dir)
        super().tearDown()

    def crawl_materials(self, url, top):
        seen = set()
        def follow(url):
            seen.add(url)
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)
            if not ('.' in url and url.rsplit('.', 1)[1] in ['tgz', 'pdf', ]):
                if r.content:
                    page = unicontent(r)
                    soup = BeautifulSoup(page, 'html.parser')
                    for a in soup('a'):
                        href = a.get('href')
                        path = urlparse(href).path
                        if (path and path not in seen and path.startswith(top)):
                            follow(path)
        follow(url)
    
    def test_upload_bluesheets(self):
        session = SessionFactory(meeting__type_id='ietf')
        url = urlreverse('ietf.meeting.views.upload_session_bluesheets',kwargs={'num':session.meeting.number,'session_id':session.id})
        login_testing_unauthorized(self,"secretary",url)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertIn('Upload', str(q("title")))
        self.assertFalse(session.presentations.exists())
        test_file = StringIO('%PDF-1.4\n%âãÏÓ\nthis is some text for a test')
        test_file.name = "not_really.pdf"
        r = self.client.post(url,dict(file=test_file))
        self.assertEqual(r.status_code, 302)
        bs_doc = session.presentations.filter(document__type_id='bluesheets').first().document
        self.assertEqual(bs_doc.rev,'00')
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertIn('Revise', str(q("title")))
        test_file = StringIO('%PDF-1.4\n%âãÏÓ\nthis is some different text for a test')
        test_file.name = "also_not_really.pdf"
        r = self.client.post(url,dict(file=test_file))
        self.assertEqual(r.status_code, 302)
        bs_doc = Document.objects.get(pk=bs_doc.pk)
        self.assertEqual(bs_doc.rev,'01')
    
    def test_upload_bluesheets_chair_access(self):
        make_meeting_test_data()
        mars = Group.objects.get(acronym='mars')
        session=SessionFactory(meeting__type_id='ietf',group=mars)
        url = urlreverse('ietf.meeting.views.upload_session_bluesheets',kwargs={'num':session.meeting.number,'session_id':session.id})
        self.client.login(username="marschairman", password="marschairman+password")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 403)

    def test_upload_bluesheets_interim(self):
        session=SessionFactory(meeting__type_id='interim')
        url = urlreverse('ietf.meeting.views.upload_session_bluesheets',kwargs={'num':session.meeting.number,'session_id':session.id})
        login_testing_unauthorized(self,"secretary",url)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertIn('Upload', str(q("title")))
        self.assertFalse(session.presentations.exists())
        test_file = StringIO('%PDF-1.4\n%âãÏÓ\nthis is some text for a test')
        test_file.name = "not_really.pdf"
        r = self.client.post(url,dict(file=test_file))
        self.assertEqual(r.status_code, 302)
        bs_doc = session.presentations.filter(document__type_id='bluesheets').first().document
        self.assertEqual(bs_doc.rev,'00')

    def test_upload_bluesheets_interim_chair_access(self):
        make_meeting_test_data()
        mars = Group.objects.get(acronym='mars')
        session=SessionFactory(meeting__type_id='interim',group=mars, meeting__date = date_today())
        url = urlreverse('ietf.meeting.views.upload_session_bluesheets',kwargs={'num':session.meeting.number,'session_id':session.id})
        self.client.login(username="marschairman", password="marschairman+password")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertIn('Upload', str(q("title")))
        

    def test_upload_minutes_agenda(self):
        for doctype in ('minutes','agenda'):
            session = SessionFactory(meeting__type_id='ietf')
            if doctype == 'minutes':
                url = urlreverse('ietf.meeting.views.upload_session_minutes',kwargs={'num':session.meeting.number,'session_id':session.id})
            else:
                url = urlreverse('ietf.meeting.views.upload_session_agenda',kwargs={'num':session.meeting.number,'session_id':session.id})
            self.client.logout()
            login_testing_unauthorized(self,"secretary",url)
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)
            q = PyQuery(r.content)
            self.assertIn('Upload', str(q("Title")))
            self.assertFalse(session.presentations.exists())
            self.assertFalse(q('form input[type="checkbox"]'))
    
            session2 = SessionFactory(meeting=session.meeting,group=session.group)
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)
            q = PyQuery(r.content)
            self.assertTrue(q('form input[type="checkbox"]'))
    
            # test not submitting a file
            r = self.client.post(url, dict(submission_method="upload"))
            self.assertEqual(r.status_code, 200)
            q = PyQuery(r.content)
            self.assertTrue(q("form .is-invalid"))
    
            test_file = BytesIO(b'this is some text for a test')
            test_file.name = "not_really.json"
            r = self.client.post(url,dict(submission_method="upload",file=test_file))
            self.assertEqual(r.status_code, 200)
            q = PyQuery(r.content)
            self.assertTrue(q('form .is-invalid'))
    
            test_file = BytesIO(b'this is some text for a test'*1510000)
            test_file.name = "not_really.pdf"
            r = self.client.post(url,dict(submission_method="upload",file=test_file))
            self.assertEqual(r.status_code, 200)
            q = PyQuery(r.content)
            self.assertTrue(q('form .is-invalid'))
    
            test_file = BytesIO(b'<html><frameset><frame src="foo.html"></frame><frame src="bar.html"></frame></frameset></html>')
            test_file.name = "not_really.html"
            r = self.client.post(url,dict(submission_method="upload",file=test_file))
            self.assertEqual(r.status_code, 200)
            q = PyQuery(r.content)
            self.assertTrue(q('form .is-invalid'))

            # Test html sanitization
            test_file = BytesIO(b'<html><head><title>Title</title></head><body><h1>Title</h1><section>Some text</section></body></html>')
            test_file.name = "some.html"
            r = self.client.post(url,dict(submission_method="upload",file=test_file))
            self.assertEqual(r.status_code, 302)
            doc = session.presentations.filter(document__type_id=doctype).first().document
            self.assertEqual(doc.rev,'00')
            text = doc.text()
            self.assertIn('Some text', text)
            self.assertNotIn('<section>', text)
            self.assertIn('charset="utf-8"', text)

            # txt upload
            test_file = BytesIO(b'This is some text for a test, with the word\nvirtual at the beginning of a line.')
            test_file.name = "some.txt"
            r = self.client.post(url,dict(submission_method="upload",file=test_file,apply_to_all=False))
            self.assertEqual(r.status_code, 302)
            doc = session.presentations.filter(document__type_id=doctype).first().document
            self.assertEqual(doc.rev,'01')
            self.assertFalse(session2.presentations.filter(document__type_id=doctype))
    
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)
            q = PyQuery(r.content)
            self.assertIn('Revise', str(q("Title")))
            test_file = BytesIO(b'this is some different text for a test')
            test_file.name = "also_some.txt"
            r = self.client.post(url,dict(submission_method="upload",file=test_file,apply_to_all=True))
            self.assertEqual(r.status_code, 302)
            doc = Document.objects.get(pk=doc.pk)
            self.assertEqual(doc.rev,'02')
            self.assertTrue(session2.presentations.filter(document__type_id=doctype))

            # Test bad encoding
            test_file = BytesIO('<html><h1>Title</h1><section>Some\x93text</section></html>'.encode('latin1'))
            test_file.name = "some.html"
            r = self.client.post(url,dict(submission_method="upload",file=test_file))
            self.assertContains(r, 'Could not identify the file encoding')
            doc = Document.objects.get(pk=doc.pk)
            self.assertEqual(doc.rev,'02')

            # Verify that we don't have dead links
            url = urlreverse('ietf.meeting.views.session_details', kwargs={'num':session.meeting.number, 'acronym': session.group.acronym})
            top = '/meeting/%s/' % session.meeting.number
            self.requests_mock.get(f'{session.notes_url()}/download', text='markdown notes')
            self.requests_mock.get(f'{session.notes_url()}/info', text=json.dumps({'title': 'title', 'updatetime': '2021-12-01T17:11:00z'}))
            self.crawl_materials(url=url, top=top)

    def test_upload_minutes_agenda_unscheduled(self):
        for doctype in ('minutes','agenda'):
            session = SessionFactory(meeting__type_id='ietf', add_to_schedule=False)
            if doctype == 'minutes':
                url = urlreverse('ietf.meeting.views.upload_session_minutes',kwargs={'num':session.meeting.number,'session_id':session.id})
            else:
                url = urlreverse('ietf.meeting.views.upload_session_agenda',kwargs={'num':session.meeting.number,'session_id':session.id})
            self.client.logout()
            login_testing_unauthorized(self,"secretary",url)
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)
            q = PyQuery(r.content)
            self.assertIn('Upload', str(q("Title")))
            self.assertFalse(session.presentations.exists())
            self.assertFalse(q('form input[type="checkbox"]'))

            test_file = BytesIO(b'this is some text for a test')
            test_file.name = "not_really.txt"
            r = self.client.post(url,dict(submission_method="upload",file=test_file,apply_to_all=False))
            self.assertEqual(r.status_code, 410)

    @override_settings(MEETING_MATERIALS_SERVE_LOCALLY=True)
    def test_upload_minutes_agenda_interim(self):
        session=SessionFactory(meeting__type_id='interim')
        for doctype in ('minutes','agenda'):
            if doctype=='minutes':
                url = urlreverse('ietf.meeting.views.upload_session_minutes',kwargs={'num':session.meeting.number,'session_id':session.id})
            else:
                url = urlreverse('ietf.meeting.views.upload_session_agenda',kwargs={'num':session.meeting.number,'session_id':session.id})
            self.client.logout()
            login_testing_unauthorized(self,"secretary",url)
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)
            q = PyQuery(r.content)
            self.assertIn('Upload', str(q("title")))
            self.assertFalse(session.presentations.filter(document__type_id=doctype))
            test_file = BytesIO(b'this is some text for a test')
            test_file.name = "not_really.txt"
            r = self.client.post(url,dict(submission_method="upload",file=test_file))
            self.assertEqual(r.status_code, 302)
            doc = session.presentations.filter(document__type_id=doctype).first().document
            self.assertEqual(doc.rev,'00')

            # Verify that we don't have dead links
            url = urlreverse('ietf.meeting.views.session_details', kwargs={'num':session.meeting.number, 'acronym': session.group.acronym})
            top = '/meeting/%s/' % session.meeting.number
            self.requests_mock.get(f'{session.notes_url()}/download', text='markdown notes')
            self.requests_mock.get(f'{session.notes_url()}/info', text=json.dumps({'title': 'title', 'updatetime': '2021-12-01T17:11:00z'}))
            self.crawl_materials(url=url, top=top)

    @override_settings(MEETING_MATERIALS_SERVE_LOCALLY=True)
    def test_upload_narrativeminutes(self):
        for type_id in ["interim","ietf"]:
            session=SessionFactory(meeting__type_id=type_id,group__acronym='iesg')
            doctype='narrativeminutes'
            url = urlreverse('ietf.meeting.views.upload_session_narrativeminutes',kwargs={'num':session.meeting.number,'session_id':session.id})
            self.client.logout()
            login_testing_unauthorized(self,"secretary",url)
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)
            q = PyQuery(r.content)
            self.assertIn('Upload', str(q("title")))
            self.assertFalse(session.presentations.filter(document__type_id=doctype))
            test_file = BytesIO(b'this is some text for a test')
            test_file.name = "not_really.txt"
            r = self.client.post(url,dict(submission_method="upload",file=test_file))
            self.assertEqual(r.status_code, 302)
            doc = session.presentations.filter(document__type_id=doctype).first().document
            self.assertEqual(doc.rev,'00')

            # Verify that we don't have dead links
            url = urlreverse('ietf.meeting.views.session_details', kwargs={'num':session.meeting.number, 'acronym': session.group.acronym})
            top = '/meeting/%s/' % session.meeting.number
            self.requests_mock.get(f'{session.notes_url()}/download', text='markdown notes')
            self.requests_mock.get(f'{session.notes_url()}/info', text=json.dumps({'title': 'title', 'updatetime': '2021-12-01T17:11:00z'}))
            self.crawl_materials(url=url, top=top)

    def test_enter_agenda(self):
        session = SessionFactory(meeting__type_id='ietf')
        url = urlreverse('ietf.meeting.views.upload_session_agenda',kwargs={'num':session.meeting.number,'session_id':session.id})
        redirect_url = urlreverse('ietf.meeting.views.session_details', kwargs={'num':session.meeting.number,'acronym':session.group.acronym})
        login_testing_unauthorized(self,"secretary",url)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertIn('Upload', str(q("Title")))
        self.assertFalse(session.presentations.exists())

        test_text = 'Enter agenda from scratch'
        r = self.client.post(url,dict(submission_method="enter",content=test_text))
        self.assertRedirects(r, redirect_url)
        doc = session.presentations.filter(document__type_id='agenda').first().document
        self.assertEqual(doc.rev,'00')

        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertIn('Revise', str(q("Title")))

        test_file = BytesIO(b'Upload after enter')
        test_file.name = "some.txt"
        r = self.client.post(url,dict(submission_method="upload",file=test_file))
        self.assertRedirects(r, redirect_url)
        doc = Document.objects.get(pk=doc.pk)
        self.assertEqual(doc.rev,'01')

        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertIn('Revise', str(q("Title")))

        test_text = 'Enter after upload'
        r = self.client.post(url,dict(submission_method="enter",content=test_text))
        self.assertRedirects(r, redirect_url)
        doc = Document.objects.get(pk=doc.pk)
        self.assertEqual(doc.rev,'02')

    @override_settings(MEETECHO_API_CONFIG="fake settings")  # enough to trigger API calls
    @patch("ietf.meeting.views.SlidesManager")
    def test_upload_slides(self, mock_slides_manager_cls):

        session1 = SessionFactory(meeting__type_id='ietf')
        session2 = SessionFactory(meeting=session1.meeting,group=session1.group)
        url = urlreverse('ietf.meeting.views.upload_session_slides',kwargs={'num':session1.meeting.number,'session_id':session1.id})
        login_testing_unauthorized(self,"secretary",url)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertFalse(mock_slides_manager_cls.called)
        q = PyQuery(r.content)
        self.assertIn('Upload', str(q("title")))
        self.assertFalse(session1.presentations.filter(document__type_id='slides'))
        test_file = BytesIO(b'this is not really a slide')
        test_file.name = 'not_really.txt'
        r = self.client.post(url,dict(file=test_file,title='a test slide file',apply_to_all=True,approved=True))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(session1.presentations.count(),1) 
        self.assertEqual(session2.presentations.count(),1) 
        sp = session2.presentations.first()
        self.assertEqual(sp.document.name, 'slides-%s-%s-a-test-slide-file' % (session1.meeting.number,session1.group.acronym ) )
        self.assertEqual(sp.order,1)
        self.assertEqual(mock_slides_manager_cls.call_count, 1)
        self.assertEqual(mock_slides_manager_cls.call_args, call(api_config="fake settings"))
        self.assertEqual(mock_slides_manager_cls.return_value.add.call_count, 2)
        # don't care which order they were called in, just that both sessions were updated
        self.assertCountEqual(
            mock_slides_manager_cls.return_value.add.call_args_list,
            [
                call(session=session1, slides=sp.document, order=1),
                call(session=session2, slides=sp.document, order=1),
            ],
        )
        mock_slides_manager_cls.reset_mock()

        url = urlreverse('ietf.meeting.views.upload_session_slides',kwargs={'num':session2.meeting.number,'session_id':session2.id})
        test_file = BytesIO(b'some other thing still not slidelike')
        test_file.name = 'also_not_really.txt'
        r = self.client.post(url,dict(file=test_file,title='a different slide file',apply_to_all=False,approved=True))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(session1.presentations.count(),1)
        self.assertEqual(session2.presentations.count(),2)
        sp = session2.presentations.get(document__name__endswith='-a-different-slide-file')
        self.assertEqual(sp.order,2)
        self.assertEqual(sp.rev,'00')
        self.assertEqual(sp.document.rev,'00')
        self.assertEqual(mock_slides_manager_cls.call_count, 1)
        self.assertEqual(mock_slides_manager_cls.call_args, call(api_config="fake settings"))
        self.assertEqual(mock_slides_manager_cls.return_value.add.call_count, 1)
        self.assertEqual(
            mock_slides_manager_cls.return_value.add.call_args,
            call(session=session2, slides=sp.document, order=2),
        )
        mock_slides_manager_cls.reset_mock()

        url = urlreverse('ietf.meeting.views.upload_session_slides',kwargs={'num':session2.meeting.number,'session_id':session2.id,'name':session2.presentations.get(order=2).document.name})
        r = self.client.get(url)
        self.assertTrue(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertIn('Revise', str(q("title")))
        test_file = BytesIO(b'new content for the second slide deck')
        test_file.name = 'doesnotmatter.txt'
        r = self.client.post(url,dict(file=test_file,title='rename the presentation',apply_to_all=False, approved=True))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(session1.presentations.count(),1)
        self.assertEqual(session2.presentations.count(),2)
        replacement_sp = session2.presentations.get(order=2)
        self.assertEqual(replacement_sp.rev,'01')
        self.assertEqual(replacement_sp.document.rev,'01')
        self.assertEqual(mock_slides_manager_cls.call_count, 1)
        self.assertEqual(mock_slides_manager_cls.call_args, call(api_config="fake settings"))
        self.assertEqual(mock_slides_manager_cls.return_value.revise.call_count, 1)
        self.assertEqual(
            mock_slides_manager_cls.return_value.revise.call_args,
            call(session=session2, slides=sp.document),
        )

    def test_upload_slide_title_bad_unicode(self):
        session1 = SessionFactory(meeting__type_id='ietf')
        url = urlreverse('ietf.meeting.views.upload_session_slides',kwargs={'num':session1.meeting.number,'session_id':session1.id})
        login_testing_unauthorized(self,"secretary",url)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertIn('Upload', str(q("title")))
        self.assertFalse(session1.presentations.filter(document__type_id='slides'))
        test_file = BytesIO(b'this is not really a slide')
        test_file.name = 'not_really.txt'
        r = self.client.post(url,dict(file=test_file,title='title with bad character \U0001fabc '))
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(q('form .is-invalid'))
        self.assertIn("Unicode BMP", q('form .is-invalid div').text())

    @override_settings(MEETECHO_API_CONFIG="fake settings")  # enough to trigger API calls
    @patch("ietf.meeting.views.SlidesManager")
    def test_remove_sessionpresentation(self, mock_slides_manager_cls):
        session = SessionFactory(meeting__type_id='ietf')
        agenda = DocumentFactory(type_id='agenda')
        doc = DocumentFactory(type_id='slides')
        session.presentations.create(document=agenda)
        session.presentations.create(document=doc)

        url = urlreverse('ietf.meeting.views.remove_sessionpresentation',kwargs={'num':session.meeting.number,'session_id':session.id,'name':'no-such-doc'})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)
        self.assertFalse(mock_slides_manager_cls.called)

        url = urlreverse('ietf.meeting.views.remove_sessionpresentation',kwargs={'num':session.meeting.number,'session_id':0,'name':doc.name})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)
        self.assertFalse(mock_slides_manager_cls.called)

        url = urlreverse('ietf.meeting.views.remove_sessionpresentation',kwargs={'num':session.meeting.number,'session_id':session.id,'name':doc.name})
        login_testing_unauthorized(self,"secretary",url)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(mock_slides_manager_cls.called)

        # Removing slides should remove the materials and call MeetechoAPI
        self.assertEqual(2, session.presentations.count())
        response = self.client.post(url,{'remove_session':''})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(1, session.presentations.count())
        self.assertEqual(2, doc.docevent_set.count())
        self.assertEqual(mock_slides_manager_cls.call_count, 1)
        self.assertEqual(mock_slides_manager_cls.call_args, call(api_config="fake settings"))
        self.assertEqual(mock_slides_manager_cls.return_value.delete.call_count, 1)
        self.assertEqual(
            mock_slides_manager_cls.return_value.delete.call_args,
            call(session=session, slides=doc),
        )
        mock_slides_manager_cls.reset_mock()

        # Removing non-slides should only remove the materials
        url = urlreverse(
            "ietf.meeting.views.remove_sessionpresentation",
            kwargs={
                "num": session.meeting.number,
                "session_id": session.id,
                "name": agenda.name,
            },
        )
        response = self.client.post(url, {"remove_session" : ""})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(0, session.presentations.count())
        self.assertEqual(2, agenda.docevent_set.count())
        self.assertFalse(mock_slides_manager_cls.called)


    def test_propose_session_slides(self):
        for type_id in ['ietf','interim']:
            session = SessionFactory(meeting__type_id=type_id)
            chair = RoleFactory(group=session.group,name_id='chair').person
            session.meeting.importantdate_set.create(name_id='revsub',date=date_today() + datetime.timedelta(days=20))
            newperson = PersonFactory()
            
            session_overview_url = urlreverse('ietf.meeting.views.session_details',kwargs={'num':session.meeting.number,'acronym':session.group.acronym})
            upload_url = urlreverse('ietf.meeting.views.upload_session_slides', kwargs={'session_id':session.pk, 'num': session.meeting.number})    

            r = self.client.get(session_overview_url)
            self.assertEqual(r.status_code,200)
            q = PyQuery(r.content)
            self.assertFalse(q('.uploadslides'))
            self.assertFalse(q('.proposeslides'))

            self.client.login(username=newperson.user.username,password=newperson.user.username+"+password")
            r = self.client.get(session_overview_url)
            self.assertEqual(r.status_code,200)
            q = PyQuery(r.content)
            self.assertTrue(q('.proposeslides'))
            self.client.logout()

            login_testing_unauthorized(self,newperson.user.username,upload_url)
            r = self.client.get(upload_url)
            self.assertEqual(r.status_code,200)
            test_file = BytesIO(b'this is not really a slide')
            test_file.name = 'not_really.txt'
            empty_outbox()
            r = self.client.post(upload_url,dict(file=test_file,title='a test slide file',apply_to_all=True,approved=False))
            self.assertEqual(r.status_code, 302)
            session = Session.objects.get(pk=session.pk)
            self.assertEqual(session.slidesubmission_set.count(),1)
            self.assertEqual(len(outbox),1)

            r = self.client.get(session_overview_url)
            self.assertEqual(r.status_code, 200)
            q = PyQuery(r.content)
            self.assertEqual(len(q('.proposedslidelist p')), 1)

            SlideSubmissionFactory(session = session)

            self.client.logout()
            self.client.login(username=chair.user.username, password=chair.user.username+"+password")
            r = self.client.get(session_overview_url)
            self.assertEqual(r.status_code, 200)
            q = PyQuery(r.content)
            self.assertEqual(len(q('.proposedslidelist p')), 2)
            self.client.logout()

            login_testing_unauthorized(self,chair.user.username,upload_url)
            r = self.client.get(upload_url)
            self.assertEqual(r.status_code,200)
            test_file = BytesIO(b'this is not really a slide either')
            test_file.name = 'again_not_really.txt'
            empty_outbox()
            r = self.client.post(upload_url,dict(file=test_file,title='a selfapproved test slide file',apply_to_all=True,approved=True))
            self.assertEqual(r.status_code, 302)
            self.assertEqual(len(outbox),0)
            self.assertEqual(session.slidesubmission_set.count(),2)
            self.client.logout()

            self.client.login(username=chair.user.username, password=chair.user.username+"+password")
            r = self.client.get(session_overview_url)
            self.assertEqual(r.status_code, 200)
            q = PyQuery(r.content)
            self.assertEqual(len(q('.uploadslidelist p')), 0)
            self.client.logout()

    def test_disapprove_proposed_slides(self):
        submission = SlideSubmissionFactory()
        submission.session.meeting.importantdate_set.create(name_id='revsub',date=date_today() + datetime.timedelta(days=20))
        self.assertEqual(SlideSubmission.objects.filter(status__slug = 'pending').count(), 1)
        chair = RoleFactory(group=submission.session.group,name_id='chair').person
        url = urlreverse('ietf.meeting.views.approve_proposed_slides', kwargs={'slidesubmission_id':submission.pk,'num':submission.session.meeting.number})
        login_testing_unauthorized(self, chair.user.username, url)
        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        r = self.client.post(url,dict(title='some title',disapprove="disapprove"))
        self.assertEqual(r.status_code,302)
        self.assertEqual(SlideSubmission.objects.filter(status__slug = 'rejected').count(), 1)
        self.assertEqual(SlideSubmission.objects.filter(status__slug = 'pending').count(), 0)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertRegex(r.content.decode(), r"These\s+slides\s+have\s+already\s+been\s+rejected")

    @override_settings(MEETECHO_API_CONFIG="fake settings")  # enough to trigger API calls
    @patch("ietf.meeting.views.SlidesManager")
    def test_approve_proposed_slides(self, mock_slides_manager_cls):
        submission = SlideSubmissionFactory()
        session = submission.session
        session.meeting.importantdate_set.create(name_id='revsub',date=date_today() + datetime.timedelta(days=20))
        chair = RoleFactory(group=submission.session.group,name_id='chair').person
        url = urlreverse('ietf.meeting.views.approve_proposed_slides', kwargs={'slidesubmission_id':submission.pk,'num':submission.session.meeting.number})
        login_testing_unauthorized(self, chair.user.username, url)
        self.assertEqual(submission.status_id, 'pending')
        self.assertIsNone(submission.doc)
        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        empty_outbox()
        r = self.client.post(url,dict(title='different title',approve='approve'))
        self.assertEqual(r.status_code,302)
        self.assertEqual(SlideSubmission.objects.filter(status__slug = 'pending').count(), 0)
        self.assertEqual(SlideSubmission.objects.filter(status__slug = 'approved').count(), 1)
        submission.refresh_from_db()
        self.assertEqual(submission.status_id, 'approved')
        self.assertIsNotNone(submission.doc)
        self.assertEqual(session.presentations.count(),1)
        self.assertEqual(session.presentations.first().document.title,'different title')
        self.assertEqual(mock_slides_manager_cls.call_count, 1)
        self.assertEqual(mock_slides_manager_cls.call_args, call(api_config="fake settings"))
        self.assertEqual(mock_slides_manager_cls.return_value.add.call_count, 1)
        self.assertEqual(
            mock_slides_manager_cls.return_value.add.call_args,
            call(session=session, slides=submission.doc, order=1),
        )
        mock_slides_manager_cls.reset_mock()
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertRegex(r.content.decode(), r"These\s+slides\s+have\s+already\s+been\s+approved")
        self.assertFalse(mock_slides_manager_cls.called)
        self.assertEqual(len(outbox), 1)
        self.assertIn(submission.submitter.email_address(), outbox[0]['To'])
        self.assertIn('Slides approved', outbox[0]['Subject'])

    @override_settings(MEETECHO_API_CONFIG="fake settings")  # enough to trigger API calls
    @patch("ietf.meeting.views.SlidesManager")
    def test_approve_proposed_slides_multisession_apply_one(self, mock_slides_manager_cls):
        submission = SlideSubmissionFactory(session__meeting__type_id='ietf')
        session1 = submission.session
        session2 = SessionFactory(group=submission.session.group, meeting=submission.session.meeting)
        submission.session.meeting.importantdate_set.create(name_id='revsub',date=date_today() + datetime.timedelta(days=20))
        chair = RoleFactory(group=submission.session.group,name_id='chair').person
        url = urlreverse('ietf.meeting.views.approve_proposed_slides', kwargs={'slidesubmission_id':submission.pk,'num':submission.session.meeting.number})
        login_testing_unauthorized(self, chair.user.username, url)
        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        q = PyQuery(r.content)
        self.assertTrue(q('#id_apply_to_all'))
        r = self.client.post(url,dict(title='yet another title',approve='approve'))
        submission.refresh_from_db()
        self.assertIsNotNone(submission.doc)
        self.assertEqual(r.status_code,302)
        self.assertEqual(session1.presentations.count(),1)
        self.assertEqual(session2.presentations.count(),0)
        self.assertEqual(mock_slides_manager_cls.call_count, 1)
        self.assertEqual(mock_slides_manager_cls.call_args, call(api_config="fake settings"))
        self.assertEqual(mock_slides_manager_cls.return_value.add.call_count, 1)
        self.assertEqual(
            mock_slides_manager_cls.return_value.add.call_args,
            call(session=session1, slides=submission.doc, order=1),
        )

    @override_settings(MEETECHO_API_CONFIG="fake settings")  # enough to trigger API calls
    @patch("ietf.meeting.views.SlidesManager")
    def test_approve_proposed_slides_multisession_apply_all(self, mock_slides_manager_cls):
        submission = SlideSubmissionFactory(session__meeting__type_id='ietf')
        session1 = submission.session
        session2 = SessionFactory(group=submission.session.group, meeting=submission.session.meeting)
        submission.session.meeting.importantdate_set.create(name_id='revsub',date=date_today() + datetime.timedelta(days=20))
        chair = RoleFactory(group=submission.session.group,name_id='chair').person
        url = urlreverse('ietf.meeting.views.approve_proposed_slides', kwargs={'slidesubmission_id':submission.pk,'num':submission.session.meeting.number})
        login_testing_unauthorized(self, chair.user.username, url)
        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        r = self.client.post(url,dict(title='yet another title',apply_to_all=1,approve='approve'))
        submission.refresh_from_db()
        self.assertEqual(r.status_code,302)
        self.assertEqual(session1.presentations.count(),1)
        self.assertEqual(session2.presentations.count(),1)
        self.assertEqual(mock_slides_manager_cls.call_count, 1)
        self.assertEqual(mock_slides_manager_cls.call_args, call(api_config="fake settings"))
        self.assertEqual(mock_slides_manager_cls.return_value.add.call_count, 2)
        self.assertCountEqual(
            mock_slides_manager_cls.return_value.add.call_args_list,
            [
                call(session=session1, slides=submission.doc, order=1),
                call(session=session2, slides=submission.doc, order=1),
            ]
        )

    @override_settings(MEETECHO_API_CONFIG="fake settings")  # enough to trigger API calls
    @patch("ietf.meeting.views.SlidesManager")
    def test_submit_and_approve_multiple_versions(self, mock_slides_manager_cls):
        session = SessionFactory(meeting__type_id='ietf')
        chair = RoleFactory(group=session.group,name_id='chair').person
        session.meeting.importantdate_set.create(name_id='revsub',date=date_today()+datetime.timedelta(days=20))
        newperson = PersonFactory()
        
        upload_url = urlreverse('ietf.meeting.views.upload_session_slides', kwargs={'session_id':session.pk, 'num': session.meeting.number})          
        
        login_testing_unauthorized(self,newperson.user.username,upload_url)
        test_file = BytesIO(b'this is not really a slide')
        test_file.name = 'not_really.txt'
        r = self.client.post(upload_url,dict(file=test_file,title='a test slide file',apply_to_all=True,approved=False))
        self.assertEqual(r.status_code, 302)
        self.client.logout()

        submission = SlideSubmission.objects.get(session=session)

        approve_url = urlreverse('ietf.meeting.views.approve_proposed_slides', kwargs={'slidesubmission_id':submission.pk,'num':submission.session.meeting.number})
        login_testing_unauthorized(self, chair.user.username, approve_url)
        r = self.client.post(approve_url,dict(title=submission.title,approve='approve'))
        submission.refresh_from_db()
        self.assertEqual(r.status_code,302)
        self.client.logout()
        self.assertEqual(mock_slides_manager_cls.call_count, 1)
        self.assertEqual(mock_slides_manager_cls.call_args, call(api_config="fake settings"))
        self.assertEqual(mock_slides_manager_cls.return_value.add.call_count, 1)
        self.assertEqual(
            mock_slides_manager_cls.return_value.add.call_args,
            call(session=session, slides=submission.doc, order=1),
        )
        mock_slides_manager_cls.reset_mock()
        
        self.assertEqual(session.presentations.first().document.rev,'00')

        login_testing_unauthorized(self,newperson.user.username,upload_url)
        test_file = BytesIO(b'this is not really a slide, but it is another version of it')
        test_file.name = 'not_really.txt'
        r = self.client.post(upload_url,dict(file=test_file,title='a test slide file',apply_to_all=True))
        self.assertEqual(r.status_code, 302)

        test_file = BytesIO(b'this is not really a slide, but it is third version of it')
        test_file.name = 'not_really.txt'
        r = self.client.post(upload_url,dict(file=test_file,title='a test slide file',apply_to_all=True))
        self.assertEqual(r.status_code, 302)
        self.client.logout()       

        (first_submission, second_submission) = SlideSubmission.objects.filter(session=session, status__slug = 'pending').order_by('id')

        approve_url = urlreverse('ietf.meeting.views.approve_proposed_slides', kwargs={'slidesubmission_id':second_submission.pk,'num':second_submission.session.meeting.number})
        login_testing_unauthorized(self, chair.user.username, approve_url)
        r = self.client.post(approve_url,dict(title=submission.title,approve='approve'))
        first_submission.refresh_from_db()
        second_submission.refresh_from_db()
        self.assertEqual(r.status_code,302)
        self.assertEqual(mock_slides_manager_cls.call_count, 1)
        self.assertEqual(mock_slides_manager_cls.call_args, call(api_config="fake settings"))
        self.assertEqual(mock_slides_manager_cls.return_value.add.call_count, 0)
        self.assertEqual(mock_slides_manager_cls.return_value.revise.call_count, 1)
        self.assertEqual(
            mock_slides_manager_cls.return_value.revise.call_args,
            call(session=session, slides=second_submission.doc),
        )
        mock_slides_manager_cls.reset_mock()

        disapprove_url = urlreverse('ietf.meeting.views.approve_proposed_slides', kwargs={'slidesubmission_id':first_submission.pk,'num':first_submission.session.meeting.number})
        r = self.client.post(disapprove_url,dict(title='some title',disapprove="disapprove"))
        self.assertEqual(r.status_code,302)
        self.client.logout()
        self.assertFalse(mock_slides_manager_cls.called)

        self.assertEqual(SlideSubmission.objects.filter(status__slug = 'pending').count(),0)
        self.assertEqual(SlideSubmission.objects.filter(status__slug = 'rejected').count(),1)
        self.assertEqual(session.presentations.first().document.rev,'01')
        path = os.path.join(submission.session.meeting.get_materials_path(),'slides')
        filename = os.path.join(path,session.presentations.first().document.name+'-01.txt')
        self.assertTrue(os.path.exists(filename))
        fd = io.open(filename, 'r')
        contents = fd.read()
        fd.close()
        self.assertIn('third version', contents)


@override_settings(IETF_NOTES_URL='https://notes.ietf.org/')
class ImportNotesTests(TestCase):
    settings_temp_path_overrides = TestCase.settings_temp_path_overrides + ['AGENDA_PATH']

    def setUp(self):
        super().setUp()
        self.session = SessionFactory(meeting__type_id='ietf')
        self.meeting = self.session.meeting

    def test_retrieves_note(self):
        """Can import and preview a note from notes.ietf.org"""
        url = urlreverse('ietf.meeting.views.import_session_minutes',
                         kwargs={'num': self.meeting.number, 'session_id': self.session.pk})

        self.client.login(username='secretary', password='secretary+password')
        with requests_mock.Mocker() as mock:
            mock.get(f'https://notes.ietf.org/{self.session.notes_id()}/download', text='markdown text')
            mock.get(f'https://notes.ietf.org/{self.session.notes_id()}/info',
                     text=json.dumps({"title": "title", "updatetime": "2021-12-02T11:22:33z"}))
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)
            q = PyQuery(r.content)
            iframe = q('iframe#preview')
            self.assertEqual('<p>markdown text</p>', iframe.attr('srcdoc'))
            markdown_text_input = q('form #id_markdown_text')
            self.assertEqual(markdown_text_input.val(), 'markdown text')

    def test_retrieves_with_broken_metadata(self):
        """Can import and preview a note even if it has a metadata problem"""
        url = urlreverse('ietf.meeting.views.import_session_minutes',
                         kwargs={'num': self.meeting.number, 'session_id': self.session.pk})

        self.client.login(username='secretary', password='secretary+password')
        with requests_mock.Mocker() as mock:
            mock.get(f'https://notes.ietf.org/{self.session.notes_id()}/download', text='markdown text')
            mock.get(f'https://notes.ietf.org/{self.session.notes_id()}/info', text='this is not valid json {]')
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)
            q = PyQuery(r.content)
            iframe = q('iframe#preview')
            self.assertEqual('<p>markdown text</p>', iframe.attr('srcdoc'))
            markdown_text_input = q('form #id_markdown_text')
            self.assertEqual(markdown_text_input.val(), 'markdown text')

    def test_redirects_on_success(self):
        """Redirects to session details page after import"""
        url = urlreverse('ietf.meeting.views.import_session_minutes',
                         kwargs={'num': self.meeting.number, 'session_id': self.session.pk})

        self.client.login(username='secretary', password='secretary+password')
        r = self.client.post(url, {'markdown_text': 'markdown text'})
        self.assertRedirects(
            r,
            urlreverse(
                'ietf.meeting.views.session_details',
                kwargs={
                    'num': self.meeting.number,
                    'acronym': self.session.group.acronym,
                },
            ),
        )

    def test_imports_previewed_text(self):
        """Import text that was shown as preview even if notes site is updated"""
        url = urlreverse('ietf.meeting.views.import_session_minutes',
                         kwargs={'num': self.meeting.number, 'session_id': self.session.pk})

        self.client.login(username='secretary', password='secretary+password')
        with requests_mock.Mocker() as mock:
            mock.get(f'https://notes.ietf.org/{self.session.notes_id()}/download', text='updated markdown text')
            mock.get(f'https://notes.ietf.org/{self.session.notes_id()}/info',
                     text=json.dumps({"title": "title", "updatetime": "2021-12-02T11:22:33z"}))
            r = self.client.post(url, {'markdown_text': 'original markdown text'})
        self.assertEqual(r.status_code, 302)
        minutes_path = Path(self.meeting.get_materials_path()) / 'minutes'
        with (minutes_path / self.session.minutes().uploaded_filename).open() as f:
            self.assertEqual(f.read(), 'original markdown text')

    def test_refuses_identical_import(self):
        """Should not be able to import text identical to the current revision"""
        url = urlreverse('ietf.meeting.views.import_session_minutes',
                         kwargs={'num': self.meeting.number, 'session_id': self.session.pk})

        self.client.login(username='secretary', password='secretary+password')
        with requests_mock.Mocker() as mock:
            mock.get(f'https://notes.ietf.org/{self.session.notes_id()}/download', text='original markdown text')
            mock.get(f'https://notes.ietf.org/{self.session.notes_id()}/info',
                     text=json.dumps({"title": "title", "updatetime": "2021-12-02T11:22:33z"}))
            # Create a revision. Run the original text through the preprocessing done when importing
            # from the notes site.
            r = self.client.get(url)  # let GET do its preprocessing
            q = PyQuery(r.content)
            r = self.client.post(url, {'markdown_text': q('input[name="markdown_text"]').attr['value']})
            self.assertEqual(r.status_code, 302)

            r = self.client.get(url)  # try to import the same text
            self.assertContains(r, "This document is identical", status_code=200)
            q = PyQuery(r.content)
            self.assertEqual(len(q('#content button:disabled[type="submit"]')), 1)
            self.assertEqual(len(q('#content button:enabled[type="submit"]')), 0)

    def test_allows_import_on_existing_bad_unicode(self):
        """Should not be able to import text identical to the current revision"""
        url = urlreverse('ietf.meeting.views.import_session_minutes',
                         kwargs={'num': self.meeting.number, 'session_id': self.session.pk})

        self.client.login(username='secretary', password='secretary+password')
        r = self.client.post(url, {'markdown_text': 'replaced below'})  # create a rev
        with open(
                self.session.presentations.filter(document__type="minutes").first().document.get_file_name(),
                'wb'
        ) as f:
            # Replace existing content with an invalid Unicode byte string. The particular invalid
            # values here are accented characters in the MacRoman charset (see ticket #3756).
            f.write(b'invalid \x8e unicode \x99\n')
        self.assertEqual(r.status_code, 302)
        with requests_mock.Mocker() as mock:
            mock.get(f'https://notes.ietf.org/{self.session.notes_id()}/download', text='original markdown text')
            mock.get(f'https://notes.ietf.org/{self.session.notes_id()}/info',
                     text=json.dumps({"title": "title", "updatetime": "2021-12-02T11:22:33z"}))
            r = self.client.get(url)  # try to import the same text
            self.assertNotContains(r, "This document is identical", status_code=200)
            q = PyQuery(r.content)
            self.assertEqual(len(q('#content button:enabled[type="submit"]')), 1)
            self.assertEqual(len(q('#content button:disabled[type="submit"]')), 0)

    def test_handles_missing_previous_revision_file(self):
        """Should still allow import if the file for the previous revision is missing"""
        url = urlreverse('ietf.meeting.views.import_session_minutes',
                         kwargs={'num': self.meeting.number, 'session_id': self.session.pk})

        self.client.login(username='secretary', password='secretary+password')
        r = self.client.post(url, {'markdown_text': 'original markdown text'})  # create a rev
        # remove the file uploaded for the first rev
        minutes_docs = self.session.presentations.filter(document__type='minutes')
        self.assertEqual(minutes_docs.count(), 1)
        Path(minutes_docs.first().document.get_file_name()).unlink()

        self.assertEqual(r.status_code, 302)
        with requests_mock.Mocker() as mock:
            mock.get(f'https://notes.ietf.org/{self.session.notes_id()}/download', text='original markdown text')
            mock.get(f'https://notes.ietf.org/{self.session.notes_id()}/info',
                     text=json.dumps({"title": "title", "updatetime": "2021-12-02T11:22:33z"}))
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)
            q = PyQuery(r.content)
            iframe = q('iframe#preview')
            self.assertEqual('<p>original markdown text</p>', iframe.attr('srcdoc'))
            markdown_text_input = q('form #id_markdown_text')
            self.assertEqual(markdown_text_input.val(), 'original markdown text')

    def test_handles_note_does_not_exist(self):
        """Should not try to import a note that does not exist"""
        url = urlreverse('ietf.meeting.views.import_session_minutes',
                         kwargs={'num': self.meeting.number, 'session_id': self.session.pk})

        self.client.login(username='secretary', password='secretary+password')
        with requests_mock.Mocker() as mock:
            mock.get(requests_mock.ANY, status_code=404)
            r = self.client.get(url, follow=True)
        self.assertContains(r, 'Could not import', status_code=200)

    def test_handles_notes_server_failure(self):
        """Problems communicating with the notes server should be handled gracefully"""
        url = urlreverse('ietf.meeting.views.import_session_minutes',
                         kwargs={'num': self.meeting.number, 'session_id': self.session.pk})
        self.client.login(username='secretary', password='secretary+password')

        with requests_mock.Mocker() as mock:
            mock.get(re.compile(r'.+/download'), exc=requests.exceptions.ConnectTimeout)
            mock.get(re.compile(r'.+//info'), text='{}')
            r = self.client.get(url, follow=True)
        self.assertContains(r, 'Could not reach the notes server', status_code=200)


class SessionTests(TestCase):

    def test_get_summary_by_area(self):
        meeting = make_meeting_test_data(meeting=MeetingFactory(type_id='ietf', number='100'))
        sessions = Session.objects.filter(meeting=meeting).with_current_status()
        data = get_summary_by_area(sessions)
        self.assertEqual(data[0][0], 'Duration')
        self.assertGreater(len(data), 2)
        self.assertEqual(data[-1][0], 'Total Hours')

    def test_get_summary_by_type(self):
        meeting = make_meeting_test_data(meeting=MeetingFactory(type_id='ietf', number='100'))
        sessions = Session.objects.filter(meeting=meeting).with_current_status()
        data = get_summary_by_type(sessions)
        self.assertEqual(data[0][0], 'Group Type')
        self.assertGreater(len(data), 2)

    def test_get_summary_by_purpose(self):
        meeting = make_meeting_test_data(meeting=MeetingFactory(type_id='ietf', number='100'))
        sessions = Session.objects.filter(meeting=meeting).with_current_status()
        data = get_summary_by_purpose(sessions)
        self.assertEqual(data[0][0], 'Purpose')
        self.assertGreater(len(data), 2)

    def test_meeting_requests(self):
        meeting = MeetingFactory(type_id='ietf')

        # a couple non-wg group types, confirm that their has_meetings features are as expected
        group_type_with_meetings = 'adhoc'
        self.assertTrue(GroupFeatures.objects.get(pk=group_type_with_meetings).has_meetings)
        group_type_without_meetings = 'sdo'
        self.assertFalse(GroupFeatures.objects.get(pk=group_type_without_meetings).has_meetings)

        area = GroupFactory(type_id='area', acronym='area')
        requested_session = SessionFactory(meeting=meeting,group__parent=area,status_id='schedw',add_to_schedule=False)
        conflicting_session = SessionFactory(meeting=meeting,group__parent=area,status_id='schedw',add_to_schedule=False)
        ConstraintFactory(name_id='key_participant',meeting=meeting,source=requested_session.group,target=conflicting_session.group)
        not_meeting = SessionFactory(meeting=meeting,group__parent=area,status_id='notmeet',add_to_schedule=False)
        has_meetings = SessionFactory(
            meeting=meeting,
            group__type_id=group_type_with_meetings,
            status_id='schedw',
            add_to_schedule=False,
        )
        has_meetings_not_meeting = SessionFactory(
            meeting=meeting,
            group__type_id=group_type_with_meetings,
            status_id='notmeet',
            add_to_schedule=False,
        )
        # admin and social sessions are not to be shown on the requests page
        has_meetings_admin_session = SessionFactory(
            meeting=meeting,
            group__type_id=group_type_with_meetings,
            status_id='schedw',
            purpose_id='admin',
            type_id='other',
            add_to_schedule=False,
        )
        has_meetings_social_session = SessionFactory(
            meeting=meeting,
            group__type_id=group_type_with_meetings,
            status_id='schedw',
            purpose_id='social',
            type_id='break',
            add_to_schedule=False,
        )
        not_has_meetings = SessionFactory(
            meeting=meeting,
            group__type_id=group_type_without_meetings,
            status_id='schedw',
            add_to_schedule=False,
        )
        # bof sessions should be shown
        bof_session = SessionFactory(
            meeting=meeting,
            group__parent=area,
            group__state_id='bof',
            status_id='schedw',
            add_to_schedule=False,
        )
        # proposed WG sessions should be shown
        proposed_wg_session = SessionFactory(
            meeting=meeting,
            group__parent=area,
            group__state_id='proposed',
            status_id='schedw',
            add_to_schedule=False,
        )
        # rg sessions should be shown under 'irtf' heading
        rg_session = SessionFactory(
            meeting=meeting,
            group__type_id='rg',
            status_id='schedw',
            add_to_schedule=False,
        )
        session_with_none_purpose = SessionFactory(
            meeting=meeting,
            group__parent=area,
            purpose_id="none",
            status_id="schedw",
            add_to_schedule=False,
        )
        tutorial_session = SessionFactory(
            meeting=meeting,
            group__parent=area,
            purpose_id="tutorial",
            status_id="schedw",
            add_to_schedule=False,
        )
        def _sreq_edit_link(sess):
            return urlreverse(
                'ietf.secr.sreq.views.edit',
                kwargs={
                    'num': meeting.number,
                    'acronym': sess.group.acronym,
                },
            )

        url = urlreverse('ietf.meeting.views.meeting_requests',kwargs={'num':meeting.number})
        r = self.client.get(url)
        # requested_session group should be listed with a link to the request
        self.assertContains(r, requested_session.group.acronym)
        self.assertContains(r, _sreq_edit_link(requested_session))  # link to the session request
        self.assertContains(r, not_meeting.group.acronym)
        # The admin/social session groups should be listed under "no timeslot request received"; it's easier
        # to check that the group is listed but that there is no link to the session request than to try to
        # parse the HTML. If the view is changed to link to the "no timeslot request received" session requests,
        # then need to revisit.
        self.assertContains(r, has_meetings_admin_session.group.acronym)
        self.assertNotContains(r, _sreq_edit_link(has_meetings_admin_session))  # no link to the session request
        self.assertContains(r, has_meetings_social_session.group.acronym)
        self.assertNotContains(r, _sreq_edit_link(has_meetings_social_session))  # no link to the session request
        self.assertContains(r, requested_session.constraints().first().name)
        self.assertContains(r, conflicting_session.group.acronym)
        self.assertContains(r, _sreq_edit_link(conflicting_session))  # link to the session request
        self.assertContains(r, has_meetings.group.acronym)
        self.assertContains(r, _sreq_edit_link(has_meetings))  # link to the session request
        self.assertContains(r, has_meetings_not_meeting.group.acronym)
        self.assertContains(r, _sreq_edit_link(has_meetings_not_meeting))  # link to the session request
        self.assertNotContains(r, not_has_meetings.group.acronym)
        self.assertNotContains(r, _sreq_edit_link(not_has_meetings))  # no link to the session request
        self.assertContains(r, bof_session.group.acronym)
        self.assertContains(r, _sreq_edit_link(bof_session))  # link to the session request
        self.assertContains(r, proposed_wg_session.group.acronym)
        self.assertContains(r, _sreq_edit_link(proposed_wg_session))  # link to the session request
        self.assertContains(r, rg_session.group.acronym)
        self.assertContains(r, _sreq_edit_link(rg_session))  # link to the session request
        self.assertContains(r, session_with_none_purpose.group.acronym)
        self.assertContains(r, tutorial_session.group.acronym)
        # check headings - note that the special types (has_meetings, etc) do not have a group parent
        # so they show up in 'other'
        q = PyQuery(r.content)
        self.assertEqual(len(q('h2#area')), 1)
        self.assertEqual(len(q('h2#other-groups')), 1)
        self.assertEqual(len(q('h2#irtf')), 1)  # rg group has irtf group as parent

        # check rounded pills
        self.assertNotContains(  # no rounded pill for sessions with regular purpose
            r,
            '<span class="badge rounded-pill text-bg-info">Regular</span>',
            html=True,
        )
        self.assertNotContains(  # no rounded pill for session with no purpose specified
            r,
            '<span class="badge rounded-pill text-bg-info">None</span>',
            html=True,
        )
        self.assertContains(  # rounded pill for session with non-regular purpose
            r,
            '<span class="badge rounded-pill text-bg-info">Tutorial</span>',
            html=True,
        )

    def test_request_minutes(self):
        meeting = MeetingFactory(type_id='ietf')
        area = GroupFactory(type_id='area')
        has_minutes = SessionFactory(meeting=meeting,group__parent=area)
        has_no_minutes = SessionFactory(meeting=meeting,group__parent=area)
        SessionPresentation.objects.create(session=has_minutes,document=DocumentFactory(type_id='minutes'))

        empty_outbox()
        url = urlreverse('ietf.meeting.views.request_minutes',kwargs={'num':meeting.number})
        login_testing_unauthorized(self,"secretary",url)
        r = self.client.get(url)
        self.assertNotContains(r, has_minutes.group.acronym.upper())
        self.assertContains(r, has_no_minutes.group.acronym.upper())
        r = self.client.post(url,{'to':'wgchairs@ietf.org',
                                  'cc': 'irsg@irtf.org',
                                  'subject': 'I changed the subject',
                                  'body': 'corpus',
                                 })
        self.assertEqual(r.status_code,302)
        self.assertEqual(len(outbox),1)

class HasMeetingsTests(TestCase):
    settings_temp_path_overrides = TestCase.settings_temp_path_overrides + ['AGENDA_PATH']

    def do_request_interim(self, url, group, user, meeting_count):
        login_testing_unauthorized(self,user.username, url)
        r = self.client.get(url) 
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(q('#id_group option[value="%d"]'%group.pk))
        date = date_today() + datetime.timedelta(days=30+meeting_count)
        time = time_now().replace(microsecond=0,second=0)
        remote_instructions = 'Use webex'
        agenda = 'Intro. Slides. Discuss.'
        agenda_note = 'On second level'
        meeting_count = Meeting.objects.filter(number__contains='-%s-'%group.acronym, date__year=date.year).count()
        next_num = "%02d" % (meeting_count+1)
        data = {'group':group.pk,
                'meeting_type':'single',
                'city':'',
                'country':'',
                'time_zone':'UTC',
                'session_set-0-date':date.strftime("%Y-%m-%d"),
                'session_set-0-time':time.strftime('%H:%M'),
                'session_set-0-requested_duration':'03:00:00',
                'session_set-0-remote_instructions':remote_instructions,
                'session_set-0-agenda':agenda,
                'session_set-0-agenda_note':agenda_note,
                'session_set-TOTAL_FORMS':1,
                'session_set-INITIAL_FORMS':0,
                'session_set-MIN_NUM_FORMS':0,
                'session_set-MAX_NUM_FORMS':1000}

        empty_outbox()
        r = self.client.post(urlreverse("ietf.meeting.views.interim_request"),data)
        self.assertRedirects(r,urlreverse('ietf.meeting.views.upcoming'))
        meeting = Meeting.objects.order_by('id').last()
        self.assertEqual(meeting.type_id,'interim')
        self.assertEqual(meeting.date,date)
        self.assertEqual(meeting.number,'interim-%s-%s-%s' % (date.year, group.acronym, next_num))
        self.assertTrue(len(outbox)>0)
        self.assertIn('interim approved',outbox[0]["Subject"])
        self.assertIn(user.person.email().address,outbox[0]["To"])
        self.client.logout()


    def create_role_for_authrole(self, authrole):
        role = None
        if authrole == 'Secretariat':
            role = RoleFactory.create(group__acronym='secretariat',name_id='secr')
        elif authrole == 'Area Director':
            role = RoleFactory.create(name_id='ad', group__type_id='area')
        elif authrole == 'IAB':
            role = RoleFactory.create(name_id='member', group__acronym='iab')
        elif authrole == 'IRTF Chair':
            role = RoleFactory.create(name_id='chair', group__acronym='irtf')
        if role is None:
            self.assertIsNone("Can't test authrole:"+authrole)
        self.assertNotEqual(role, None)                       
        return role


    def test_can_request_interim(self):

        url = urlreverse('ietf.meeting.views.interim_request')
        for gf in GroupFeatures.objects.filter(has_meetings=True):
            meeting_count = 0
            for role in gf.groupman_roles:
                role = RoleFactory(group__type_id=gf.type_id, name_id=role)
                self.do_request_interim(url, role.group, role.person.user, meeting_count)
            for authrole in gf.groupman_authroles:
                group = GroupFactory(type_id=gf.type_id)
                role = self.create_role_for_authrole(authrole)
                self.do_request_interim(url, group, role.person.user, 0)


    def test_cannot_request_interim(self):

        url = urlreverse('ietf.meeting.views.interim_request')

        self.client.login(username='secretary', password='secretary+password')
        nomeetings = []
        for gf in GroupFeatures.objects.exclude(has_meetings=True):
            nomeetings.append(GroupFactory(type_id=gf.type_id))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        for group in nomeetings:
            self.assertFalse(q('#id_group option[value="%d"]'%group.pk))
        self.client.logout()

        all_role_names = set(RoleName.objects.values_list('slug',flat=True))
        for gf in GroupFeatures.objects.filter(has_meetings=True):
            for role_name in all_role_names - set(gf.groupman_roles):
                role = RoleFactory(group__type_id=gf.type_id,name_id=role_name)
                self.assertFalse(can_request_interim_meeting(role.person.user))

    def test_appears_on_upcoming(self):
        url = urlreverse('ietf.meeting.views.upcoming')
        sessions=[]
        for gf in GroupFeatures.objects.filter(has_meetings=True):
            session = SessionFactory(
                group__type_id = gf.type_id,
                meeting__type_id='interim', 
                meeting__date = timezone.now()+datetime.timedelta(days=30),
                status_id='sched',
            )
            sessions.append(session)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        for session in sessions:
            self.assertIn(session.meeting.number, q('.interim-meeting-link').text())


    def test_appears_on_pending(self):
        url = urlreverse('ietf.meeting.views.interim_pending')
        sessions=[]
        for gf in GroupFeatures.objects.filter(has_meetings=True):
            group = GroupFactory(type_id=gf.type_id)
            meeting_date = timezone.now() + datetime.timedelta(days=30)
            session = SessionFactory(
                group=group,
                meeting__type_id='interim', 
                meeting__date = meeting_date,
                meeting__number = 'interim-%d-%s-00'%(meeting_date.year,group.acronym),
                status_id='apprw',
            )
            sessions.append(session)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        for session in sessions:
            self.assertIn(session.meeting.number, q('.interim-meeting-link').text())


    def test_appears_on_announce(self):
        url = urlreverse('ietf.meeting.views.interim_announce')
        sessions=[]
        for gf in GroupFeatures.objects.filter(has_meetings=True):
            group = GroupFactory(type_id=gf.type_id)
            meeting_date = timezone.now() + datetime.timedelta(days=30)
            session = SessionFactory(
                group=group,
                meeting__type_id='interim', 
                meeting__date = meeting_date,
                meeting__number = 'interim-%d-%s-00'%(meeting_date.year,group.acronym),
                status_id='scheda',
            )
            sessions.append(session)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        for session in sessions:
            self.assertIn(session.meeting.number, q('.interim-meeting-link').text())


class AgendaFilterTests(TestCase):
    """Tests for the AgendaFilter template"""

    def test_agenda_filter_template(self):
        """Test rendering of input data by the agenda filter template"""
        def _assert_button_ok(btn, expected_label=None, expected_filter_item=None, 
                              expected_filter_keywords=None):
            """Test button properties"""
            if expected_label:
                self.assertIn(btn.text(), expected_label)
            self.assertEqual(btn.attr('data-filter-item'), expected_filter_item)
            self.assertEqual(btn.attr('data-filter-keywords'), expected_filter_keywords)

        template = Template('{% include "meeting/agenda_filter.html" %}')

        # Test with/without custom button text
        context = Context({'customize_button_text': None, 'filter_categories': []})
        q = PyQuery(template.render(context))
        self.assertIn('Customize...', q('h2.accordion-header').text())
        self.assertEqual(q('table'), [])  # no filter_categories, so no button table

        context['customize_button_text'] = 'My custom text...'
        q = PyQuery(template.render(context))
        self.assertIn(context['customize_button_text'], q('h2.accordion-header').text())
        self.assertEqual(q('table'), [])  # no filter_categories, so no button table
        
        # Now add a non-trivial set of filters
        context['filter_categories'] = [
            [  # first category
                dict(
                    label='area0',
                    keyword='keyword0',
                    children=[
                        dict(
                            label='child00',
                            keyword='keyword00',
                            toggled_by=['keyword0'],
                            is_bof=False,
                        ),
                        dict(
                            label='child01',
                            keyword='keyword01',
                            toggled_by=['keyword0', 'bof'],
                            is_bof=True,
                        ),
                    ]),
                dict(
                    label='area1',
                    keyword='keyword1',
                    children=[
                        dict(
                            label='child10',
                            keyword='keyword10',
                            toggled_by=['keyword1'],
                            is_bof=False,
                        ),
                        dict(
                            label='child11',
                            keyword='keyword11',
                            toggled_by=['keyword1', 'bof'],
                            is_bof=True,
                        ),
                    ]),
            ],
            [  # second category
                dict(
                    label='area2',
                    keyword='keyword2',
                    children=[
                        dict(
                            label='child20',
                            keyword='keyword20',
                            toggled_by=['keyword2', 'bof'],
                            is_bof=True,
                        ),
                        dict(
                            label='child21',
                            keyword='keyword21',
                            toggled_by=['keyword2'],
                            is_bof=False,
                        ),
                    ]),
            ],
            [  # third category
                dict(
                    label=None,
                    keyword=None,
                    children=[
                        dict(
                            label='child30',
                            keyword='keyword30',
                            toggled_by=[],
                            is_bof=False,
                        ),
                        dict(
                            label='child31',
                            keyword='keyword31',
                            toggled_by=['bof'],
                            is_bof=True,
                        ),
                    ]),
            ],
        ]

        q = PyQuery(template.render(context))
        self.assertIn(context['customize_button_text'], q('h2.accordion-header').text())
        self.assertNotEqual(q('button.pickview'), [])  # should now have group buttons
        
        # Check that buttons are present for the expected things
        header_row = q('.col-1 .row:first')
        self.assertEqual(len(header_row), 4)
        button_row = q('.row.view')
        self.assertEqual(len(button_row), 4)

        # verify correct headers
        header_cells = header_row('.row')
        self.assertEqual(len(header_cells), 4)
        header_buttons = header_cells('button.pickview')
        self.assertEqual(len(header_buttons), 3)  # last column has disabled header, so only 3
        
        # verify buttons
        button_cells = button_row('.btn-group-vertical')

        # area0
        _assert_button_ok(header_cells.eq(0)('button.keyword0'),
                          expected_label='area0',
                          expected_filter_item='keyword0')
        buttons = button_cells.eq(0)('button.pickview')
        self.assertEqual(len(buttons), 2)  # two children
        _assert_button_ok(buttons('.keyword00'),
                          expected_label='child00',
                          expected_filter_item='keyword00',
                          expected_filter_keywords='keyword0')
        _assert_button_ok(buttons('.keyword01'),
                          expected_label='child01',
                          expected_filter_item='keyword01',
                          expected_filter_keywords='keyword0,bof')

        # area1
        _assert_button_ok(header_cells.eq(1)('button.keyword1'),
                          expected_label='area1',
                          expected_filter_item='keyword1')

        buttons = button_cells.eq(1)('button.pickview')
        self.assertEqual(len(buttons), 2)  # two children
        _assert_button_ok(buttons('.keyword10'),
                          expected_label='child10',
                          expected_filter_item='keyword10',
                          expected_filter_keywords='keyword1')
        _assert_button_ok(buttons('.keyword11'),
                          expected_label='child11',
                          expected_filter_item='keyword11',
                          expected_filter_keywords='keyword1,bof')
        
        # area2
        _assert_button_ok(header_cells.eq(2)('button.keyword2'),
                          expected_label='area2',
                          expected_filter_item='keyword2')

        buttons = button_cells.eq(2)('button.pickview')
        self.assertEqual(len(buttons), 2)  # two children
        _assert_button_ok(buttons('.keyword20'),
                          expected_label='child20',
                          expected_filter_item='keyword20',
                          expected_filter_keywords='keyword2,bof')
        _assert_button_ok(buttons('.keyword21'),
                          expected_label='child21',
                          expected_filter_item='keyword21',
                          expected_filter_keywords='keyword2')

        # area3
        _assert_button_ok(header_cells.eq(3)('button.keyword2'),
                          expected_label=None,
                          expected_filter_item=None)
        buttons = button_cells.eq(3)('button.pickview')
        self.assertEqual(len(buttons), 2)  # two children
        _assert_button_ok(buttons('.keyword30'),
                          expected_label='child30',
                          expected_filter_item='keyword30',
                          expected_filter_keywords=None)
        _assert_button_ok(buttons('.keyword31'),
                          expected_label='child31',
                          expected_filter_item='keyword31',
                          expected_filter_keywords='bof')


def logo_file(width=128, height=128, format='PNG', ext=None):
    img = Image.new('RGB', (width, height))  # just a black image
    data = BytesIO()
    img.save(data, format=format)
    data.seek(0)
    data.name = f'logo.{ext if ext is not None else format.lower()}'
    return data


class MeetingHostTests(BaseMeetingTestCase):
    def _assertHostFieldCountGreaterEqual(self, r, min_count):
        q = PyQuery(r.content)
        self.assertGreaterEqual(
            len(q('input[type="text"][name^="meetinghosts-"][name$="-name"]')),
            min_count,
            f'Must have at least {min_count} host name field(s)',
        )
        self.assertGreaterEqual(
            len(q('input[type="file"][name^="meetinghosts-"][name$="-logo"]')),
            min_count,
            f'Must have at least {min_count} host logo field(s)',
        )

    def _create_first_host(self, meeting, logo, url):
        """Helper to create a first host via POST"""
        return self.client.post(
            url,
            {
                'meetinghosts-TOTAL_FORMS': '2',
                'meetinghosts-INITIAL_FORMS': '0',
                'meetinghosts-MIN_NUM_FORMS': '0',
                'meetinghosts-MAX_NUM_FORMS': '1000',
                'meetinghosts-0-id': '',
                'meetinghosts-0-meeting': str(meeting.pk),
                'meetinghosts-0-name': 'Some Sponsor, Inc.',
                'meetinghosts-0-logo': logo,
                'meetinghosts-1-id': '',
                'meetinghosts-1-meeting': str(meeting.pk),
                'meetinghosts-1-name': '',
            },
        )

    def test_permissions(self):
        meeting = MeetingFactory(type_id='ietf')
        url = urlreverse('ietf.meeting.views_proceedings.edit_meetinghosts', kwargs=dict(num=meeting.number))
        self.client.logout()
        login_testing_unauthorized(self, 'ad', url)
        login_testing_unauthorized(self, 'secretary', url)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        self.client.logout()
        login_testing_unauthorized(self, 'ad', url, method='post')
        login_testing_unauthorized(self, 'secretary', url, method='post')
        # don't bother checking a real post - it'll be tested in other methods

    def _assertMatch(self, value, pattern):
        self.assertIsNotNone(re.match(pattern, value))

    def test_add(self):
        """Can add a new meeting host"""
        meeting = MeetingFactory(type_id='ietf')
        url = urlreverse('ietf.meeting.views_proceedings.edit_meetinghosts', kwargs=dict(num=meeting.number))

        # get the edit page to check that it has the necessary fields
        self.client.login(username='secretary', password='secretary+password')
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self._assertHostFieldCountGreaterEqual(r, 1)

        # post our response
        logos = [logo_file() for _ in range(2)]
        r = self._create_first_host(meeting, logos[0], url)
        self.assertRedirects(r, urlreverse('ietf.meeting.views.materials', kwargs=dict(num=meeting.number)))
        self.assertEqual(meeting.meetinghosts.count(), 1)
        host = meeting.meetinghosts.first()
        self.assertEqual(host.name, 'Some Sponsor, Inc.')
        logo_filename = Path(host.logo.path)
        self._assertMatch(logo_filename.name, r'logo-[a-z]+.png')
        self.assertCountEqual(
            logo_filename.parent.iterdir(),
            [logo_filename],
            'Unexpected or missing files in the output directory',
        )

        # retrieve the page again to ensure we have more fields
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self._assertHostFieldCountGreaterEqual(r, 2)  # must have at least one extra

        # post our response to add an additional host
        r = self.client.post(
            url,
            {
                'meetinghosts-TOTAL_FORMS': '3',
                'meetinghosts-INITIAL_FORMS': '1',
                'meetinghosts-MIN_NUM_FORMS': '0',
                'meetinghosts-MAX_NUM_FORMS': '1000',
                'meetinghosts-0-id': str(host.pk),
                'meetinghosts-0-meeting': str(meeting.pk),
                'meetinghosts-0-name': 'Some Sponsor, Inc.',
                'meetinghosts-1-id':'',
                'meetinghosts-1-meeting': str(meeting.pk),
                'meetinghosts-1-name': 'Another Sponsor, Ltd.',
                'meetinghosts-1-logo': logos[1],
                'meetinghosts-2-id':'',
                'meetinghosts-2-meeting': str(meeting.pk),
                'meetinghosts-2-name': '',
            },
        )
        self.assertRedirects(r, urlreverse('ietf.meeting.views.materials', kwargs=dict(num=meeting.number)))
        self.assertEqual(meeting.meetinghosts.count(), 2)
        host = meeting.meetinghosts.first()
        self.assertEqual(host.name, 'Some Sponsor, Inc.')
        logo_filename = Path(host.logo.path)
        self._assertMatch(logo_filename.name, r'logo-[a-z]+.png')
        host = meeting.meetinghosts.last()
        self.assertEqual(host.name, 'Another Sponsor, Ltd.')
        logo2_filename = Path(host.logo.path)
        self._assertMatch(logo2_filename.name, r'logo-[a-z]+.png')
        self.assertCountEqual(
            logo_filename.parent.iterdir(),
            [logo_filename, logo2_filename],
            'Unexpected or missing files in the output directory',
        )

        # retrieve the page again to ensure we have yet more fields
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self._assertHostFieldCountGreaterEqual(r, 3)  # must have at least one extra

    def test_edit_name(self):
        """Can change name of meeting host

        The main complication is checking that the file has been
        renamed to match the new host name.
        """
        meeting = MeetingFactory(type_id='ietf')
        url = urlreverse('ietf.meeting.views_proceedings.edit_meetinghosts', kwargs=dict(num=meeting.number))

        # create via UI so we don't have to deal with creating storage paths
        self.client.login(username='secretary', password='secretary+password')
        logo = logo_file()
        r = self._create_first_host(meeting, logo, url)
        self.assertRedirects(r, urlreverse('ietf.meeting.views.materials', kwargs=dict(num=meeting.number)))
        self.assertEqual(meeting.meetinghosts.count(), 1)
        host = meeting.meetinghosts.first()
        self.assertEqual(host.name, 'Some Sponsor, Inc.')
        orig_logopath = Path(host.logo.path)
        self._assertMatch(orig_logopath.name, r'logo-[a-z]+.png')
        self.assertTrue(orig_logopath.exists())

        # post our response to modify the name
        r = self.client.post(
            url,
            {
                'meetinghosts-TOTAL_FORMS': '3',
                'meetinghosts-INITIAL_FORMS': '1',
                'meetinghosts-MIN_NUM_FORMS': '0',
                'meetinghosts-MAX_NUM_FORMS': '1000',
                'meetinghosts-0-id': str(host.pk),
                'meetinghosts-0-meeting': str(meeting.pk),
                'meetinghosts-0-name': 'Modified Sponsor, Inc.',
                'meetinghosts-1-id':'',
                'meetinghosts-1-meeting': str(meeting.pk),
                'meetinghosts-1-name': '',
                'meetinghosts-2-id':'',
                'meetinghosts-2-meeting': str(meeting.pk),
                'meetinghosts-2-name': '',
            },
        )
        self.assertRedirects(r, urlreverse('ietf.meeting.views.materials', kwargs=dict(num=meeting.number)))
        self.assertEqual(meeting.meetinghosts.count(), 1)
        host = meeting.meetinghosts.first()
        self.assertEqual(host.name, 'Modified Sponsor, Inc.')
        second_logopath = Path(host.logo.path)
        self.assertEqual(second_logopath, orig_logopath)
        self.assertTrue(second_logopath.exists())
        with second_logopath.open('rb') as f:
            self.assertEqual(f.read(), logo.getvalue())

    def test_meeting_host_replace_logo(self):
        """Can replace logo of a meeting host"""
        meeting = MeetingFactory(type_id='ietf')
        url = urlreverse('ietf.meeting.views_proceedings.edit_meetinghosts', kwargs=dict(num=meeting.number))

        # create via UI so we don't have to deal with creating storage paths
        self.client.login(username='secretary', password='secretary+password')
        logo = logo_file()
        r = self._create_first_host(meeting, logo, url)
        self.assertRedirects(r, urlreverse('ietf.meeting.views.materials', kwargs=dict(num=meeting.number)))
        self.assertEqual(meeting.meetinghosts.count(), 1)
        host = meeting.meetinghosts.first()
        self.assertEqual(host.name, 'Some Sponsor, Inc.')
        orig_logopath = Path(host.logo.path)
        self._assertMatch(orig_logopath.name, r'logo-[a-z]+.png')
        self.assertTrue(orig_logopath.exists())

        # post our response to replace the logo
        new_logo = logo_file(200, 200)  # different size to distinguish images
        r = self.client.post(
            url,
            {
                'meetinghosts-TOTAL_FORMS': '3',
                'meetinghosts-INITIAL_FORMS': '1',
                'meetinghosts-MIN_NUM_FORMS': '0',
                'meetinghosts-MAX_NUM_FORMS': '1000',
                'meetinghosts-0-id': str(host.pk),
                'meetinghosts-0-meeting': str(meeting.pk),
                'meetinghosts-0-name': 'Some Sponsor, Inc.',
                'meetinghosts-0-logo': new_logo,
                'meetinghosts-1-id':'',
                'meetinghosts-1-meeting': str(meeting.pk),
                'meetinghosts-1-name': '',
                'meetinghosts-2-id':'',
                'meetinghosts-2-meeting': str(meeting.pk),
                'meetinghosts-2-name': '',
            },
        )
        self.assertRedirects(r, urlreverse('ietf.meeting.views.materials', kwargs=dict(num=meeting.number)))
        self.assertEqual(meeting.meetinghosts.count(), 1)
        host = meeting.meetinghosts.first()
        self.assertEqual(host.name, 'Some Sponsor, Inc.')
        second_logopath = Path(host.logo.path)
        self._assertMatch(second_logopath.name, r'logo-[a-z]+.png')
        self.assertTrue(second_logopath.exists())
        with second_logopath.open('rb') as f:
            self.assertEqual(f.read(), new_logo.getvalue())

    def test_change_name_and_replace_logo(self):
        """Can simultaneously change name and replace logo"""
        meeting = MeetingFactory(type_id='ietf')
        url = urlreverse('ietf.meeting.views_proceedings.edit_meetinghosts', kwargs=dict(num=meeting.number))

        # create via UI so we don't have to deal with creating storage paths
        self.client.login(username='secretary', password='secretary+password')
        logo = logo_file()
        r = self._create_first_host(meeting, logo, url)
        self.assertRedirects(r, urlreverse('ietf.meeting.views.materials', kwargs=dict(num=meeting.number)))
        self.assertEqual(meeting.meetinghosts.count(), 1)
        host = meeting.meetinghosts.first()
        self.assertEqual(host.name, 'Some Sponsor, Inc.')
        orig_logopath = Path(host.logo.path)
        self._assertMatch(orig_logopath.name, r'logo-[a-z]+.png')
        self.assertTrue(orig_logopath.exists())

        # post our response to replace the logo
        new_logo = logo_file(200, 200)  # different size to distinguish images
        r = self.client.post(
            url,
            {
                'meetinghosts-TOTAL_FORMS': '3',
                'meetinghosts-INITIAL_FORMS': '1',
                'meetinghosts-MIN_NUM_FORMS': '0',
                'meetinghosts-MAX_NUM_FORMS': '1000',
                'meetinghosts-0-id': str(host.pk),
                'meetinghosts-0-meeting': str(meeting.pk),
                'meetinghosts-0-name': 'Modified Sponsor, Ltd.',
                'meetinghosts-0-logo': new_logo,
                'meetinghosts-1-id':'',
                'meetinghosts-1-meeting': str(meeting.pk),
                'meetinghosts-1-name': '',
                'meetinghosts-2-id':'',
                'meetinghosts-2-meeting': str(meeting.pk),
                'meetinghosts-2-name': '',
            },
        )
        self.assertRedirects(r, urlreverse('ietf.meeting.views.materials', kwargs=dict(num=meeting.number)))
        self.assertEqual(meeting.meetinghosts.count(), 1)
        host = meeting.meetinghosts.first()
        self.assertEqual(host.name, 'Modified Sponsor, Ltd.')
        second_logopath = Path(host.logo.path)
        self._assertMatch(second_logopath.name, r'logo-[a-z]+.png')
        self.assertTrue(second_logopath.exists())
        with second_logopath.open('rb') as f:
            self.assertEqual(f.read(), new_logo.getvalue())
        self.assertFalse(orig_logopath.exists())

    def test_remove(self):
        """Can delete a meeting host and its logo"""
        meeting = MeetingFactory(type_id='ietf')
        url = urlreverse('ietf.meeting.views_proceedings.edit_meetinghosts', kwargs=dict(num=meeting.number))

        # create via UI so we don't have to deal with creating storage paths
        self.client.login(username='secretary', password='secretary+password')
        logo = logo_file()
        r = self._create_first_host(meeting, logo, url)
        self.assertRedirects(r, urlreverse('ietf.meeting.views.materials', kwargs=dict(num=meeting.number)))
        self.assertEqual(meeting.meetinghosts.count(), 1)
        host = meeting.meetinghosts.first()
        self.assertEqual(host.name, 'Some Sponsor, Inc.')
        logopath = Path(host.logo.path)
        self._assertMatch(logopath.name, r'logo-[a-z]+.png')
        self.assertTrue(logopath.exists())

        # now delete
        r = self.client.post(
            url,
            {
                'meetinghosts-TOTAL_FORMS': '3',
                'meetinghosts-INITIAL_FORMS': '1',
                'meetinghosts-MIN_NUM_FORMS': '0',
                'meetinghosts-MAX_NUM_FORMS': '1000',
                'meetinghosts-0-id': str(host.pk),
                'meetinghosts-0-meeting': str(meeting.pk),
                'meetinghosts-0-name': 'Modified Sponsor, Ltd.',
                'meetinghosts-0-DELETE': 'on',
                'meetinghosts-1-id':'',
                'meetinghosts-1-meeting': str(meeting.pk),
                'meetinghosts-1-name': '',
                'meetinghosts-2-id':'',
                'meetinghosts-2-meeting': str(meeting.pk),
                'meetinghosts-2-name': '',
            },
        )
        self.assertRedirects(r, urlreverse('ietf.meeting.views.materials', kwargs=dict(num=meeting.number)))
        self.assertEqual(meeting.meetinghosts.count(), 0)
        self.assertFalse(logopath.exists())

    def test_remove_with_selected_logo(self):
        """Can delete a meeting host after selecting a replacement file"""
        meeting = MeetingFactory(type_id='ietf')
        url = urlreverse('ietf.meeting.views_proceedings.edit_meetinghosts', kwargs=dict(num=meeting.number))

        # create via UI so we don't have to deal with creating storage paths
        self.client.login(username='secretary', password='secretary+password')
        logo = logo_file()
        r = self._create_first_host(meeting, logo, url)
        self.assertRedirects(r, urlreverse('ietf.meeting.views.materials', kwargs=dict(num=meeting.number)))
        self.assertEqual(meeting.meetinghosts.count(), 1)
        host = meeting.meetinghosts.first()
        self.assertEqual(host.name, 'Some Sponsor, Inc.')
        logopath = Path(host.logo.path)
        self._assertMatch(logopath.name, r'logo-[a-z]+.png')
        self.assertTrue(logopath.exists())

        # now delete
        r = self.client.post(
            url,
            {
                'meetinghosts-TOTAL_FORMS': '3',
                'meetinghosts-INITIAL_FORMS': '1',
                'meetinghosts-MIN_NUM_FORMS': '0',
                'meetinghosts-MAX_NUM_FORMS': '1000',
                'meetinghosts-0-id': str(host.pk),
                'meetinghosts-0-meeting': str(meeting.pk),
                'meetinghosts-0-name': 'Modified Sponsor, Ltd.',
                'meetinghosts-0-DELETE': 'on',
                'meetinghosts-0-logo': logo_file(format='JPEG'),
                'meetinghosts-1-id':'',
                'meetinghosts-1-meeting': str(meeting.pk),
                'meetinghosts-1-name': '',
                'meetinghosts-2-id':'',
                'meetinghosts-2-meeting': str(meeting.pk),
                'meetinghosts-2-name': '',
            },
        )
        self.assertRedirects(r, urlreverse('ietf.meeting.views.materials', kwargs=dict(num=meeting.number)))
        self.assertEqual(meeting.meetinghosts.count(), 0)
        self.assertFalse(logopath.exists())

    def test_logo_types_checked(self):
        """Only allowed image types should be accepted"""
        allowed_formats = [('JPEG', 'jpg'), ('JPEG', 'jpeg'), ('PNG', 'png')]

        meeting = MeetingFactory(type_id='ietf')
        url = urlreverse('ietf.meeting.views_proceedings.edit_meetinghosts', kwargs=dict(num=meeting.number))
        self.client.login(username='secretary', password='secretary+password')

        junk = BytesIO()
        junk.write(b'this is not an image')
        junk.seek(0)
        r = self._create_first_host(meeting, junk, url)
        self.assertContains(r, 'Upload a valid image', status_code=200)
        self.assertEqual(meeting.meetinghosts.count(), 0)

        for fmt, ext in allowed_formats:
            r = self._create_first_host(
                meeting,
                logo_file(format=fmt, ext=ext),
                url
            )
            self.assertRedirects(r, urlreverse('ietf.meeting.views.materials', kwargs=dict(num=meeting.number)))
            self.assertEqual(meeting.meetinghosts.count(), 1)
            meeting.meetinghosts.all().delete()


# Keep these settings consistent with the assumptions in these tests
@override_settings(PROCEEDINGS_VERSION_CHANGES=[0, 97, 111])
class ProceedingsTests(BaseMeetingTestCase):
    """Tests related to meeting proceedings display

    Fills in all material types
    """
    def _create_proceedings_materials(self, meeting):
        """Create various types of proceedings materials for meeting"""
        MeetingHostFactory.create_batch(2, meeting=meeting)  # create a couple of meeting hosts/logos
        ProceedingsMaterialFactory(
            # default title, not removed
            meeting=meeting,
            type=ProceedingsMaterialTypeName.objects.get(slug='supporters')
        )
        ProceedingsMaterialFactory(
            # custom title, not removed
            meeting=meeting,
            type=ProceedingsMaterialTypeName.objects.get(slug='host_speaker_series'),
            document__title='Speakers'
        )
        ProceedingsMaterialFactory(
            # default title, removed
            meeting=meeting,
            type=ProceedingsMaterialTypeName.objects.get(slug='social_event'),
            document__states=[('procmaterials', 'removed')]
        )
        ProceedingsMaterialFactory(
            # custom title, removed
            meeting=meeting,
            type=ProceedingsMaterialTypeName.objects.get(slug='additional_information'),
            document__title='Party', document__states=[('procmaterials', 'removed')]
        )
        ProceedingsMaterialFactory(
            # url
            meeting=meeting,
            type=ProceedingsMaterialTypeName.objects.get(slug='wiki'),
            document__external_url='https://example.com/wiki'
        )

    @staticmethod
    def _proceedings_file():
        """Get a file containing content suitable for a proceedings document

        Currently returns the same file every time.
        """
        path = Path(settings.BASE_DIR) / 'meeting/test_procmat.pdf'
        return path.open('rb')

    def _assertMeetingHostsDisplayed(self, response, meeting):
        pq = PyQuery(response.content)
        host_divs = pq('div.host-logo')
        self.assertEqual(len(host_divs), meeting.meetinghosts.count(), 'Should have a logo for every meeting host')
        self.assertEqual(
            [(img.attr('title'), img.attr('src')) for img in host_divs.items('img')],
            [
                (host.name,
                 urlreverse(
                     'ietf.meeting.views_proceedings.meetinghost_logo',
                     kwargs=dict(num=meeting.number, host_id=host.pk),
                 ))
                for host in meeting.meetinghosts.all()
            ],
            'Correct image and name for each host should appear in the correct order'
        )

    def _assertProceedingsMaterialsDisplayed(self, response, meeting):
        """Checks that all (and only) active materials are linked with correct href and title"""
        expected_materials = [
            m for m in meeting.proceedings_materials.order_by('type__order') if m.active()
        ]
        pq = PyQuery(response.content)
        links = pq('div.proceedings-material a')
        self.assertEqual(len(links), len(expected_materials), 'Should have an entry for each active ProceedingsMaterial')
        self.assertEqual(
            [(link.eq(0).text(), link.eq(0).attr('href')) for link in links.items()],
            [(str(pm), pm.get_href()) for pm in expected_materials],
            'Correct title and link for each ProceedingsMaterial should appear in the correct order'
        )

    def _assertGroupSessions(self, response, meeting):
        """Checks that group/sessions are present"""
        pq = PyQuery(response.content)
        sections = ["plenaries", "gen", "iab", "editorial", "irtf", "training"]
        for section in sections:
            self.assertEqual(len(pq(f"#{section}")), 1, f"{section} section should exists in proceedings")

    def test_proceedings(self):
        """Proceedings should be displayed correctly

        Currently only tests that the view responds with a 200 response code and checks the ProceedingsMaterials
        at the top of the proceedings. Ought to actually test the display of the individual group/session
        materials as well.
        """
        meeting = make_meeting_test_data(meeting=MeetingFactory(type_id='ietf', number='100'))
        session = Session.objects.filter(meeting=meeting, group__acronym="mars").first()
        GroupEventFactory(group=session.group,type='status_update')
        SessionPresentationFactory(document__type_id='recording',session=session)
        SessionPresentationFactory(document__type_id='recording',session=session,document__title="Audio recording for tests")

        # Add various group sessions
        groups = []
        parent_groups = [
                GroupFactory.create(type_id="area", acronym="gen"),
                GroupFactory.create(acronym="iab"),
                GroupFactory.create(acronym="irtf"),
                ]
        for parent in parent_groups:
            groups.append(GroupFactory.create(parent=parent))
        for acronym in ["rsab", "edu"]:
            groups.append(GroupFactory.create(acronym=acronym))
        for group in groups:
            SessionFactory(meeting=meeting, group=group)

        self.write_materials_files(meeting, session)
        self._create_proceedings_materials(meeting)

        url = urlreverse("ietf.meeting.views.proceedings", kwargs=dict(num=meeting.number))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        if len(meeting.city) > 0:
            self.assertContains(r, meeting.city)
        if len(meeting.venue_name) > 0:
            self.assertContains(r, meeting.venue_name)

        # standard items on every proceedings
        pq = PyQuery(r.content)
        self.assertNotEqual(
            pq('a[href="{}"]'.format(
                urlreverse('ietf.meeting.views.proceedings_overview', kwargs=dict(num=meeting.number)))
            ),
            [],
            'Should have a link to IETF overview',
        )
        self.assertNotEqual(
            pq('a[href="{}"]'.format(
                urlreverse('ietf.meeting.views.proceedings_attendees', kwargs=dict(num=meeting.number)))
            ),
            [],
            'Should have a link to attendees',
        )
        self.assertNotEqual(
            pq('a[href="{}"]'.format(
                urlreverse('ietf.meeting.views.proceedings_activity_report', kwargs=dict(num=meeting.number)))
            ),
            [],
            'Should have a link to activity report',
        )
        self.assertNotEqual(
            pq('a[href="{}"]'.format(
                urlreverse('ietf.meeting.views.important_dates', kwargs=dict(num=meeting.number)))
            ),
            [],
            'Should have a link to important dates',
        )

        # configurable contents
        self._assertMeetingHostsDisplayed(r, meeting)
        self._assertProceedingsMaterialsDisplayed(r, meeting)
        self._assertGroupSessions(r, meeting)

    def test_named_session(self):
        """Session with a name should appear separately in the proceedings"""
        meeting = MeetingFactory(type_id='ietf', number='100', proceedings_final=True)
        group = GroupFactory()
        plain_session = SessionFactory(meeting=meeting, group=group)
        named_session = SessionFactory(meeting=meeting, group=group, name='I Got a Name')
        for doc_type_id in ('agenda', 'minutes', 'bluesheets', 'recording', 'slides', 'draft'):
            # Set up sessions materials that will have distinct URLs for each session.
            # This depends on settings.MEETING_DOC_HREFS and may need updating if that changes.
            SessionPresentationFactory(
                session=plain_session,
                document__type_id=doc_type_id,
                document__uploaded_filename=f'upload-{doc_type_id}-plain',
                document__external_url=f'external_url-{doc_type_id}-plain',
            )
            SessionPresentationFactory(
                session=named_session,
                document__type_id=doc_type_id,
                document__uploaded_filename=f'upload-{doc_type_id}-named',
                document__external_url=f'external_url-{doc_type_id}-named',
            )

        url = urlreverse('ietf.meeting.views.proceedings', kwargs={'num': meeting.number})
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)

        plain_label = q(f'div#{group.acronym}')
        self.assertEqual(plain_label.text(), group.acronym)
        plain_row = plain_label.closest('tr')
        self.assertTrue(plain_row)

        named_label = q(f'div#{slugify(named_session.name)}')
        self.assertEqual(named_label.text(), named_session.name)
        named_row = named_label.closest('tr')
        self.assertTrue(named_row)

        for material in (sp.document for sp in plain_session.presentations.all()):
            if material.type_id == 'draft':
                expected_url = urlreverse(
                    'ietf.doc.views_doc.document_main',
                    kwargs={'name': material.name},
                )
            else:
                expected_url = material.get_href(meeting)
            self.assertTrue(plain_row.find(f'a[href="{expected_url}"]'))
            self.assertFalse(named_row.find(f'a[href="{expected_url}"]'))

        for material in (sp.document for sp in named_session.presentations.all()):
            if material.type_id == 'draft':
                expected_url = urlreverse(
                    'ietf.doc.views_doc.document_main',
                    kwargs={'name': material.name},
                )
            else:
                expected_url = material.get_href(meeting)
            self.assertFalse(plain_row.find(f'a[href="{expected_url}"]'))
            self.assertTrue(named_row.find(f'a[href="{expected_url}"]'))

    def test_proceedings_no_agenda(self):
        # Meeting number must be larger than the last special-cased proceedings (currently 96)
        meeting = MeetingFactory(type_id='ietf',populate_schedule=False,date=date_today(), number='100')
        url = urlreverse('ietf.meeting.views.proceedings')
        r = self.client.get(url)
        self.assertRedirects(r, urlreverse('ietf.meeting.views.materials'))
        url = urlreverse('ietf.meeting.views.proceedings', kwargs=dict(num=meeting.number))
        r = self.client.get(url)
        self.assertRedirects(r, urlreverse('ietf.meeting.views.materials', kwargs=dict(num=meeting.number)))

    def test_proceedings_acknowledgements(self):
        make_meeting_test_data()
        meeting = MeetingFactory(type_id='ietf', date=datetime.date(2016,7,14), number="97")
        meeting.acknowledgements = 'test acknowledgements'
        meeting.save()
        url = urlreverse('ietf.meeting.views.proceedings_acknowledgements',kwargs={'num':meeting.number})
        response = self.client.get(url)
        self.assertContains(response, 'test acknowledgements')

    def test_proceedings_acknowledgements_link(self):
        """Link to proceedings_acknowledgements view should not appear for 'new' meetings

        With the PROCEEDINGS_VERSION_CHANGES settings value used here, expect the proceedings_acknowledgements
        view to be linked for meetings 95-110.
        """
        meeting_with_acks = MeetingFactory(type_id='ietf', date=datetime.date(2020,7,25), number='108')
        SessionFactory(meeting=meeting_with_acks)  # make sure meeting has a scheduled session
        meeting_with_acks.acknowledgements = 'these acknowledgements should appear'
        meeting_with_acks.save()
        url = urlreverse('ietf.meeting.views.proceedings',kwargs={'num':meeting_with_acks.number})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        q = PyQuery(response.content)
        self.assertEqual(
            len(q('a[href="{}"]'.format(
                urlreverse('ietf.meeting.views.proceedings_acknowledgements',
                           kwargs={'num':meeting_with_acks.number})
            ))),
            1,
        )

        meeting_without_acks = MeetingFactory(type_id='ietf', date=datetime.date(2022,7,25), number='113')
        SessionFactory(meeting=meeting_without_acks)  # make sure meeting has a scheduled session
        meeting_without_acks.acknowledgements = 'these acknowledgements should not appear'
        meeting_without_acks.save()
        url = urlreverse('ietf.meeting.views.proceedings',kwargs={'num':meeting_without_acks.number})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        q = PyQuery(response.content)
        self.assertEqual(
            len(q('a[href="{}"]'.format(
                urlreverse('ietf.meeting.views.proceedings_acknowledgements',
                           kwargs={'num':meeting_without_acks.number})
            ))),
            0,
        )

    def test_proceedings_attendees(self):
        """Test proceedings attendee list. Check the following:
           - assert onsite checkedin=True appears, not onsite checkedin=False
           - assert remote attended appears, not remote not attended
           - prefer onsite checkedin=True to remote attended when same person has both
        """

        meeting = MeetingFactory(type_id='ietf', date=datetime.date(2023, 11, 4), number="118")
        person_a = PersonFactory(name='Person A')
        person_b = PersonFactory(name='Person B')
        person_c = PersonFactory(name='Person C')
        person_d = PersonFactory(name='Person D')
        MeetingRegistrationFactory(meeting=meeting, person=person_a, reg_type='onsite', checkedin=True)
        MeetingRegistrationFactory(meeting=meeting, person=person_b, reg_type='onsite', checkedin=False)
        MeetingRegistrationFactory(meeting=meeting, person=person_a, reg_type='remote')
        AttendedFactory(session__meeting=meeting, session__type_id='plenary', person=person_a)
        MeetingRegistrationFactory(meeting=meeting, person=person_c, reg_type='remote')
        AttendedFactory(session__meeting=meeting, session__type_id='plenary', person=person_c)
        MeetingRegistrationFactory(meeting=meeting, person=person_d, reg_type='remote')
        url = urlreverse('ietf.meeting.views.proceedings_attendees',kwargs={'num': 118})
        response = self.client.get(url)
        self.assertContains(response, 'Attendee list')
        q = PyQuery(response.content)
        self.assertEqual(2, len(q("#id_attendees tbody tr")))
        text = q('#id_attendees tbody tr').text().replace('\n', ' ')
        self.assertEqual(text, "A Person onsite C Person remote")

    def test_proceedings_overview(self):
        '''Test proceedings IETF Overview page.
        Note: old meetings aren't supported so need to add a new meeting then test.
        '''
        meeting = make_meeting_test_data(meeting=MeetingFactory(type_id='ietf', date=datetime.date(2016,7,14), number="97"))

        # finalize meeting
        url = urlreverse('ietf.meeting.views.finalize_proceedings',kwargs={'num':meeting.number})
        login_testing_unauthorized(self,"secretary",url)
        r = self.client.post(url,{'finalize':1})
        self.assertEqual(r.status_code, 302)

        url = urlreverse('ietf.meeting.views.proceedings_overview',kwargs={'num':97})
        response = self.client.get(url)
        self.assertContains(response, 'The Internet Engineering Task Force')

    def test_proceedings_activity_report(self):
        make_meeting_test_data()
        MeetingFactory(type_id='ietf', date=datetime.date(2016,4,3), number="96")
        MeetingFactory(type_id='ietf', date=datetime.date(2016,7,14), number="97")

        url = urlreverse('ietf.meeting.views.proceedings_activity_report',kwargs={'num':97})
        response = self.client.get(url)
        self.assertContains(response, 'Activity Report')

    def test_feed(self):
        meeting = make_meeting_test_data()
        session = Session.objects.filter(meeting=meeting, group__acronym="mars").first()

        r = self.client.get("/feed/wg-proceedings/")
        self.assertContains(r, "agenda")
        self.assertContains(r, session.group.acronym)

    def _procmat_test_meeting(self):
        """Generate a meeting for proceedings material test"""
        # meeting number 123 avoids various legacy cases that affect these tests
        # (as of Aug 2021, anything above 96 is probably ok)
        return MeetingFactory(type_id='ietf', number='123', date=date_today())

    def _secretary_only_permission_test(self, url, include_post=True):
        self.client.logout()
        login_testing_unauthorized(self, 'ad', url)
        login_testing_unauthorized(self, 'secretary', url)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        if include_post:
            self.client.logout()
            login_testing_unauthorized(self, 'ad', url, method='post')
            login_testing_unauthorized(self, 'secretary', url, method='post')
            # don't bother checking a real post - it'll be tested in other methods

    def test_material_management_permissions(self):
        """Only the secreatariat should be able to manage proceedings materials"""
        meeting = self._procmat_test_meeting()
        # test all materials types in case they wind up treated differently
        # (unlikely, but more likely than an unwieldy number of types are introduced)
        for mat_type in ProceedingsMaterialTypeName.objects.filter(used=True):
            self._secretary_only_permission_test(
                urlreverse(
                    'ietf.meeting.views_proceedings.material_details',
                    kwargs=dict(num=meeting.number),
                ))
            self._secretary_only_permission_test(
                urlreverse(
                    'ietf.meeting.views_proceedings.upload_material',
                    kwargs=dict(num=meeting.number, material_type=mat_type.slug),
                ))

            # remaining tests need material to exist, so create
            ProceedingsMaterialFactory(meeting=meeting, type=mat_type)
            self._secretary_only_permission_test(
                urlreverse(
                    'ietf.meeting.views_proceedings.edit_material',
                    kwargs=dict(num=meeting.number, material_type=mat_type.slug),
                ))
            self._secretary_only_permission_test(
                urlreverse(
                    'ietf.meeting.views_proceedings.remove_material',
                    kwargs=dict(num=meeting.number, material_type=mat_type.slug),
                ))
            # it's ok to use active materials for restore test - no restore is actually issued
            self._secretary_only_permission_test(
                urlreverse(
                    'ietf.meeting.views_proceedings.restore_material',
                    kwargs=dict(num=meeting.number, material_type=mat_type.slug),
                ))

    def test_proceedings_material_details(self):
        """Material details page should correctly show materials"""
        meeting = self._procmat_test_meeting()
        url = urlreverse('ietf.meeting.views_proceedings.material_details', kwargs=dict(num=meeting.number))
        self.client.login(username='secretary', password='secretary+password')
        procmat_types = ProceedingsMaterialTypeName.objects.filter(used=True)

        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        pq = PyQuery(r.content)
        body_rows = pq('tbody > tr')
        self.assertEqual(len(body_rows), procmat_types.count())
        for row, mat_type in zip(body_rows.items(), procmat_types.all()):
            cells = row.find('td')
            # no materials, so rows should be empty except for label and 'Add' button
            self.assertEqual(len(cells), 3)  # label, blank, buttons
            self.assertEqual(cells.eq(0).text(), str(mat_type), 'First column should be material type name')
            self.assertEqual(cells.eq(1).text(), '', 'Second column should be empty')
            add_url = urlreverse('ietf.meeting.views_proceedings.upload_material',
                                 kwargs=dict(num=meeting.number, material_type=mat_type.slug))
            self.assertEqual(len(cells.eq(2).find(f'a[href="{add_url}"]')), 1, 'Third column should have Add link')

        self._create_proceedings_materials(meeting)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        pq = PyQuery(r.content)
        body_rows = pq('tbody > tr')
        self.assertEqual(len(body_rows), procmat_types.count())
        # n.b., this loop is over materials, not the type names!
        for row, mat in zip(body_rows.items(), meeting.proceedings_materials.order_by('type__order')):
            add_url = urlreverse('ietf.meeting.views_proceedings.upload_material',
                                 kwargs=dict(num=meeting.number, material_type=mat.type.slug))
            edit_url = urlreverse('ietf.meeting.views_proceedings.upload_material',
                                  kwargs=dict(num=meeting.number, material_type=mat.type.slug))
            remove_url = urlreverse('ietf.meeting.views_proceedings.upload_material',
                                    kwargs=dict(num=meeting.number, material_type=mat.type.slug))
            restore_url = urlreverse('ietf.meeting.views_proceedings.upload_material',
                                     kwargs=dict(num=meeting.number, material_type=mat.type.slug))
            cells = row.find('td')
            # no materials, so rows should be empty except for label and 'Add' button
            self.assertEqual(cells.eq(0).text(), str(mat.type), 'First column should be material type name')
            if mat.active():
                self.assertEqual(len(cells), 5)  # label, title, doc, updated, buttons
                self.assertEqual(cells.eq(1).text(), str(mat), 'Second column should be active material title')
                self.assertEqual(
                    cells.eq(2).text(),
                    '{} ({})'.format(
                        str(mat.document),
                        'external URL' if mat.document.external_url else 'uploaded file',
                    ))
                mod_time = mat.document.time.astimezone(pytz.utc)
                c3text = cells.eq(3).text()
                self.assertIn(mod_time.strftime('%Y-%m-%d'), c3text, 'Updated date incorrect')
                self.assertIn(mod_time.strftime('%H:%M:%S'), c3text, 'Updated time incorrect')
                self.assertEqual(len(cells.eq(4).find(f'a[href="{add_url}"]')), 1,
                                 'Fourth column should have a Replace link')
                self.assertEqual(len(cells.eq(4).find(f'a[href="{edit_url}"]')), 1,
                                 'Fourth column should have an Edit link')
                self.assertEqual(len(cells.eq(4).find(f'a[href="{remove_url}"]')), 1,
                                 'Fourth column should have a Remove link')
            else:
                self.assertEqual(len(cells), 3)  # label, blank, buttons
                self.assertEqual(cells.eq(0).text(), str(mat.type), 'First column should be material type name')
                self.assertEqual(cells.eq(1).text(), '', 'Second column should be empty')
                add_url = urlreverse('ietf.meeting.views_proceedings.upload_material',
                                     kwargs=dict(num=meeting.number, material_type=mat.type.slug))
                self.assertEqual(len(cells.eq(2).find(f'a[href="{add_url}"]')), 1,
                                 'Third column should have Add link')
                self.assertEqual(len(cells.eq(2).find(f'a[href="{restore_url}"]')), 1,
                                 'Third column should have Restore link')

    def upload_proceedings_material_test(self, meeting, mat_type, post_data):
        """Test the upload_proceedings view using provided POST data"""
        url = urlreverse(
            'ietf.meeting.views_proceedings.upload_material',
            kwargs=dict(num=meeting.number, material_type=mat_type.slug),
        )
        self.client.login(username='secretary', password='secretary+password')
        mats_before = [m.pk for m in meeting.proceedings_materials.all()]
        r = self.client.post(url, post_data)
        self.assertRedirects(
            r,
            urlreverse('ietf.meeting.views_proceedings.material_details',
                       kwargs=dict(num=meeting.number)),
        )

        self.assertEqual(meeting.proceedings_materials.count(), len(mats_before) + 1)
        mat = meeting.proceedings_materials.exclude(pk__in=mats_before).first()
        self.assertEqual(mat.type, mat_type)
        self.assertEqual(str(mat), mat_type.name)
        self.assertEqual(mat.document.rev, '00')
        return mat

    # use a simple and predictable href format for this test
    @override_settings(MEETING_DOC_HREFS={'procmaterials': '{doc.name}:{doc.rev}'})
    def test_add_proceedings_material_doc(self):
        """Upload proceedings materials document"""
        meeting = self._procmat_test_meeting()
        for mat_type in ProceedingsMaterialTypeName.objects.filter(used=True):
            with self._proceedings_file() as fd:
                mat = self.upload_proceedings_material_test(
                    meeting,
                    mat_type,
                    {'file': fd, 'external_url': ''},
                )
                self.assertEqual(mat.get_href(), f'{mat.document.name}:00')

    def test_add_proceedings_material_doc_invalid_ext(self):
        """Upload proceedings materials document with disallowed extension"""
        meeting = self._procmat_test_meeting()
        self.client.login(username='secretary', password='secretary+password')
        with NamedTemporaryFile('w+', suffix='.png') as invalid_file:
            invalid_file.write('this is not a PDF file!!')
            for mat_type in ProceedingsMaterialTypeName.objects.filter(used=True):
                url = urlreverse(
                    'ietf.meeting.views_proceedings.upload_material',
                    kwargs=dict(num=meeting.number, material_type=mat_type.slug),
                )
                invalid_file.seek(0)  # read the file contents again
                r = self.client.post(url, {'file': invalid_file, 'external_url': ''})
                self.assertEqual(r.status_code, 200)
                self.assertFormError(r.context["form"], 'file', 'Found an unexpected extension: .png.  Expected one of .pdf')

    def test_add_proceedings_material_doc_empty(self):
        """Upload proceedings materials document without specifying a file"""
        meeting = self._procmat_test_meeting()
        self.client.login(username='secretary', password='secretary+password')
        for mat_type in ProceedingsMaterialTypeName.objects.filter(used=True):
            url = urlreverse(
                'ietf.meeting.views_proceedings.upload_material',
                kwargs=dict(num=meeting.number, material_type=mat_type.slug),
            )
            r = self.client.post(url, {'external_url': ''})
            self.assertEqual(r.status_code, 200)
            self.assertFormError(r.context["form"], 'file', 'This field is required')

    def test_add_proceedings_material_url(self):
        """Add a URL as proceedings material"""
        meeting = self._procmat_test_meeting()
        for mat_type in ProceedingsMaterialTypeName.objects.filter(used=True):
            mat = self.upload_proceedings_material_test(
                meeting,
                mat_type,
                {'use_url': 'on', 'external_url': 'https://example.com'},
            )
            self.assertEqual(mat.get_href(), 'https://example.com')

    def test_add_proceedings_material_url_invalid(self):
        """Add proceedings materials URL with a non-URL value"""
        meeting = self._procmat_test_meeting()
        self.client.login(username='secretary', password='secretary+password')
        for mat_type in ProceedingsMaterialTypeName.objects.filter(used=True):
            url = urlreverse(
                'ietf.meeting.views_proceedings.upload_material',
                kwargs=dict(num=meeting.number, material_type=mat_type.slug),
            )
            r = self.client.post(url, {'use_url': 'on', 'external_url': "Ceci n'est pas une URL"})
            self.assertEqual(r.status_code, 200)
            self.assertFormError(r.context["form"], 'external_url', 'Enter a valid URL.')

    def test_add_proceedings_material_url_empty(self):
        """Add proceedings materials URL without specifying the URL"""
        meeting = self._procmat_test_meeting()
        self.client.login(username='secretary', password='secretary+password')
        for mat_type in ProceedingsMaterialTypeName.objects.filter(used=True):
            url = urlreverse(
                'ietf.meeting.views_proceedings.upload_material',
                kwargs=dict(num=meeting.number, material_type=mat_type.slug),
            )
            r = self.client.post(url, {'use_url': 'on', 'external_url': ''})
            self.assertEqual(r.status_code, 200)
            self.assertFormError(r.context["form"], 'external_url', 'This field is required')

    @override_settings(MEETING_DOC_HREFS={'procmaterials': '{doc.name}:{doc.rev}'})
    def test_replace_proceedings_material(self):
        """Replace uploaded document with new uploaded document"""
        # Set up a meeting with a proceedings material in place
        meeting = self._procmat_test_meeting()
        pm_doc = ProceedingsMaterialFactory(meeting=meeting)
        with self._proceedings_file() as f:
            self.write_materials_file(meeting, pm_doc.document, f.read())
        pm_url = ProceedingsMaterialFactory(meeting=meeting, document__external_url='https://example.com/first')
        success_url = urlreverse('ietf.meeting.views_proceedings.material_details', kwargs=dict(num=meeting.number))
        self.assertNotEqual(pm_doc.type, pm_url.type)
        self.assertEqual(meeting.proceedings_materials.count(), 2)

        # Replace the uploaded document with another uploaded document
        pm_doc_url = urlreverse(
            'ietf.meeting.views_proceedings.upload_material',
            kwargs=dict(num=meeting.number, material_type=pm_doc.type.slug),
        )
        self.client.login(username='secretary', password='secretary+password')
        with self._proceedings_file() as fd:
            r = self.client.post(pm_doc_url, {'file': fd, 'external_url': ''})
            self.assertRedirects(r, success_url)
            self.assertEqual(meeting.proceedings_materials.count(), 2)
            pm_doc = meeting.proceedings_materials.get(pk=pm_doc.pk)  # refresh from DB
            self.assertEqual(pm_doc.document.rev, '01')
            self.assertEqual(pm_doc.get_href(), f'{pm_doc.document.name}:01')

        # Replace the uploaded document with a URL
        r = self.client.post(pm_doc_url, {'use_url': 'on', 'external_url': 'https://example.com/second'})
        self.assertRedirects(r, success_url)
        self.assertEqual(meeting.proceedings_materials.count(), 2)
        pm_doc = meeting.proceedings_materials.get(pk=pm_doc.pk)  # refresh from DB
        self.assertEqual(pm_doc.document.rev, '02')
        self.assertEqual(pm_doc.get_href(), 'https://example.com/second')

        # Now replace the URL doc with another URL
        pm_url_url = urlreverse(
            'ietf.meeting.views_proceedings.upload_material',
            kwargs=dict(num=meeting.number, material_type=pm_url.type.slug),
        )
        r = self.client.post(pm_url_url, {'use_url': 'on', 'external_url': 'https://example.com/third'})
        self.assertRedirects(r, success_url)
        self.assertEqual(meeting.proceedings_materials.count(), 2)
        pm_url = meeting.proceedings_materials.get(pk=pm_url.pk)  # refresh from DB
        self.assertEqual(pm_url.document.rev, '01')
        self.assertEqual(pm_url.get_href(), 'https://example.com/third')

        # Now replace the URL doc with an uploaded file
        with self._proceedings_file() as fd:
            r = self.client.post(pm_url_url, {'file': fd, 'external_url': ''})
            self.assertRedirects(r, success_url)
            self.assertEqual(meeting.proceedings_materials.count(), 2)
            pm_url = meeting.proceedings_materials.get(pk=pm_url.pk)  # refresh from DB
            self.assertEqual(pm_url.document.rev, '02')
            self.assertEqual(pm_url.get_href(), f'{pm_url.document.name}:02')

    def test_remove_proceedings_material(self):
        """Proceedings material can be removed"""
        meeting = self._procmat_test_meeting()
        pm = ProceedingsMaterialFactory(meeting=meeting)

        self.assertEqual(pm.active(), True)

        url = urlreverse(
            'ietf.meeting.views_proceedings.remove_material',
            kwargs=dict(num=meeting.number, material_type=pm.type.slug),
        )
        self.client.login(username='secretary', password='secretary+password')
        r = self.client.post(url)
        self.assertRedirects(
            r,
            urlreverse('ietf.meeting.views_proceedings.material_details',
                       kwargs=dict(num=meeting.number)),
        )
        pm = meeting.proceedings_materials.get(pk=pm.pk)
        self.assertEqual(pm.active(), False)

    def test_restore_proceedings_material(self):
        """Proceedings material can be removed"""
        meeting = self._procmat_test_meeting()
        pm = ProceedingsMaterialFactory(meeting=meeting, document__states=[('procmaterials', 'removed')])

        self.assertEqual(pm.active(), False)

        url = urlreverse(
            'ietf.meeting.views_proceedings.restore_material',
            kwargs=dict(num=meeting.number, material_type=pm.type.slug),
        )
        self.client.login(username='secretary', password='secretary+password')
        r = self.client.post(url)
        self.assertRedirects(
            r,
            urlreverse('ietf.meeting.views_proceedings.material_details',
                       kwargs=dict(num=meeting.number)),
        )
        pm = meeting.proceedings_materials.get(pk=pm.pk)
        self.assertEqual(pm.active(), True)

    def test_rename_proceedings_material(self):
        """Proceedings material can be renamed"""
        meeting = self._procmat_test_meeting()
        pm = ProceedingsMaterialFactory(meeting=meeting)
        self.assertEqual(str(pm), pm.type.name)
        orig_rev = pm.document.rev
        url = urlreverse(
            'ietf.meeting.views_proceedings.edit_material',
            kwargs=dict(num=meeting.number, material_type=pm.type.slug),
        )
        self.client.login(username='secretary', password='secretary+password')
        r = self.client.post(url, {'title': 'This Is Not the Default Name'})
        self.assertRedirects(
            r,
            urlreverse('ietf.meeting.views_proceedings.material_details',
                       kwargs=dict(num=meeting.number)),
        )
        pm = meeting.proceedings_materials.get(pk=pm.pk)
        self.assertEqual(str(pm), 'This Is Not the Default Name')
        self.assertEqual(pm.document.rev, orig_rev, 'Renaming should not change document revision')

    def test_create_recording(self):
        session = SessionFactory(meeting__type_id='ietf', meeting__number=72, group__acronym='mars')
        filename = 'ietf42-testroomt-20000101-0800.mp3'
        url = settings.IETF_AUDIO_URL + 'ietf{}/{}'.format(session.meeting.number, filename)
        doc = create_recording(session, url)
        self.assertEqual(doc.name,'recording-72-mars-1')
        self.assertEqual(doc.group,session.group)
        self.assertEqual(doc.external_url,url)
        self.assertTrue(doc in session.materials.all())

    def test_get_next_sequence(self):
        session = SessionFactory(meeting__type_id='ietf', meeting__number=72, group__acronym='mars')
        meeting = session.meeting
        group = session.group
        sequence = get_next_sequence(group,meeting,'recording')
        self.assertEqual(sequence,1)

    def test_participants_for_meeting(self):
        person_a = PersonFactory()
        person_b = PersonFactory()
        person_c = PersonFactory()
        person_d = PersonFactory()
        m = MeetingFactory.create(type_id='ietf')
        MeetingRegistrationFactory(meeting=m, person=person_a, reg_type='onsite', checkedin=True)
        MeetingRegistrationFactory(meeting=m, person=person_b, reg_type='onsite', checkedin=False)
        MeetingRegistrationFactory(meeting=m, person=person_c, reg_type='remote')
        MeetingRegistrationFactory(meeting=m, person=person_d, reg_type='remote')
        AttendedFactory(session__meeting=m, session__type_id='plenary', person=person_c)
        checked_in, attended = participants_for_meeting(m)
        self.assertTrue(person_a.pk in checked_in)
        self.assertTrue(person_b.pk not in checked_in)
        self.assertTrue(person_c.pk in attended)
        self.assertTrue(person_d.pk not in attended)

    def test_session_attendance(self):
        meeting = MeetingFactory(type_id='ietf', date=datetime.date(2023, 11, 4), number='118')
        make_meeting_test_data(meeting=meeting)
        session = Session.objects.filter(meeting=meeting, group__acronym='mars').first()
        regs = MeetingRegistrationFactory.create_batch(3, meeting=meeting)
        persons = [reg.person for reg in regs]
        self.assertEqual(session.attended_set.count(), 0)

        # If there are no attendees, the link isn't offered, and getting
        # the page directly returns an empty list.
        session_url = urlreverse('ietf.meeting.views.session_details', kwargs={'num':meeting.number, 'acronym':session.group.acronym})
        attendance_url = urlreverse('ietf.meeting.views.session_attendance', kwargs={'num':meeting.number, 'session_id':session.id})
        r = self.client.get(session_url)
        self.assertNotContains(r, attendance_url)
        r = self.client.get(attendance_url)
        self.assertEqual(r.status_code, 200)  
        self.assertContains(r, '0 attendees')

        # Add some attendees
        add_attendees_url = urlreverse('ietf.meeting.views.api_add_session_attendees')
        recmanrole = RoleFactory(group__type_id='ietf', name_id='recman', person__user__last_login=timezone.now())
        recman = recmanrole.person
        apikey = PersonalApiKeyFactory(endpoint=add_attendees_url, person=recman)
        attendees = [person.user.pk for person in persons]
        self.client.login(username='recman', password='recman+password')
        r = self.client.post(add_attendees_url, {'apikey':apikey.hash(), 'attended':f'{{"session_id":{session.pk},"attendees":{attendees}}}'})
        self.assertEqual(r.status_code, 200)  
        self.assertEqual(session.attended_set.count(), 3)

        # Before a meeting is finalized, session_attendance renders a live
        # view of the Attended records for the session.
        r = self.client.get(session_url)
        self.assertContains(r, attendance_url)
        r = self.client.get(attendance_url)
        self.assertEqual(r.status_code, 200)  
        self.assertContains(r, '3 attendees')
        for person in persons:
            self.assertContains(r, person.plain_name())

        # Test for the "I was there" button.
        def _test_button(person, expected):
            username = person.user.username
            self.client.login(username=username, password=f'{username}+password')
            r = self.client.get(attendance_url)
            self.assertEqual(b"I was there" in r.content, expected)
        # recman isn't registered for the meeting
        _test_button(recman, False)
        # person0 is already on the bluesheet
        _test_button(persons[0], False)
        # person3 attests he was there
        persons.append(MeetingRegistrationFactory(meeting=meeting).person)
        # button isn't shown if we're outside the corrections windows
        meeting.importantdate_set.create(name_id='revsub',date=date_today() - datetime.timedelta(days=20))
        _test_button(persons[3], False)
        # attempt to POST anyway is ignored
        r = self.client.post(attendance_url)
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, persons[3].plain_name())
        self.assertEqual(session.attended_set.count(), 3)
        # button is shown, and POST is accepted
        meeting.importantdate_set.update(name_id='revsub',date=date_today() + datetime.timedelta(days=20))
        _test_button(persons[3], True)
        r = self.client.post(attendance_url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, persons[3].plain_name())
        self.assertEqual(session.attended_set.count(), 4)

        # When the meeting is finalized, a bluesheet file is generated,
        # and session_attendance redirects to the file.
        self.client.login(username='secretary',password='secretary+password')
        finalize_url = urlreverse('ietf.meeting.views.finalize_proceedings', kwargs={'num':meeting.number})
        r = self.client.post(finalize_url, {'finalize':1})
        self.assertRedirects(r, urlreverse('ietf.meeting.views.proceedings', kwargs={'num':meeting.number}))
        doc = session.presentations.filter(document__type_id='bluesheets').first().document
        self.assertEqual(doc.rev,'00')
        text = doc.text()
        self.assertIn('4 attendees', text)
        for person in persons:
            self.assertIn(person.plain_name(), text)
        r = self.client.get(session_url)
        self.assertContains(r, doc.get_href())
        self.assertNotContains(r, attendance_url)
        r = self.client.get(attendance_url)
        self.assertEqual(r.status_code,302)
        self.assertEqual(r['Location'],doc.get_href())

        # An interim meeting is considered finalized immediately.
        meeting = make_interim_meeting(group=GroupFactory(acronym='mars'), date=date_today())
        session = Session.objects.filter(meeting=meeting, group__acronym='mars').first()
        attendance_url = urlreverse('ietf.meeting.views.session_attendance', kwargs={'num':meeting.number, 'session_id':session.id})
        self.assertEqual(session.attended_set.count(), 0)
        self.client.login(username='recman', password='recman+password')
        attendees = [person.user.pk for person in persons]
        r = self.client.post(add_attendees_url, {'apikey':apikey.hash(), 'attended':f'{{"session_id":{session.pk},"attendees":{attendees}}}'})
        self.assertEqual(r.status_code, 200)  
        self.assertEqual(session.attended_set.count(), 4)
        doc = session.presentations.filter(document__type_id='bluesheets').first().document
        self.assertEqual(doc.rev,'00')
        session_url = urlreverse('ietf.meeting.views.session_details', kwargs={'num':meeting.number, 'acronym':session.group.acronym})
        r = self.client.get(session_url)
        self.assertContains(r, doc.get_href())
        self.assertNotContains(r, attendance_url)
        r = self.client.get(attendance_url)
        self.assertEqual(r.status_code,302)
        self.assertEqual(r['Location'],doc.get_href())

    def test_bluesheet_data(self):
        session = SessionFactory(meeting__type_id="ietf") 
        attended_with_affil = MeetingRegistrationFactory(meeting=session.meeting, affiliation="Somewhere")
        AttendedFactory(session=session, person=attended_with_affil.person, time="2023-03-13T01:24:00Z")  # joined 2nd
        attended_no_affil = MeetingRegistrationFactory(meeting=session.meeting)
        AttendedFactory(session=session, person=attended_no_affil.person, time="2023-03-13T01:23:00Z")  # joined 1st
        MeetingRegistrationFactory(meeting=session.meeting)  # did not attend
        
        data = bluesheet_data(session)
        self.assertEqual(
            data,
            [
                {"name": attended_no_affil.person.plain_name(), "affiliation": ""},
                {"name": attended_with_affil.person.plain_name(), "affiliation": "Somewhere"},
            ]
        )

