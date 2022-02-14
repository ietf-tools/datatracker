# Copyright The IETF Trust 2009-2020, All Rights Reserved
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
from mock import patch, PropertyMock
from pyquery import PyQuery
from lxml.etree import tostring
from io import StringIO, BytesIO
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urlsplit
from PIL import Image
from pathlib import Path

from django.urls import reverse as urlreverse
from django.conf import settings
from django.contrib.auth.models import User
from django.test import Client, override_settings
from django.db.models import F, Max
from django.http import QueryDict, FileResponse
from django.template import Context, Template
from django.utils.text import slugify
from django.utils.timezone import now

import debug           # pyflakes:ignore

from ietf.doc.models import Document
from ietf.group.models import Group, Role, GroupFeatures
from ietf.group.utils import can_manage_group
from ietf.person.models import Person
from ietf.meeting.helpers import can_approve_interim_request, can_view_interim_request
from ietf.meeting.helpers import send_interim_approval_request
from ietf.meeting.helpers import send_interim_meeting_cancellation_notice, send_interim_session_cancellation_notice
from ietf.meeting.helpers import send_interim_minutes_reminder, populate_important_dates, update_important_dates
from ietf.meeting.models import Session, TimeSlot, Meeting, SchedTimeSessAssignment, Schedule, SessionPresentation, SlideSubmission, SchedulingEvent, Room, Constraint, ConstraintName
from ietf.meeting.test_data import make_meeting_test_data, make_interim_meeting, make_interim_test_data
from ietf.meeting.utils import finalize, condition_slide_order
from ietf.meeting.utils import add_event_info_to_session_qs
from ietf.meeting.views import session_draft_list, parse_agenda_filter_params, sessions_post_save
from ietf.name.models import SessionStatusName, ImportantDateName, RoleName, ProceedingsMaterialTypeName
from ietf.utils.decorators import skip_coverage
from ietf.utils.mail import outbox, empty_outbox, get_payload_text
from ietf.utils.test_utils import TestCase, login_testing_unauthorized, unicontent
from ietf.utils.text import xslugify

from ietf.person.factories import PersonFactory
from ietf.group.factories import GroupFactory, GroupEventFactory, RoleFactory
from ietf.meeting.factories import ( SessionFactory, ScheduleFactory,
    SessionPresentationFactory, MeetingFactory, FloorPlanFactory,
    TimeSlotFactory, SlideSubmissionFactory, RoomFactory,
    ConstraintFactory, MeetingHostFactory, ProceedingsMaterialFactory )
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

    def write_materials_file(self, meeting, doc, content):
        path = os.path.join(self.materials_dir, "%s/%s/%s" % (meeting.number, doc.type_id, doc.uploaded_filename))

        dirname = os.path.dirname(path)
        if not os.path.exists(dirname):
            os.makedirs(dirname)

        if isinstance(content, str):
            content = content.encode()
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



class MeetingTests(BaseMeetingTestCase):
    def test_meeting_agenda(self):
        meeting = make_meeting_test_data()
        session = Session.objects.filter(meeting=meeting, group__acronym="mars").first()
        slot = TimeSlot.objects.get(sessionassignments__session=session,sessionassignments__schedule=meeting.schedule)
        #
        self.write_materials_files(meeting, session)
        #
        future_year = datetime.date.today().year+1
        future_num =  (future_year-1984)*3            # valid for the mid-year meeting
        future_meeting = Meeting.objects.create(date=datetime.date(future_year, 7, 22), number=future_num, type_id='ietf',
                                city="Panama City", country="PA", time_zone='America/Panama')

        registration_text = "Registration"

        # utc
        time_interval = "%s-%s" % (slot.utc_start_time().strftime("%H:%M").lstrip("0"), (slot.utc_start_time() + slot.duration).strftime("%H:%M").lstrip("0"))

        r = self.client.get(urlreverse("ietf.meeting.views.agenda", kwargs=dict(num=meeting.number,utc='-utc')))
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        agenda_content = q("#content").html()
        self.assertIn(session.group.acronym, agenda_content)
        self.assertIn(session.group.name, agenda_content)
        self.assertIn(session.group.parent.acronym.upper(), agenda_content)
        self.assertIn(slot.location.name, agenda_content)
        self.assertIn(time_interval, agenda_content)
        self.assertIsNotNone(q(':input[value="%s"]' % meeting.time_zone),
                             'Time zone selector should show meeting timezone')
        self.assertIsNotNone(q('.nav *:contains("%s")' % meeting.time_zone),
                             'Time zone indicator should be in nav sidebar')

        # plain
        time_interval = "%s-%s" % (slot.time.strftime("%H:%M").lstrip("0"), (slot.time + slot.duration).strftime("%H:%M").lstrip("0"))

        r = self.client.get(urlreverse("ietf.meeting.views.agenda", kwargs=dict(num=meeting.number)))
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        agenda_content = q("#content").html()
        self.assertIn(session.group.acronym, agenda_content)
        self.assertIn(session.group.name, agenda_content)
        self.assertIn(session.group.parent.acronym.upper(), agenda_content)
        self.assertIn(slot.location.name, agenda_content)
        self.assertIn(time_interval, agenda_content)
        self.assertIn(registration_text, agenda_content)

        # Make sure there's a frame for the session agenda and it points to the right place
        assignment_url = urlreverse('ietf.meeting.views.session_materials', kwargs=dict(session_id=session.pk))
        self.assertTrue(
            any(
                [assignment_url in x.attrib["data-src"] 
                 for x in q('tr div.modal-body  div.session-materials')]
            )
        ) 

        # future meeting, no agenda
        r = self.client.get(urlreverse("ietf.meeting.views.agenda", kwargs=dict(num=future_meeting.number)))
        self.assertContains(r, "There is no agenda available yet.")
        self.assertTemplateUsed(r, 'meeting/no-agenda.html')

        # text
        # the rest of the results don't have as nicely formatted times
        time_interval = time_interval.replace(":", "")

        r = self.client.get(urlreverse("ietf.meeting.views.agenda", kwargs=dict(num=meeting.number, ext=".txt")))
        self.assertContains(r, session.group.acronym)
        self.assertContains(r, session.group.name)
        self.assertContains(r, session.group.parent.acronym.upper())
        self.assertContains(r, slot.location.name)

        self.assertContains(r, time_interval)

        r = self.client.get(urlreverse("ietf.meeting.views.agenda", kwargs=dict(num=meeting.number,name=meeting.unofficial_schedule.name,owner=meeting.unofficial_schedule.owner.email())))
        self.assertContains(r, 'not the official schedule')

        # future meeting, no agenda
        r = self.client.get(urlreverse("ietf.meeting.views.agenda", kwargs=dict(num=future_meeting.number, ext=".txt")))
        self.assertContains(r, "There is no agenda available yet.")
        self.assertTemplateUsed(r, 'meeting/no-agenda.txt')

        # CSV
        r = self.client.get(urlreverse("ietf.meeting.views.agenda", kwargs=dict(num=meeting.number, ext=".csv")))
        self.assertContains(r, session.group.acronym)
        self.assertContains(r, session.group.name)
        self.assertContains(r, session.group.parent.acronym.upper())
        self.assertContains(r, slot.location.name)
        self.assertContains(r, registration_text)

        self.assertContains(r, session.materials.get(type='agenda').uploaded_filename)
        self.assertContains(r, session.materials.filter(type='slides').exclude(states__type__slug='slides',states__slug='deleted').first().uploaded_filename)
        self.assertNotContains(r, session.materials.filter(type='slides',states__type__slug='slides',states__slug='deleted').first().uploaded_filename)

        # iCal
        r = self.client.get(urlreverse("ietf.meeting.views.agenda_ical", kwargs=dict(num=meeting.number))
                            + "?show=" + session.group.parent.acronym.upper())
        assert_ical_response_is_valid(self, r)
        self.assertContains(r, session.group.acronym)
        self.assertContains(r, session.group.name)
        self.assertContains(r, slot.location.name)
        self.assertContains(r, "BEGIN:VTIMEZONE")
        self.assertContains(r, "END:VTIMEZONE")        

        self.assertContains(r, session.agenda().get_href())
        self.assertContains(
            r,
            urlreverse(
                'ietf.meeting.views.session_details',
                kwargs=dict(num=meeting.number, acronym=session.group.acronym)),
            msg_prefix='ical should contain link to meeting materials page for session')
        self.assertContains(
            r,
            urlreverse(
                'ietf.meeting.views.agenda', kwargs=dict(num=meeting.number)
            ) + f'#row-{session.official_timeslotassignment().slug()}',
            msg_prefix='ical should contain link to agenda entry for session')

        # week view
        r = self.client.get(urlreverse("ietf.meeting.views.week_view", kwargs=dict(num=meeting.number)))
        self.assertNotContains(r, 'CANCELLED')
        self.assertContains(r, session.group.acronym)
        self.assertContains(r, slot.location.name)
        self.assertContains(r, registration_text)

        # week view with a cancelled session
        SchedulingEvent.objects.create(
            session=session,
            status=SessionStatusName.objects.get(slug='canceled'),
            by=Person.objects.get(name='(System)')
        )
        r = self.client.get(urlreverse("ietf.meeting.views.week_view", kwargs=dict(num=meeting.number)))
        self.assertContains(r, 'CANCELLED')
        self.assertContains(r, session.group.acronym)
        self.assertContains(r, slot.location.name)

    def test_meeting_agenda_filters_ignored(self):
        """The agenda view should ignore filter querystrings
        
        (They are handled by javascript on the front end)
        """
        meeting = make_meeting_test_data()
        expected_items = meeting.schedule.assignments.exclude(timeslot__type__in=['lead','offagenda'])
        expected_rows = ['row-%s' % item.slug() for item in expected_items]
        
        r = self.client.get(urlreverse('ietf.meeting.views.agenda'))
        for row_id in expected_rows:
            self.assertContains(r, row_id)

        r = self.client.get(urlreverse('ietf.meeting.views.agenda') + '?show=mars')
        for row_id in expected_rows:
            self.assertContains(r, row_id)

        r = self.client.get(urlreverse('ietf.meeting.views.agenda') + '?show=mars&hide=ames,mars,plenary,ietf,bof')
        for row_id in expected_rows:
            self.assertContains(r, row_id)

    def test_agenda_iab_session(self):
        date = datetime.date.today()
        meeting = MeetingFactory(type_id='ietf', date=date )
        make_meeting_test_data(meeting=meeting)
        
        iab = Group.objects.get(acronym='iab')
        venus = Group.objects.create(
            name="Three letter acronym",
            acronym="venus",
            description="This group discusses exploration of Venus",
            state_id="active",
            type_id="program",
            parent=iab,
            list_email="venus@ietf.org",
        )
        venus_session = SessionFactory(
            meeting=meeting,
            group=venus,
            attendees=10,
            requested_duration=datetime.timedelta(minutes=60),
            add_to_schedule=False,
        )
        system_person = Person.objects.get(name="(System)")
        SchedulingEvent.objects.create(session=venus_session, status_id='schedw', by=system_person)
        room = Room.objects.create(meeting=meeting,
                                   name="Aphrodite",
                                   capacity=100,
                                   functional_name="Aphrodite Room")
        room.session_types.add('regular')
        session_date = meeting.date + datetime.timedelta(days=1)
        slot3 = TimeSlot.objects.create(meeting=meeting, type_id='regular', location=room,
                                        duration=datetime.timedelta(minutes=60),
                                        time=datetime.datetime.combine(session_date, datetime.time(13, 30)))
        SchedTimeSessAssignment.objects.create(timeslot=slot3, session=venus_session, schedule=meeting.schedule)
        url = urlreverse('ietf.meeting.views.agenda', kwargs=dict(num=meeting.number))
        r = self.client.get(url)
        self.assertContains(r, 'venus')
        q = PyQuery(r.content)
        venus_row = q('[id*="-iab-"]').html()
        self.assertIn('venus', venus_row)
        
    def test_agenda_current_audio(self):
        date = datetime.date.today()
        meeting = MeetingFactory(type_id='ietf', date=date )
        make_meeting_test_data(meeting=meeting)
        url = urlreverse("ietf.meeting.views.agenda", kwargs=dict(num=meeting.number))
        r = self.client.get(url)
        self.assertContains(r, "Audio stream")

    def test_agenda_by_room(self):
        meeting = make_meeting_test_data()
        url = urlreverse("ietf.meeting.views.agenda_by_room",kwargs=dict(num=meeting.number))
        login_testing_unauthorized(self,"secretary",url)
        r = self.client.get(url)
        self.assertTrue(all([x in unicontent(r) for x in ['mars','IESG Breakfast','Test Room','Breakfast Room']]))

        url = urlreverse("ietf.meeting.views.agenda_by_room",kwargs=dict(num=meeting.number,name=meeting.unofficial_schedule.name,owner=meeting.unofficial_schedule.owner.email()))
        r = self.client.get(url)
        self.assertTrue(all([x in unicontent(r) for x in ['mars','Test Room',]]))
        self.assertNotContains(r, 'IESG Breakfast')

    def test_agenda_by_type(self):
        meeting = make_meeting_test_data()

        url = urlreverse("ietf.meeting.views.agenda_by_type",kwargs=dict(num=meeting.number))
        login_testing_unauthorized(self,"secretary",url)
        r = self.client.get(url)
        self.assertTrue(all([x in unicontent(r) for x in ['mars','IESG Breakfast','Test Room','Breakfast Room']]))

        url = urlreverse("ietf.meeting.views.agenda_by_type",kwargs=dict(num=meeting.number,name=meeting.unofficial_schedule.name,owner=meeting.unofficial_schedule.owner.email()))
        r = self.client.get(url)
        self.assertTrue(all([x in unicontent(r) for x in ['mars','Test Room',]]))
        self.assertNotContains(r, 'IESG Breakfast')

        url = urlreverse("ietf.meeting.views.agenda_by_type",kwargs=dict(num=meeting.number,type='regular'))
        r = self.client.get(url)
        self.assertTrue(all([x in unicontent(r) for x in ['mars','Test Room']]))
        self.assertFalse(any([x in unicontent(r) for x in ['IESG Breakfast','Breakfast Room']]))

        url = urlreverse("ietf.meeting.views.agenda_by_type",kwargs=dict(num=meeting.number,type='lead'))
        r = self.client.get(url)
        self.assertFalse(any([x in unicontent(r) for x in ['mars','Test Room']]))
        self.assertTrue(all([x in unicontent(r) for x in ['IESG Breakfast','Breakfast Room']]))

        url = urlreverse("ietf.meeting.views.agenda_by_type",kwargs=dict(num=meeting.number,type='lead',name=meeting.unofficial_schedule.name,owner=meeting.unofficial_schedule.owner.email()))
        r = self.client.get(url)
        self.assertFalse(any([x in unicontent(r) for x in ['IESG Breakfast','Breakfast Room']]))

    def test_agenda_room_view(self):
        meeting = make_meeting_test_data()
        url = urlreverse("ietf.meeting.views.room_view",kwargs=dict(num=meeting.number))
        login_testing_unauthorized(self,"secretary",url)
        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        self.assertTrue(all([x in unicontent(r) for x in ['mars','IESG Breakfast','Test Room','Breakfast Room']]))
        url = urlreverse("ietf.meeting.views.room_view",kwargs=dict(num=meeting.number,name=meeting.unofficial_schedule.name,owner=meeting.unofficial_schedule.owner.email()))
        r = self.client.get(url)
        self.assertTrue(all([x in unicontent(r) for x in ['mars','Test Room','Breakfast Room']]))
        self.assertNotContains(r, 'IESG Breakfast')


    def test_agenda_week_view(self):
        meeting = make_meeting_test_data()
        url = urlreverse("ietf.meeting.views.week_view",kwargs=dict(num=meeting.number)) + "?show=farfut"
        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        self.assertTrue(all([x in unicontent(r) for x in ['var all_items', 'maximize', 'draw_calendar', ]]))

        # Specifying a time zone should not change the output (time zones are handled by the JS)
        url = urlreverse("ietf.meeting.views.week_view",kwargs=dict(num=meeting.number)) + "?show=farfut&tz=Asia/Bangkok"
        r_with_tz = self.client.get(url)
        self.assertEqual(r_with_tz.status_code,200)
        self.assertEqual(r.content, r_with_tz.content)

    def test_agenda_personalize(self):
        """Session selection page should have a checkbox for each session with appropriate keywords"""
        meeting = make_meeting_test_data()
        url = urlreverse("ietf.meeting.views.agenda_personalize",kwargs=dict(num=meeting.number))
        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        q = PyQuery(r.content)
        for assignment in SchedTimeSessAssignment.objects.filter(
                schedule__in=[meeting.schedule, meeting.schedule.base],
                session__on_agenda=True,
        ):
            row = q('#row-{}'.format(assignment.slug()))
            self.assertIsNotNone(row, 'No row for assignment {}'.format(assignment))
            checkboxes = row('input[type="checkbox"][name="selected-sessions"]')
            self.assertEqual(len(checkboxes), 1,
                             'Row for assignment {} does not have a checkbox input'.format(assignment))
            checkbox = checkboxes.eq(0)
            kw_token = assignment.session.docname_token_only_for_multiple()
            self.assertEqual(
                checkbox.attr('data-filter-item'),
                assignment.session.group.acronym.lower() + (
                    '' if kw_token is None else f'-{kw_token}'
                )
            )

    def test_agenda_personalize_updates_urls(self):
        """The correct URLs should be updated when filter settings change on the personalize agenda view

        Tests that the expected elements have the necessary classes. The actual update of these fields
        is tested in the JS tests
        """
        meeting = make_meeting_test_data()
        url = urlreverse("ietf.meeting.views.agenda_personalize",kwargs=dict(num=meeting.number))
        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        q = PyQuery(r.content)

        # Find all the elements expected to be updated
        expected_elements = []
        nav_tab_anchors = q('ul.nav.nav-tabs > li > a')
        for anchor in nav_tab_anchors.items():
            text = anchor.text().strip()
            if text in ['Agenda', 'UTC Agenda', 'Select Sessions']:
                expected_elements.append(anchor)
        for btn in q('.buttonlist a.btn').items():
            text = btn.text().strip()
            if text in ['View customized agenda', 'Download as .ics', 'Subscribe with webcal']:
                expected_elements.append(btn)

        # Check that all the expected elements have the correct classes
        for elt in expected_elements:
            self.assertTrue(elt.has_class('agenda-link'))
            self.assertTrue(elt.has_class('filterable'))

        # Finally, check that there are no unexpected elements marked to be updated.
        # If there are, they should be added to the test above.
        self.assertEqual(len(expected_elements),
                         len(q('.agenda-link.filterable')),
                         'Unexpected elements updated')

    @override_settings(MEETING_MATERIALS_SERVE_LOCALLY=False, MEETING_DOC_HREFS = settings.MEETING_DOC_CDN_HREFS)
    def test_materials_through_cdn(self):
        meeting = make_meeting_test_data(create_interims=True)

        session107 = SessionFactory(meeting__number='172',group__acronym='mars')
        doc = DocumentFactory.create(name='agenda-172-mars', type_id='agenda', title="Agenda",
            uploaded_filename="agenda-172-mars.txt", group=session107.group, rev='00', states=[('agenda','active')])
        pres = SessionPresentation.objects.create(session=session107,document=doc,rev=doc.rev)
        session107.sessionpresentation_set.add(pres) # 
        doc = DocumentFactory.create(name='minutes-172-mars', type_id='minutes', title="Minutes",
            uploaded_filename="minutes-172-mars.md", group=session107.group, rev='00', states=[('minutes','active')])
        pres = SessionPresentation.objects.create(session=session107,document=doc,rev=doc.rev)
        session107.sessionpresentation_set.add(pres)
        doc = DocumentFactory.create(name='slides-172-mars-1-active', type_id='slides', title="Slideshow",
            uploaded_filename="slides-172-mars.txt", group=session107.group, rev='00',
            states=[('slides','active'), ('reuse_policy', 'single')])
        pres = SessionPresentation.objects.create(session=session107,document=doc,rev=doc.rev)
        session107.sessionpresentation_set.add(pres)

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
        date = datetime.datetime.today() - datetime.timedelta(days=10)
        meeting = make_interim_meeting(group=group, date=date, status='sched')
        session = meeting.session_set.first()

        self.do_test_materials(meeting, session)

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
        
        
        cont_disp = r._headers.get('content-disposition', ('Content-Disposition', ''))[1]
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
            url = urlreverse("ietf.meeting.views.materials", kwargs=dict())
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)
            q = PyQuery(r.content)
            row = q('#content #%s' % str(session.group.acronym)).closest("tr")
            self.assertTrue(row.find('a:contains("Agenda")'))
            self.assertTrue(row.find('a:contains("Minutes")'))
            self.assertTrue(row.find('a:contains("Slideshow")'))
            self.assertFalse(row.find("a:contains(\"Bad Slideshow\")"))

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
        sp = SessionPresentationFactory(document__name='slides-junk-15',document__type_id='slides',document__states=[('reuse_policy','single')])
        sp.document.uploaded_filename = '%s-%s.pdf'%(sp.document.name,sp.document.rev)
        sp.document.save()
        self.write_materials_file(sp.session.meeting, sp.document, 'Fake slide contents')
        url = urlreverse("ietf.meeting.views.materials_document", kwargs=dict(document=sp.document.name,num=sp.session.meeting.number))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

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

    def test_group_ical(self):
        meeting = make_meeting_test_data()
        s1 = Session.objects.filter(meeting=meeting, group__acronym="mars").first()
        a1 = s1.official_timeslotassignment()
        t1 = a1.timeslot
        # Create an extra session
        t2 = TimeSlotFactory.create(meeting=meeting, time=datetime.datetime.combine(meeting.date, datetime.time(11, 30)))
        s2 = SessionFactory.create(meeting=meeting, group=s1.group, add_to_schedule=False)
        SchedTimeSessAssignment.objects.create(timeslot=t2, session=s2, schedule=meeting.schedule)
        #
        url = urlreverse('ietf.meeting.views.agenda_ical', kwargs={'num':meeting.number, 'acronym':s1.group.acronym, })
        r = self.client.get(url)
        assert_ical_response_is_valid(self,
                                      r,
                                      expected_event_summaries=['mars - Martian Special Interest Group'],
                                      expected_event_count=2)
        self.assertContains(r, t1.time.strftime('%Y%m%dT%H%M%S'))
        self.assertContains(r, t2.time.strftime('%Y%m%dT%H%M%S'))
        #
        url = urlreverse('ietf.meeting.views.agenda_ical', kwargs={'num':meeting.number, 'session_id':s1.id, })
        r = self.client.get(url)
        assert_ical_response_is_valid(self, r,
                                      expected_event_summaries=['mars - Martian Special Interest Group'],
                                      expected_event_count=1)
        self.assertContains(r, t1.time.strftime('%Y%m%dT%H%M%S'))
        self.assertNotContains(r, t2.time.strftime('%Y%m%dT%H%M%S'))

    def test_meeting_agenda_has_static_ical_links(self):
        """Links to the agenda_ical view must appear on the agenda page
        
        Confirms that these have the correct querystrings. Does not test the JS-based
        'Customized schedule' button.
        """
        meeting = make_meeting_test_data()

        # get the agenda
        url = urlreverse('ietf.meeting.views.agenda', kwargs=dict(num=meeting.number))
        r = self.client.get(url)
        
        # Check that it has the links we expect
        ical_url = urlreverse('ietf.meeting.views.agenda_ical', kwargs=dict(num=meeting.number))
        q = PyQuery(r.content)
        content = q('#content').html()

        assignments = meeting.schedule.assignments.exclude(timeslot__type__in=['lead', 'offagenda'])

        # Assume the test meeting is not using historic groups
        groups = [a.session.group for a in assignments if a.session is not None]
        for g in groups:
            if g.parent_id is not None:
                self.assertIn('%s?show=%s' % (ical_url, g.parent.acronym.lower()), content)

        # The 'non-area events' are those whose keywords are in the last column of buttons
        na_col = q('#customize td.view:last-child')  # find the column
        non_area_labels = [e.attrib['data-filter-item']
                           for e in na_col.find('button.pickview')]
        assert len(non_area_labels) > 0  # test setup must produce at least one label for this test

        # Should be a 'non-area events' link showing appropriate types
        self.assertIn('%s?show=%s' % (ical_url, ','.join(non_area_labels).lower()), content)

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
        session.sessionpresentation_set.create(document=draft1)
        draft2 = WgDraftFactory(group=session.group)
        agenda = DocumentFactory(type_id='agenda',group=session.group, uploaded_filename='agenda-%s-%s' % (session.meeting.number,session.group.acronym), states=[('agenda','active')])
        session.sessionpresentation_set.create(document=agenda)
        self.write_materials_file(session.meeting, session.materials.get(type="agenda"),
                                  "1. WG status (15 minutes)\n\n2. Status of %s\n\n" % draft2.name)
        filenames = []
        for d in (draft1, draft2):
            file,_ = submission_file(name=d.name,format='txt',templatename='test_submission.txt',group=session.group,rev="00")
            filename = os.path.join(d.get_file_path(),file.name)
            with io.open(filename,'w') as draftbits:
                draftbits.write(file.getvalue())
            filenames.append(filename)
        self.assertEqual( len(session_draft_list(session.meeting.number,session.group.acronym)), 2)
        return (session, filenames)

    def test_session_draft_tarfile(self):
        session, filenames = self.build_session_setup()
        url = urlreverse('ietf.meeting.views.session_draft_tarfile', kwargs={'num':session.meeting.number,'acronym':session.group.acronym})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get('Content-Type'), 'application/octet-stream')
        for filename in filenames:
            os.unlink(filename)

    @skipIf(skip_pdf_tests, skip_message)
    @skip_coverage
    def test_session_draft_pdf(self):
        session, filenames = self.build_session_setup()
        url = urlreverse('ietf.meeting.views.session_draft_pdf', kwargs={'num':session.meeting.number,'acronym':session.group.acronym})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get('Content-Type'), 'application/pdf')
        for filename in filenames:
            os.unlink(filename)

    def test_current_materials(self):
        url = urlreverse('ietf.meeting.views.current_materials')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)
        MeetingFactory(type_id='ietf', date=datetime.date.today())
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
                'name':schedule.name,
                'visible':True,
                'public':True,
                'notes': "New Notes",
                'base': new_base.pk,
            }
        )
        self.assertNoFormPostErrors(response)
        schedule.refresh_from_db()
        self.assertTrue(schedule.visible)
        self.assertTrue(schedule.public)
        self.assertEqual(schedule.notes, "New Notes")
        self.assertEqual(schedule.base_id, new_base.pk)

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
                        time=datetime.datetime.combine(meeting.date, time),
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
            date=datetime.date.today() + datetime.timedelta(days=7),
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
        t0 = datetime.datetime.combine(meeting.date, datetime.time(11, 0))
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
        right_now = self._right_now_in(meeting.time_zone)
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
        right_now = self._right_now_in(meeting.time_zone)
        yesterday = (right_now - datetime.timedelta(days=1)).date()
        day_before = (right_now - datetime.timedelta(days=2)).date()
        for room in room_groups[0]:
            ts = room.timeslot_set.last()
            ts.time = datetime.datetime.combine(yesterday, ts.time.time())
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
            ts.time = datetime.datetime.combine(day_before, ts.time.time())
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
    def _right_now_in(tzname):
        right_now = now().astimezone(pytz.timezone(tzname))
        if not settings.USE_TZ:
            right_now = right_now.replace(tzinfo=None)
        return right_now

    def test_assign_session(self):
        """Allow assignment to future timeslots only for official schedule"""
        meeting = MeetingFactory(
            type_id='ietf',
            date=(datetime.datetime.today() - datetime.timedelta(days=1)).date(),
            days=3,
        )
        right_now = self._right_now_in(meeting.time_zone)

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
            date=(datetime.datetime.today() - datetime.timedelta(days=1)).date(),
            days=3,
        )
        right_now = self._right_now_in(meeting.time_zone)

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
            date=(datetime.datetime.today() - datetime.timedelta(days=1)).date(),
            days=3,
        )
        right_now = self._right_now_in(meeting.time_zone)

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
            date=datetime.date.today() + datetime.timedelta(days=7),
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
            date=datetime.datetime.today() + datetime.timedelta(days=10),
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
        return meeting

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
        days = [meeting.get_meeting_date(ii).date() for ii in range(meeting.days)]

        timeslots = []
        duration = datetime.timedelta(minutes=90)
        for room in meeting.room_set.all():
            for day in days:
                timeslots.extend(
                    TimeSlotFactory(
                        meeting=meeting,
                        location=room,
                        time=datetime.datetime.combine(day, t),
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
                time=datetime.datetime.combine(
                    meeting.get_meeting_date(day).date(),
                    datetime.time(hour=11)
                ),
            )
            TimeSlotFactory(
                meeting=meeting,
                location=meeting.room_set.first(),
                time=datetime.datetime.combine(
                    meeting.get_meeting_date(day).date(),
                    datetime.time(hour=14)
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
        time_before = datetime.datetime.combine(
            meeting.date,
            datetime.time(hour=10),
        )
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
        name_after = 'New Name (tm)'
        type_after = 'plenary'
        time_after = time_before.replace(day=time_before.day + 1, hour=time_before.hour + 2)
        duration_after = duration_before * 2
        show_location_after = False
        location_after = meeting.room_set.last()
        r = self.client.post(
            self.edit_timeslot_url(ts),
            data=dict(
                name=name_after,
                type=type_after,
                time_0=time_after.strftime('%Y-%m-%d'),  # date for SplitDateTimeField
                time_1=time_after.strftime('%H:%M'),  # time for SplitDateTimeField
                duration=str(duration_after),
                # show_location=show_location_after,  # False values are omitted from form
                location=location_after.pk,
            )
        )
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

    def test_invalid_edit_timeslot(self):
        meeting = self.create_bare_meeting()
        ts: TimeSlot = TimeSlotFactory(meeting=meeting, name='slot')  # n.b., colon indicates type hinting
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
        self.assertEqual(str(ts.time.date().toordinal()), post_data['days'])
        self.assertEqual(ts.time.strftime('%H:%M'), post_data['time'])
        self.assertEqual(str(ts.duration), '{}:00'.format(post_data['duration']))  # add seconds
        self.assertEqual(ts.show_location, post_data['show_location'])
        self.assertEqual(str(ts.location.pk), post_data['locations'])

    def test_create_single_timeslot_outside_meeting_days(self):
        """Creating a single timeslot outside the official meeting days should work"""
        meeting = self.create_meeting()
        timeslots_before = set(ts.pk for ts in meeting.timeslot_set.all())
        other_date = meeting.get_meeting_date(-7).date()
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
        self.assertEqual(ts.time.date(), other_date)
        self.assertEqual(ts.time.strftime('%H:%M'), post_data['time'])
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
        days = [meeting.get_meeting_date(n).date() for n in range(meeting.days)]
        other_date = meeting.get_meeting_date(-1).date()  # date before start of meeting
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
            self.assertEqual(ts.time.strftime('%H:%M'), post_data['time'])
            self.assertEqual(str(ts.duration), '{}:00'.format(post_data['duration']))  # add seconds
            self.assertEqual(ts.show_location, post_data['show_location'])
            self.assertIn(ts.time.date(), days)
            self.assertIn(ts.location, locations)
            self.assertIn((ts.time.date(), ts.location), day_locs,
                          'Duplicated day / location found')
            day_locs.discard((ts.time.date(), ts.location))
        self.assertEqual(day_locs, set(), 'Not all day/location combinations created')

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

    def test_add_slides_to_session(self):
        for type_id in ('ietf','interim'):
            chair_role = RoleFactory(name_id='chair')
            session = SessionFactory(group=chair_role.group, meeting__date=datetime.date.today()-datetime.timedelta(days=90), meeting__type_id=type_id)
            slides = DocumentFactory(type_id='slides')
            url = urlreverse('ietf.meeting.views.ajax_add_slides_to_session', kwargs={'session_id':session.pk, 'num':session.meeting.number})

            # Not a valid user
            r = self.client.post(url, {'order':1, 'name':slides.name })
            self.assertEqual(r.status_code, 403)
            self.assertIn('have permission', unicontent(r))

            self.client.login(username=chair_role.person.user.username, password=chair_role.person.user.username+"+password")

            # Past submission cutoff
            r = self.client.post(url, {'order':0, 'name':slides.name })
            self.assertEqual(r.status_code, 403)
            self.assertIn('materials cutoff', unicontent(r))

            session.meeting.date = datetime.date.today()
            session.meeting.save()

            # Invalid order
            r = self.client.post(url, {})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()['success'],False)
            self.assertIn('No data',r.json()['error'])

            r = self.client.post(url, {'garbage':'garbage'})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()['success'],False)
            self.assertIn('order is not valid',r.json()['error'])

            r = self.client.post(url, {'order':0, 'name':slides.name })
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()['success'],False)
            self.assertIn('order is not valid',r.json()['error'])

            r = self.client.post(url, {'order':2, 'name':slides.name })
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()['success'],False)
            self.assertIn('order is not valid',r.json()['error'])

            r = self.client.post(url, {'order':'garbage', 'name':slides.name })
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()['success'],False)
            self.assertIn('order is not valid',r.json()['error'])

            # Invalid name
            r = self.client.post(url, {'order':1 })
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()['success'],False)
            self.assertIn('name is not valid',r.json()['error'])

            r = self.client.post(url, {'order':1, 'name':'garbage' })
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()['success'],False)
            self.assertIn('name is not valid',r.json()['error'])

            # Valid post
            r = self.client.post(url, {'order':1, 'name':slides.name })
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()['success'],True)
            self.assertEqual(session.sessionpresentation_set.count(),1)

            # Ingore a request to add slides that are already in a session
            r = self.client.post(url, {'order':1, 'name':slides.name })
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()['success'],True)
            self.assertEqual(session.sessionpresentation_set.count(),1)


            session2 = SessionFactory(group=session.group, meeting=session.meeting)
            SessionPresentationFactory.create_batch(3, document__type_id='slides', session=session2)
            for num, sp in enumerate(session2.sessionpresentation_set.filter(document__type_id='slides'),start=1):
                sp.order = num
                sp.save()

            url = urlreverse('ietf.meeting.views.ajax_add_slides_to_session', kwargs={'session_id':session2.pk, 'num':session2.meeting.number})

            more_slides = DocumentFactory.create_batch(3, type_id='slides')

            # Insert at beginning
            r = self.client.post(url, {'order':1, 'name':more_slides[0].name})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()['success'],True)
            self.assertEqual(session2.sessionpresentation_set.get(document=more_slides[0]).order,1)
            self.assertEqual(list(session2.sessionpresentation_set.order_by('order').values_list('order',flat=True)), list(range(1,5)))

            # Insert at end
            r = self.client.post(url, {'order':5, 'name':more_slides[1].name})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()['success'],True)
            self.assertEqual(session2.sessionpresentation_set.get(document=more_slides[1]).order,5)
            self.assertEqual(list(session2.sessionpresentation_set.order_by('order').values_list('order',flat=True)), list(range(1,6)))

            # Insert in middle
            r = self.client.post(url, {'order':3, 'name':more_slides[2].name})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()['success'],True)
            self.assertEqual(session2.sessionpresentation_set.get(document=more_slides[2]).order,3)
            self.assertEqual(list(session2.sessionpresentation_set.order_by('order').values_list('order',flat=True)), list(range(1,7)))

    def test_remove_slides_from_session(self):
        for type_id in ['ietf','interim']:
            chair_role = RoleFactory(name_id='chair')
            session = SessionFactory(group=chair_role.group, meeting__date=datetime.date.today()-datetime.timedelta(days=90), meeting__type_id=type_id)
            slides = DocumentFactory(type_id='slides')
            url = urlreverse('ietf.meeting.views.ajax_remove_slides_from_session', kwargs={'session_id':session.pk, 'num':session.meeting.number})

            # Not a valid user
            r = self.client.post(url, {'oldIndex':1, 'name':slides.name })
            self.assertEqual(r.status_code, 403)
            self.assertIn('have permission', unicontent(r))

            self.client.login(username=chair_role.person.user.username, password=chair_role.person.user.username+"+password")
            
            # Past submission cutoff
            r = self.client.post(url, {'oldIndex':0, 'name':slides.name })
            self.assertEqual(r.status_code, 403)
            self.assertIn('materials cutoff', unicontent(r))

            session.meeting.date = datetime.date.today()
            session.meeting.save()

            # Invalid order
            r = self.client.post(url, {})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()['success'],False)
            self.assertIn('No data',r.json()['error'])

            r = self.client.post(url, {'garbage':'garbage'})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()['success'],False)
            self.assertIn('index is not valid',r.json()['error'])

            r = self.client.post(url, {'oldIndex':0, 'name':slides.name })
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()['success'],False)
            self.assertIn('index is not valid',r.json()['error'])

            r = self.client.post(url, {'oldIndex':'garbage', 'name':slides.name })
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()['success'],False)
            self.assertIn('index is not valid',r.json()['error'])
           
            # No matching thing to delete
            r = self.client.post(url, {'oldIndex':1, 'name':slides.name })
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()['success'],False)
            self.assertIn('index is not valid',r.json()['error'])

            session.sessionpresentation_set.create(document=slides, rev=slides.rev, order=1)

            # Bad names
            r = self.client.post(url, {'oldIndex':1})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()['success'],False)
            self.assertIn('name is not valid',r.json()['error'])

            r = self.client.post(url, {'oldIndex':1, 'name':'garbage' })
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()['success'],False)
            self.assertIn('name is not valid',r.json()['error'])

            slides2 = DocumentFactory(type_id='slides')

            # index/name mismatch
            r = self.client.post(url, {'oldIndex':1, 'name':slides2.name })
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()['success'],False)
            self.assertIn('SessionPresentation not found',r.json()['error'])

            session.sessionpresentation_set.create(document=slides2, rev=slides2.rev, order=2)
            r = self.client.post(url, {'oldIndex':1, 'name':slides2.name })
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()['success'],False)
            self.assertIn('Name does not match index',r.json()['error'])

            # valid removal
            r = self.client.post(url, {'oldIndex':1, 'name':slides.name })
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()['success'],True)
            self.assertEqual(session.sessionpresentation_set.count(),1)

            session2 = SessionFactory(group=session.group, meeting=session.meeting)
            sp_list = SessionPresentationFactory.create_batch(5, document__type_id='slides', session=session2)
            for num, sp in enumerate(session2.sessionpresentation_set.filter(document__type_id='slides'),start=1):
                sp.order = num
                sp.save()

            url = urlreverse('ietf.meeting.views.ajax_remove_slides_from_session', kwargs={'session_id':session2.pk, 'num':session2.meeting.number})

            # delete at first of list
            r = self.client.post(url, {'oldIndex':1, 'name':sp_list[0].document.name })
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()['success'],True)
            self.assertFalse(session2.sessionpresentation_set.filter(pk=sp_list[0].pk).exists())
            self.assertEqual(list(session2.sessionpresentation_set.order_by('order').values_list('order',flat=True)), list(range(1,5)))

            # delete in middle of list
            r = self.client.post(url, {'oldIndex':4, 'name':sp_list[4].document.name })
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()['success'],True)
            self.assertFalse(session2.sessionpresentation_set.filter(pk=sp_list[4].pk).exists())
            self.assertEqual(list(session2.sessionpresentation_set.order_by('order').values_list('order',flat=True)), list(range(1,4)))

            # delete at end of list
            r = self.client.post(url, {'oldIndex':2, 'name':sp_list[2].document.name })
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()['success'],True)
            self.assertFalse(session2.sessionpresentation_set.filter(pk=sp_list[2].pk).exists())
            self.assertEqual(list(session2.sessionpresentation_set.order_by('order').values_list('order',flat=True)), list(range(1,3)))


    def test_reorder_slides_in_session(self):
        chair_role = RoleFactory(name_id='chair')
        session = SessionFactory(group=chair_role.group, meeting__date=datetime.date.today()-datetime.timedelta(days=90))
        sp_list = SessionPresentationFactory.create_batch(5, document__type_id='slides', session=session)
        for num, sp in enumerate(sp_list, start=1):
            sp.order = num
            sp.save()
        url = urlreverse('ietf.meeting.views.ajax_reorder_slides_in_session', kwargs={'session_id':session.pk, 'num':session.meeting.number})

        for type_id in ['ietf','interim']:
            
            session.meeting.type_id = type_id
            session.meeting.date = datetime.date.today()-datetime.timedelta(days=90)
            session.meeting.save()

            # Not a valid user
            r = self.client.post(url, {'oldIndex':1, 'newIndex':2 })
            self.assertEqual(r.status_code, 403)
            self.assertIn('have permission', unicontent(r))

            self.client.login(username=chair_role.person.user.username, password=chair_role.person.user.username+"+password")

            # Past submission cutoff
            r = self.client.post(url, {'oldIndex':1, 'newIndex':2 })
            self.assertEqual(r.status_code, 403)
            self.assertIn('materials cutoff', unicontent(r))

            session.meeting.date = datetime.date.today()
            session.meeting.save()

            # Bad index values
            r = self.client.post(url, {'oldIndex':0, 'newIndex':2 })
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()['success'],False)
            self.assertIn('index is not valid',r.json()['error'])

            r = self.client.post(url, {'oldIndex':2, 'newIndex':6 })
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()['success'],False)
            self.assertIn('index is not valid',r.json()['error'])

            r = self.client.post(url, {'oldIndex':2, 'newIndex':2 })
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()['success'],False)
            self.assertIn('index is not valid',r.json()['error'])

            # Move from beginning
            r = self.client.post(url, {'oldIndex':1, 'newIndex':3})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()['success'],True)
            self.assertEqual(list(session.sessionpresentation_set.order_by('order').values_list('pk',flat=True)),[2,3,1,4,5])

            # Move to beginning
            r = self.client.post(url, {'oldIndex':3, 'newIndex':1})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()['success'],True)
            self.assertEqual(list(session.sessionpresentation_set.order_by('order').values_list('pk',flat=True)),[1,2,3,4,5])
            
            # Move from end
            r = self.client.post(url, {'oldIndex':5, 'newIndex':3})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()['success'],True)
            self.assertEqual(list(session.sessionpresentation_set.order_by('order').values_list('pk',flat=True)),[1,2,5,3,4])

            # Move to end
            r = self.client.post(url, {'oldIndex':3, 'newIndex':5})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()['success'],True)
            self.assertEqual(list(session.sessionpresentation_set.order_by('order').values_list('pk',flat=True)),[1,2,3,4,5])

            # Move beginning to end
            r = self.client.post(url, {'oldIndex':1, 'newIndex':5})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()['success'],True)
            self.assertEqual(list(session.sessionpresentation_set.order_by('order').values_list('pk',flat=True)),[2,3,4,5,1])

            # Move middle to middle 
            r = self.client.post(url, {'oldIndex':3, 'newIndex':4})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()['success'],True)
            self.assertEqual(list(session.sessionpresentation_set.order_by('order').values_list('pk',flat=True)),[2,3,5,4,1])

            r = self.client.post(url, {'oldIndex':3, 'newIndex':2})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()['success'],True)
            self.assertEqual(list(session.sessionpresentation_set.order_by('order').values_list('pk',flat=True)),[2,5,3,4,1])

            # Reset for next iteration in the loop
            session.sessionpresentation_set.update(order=F('pk'))
            self.client.logout()


    def test_slide_order_reconditioning(self):
        chair_role = RoleFactory(name_id='chair')
        session = SessionFactory(group=chair_role.group, meeting__date=datetime.date.today()-datetime.timedelta(days=90))
        sp_list = SessionPresentationFactory.create_batch(5, document__type_id='slides', session=session)
        for num, sp in enumerate(sp_list, start=1):
            sp.order = 2*num
            sp.save()

        try:
            condition_slide_order(session)
        except AssertionError:
            pass

        self.assertEqual(list(session.sessionpresentation_set.order_by('order').values_list('order',flat=True)),list(range(1,6)))


class EditTests(TestCase):
    """Test schedule edit operations"""
    def setUp(self):
        super().setUp()
        # make sure we have the colors of the area
        from ietf.group.colors import fg_group_colors, bg_group_colors
        area_upper = "FARFUT"
        fg_group_colors[area_upper] = "#333"
        bg_group_colors[area_upper] = "#aaa"

    def test_official_record_schedule_is_read_only(self):
        def _set_date_offset_and_retrieve_page(meeting, days_offset, client):
            meeting.date = datetime.date.today() + datetime.timedelta(days=days_offset)
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
        self.assertTrue(q("""em:contains("You can't edit this schedule")"""))
        self.assertTrue(q("""em:contains("This is the official schedule for a meeting in the past")"""))

        # 2) An ongoing meeting
        #######################################################
        r, q = _set_date_offset_and_retrieve_page(meeting,
                                                  0, # Meeting starts today
                                                  self.client)
        self.assertFalse(q("""em:contains("You can't edit this schedule")"""))
        self.assertFalse(q("""em:contains("This is the official schedule for a meeting in the past")"""))

        # 3) A meeting in the future
        #######################################################
        r, q = _set_date_offset_and_retrieve_page(meeting,
                                                  7, # Meeting starts next week
                                                  self.client)
        self.assertFalse(q("""em:contains("You can't edit this schedule")"""))
        self.assertFalse(q("""em:contains("This is the official schedule for a meeting in the past")"""))

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
                                                time=datetime.datetime.combine(meeting.date + datetime.timedelta(days=2), datetime.time(9, 30)))

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
            self.assertEqual(constraints.eq(0).find(".fa-user-o").parent().text(), "1") # 1 person in the constraint
            self.assertEqual(constraints.eq(1).attr("data-sessions"), str(s_other.pk))
            self.assertEqual(constraints.eq(1).find(".encircled").text(), "1" if s_other == s2 else "-1")
            self.assertEqual(constraints.eq(2).attr("data-sessions"), str(s_other.pk))
            self.assertEqual(constraints.eq(2).find(".encircled").text(), "AD")

            # session info for the panel
            self.assertIn(str(round(s.requested_duration.total_seconds() / 60.0 / 60, 1)), e.find(".session-info .title").text())

            event = SchedulingEvent.objects.filter(session=s).order_by("id").first()
            if event:
                self.assertTrue(e.find("div:contains(\"{}\")".format(event.by.plain_name())))

            if s.comments:
                self.assertIn(s.comments, e.find(".comments").text())

        formatted_constraints1 = q("#session{} .session-info .formatted-constraints > *".format(s1.pk))
        self.assertIn(s2.group.acronym, formatted_constraints1.eq(0).html())
        self.assertIn(p.name, formatted_constraints1.eq(1).html())

        formatted_constraints2 = q("#session{} .session-info .formatted-constraints > *".format(s2.pk))
        self.assertIn(p.name, formatted_constraints2.eq(0).html())

        self.assertEqual(len(q("#session{}.readonly".format(base_session.pk))), 1)

        self.assertTrue(q("em:contains(\"You can't edit this schedule\")"))

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
        self.assertEqual(test_timeslot.time, datetime.datetime.combine(meeting.date, datetime.time(8, 30)))
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
        self.assertEqual(test_timeslot.time, datetime.datetime.combine(meeting.date, datetime.time(9, 30)))
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
        chair_conf_label = b'<i class="fa fa-gavel"/>'  # result of etree.tostring(etree.fromstring(editor_label))
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
        self.assertFormError(r, 'form', 'name', 'Enter a valid value.')
        self.assertEqual(meeting.schedule_set.count(), orig_schedule_count, 'Schedule should not be created')

        r = self.client.post(url, {
            'name': "/invalid/chars/",
            'public': "on",
            'notes': "Name too long",
            'base': meeting.schedule.base_id,
        })
        self.assertEqual(r.status_code, 200)
        self.assertFormError(r, 'form', 'name', 'Enter a valid value.')
        self.assertEqual(meeting.schedule_set.count(), orig_schedule_count, 'Schedule should not be created')

        # Non-ASCII alphanumeric characters
        r = self.client.post(url, {
            'name': "f\u00E9ling",
            'public': "on",
            'notes': "Name too long",
            'base': meeting.schedule.base_id,
        })
        self.assertEqual(r.status_code, 200)
        self.assertFormError(r, 'form', 'name', 'Enter a valid value.')
        self.assertEqual(meeting.schedule_set.count(), orig_schedule_count, 'Schedule should not be created')

    def test_edit_session(self):
        session = SessionFactory(meeting__type_id='ietf', group__type_id='team')  # type determines allowed session purposes
        self.client.login(username='secretary', password='secretary+password')
        url = urlreverse('ietf.meeting.views.edit_session', kwargs={'session_id': session.pk})
        r = self.client.get(url)
        self.assertContains(r, 'Edit session', status_code=200)
        r = self.client.post(url, {
            'name': 'this is a name',
            'short': 'tian',
            'purpose': 'coding',
            'type': 'other',
            'requested_duration': '3600',
            'on_agenda': True,
            'remote_instructions': 'Do this do that',
            'attendees': '103',
            'comments': 'So much to say',
        })
        self.assertNoFormPostErrors(r)
        self.assertRedirects(r, urlreverse('ietf.meeting.views.edit_meeting_schedule',
                                           kwargs={'num': session.meeting.number}))
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

class SessionDetailsTests(TestCase):

    def test_session_details(self):

        group = GroupFactory.create(type_id='wg',state_id='active')
        session = SessionFactory.create(meeting__type_id='ietf',group=group, meeting__date=datetime.date.today()+datetime.timedelta(days=90))
        SessionPresentationFactory.create(session=session,document__type_id='draft',rev=None)
        SessionPresentationFactory.create(session=session,document__type_id='minutes')
        SessionPresentationFactory.create(session=session,document__type_id='slides')
        SessionPresentationFactory.create(session=session,document__type_id='agenda')

        url = urlreverse('ietf.meeting.views.session_details', kwargs=dict(num=session.meeting.number, acronym=group.acronym))
        r = self.client.get(url)
        self.assertTrue(all([x in unicontent(r) for x in ('slides','agenda','minutes','draft')]))
        self.assertNotContains(r, 'deleted')

        q = PyQuery(r.content)
        self.assertTrue(q('h2#session_%s div#session-buttons-%s' % (session.id, session.id)),
                               'Session detail page does not contain session tool buttons') 
        self.assertFalse(q('h2#session_%s div#session-buttons-%s span.fa-arrows-alt' % (session.id, session.id)), 
                         'The session detail page is incorrectly showing the "Show meeting materials" button')

    def test_session_details_past_interim(self):
        group = GroupFactory.create(type_id='wg',state_id='active')
        chair = RoleFactory(name_id='chair',group=group)
        session = SessionFactory.create(meeting__type_id='interim',group=group, meeting__date=datetime.date.today()-datetime.timedelta(days=90))
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
        session = SessionFactory.create(meeting__type_id='ietf',group=group, meeting__date=datetime.date.today()+datetime.timedelta(days=90))
        SessionPresentationFactory.create(session=session,document__type_id='draft',rev=None)
        old_draft = session.sessionpresentation_set.filter(document__type='draft').first().document
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
        self.assertIn("Already linked:", q('form .alert-danger').text())

        self.assertEqual(1,session.sessionpresentation_set.count())
        r = self.client.post(url,dict(drafts=[new_draft.pk,]))
        self.assertTrue(r.status_code, 302)
        self.assertEqual(2,session.sessionpresentation_set.count())

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
        self.assertEqual(len(q(".schedule-diffs tr")), 3)

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
        date = datetime.date.today() + datetime.timedelta(days=30)
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
        make_interim_test_data()
        session = Session.objects.with_current_status().filter(
            meeting__type='interim', group__acronym='mars', current_status='apprw').first()
        meeting = session.meeting
        meeting.time_zone = 'America/Los_Angeles'
        meeting.save()

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
                self.assertIn(
                    '(%s to %s UTC)' % (
                        timeslot.utc_start_time().strftime('%H:%M'),timeslot.utc_end_time().strftime('%H:%M')
                    ), announcement_text)
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
        today = datetime.date.today()
        last_week = today - datetime.timedelta(days=7)
        ietf = SessionFactory(meeting__type_id='ietf',meeting__date=last_week,group__state_id='active',group__parent=GroupFactory(state_id='active'))
        SessionFactory(meeting__type_id='interim',meeting__date=last_week,status_id='canceled',group__state_id='active',group__parent=GroupFactory(state_id='active'))
        url = urlreverse('ietf.meeting.views.past')
        r = self.client.get(url)
        self.assertContains(r, 'IETF - %02d'%int(ietf.meeting.number))
        q = PyQuery(r.content)
        #id="-%s" % interim.group.acronym
        #self.assertIn('CANCELLED', q('[id*="'+id+'"]').text())
        self.assertIn('CANCELLED', q('tr>td>a>span').text())

    def do_upcoming_test(self, querystring=None, create_meeting=True):
        if create_meeting:
            make_meeting_test_data(create_interims=True)
        url = urlreverse("ietf.meeting.views.upcoming")
        if querystring is not None:
            url += '?' + querystring

        today = datetime.date.today()
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
        self.assertIn('CANCELLED', q('tr>td.text-right>span').text())

    # test_upcoming_filters_ignored removed - we _don't_ want to ignore filters now, and the test passed because it wasn't testing the filtering anyhow (which requires testing the js).

    def test_upcoming_ical(self):
        meeting = make_meeting_test_data(create_interims=True)
        populate_important_dates(meeting)
        url = urlreverse("ietf.meeting.views.upcoming_ical")
        
        r = self.client.get(url)

        self.assertEqual(r.status_code, 200)
        # Expect events 3 sessions - one for each WG and one for the IETF meeting
        assert_ical_response_is_valid(self, r,
                                      expected_event_summaries=[
                                          'ames - Asteroid Mining Equipment Standardization Group',
                                          'mars - Martian Special Interest Group',
                                          'IETF 72',
                                      ],
                                      expected_event_count=3)

    def test_upcoming_ical_filter(self):
        # Just a quick check of functionality - details tested by test_js.InterimTests
        make_meeting_test_data(create_interims=True)
        url = urlreverse("ietf.meeting.views.upcoming_ical")
        r = self.client.get(url + '?show=mars')

        self.assertEqual(r.status_code, 200)
        assert_ical_response_is_valid(self, r,
                                      expected_event_summaries=[
                                          'mars - Martian Special Interest Group',
                                          'IETF 72',
                                      ],
                                      expected_event_count=2)


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
        Group.objects.filter(type_id__in=GroupFeatures.objects.filter(has_meetings=True).values_list('type_id',flat=True), state__in=('active', 'proposed', 'bof'))
        self.assertEqual(Group.objects.filter(type_id__in=GroupFeatures.objects.filter(has_meetings=True).values_list('type_id',flat=True), state__in=('active', 'proposed', 'bof')).count(),
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
        date = datetime.date.today() + datetime.timedelta(days=30)
        time = datetime.datetime.now().time().replace(microsecond=0,second=0)
        dt = datetime.datetime.combine(date, time)
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
        date = datetime.date.today() + datetime.timedelta(days=30)
        time = datetime.datetime.now().time().replace(microsecond=0,second=0)
        dt = datetime.datetime.combine(date, time)
        duration = datetime.timedelta(hours=3)
        city = 'San Francisco'
        country = 'US'
        time_zone = 'America/Los_Angeles'
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
        date = datetime.date.today() + datetime.timedelta(days=30)
        date2 = date + datetime.timedelta(days=1)
        time = datetime.datetime.now().time().replace(microsecond=0,second=0)
        dt = datetime.datetime.combine(date, time)
        dt2 = datetime.datetime.combine(date2, time)
        duration = datetime.timedelta(hours=3)
        group = Group.objects.get(acronym='mars')
        city = 'San Francisco'
        country = 'US'
        time_zone = 'America/Los_Angeles'
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
        date = datetime.date.today() + datetime.timedelta(days=30)
        date2 = date + datetime.timedelta(days=2)
        time = datetime.datetime.now().time().replace(microsecond=0,second=0)
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
        date = datetime.date.today()+datetime.timedelta(days=15)

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
        date = datetime.date.today() + datetime.timedelta(days=30)
        if (date.month, date.day) == (12, 31):
            # Avoid date and date2 in separate years
            # (otherwise the test will fail if run on December 1st)
            date += datetime.timedelta(days=1)
        date2 = date + datetime.timedelta(days=1)
        # ensure dates are in the same year
        if date.year != date2.year:
            date += datetime.timedelta(days=1)
            date2 += datetime.timedelta(days=1)
        time = datetime.datetime.now().time().replace(microsecond=0,second=0)
        dt = datetime.datetime.combine(date, time)
        dt2 = datetime.datetime.combine(date2, time)
        duration = datetime.timedelta(hours=3)
        group = Group.objects.get(acronym='mars')
        city = ''
        country = ''
        time_zone = 'America/Los_Angeles'
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
        make_interim_test_data()
        meeting = Session.objects.with_current_status().filter(
            meeting__type='interim', group__acronym='mars', current_status='apprw').first().meeting
        url = urlreverse('ietf.meeting.views.interim_request_details',kwargs={'number':meeting.number})
        login_testing_unauthorized(self,"secretary",url)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        start_time = meeting.session_set.first().official_timeslotassignment().timeslot.time.strftime('%H:%M')
        utc_start_time = meeting.session_set.first().official_timeslotassignment().timeslot.utc_start_time().strftime('%H:%M')
        self.assertIn(start_time, unicontent(r))
        self.assertIn(utc_start_time, unicontent(r))

    def test_interim_request_details_announcement(self):
        '''Test access to Announce / Skip Announce features'''
        make_meeting_test_data()
        date = datetime.date.today() + datetime.timedelta(days=30)
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
        self.assertEqual(len(q("a.btn:contains('Announce')")),2)

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

                cancel_meeting_btns = q("a.btn:contains('Cancel Meeting')")
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
                cancel_meeting_btns = q("a.btn:contains('Cancel Meeting')")
                self.assertEqual(len(cancel_meeting_btns), 1,
                                 'Should be exactly one cancel meeting button for user %s' % username)
                self.assertEqual(cancel_meeting_btns.eq(0).attr('href'),
                                 urlreverse('ietf.meeting.views.interim_request_cancel',
                                            kwargs={'number': meeting.number}),
                                 'Cancel meeting button points to wrong URL')

                cancel_session_btns = q("a.btn:contains('Cancel Session')")
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

        # test cancelling before announcement
        self.client.login(username="marschairman", password="marschairman+password")
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
        new_time = formset_initial['time'] + datetime.timedelta(hours=1)
        data = {'group':group.pk,
                'meeting_type':'single',
                'session_set-0-id':meeting.session_set.first().id,
                'session_set-0-date':formset_initial['date'].strftime('%Y-%m-%d'),
                'session_set-0-time':new_time.strftime('%H:%M'),
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
        self.assertEqual(timeslot.time,new_time)
        
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
        new_time = formset_initial['time'] + datetime.timedelta(hours=1)
        new_duration = formset_initial['requested_duration'] + datetime.timedelta(hours=1)
        data = {'group':group.pk,
                'meeting_type':'single',
                'session_set-0-id':meeting.session_set.first().id,
                'session_set-0-date':formset_initial['date'].strftime('%Y-%m-%d'),
                'session_set-0-time':new_time.strftime('%H:%M'),
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
        self.assertEqual(timeslot.time,new_time)
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
        date = datetime.datetime.today() - datetime.timedelta(days=10)
        meeting = make_interim_meeting(group=group, date=date, status='sched')
        length_before = len(outbox)
        send_interim_minutes_reminder(meeting=meeting)
        self.assertEqual(len(outbox),length_before+1)
        self.assertIn('Action Required: Minutes', outbox[-1]['Subject'])


    def test_group_ical(self):
        make_interim_test_data()
        meeting = Meeting.objects.filter(type='interim', session__group__acronym='mars').first()
        s1 = Session.objects.filter(meeting=meeting, group__acronym="mars").first()
        a1 = s1.official_timeslotassignment()
        t1 = a1.timeslot
        # Create an extra session
        t2 = TimeSlotFactory.create(meeting=meeting, time=datetime.datetime.combine(meeting.date, datetime.time(11, 30)))
        s2 = SessionFactory.create(meeting=meeting, group=s1.group, add_to_schedule=False)
        SchedTimeSessAssignment.objects.create(timeslot=t2, session=s2, schedule=meeting.schedule)
        #
        url = urlreverse('ietf.meeting.views.agenda_ical', kwargs={'num':meeting.number, 'acronym':s1.group.acronym, })
        r = self.client.get(url)
        self.assertEqual(r.get('Content-Type'), "text/calendar")
        self.assertContains(r, 'BEGIN:VEVENT')
        self.assertEqual(r.content.count(b'UID'), 2)
        self.assertContains(r, 'SUMMARY:mars - Martian Special Interest Group')
        self.assertContains(r, t1.time.strftime('%Y%m%dT%H%M%S'))
        self.assertContains(r, t2.time.strftime('%Y%m%dT%H%M%S'))
        self.assertContains(r, 'END:VEVENT')
        #
        url = urlreverse('ietf.meeting.views.agenda_ical', kwargs={'num':meeting.number, 'session_id':s1.id, })
        r = self.client.get(url)
        self.assertEqual(r.get('Content-Type'), "text/calendar")
        self.assertContains(r, 'BEGIN:VEVENT')
        self.assertEqual(r.content.count(b'UID'), 1)
        self.assertContains(r, 'SUMMARY:mars - Martian Special Interest Group')
        self.assertContains(r, t1.time.strftime('%Y%m%dT%H%M%S'))
        self.assertNotContains(r, t2.time.strftime('%Y%m%dT%H%M%S'))
        self.assertContains(r, 'END:VEVENT')


class AjaxTests(TestCase):
    def test_ajax_get_utc(self):
        # test bad queries
        url = urlreverse('ietf.meeting.views.ajax_get_utc') + "?date=2016-1-1&time=badtime&timezone=UTC"
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["error"], True)
        url = urlreverse('ietf.meeting.views.ajax_get_utc') + "?date=2016-1-1&time=25:99&timezone=UTC"
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["error"], True)
        url = urlreverse('ietf.meeting.views.ajax_get_utc') + "?date=2016-1-1&time=10:00am&timezone=UTC"
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["error"], True)
        # test good query
        url = urlreverse('ietf.meeting.views.ajax_get_utc') + "?date=2016-1-1&time=12:00&timezone=America/Los_Angeles"
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn('timezone', data)
        self.assertIn('time', data)
        self.assertIn('utc', data)
        self.assertNotIn('error', data)
        self.assertEqual(data['utc'], '20:00')

class FloorPlanTests(TestCase):
    def test_floor_plan_page(self):
        make_meeting_test_data()
        meeting = Meeting.objects.filter(type_id='ietf').order_by('id').last()
        floorplan = FloorPlanFactory.create(meeting=meeting)

        url = urlreverse('ietf.meeting.views.floor_plan')
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        url = urlreverse('ietf.meeting.views.floor_plan', kwargs={'floor': xslugify(floorplan.name)} )
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

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
    @override_settings(STATS_REGISTRATION_ATTENDEES_JSON_URL='https://ietf.example.com/{number}')
    @requests_mock.Mocker()
    def test_finalize_proceedings(self, mock):
        make_meeting_test_data()
        meeting = Meeting.objects.filter(type_id='ietf').order_by('id').last()
        meeting.session_set.filter(group__acronym='mars').first().sessionpresentation_set.create(document=Document.objects.filter(type='draft').first(),rev=None)
        mock.get(
            settings.STATS_REGISTRATION_ATTENDEES_JSON_URL.format(number=meeting.number),
            text=json.dumps([{"LastName": "Smith", "FirstName": "John", "Company": "ABC", "Country": "US"}]),
        )

        url = urlreverse('ietf.meeting.views.finalize_proceedings',kwargs={'num':meeting.number})
        login_testing_unauthorized(self,"secretary",url)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        self.assertEqual(meeting.proceedings_final,False)
        self.assertEqual(meeting.session_set.filter(group__acronym="mars").first().sessionpresentation_set.filter(document__type="draft").first().rev,None)
        r = self.client.post(url,{'finalize':1})
        self.assertEqual(r.status_code, 302)
        meeting = Meeting.objects.get(pk=meeting.pk)
        self.assertEqual(meeting.proceedings_final,True)
        self.assertEqual(meeting.session_set.filter(group__acronym="mars").first().sessionpresentation_set.filter(document__type="draft").first().rev,'00')
 
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
        self.assertFalse(session.sessionpresentation_set.exists())
        test_file = StringIO('%PDF-1.4\n%âãÏÓ\nthis is some text for a test')
        test_file.name = "not_really.pdf"
        r = self.client.post(url,dict(file=test_file))
        self.assertEqual(r.status_code, 302)
        bs_doc = session.sessionpresentation_set.filter(document__type_id='bluesheets').first().document
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
        self.assertFalse(session.sessionpresentation_set.exists())
        test_file = StringIO('%PDF-1.4\n%âãÏÓ\nthis is some text for a test')
        test_file.name = "not_really.pdf"
        r = self.client.post(url,dict(file=test_file))
        self.assertEqual(r.status_code, 302)
        bs_doc = session.sessionpresentation_set.filter(document__type_id='bluesheets').first().document
        self.assertEqual(bs_doc.rev,'00')

    def test_upload_bluesheets_interim_chair_access(self):
        make_meeting_test_data()
        mars = Group.objects.get(acronym='mars')
        session=SessionFactory(meeting__type_id='interim',group=mars, meeting__date = datetime.date.today())
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
            self.assertFalse(session.sessionpresentation_set.exists())
            self.assertFalse(q('form input[type="checkbox"]'))
    
            session2 = SessionFactory(meeting=session.meeting,group=session.group)
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)
            q = PyQuery(r.content)
            self.assertTrue(q('form input[type="checkbox"]'))
    
            test_file = BytesIO(b'this is some text for a test')
            test_file.name = "not_really.json"
            r = self.client.post(url,dict(file=test_file))
            self.assertEqual(r.status_code, 200)
            q = PyQuery(r.content)
            self.assertTrue(q('form .has-error'))
    
            test_file = BytesIO(b'this is some text for a test'*1510000)
            test_file.name = "not_really.pdf"
            r = self.client.post(url,dict(file=test_file))
            self.assertEqual(r.status_code, 200)
            q = PyQuery(r.content)
            self.assertTrue(q('form .has-error'))
    
            test_file = BytesIO(b'<html><frameset><frame src="foo.html"></frame><frame src="bar.html"></frame></frameset></html>')
            test_file.name = "not_really.html"
            r = self.client.post(url,dict(file=test_file))
            self.assertEqual(r.status_code, 200)
            q = PyQuery(r.content)
            self.assertTrue(q('form .has-error'))

            # Test html sanitization
            test_file = BytesIO(b'<html><head><title>Title</title></head><body><h1>Title</h1><section>Some text</section></body></html>')
            test_file.name = "some.html"
            r = self.client.post(url,dict(file=test_file))
            self.assertEqual(r.status_code, 302)
            doc = session.sessionpresentation_set.filter(document__type_id=doctype).first().document
            self.assertEqual(doc.rev,'00')
            text = doc.text()
            self.assertIn('Some text', text)
            self.assertNotIn('<section>', text)
            self.assertIn('charset="utf-8"', text)

            # txt upload
            test_file = BytesIO(b'This is some text for a test, with the word\nvirtual at the beginning of a line.')
            test_file.name = "some.txt"
            r = self.client.post(url,dict(file=test_file,apply_to_all=False))
            self.assertEqual(r.status_code, 302)
            doc = session.sessionpresentation_set.filter(document__type_id=doctype).first().document
            self.assertEqual(doc.rev,'01')
            self.assertFalse(session2.sessionpresentation_set.filter(document__type_id=doctype))
    
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)
            q = PyQuery(r.content)
            self.assertIn('Revise', str(q("Title")))
            test_file = BytesIO(b'this is some different text for a test')
            test_file.name = "also_some.txt"
            r = self.client.post(url,dict(file=test_file,apply_to_all=True))
            self.assertEqual(r.status_code, 302)
            doc = Document.objects.get(pk=doc.pk)
            self.assertEqual(doc.rev,'02')
            self.assertTrue(session2.sessionpresentation_set.filter(document__type_id=doctype))

            # Test bad encoding
            test_file = BytesIO('<html><h1>Title</h1><section>Some\x93text</section></html>'.encode('latin1'))
            test_file.name = "some.html"
            r = self.client.post(url,dict(file=test_file))
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
            self.assertFalse(session.sessionpresentation_set.exists())
            self.assertFalse(q('form input[type="checkbox"]'))

            test_file = BytesIO(b'this is some text for a test')
            test_file.name = "not_really.txt"
            r = self.client.post(url,dict(file=test_file,apply_to_all=False))
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
            self.assertFalse(session.sessionpresentation_set.filter(document__type_id=doctype))
            test_file = BytesIO(b'this is some text for a test')
            test_file.name = "not_really.txt"
            r = self.client.post(url,dict(file=test_file))
            self.assertEqual(r.status_code, 302)
            doc = session.sessionpresentation_set.filter(document__type_id=doctype).first().document
            self.assertEqual(doc.rev,'00')

            # Verify that we don't have dead links
            url = urlreverse('ietf.meeting.views.session_details', kwargs={'num':session.meeting.number, 'acronym': session.group.acronym})
            top = '/meeting/%s/' % session.meeting.number
            self.requests_mock.get(f'{session.notes_url()}/download', text='markdown notes')
            self.requests_mock.get(f'{session.notes_url()}/info', text=json.dumps({'title': 'title', 'updatetime': '2021-12-01T17:11:00z'}))
            self.crawl_materials(url=url, top=top)

    def test_upload_slides(self):

        session1 = SessionFactory(meeting__type_id='ietf')
        session2 = SessionFactory(meeting=session1.meeting,group=session1.group)
        url = urlreverse('ietf.meeting.views.upload_session_slides',kwargs={'num':session1.meeting.number,'session_id':session1.id})
        login_testing_unauthorized(self,"secretary",url)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertIn('Upload', str(q("title")))
        self.assertFalse(session1.sessionpresentation_set.filter(document__type_id='slides'))
        test_file = BytesIO(b'this is not really a slide')
        test_file.name = 'not_really.txt'
        r = self.client.post(url,dict(file=test_file,title='a test slide file',apply_to_all=True))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(session1.sessionpresentation_set.count(),1) 
        self.assertEqual(session2.sessionpresentation_set.count(),1) 
        sp = session2.sessionpresentation_set.first()
        self.assertEqual(sp.document.name, 'slides-%s-%s-a-test-slide-file' % (session1.meeting.number,session1.group.acronym ) )
        self.assertEqual(sp.order,1)

        url = urlreverse('ietf.meeting.views.upload_session_slides',kwargs={'num':session2.meeting.number,'session_id':session2.id})
        test_file = BytesIO(b'some other thing still not slidelike')
        test_file.name = 'also_not_really.txt'
        r = self.client.post(url,dict(file=test_file,title='a different slide file',apply_to_all=False))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(session1.sessionpresentation_set.count(),1)
        self.assertEqual(session2.sessionpresentation_set.count(),2)
        sp = session2.sessionpresentation_set.get(document__name__endswith='-a-different-slide-file')
        self.assertEqual(sp.order,2)
        self.assertEqual(sp.rev,'00')
        self.assertEqual(sp.document.rev,'00')

        url = urlreverse('ietf.meeting.views.upload_session_slides',kwargs={'num':session2.meeting.number,'session_id':session2.id,'name':session2.sessionpresentation_set.get(order=2).document.name})
        r = self.client.get(url)
        self.assertTrue(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertIn('Revise', str(q("title")))
        test_file = BytesIO(b'new content for the second slide deck')
        test_file.name = 'doesnotmatter.txt'
        r = self.client.post(url,dict(file=test_file,title='rename the presentation',apply_to_all=False))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(session1.sessionpresentation_set.count(),1)
        self.assertEqual(session2.sessionpresentation_set.count(),2)
        sp = session2.sessionpresentation_set.get(order=2)
        self.assertEqual(sp.rev,'01')
        self.assertEqual(sp.document.rev,'01')
 
    def test_upload_slide_title_bad_unicode(self):
        session1 = SessionFactory(meeting__type_id='ietf')
        url = urlreverse('ietf.meeting.views.upload_session_slides',kwargs={'num':session1.meeting.number,'session_id':session1.id})
        login_testing_unauthorized(self,"secretary",url)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertIn('Upload', str(q("title")))
        self.assertFalse(session1.sessionpresentation_set.filter(document__type_id='slides'))
        test_file = BytesIO(b'this is not really a slide')
        test_file.name = 'not_really.txt'
        r = self.client.post(url,dict(file=test_file,title='title with bad character \U0001fabc '))
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(q('form .has-error'))
        self.assertIn("Unicode BMP", q('form .has-error div').text())

    def test_remove_sessionpresentation(self):
        session = SessionFactory(meeting__type_id='ietf')
        doc = DocumentFactory(type_id='slides')
        session.sessionpresentation_set.create(document=doc)

        url = urlreverse('ietf.meeting.views.remove_sessionpresentation',kwargs={'num':session.meeting.number,'session_id':session.id,'name':'no-such-doc'})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

        url = urlreverse('ietf.meeting.views.remove_sessionpresentation',kwargs={'num':session.meeting.number,'session_id':0,'name':doc.name})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

        url = urlreverse('ietf.meeting.views.remove_sessionpresentation',kwargs={'num':session.meeting.number,'session_id':session.id,'name':doc.name})
        login_testing_unauthorized(self,"secretary",url)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        self.assertEqual(1,session.sessionpresentation_set.count())
        response = self.client.post(url,{'remove_session':''})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(0,session.sessionpresentation_set.count())
        self.assertEqual(2,doc.docevent_set.count())

    def test_propose_session_slides(self):
        for type_id in ['ietf','interim']:
            session = SessionFactory(meeting__type_id=type_id)
            chair = RoleFactory(group=session.group,name_id='chair').person
            session.meeting.importantdate_set.create(name_id='revsub',date=datetime.date.today()+datetime.timedelta(days=20))
            newperson = PersonFactory()
            
            session_overview_url = urlreverse('ietf.meeting.views.session_details',kwargs={'num':session.meeting.number,'acronym':session.group.acronym})
            propose_url = urlreverse('ietf.meeting.views.propose_session_slides', kwargs={'session_id':session.pk, 'num': session.meeting.number})    

            r = self.client.get(session_overview_url)
            self.assertEqual(r.status_code,200)
            q = PyQuery(r.content)
            self.assertFalse(q('#uploadslides'))
            self.assertFalse(q('#proposeslides'))

            self.client.login(username=newperson.user.username,password=newperson.user.username+"+password")
            r = self.client.get(session_overview_url)
            self.assertEqual(r.status_code,200)
            q = PyQuery(r.content)
            self.assertTrue(q('#proposeslides'))
            self.client.logout()

            login_testing_unauthorized(self,newperson.user.username,propose_url)
            r = self.client.get(propose_url)
            self.assertEqual(r.status_code,200)
            test_file = BytesIO(b'this is not really a slide')
            test_file.name = 'not_really.txt'
            empty_outbox()
            r = self.client.post(propose_url,dict(file=test_file,title='a test slide file',apply_to_all=True))
            self.assertEqual(r.status_code, 302)
            session = Session.objects.get(pk=session.pk)
            self.assertEqual(session.slidesubmission_set.count(),1)
            self.assertEqual(len(outbox),1)

            r = self.client.get(session_overview_url)
            self.assertEqual(r.status_code, 200)
            q = PyQuery(r.content)
            self.assertEqual(len(q('#proposedslidelist p')), 1)

            SlideSubmissionFactory(session = session)

            self.client.logout()
            self.client.login(username=chair.user.username, password=chair.user.username+"+password")
            r = self.client.get(session_overview_url)
            self.assertEqual(r.status_code, 200)
            q = PyQuery(r.content)
            self.assertEqual(len(q('#proposedslidelist p')), 2)
            self.client.logout()

    def test_disapprove_proposed_slides(self):
        submission = SlideSubmissionFactory()
        submission.session.meeting.importantdate_set.create(name_id='revsub',date=datetime.date.today()+datetime.timedelta(days=20))
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
        self.assertContains(r, "These slides have already been  rejected")

    def test_approve_proposed_slides(self):
        submission = SlideSubmissionFactory()
        session = submission.session
        session.meeting.importantdate_set.create(name_id='revsub',date=datetime.date.today()+datetime.timedelta(days=20))
        chair = RoleFactory(group=submission.session.group,name_id='chair').person
        url = urlreverse('ietf.meeting.views.approve_proposed_slides', kwargs={'slidesubmission_id':submission.pk,'num':submission.session.meeting.number})
        login_testing_unauthorized(self, chair.user.username, url)
        self.assertEqual(submission.status_id, 'pending')
        self.assertIsNone(submission.doc)
        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        r = self.client.post(url,dict(title='different title',approve='approve'))
        self.assertEqual(r.status_code,302)
        self.assertEqual(SlideSubmission.objects.filter(status__slug = 'pending').count(), 0)
        self.assertEqual(SlideSubmission.objects.filter(status__slug = 'approved').count(), 1)
        submission = SlideSubmission.objects.get(id = submission.id)
        self.assertEqual(submission.status_id, 'approved')
        self.assertIsNotNone(submission.doc)
        self.assertEqual(session.sessionpresentation_set.count(),1)
        self.assertEqual(session.sessionpresentation_set.first().document.title,'different title')
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "These slides have already been  approved")

    def test_approve_proposed_slides_multisession_apply_one(self):
        submission = SlideSubmissionFactory(session__meeting__type_id='ietf')
        session1 = submission.session
        session2 = SessionFactory(group=submission.session.group, meeting=submission.session.meeting)
        submission.session.meeting.importantdate_set.create(name_id='revsub',date=datetime.date.today()+datetime.timedelta(days=20))
        chair = RoleFactory(group=submission.session.group,name_id='chair').person
        url = urlreverse('ietf.meeting.views.approve_proposed_slides', kwargs={'slidesubmission_id':submission.pk,'num':submission.session.meeting.number})
        login_testing_unauthorized(self, chair.user.username, url)
        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        q = PyQuery(r.content)
        self.assertTrue(q('#id_apply_to_all'))
        r = self.client.post(url,dict(title='yet another title',approve='approve'))
        self.assertEqual(r.status_code,302)
        self.assertEqual(session1.sessionpresentation_set.count(),1)
        self.assertEqual(session2.sessionpresentation_set.count(),0)

    def test_approve_proposed_slides_multisession_apply_all(self):
        submission = SlideSubmissionFactory(session__meeting__type_id='ietf')
        session1 = submission.session
        session2 = SessionFactory(group=submission.session.group, meeting=submission.session.meeting)
        submission.session.meeting.importantdate_set.create(name_id='revsub',date=datetime.date.today()+datetime.timedelta(days=20))
        chair = RoleFactory(group=submission.session.group,name_id='chair').person
        url = urlreverse('ietf.meeting.views.approve_proposed_slides', kwargs={'slidesubmission_id':submission.pk,'num':submission.session.meeting.number})
        login_testing_unauthorized(self, chair.user.username, url)
        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        r = self.client.post(url,dict(title='yet another title',apply_to_all=1,approve='approve'))
        self.assertEqual(r.status_code,302)
        self.assertEqual(session1.sessionpresentation_set.count(),1)
        self.assertEqual(session2.sessionpresentation_set.count(),1)

    def test_submit_and_approve_multiple_versions(self):
        session = SessionFactory(meeting__type_id='ietf')
        chair = RoleFactory(group=session.group,name_id='chair').person
        session.meeting.importantdate_set.create(name_id='revsub',date=datetime.date.today()+datetime.timedelta(days=20))
        newperson = PersonFactory()
        
        propose_url = urlreverse('ietf.meeting.views.propose_session_slides', kwargs={'session_id':session.pk, 'num': session.meeting.number})          
        
        login_testing_unauthorized(self,newperson.user.username,propose_url)
        test_file = BytesIO(b'this is not really a slide')
        test_file.name = 'not_really.txt'
        r = self.client.post(propose_url,dict(file=test_file,title='a test slide file',apply_to_all=True))
        self.assertEqual(r.status_code, 302)
        self.client.logout()

        submission = SlideSubmission.objects.get(session = session)

        approve_url = urlreverse('ietf.meeting.views.approve_proposed_slides', kwargs={'slidesubmission_id':submission.pk,'num':submission.session.meeting.number})
        login_testing_unauthorized(self, chair.user.username, approve_url)
        r = self.client.post(approve_url,dict(title=submission.title,approve='approve'))
        self.assertEqual(r.status_code,302)
        self.client.logout()

        self.assertEqual(session.sessionpresentation_set.first().document.rev,'00')

        login_testing_unauthorized(self,newperson.user.username,propose_url)
        test_file = BytesIO(b'this is not really a slide, but it is another version of it')
        test_file.name = 'not_really.txt'
        r = self.client.post(propose_url,dict(file=test_file,title='a test slide file',apply_to_all=True))
        self.assertEqual(r.status_code, 302)

        test_file = BytesIO(b'this is not really a slide, but it is third version of it')
        test_file.name = 'not_really.txt'
        r = self.client.post(propose_url,dict(file=test_file,title='a test slide file',apply_to_all=True))
        self.assertEqual(r.status_code, 302)
        self.client.logout()       

        (first_submission, second_submission) = SlideSubmission.objects.filter(session=session, status__slug = 'pending').order_by('id')

        approve_url = urlreverse('ietf.meeting.views.approve_proposed_slides', kwargs={'slidesubmission_id':second_submission.pk,'num':second_submission.session.meeting.number})
        login_testing_unauthorized(self, chair.user.username, approve_url)
        r = self.client.post(approve_url,dict(title=submission.title,approve='approve'))
        self.assertEqual(r.status_code,302)

        disapprove_url = urlreverse('ietf.meeting.views.approve_proposed_slides', kwargs={'slidesubmission_id':first_submission.pk,'num':first_submission.session.meeting.number})
        r = self.client.post(disapprove_url,dict(title='some title',disapprove="disapprove"))
        self.assertEqual(r.status_code,302)
        self.client.logout()

        self.assertEqual(SlideSubmission.objects.filter(status__slug = 'pending').count(),0)
        self.assertEqual(SlideSubmission.objects.filter(status__slug = 'rejected').count(),1)
        self.assertEqual(session.sessionpresentation_set.first().document.rev,'01')
        path = os.path.join(submission.session.meeting.get_materials_path(),'slides')
        filename = os.path.join(path,session.sessionpresentation_set.first().document.name+'-01.txt')
        self.assertTrue(os.path.exists(filename))
        contents = io.open(filename,'r').read()
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
        r = self.client.post(url, {'markdown_text': 'original markdown text'})  # create a rev
        self.assertEqual(r.status_code, 302)
        with requests_mock.Mocker() as mock:
            mock.get(f'https://notes.ietf.org/{self.session.notes_id()}/download', text='original markdown text')
            mock.get(f'https://notes.ietf.org/{self.session.notes_id()}/info',
                     text=json.dumps({"title": "title", "updatetime": "2021-12-02T11:22:33z"}))
            r = self.client.get(url)  # try to import the same text
            self.assertContains(r, "This document is identical", status_code=200)
            q = PyQuery(r.content)
            self.assertEqual(len(q('button:disabled[type="submit"]')), 1)
            self.assertEqual(len(q('button:not(:disabled)[type="submit"]')), 0)

    def test_handles_missing_previous_revision_file(self):
        """Should still allow import if the file for the previous revision is missing"""
        url = urlreverse('ietf.meeting.views.import_session_minutes',
                         kwargs={'num': self.meeting.number, 'session_id': self.session.pk})

        self.client.login(username='secretary', password='secretary+password')
        r = self.client.post(url, {'markdown_text': 'original markdown text'})  # create a rev
        # remove the file uploaded for the first rev
        minutes_docs = self.session.sessionpresentation_set.filter(document__type='minutes')
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

    def test_meeting_requests(self):
        meeting = MeetingFactory(type_id='ietf')
        area = GroupFactory(type_id='area')
        requested_session = SessionFactory(meeting=meeting,group__parent=area,status_id='schedw',add_to_schedule=False)
        conflicting_session = SessionFactory(meeting=meeting,group__parent=area,status_id='schedw',add_to_schedule=False)
        ConstraintFactory(name_id='key_participant',meeting=meeting,source=requested_session.group,target=conflicting_session.group)
        not_meeting = SessionFactory(meeting=meeting,group__parent=area,status_id='notmeet',add_to_schedule=False)
        url = urlreverse('ietf.meeting.views.meeting_requests',kwargs={'num':meeting.number})
        r = self.client.get(url)
        self.assertContains(r, requested_session.group.acronym)
        self.assertContains(r, not_meeting.group.acronym)
        self.assertContains(r, requested_session.constraints().first().name)
        self.assertContains(r, conflicting_session.group.acronym)

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
        date = datetime.date.today() + datetime.timedelta(days=30+meeting_count)
        time = datetime.datetime.now().time().replace(microsecond=0,second=0)
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
                self.client.login(username=role.person.user.username, password=role.person.user.username+'+password')
                r = self.client.get(url)
                self.assertEqual(r.status_code, 403)
                self.client.logout()

    def test_appears_on_upcoming(self):
        url = urlreverse('ietf.meeting.views.upcoming')
        sessions=[]
        for gf in GroupFeatures.objects.filter(has_meetings=True):
            session = SessionFactory(
                group__type_id = gf.type_id,
                meeting__type_id='interim', 
                meeting__date = datetime.datetime.today()+datetime.timedelta(days=30),
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
            meeting_date = datetime.datetime.today() + datetime.timedelta(days=30)
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
            meeting_date = datetime.datetime.today() + datetime.timedelta(days=30)
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
    def test_agenda_width_scale_filter(self):
        """Test calculation of UI column width by agenda_width_scale filter"""
        template = Template('{% load agenda_filter_tags %}{{ categories|agenda_width_scale:spacing }}')

        # Should get '1' as min value when input is empty
        context = Context({'categories': [], 'spacing': 7})
        self.assertEqual(template.render(context), '1')

        # 3 columns, no spacers
        context = Context({'categories': [range(3)], 'spacing': 7})
        self.assertEqual(template.render(context), '21')

        # 6 columns, 1 spacer
        context = Context({'categories': [range(3), range(3)], 'spacing': 7})
        self.assertEqual(template.render(context), '43')

        # 10 columns, 2 spacers
        context = Context({'categories': [range(3), range(3), range(4)], 'spacing': 7})
        self.assertEqual(template.render(context), '72')

        # 10 columns, 2 spacers, different spacer scale
        context = Context({'categories': [range(3), range(3), range(4)], 'spacing': 5})
        self.assertEqual(template.render(context), '52')

    def test_agenda_filter_template(self):
        """Test rendering of input data by the agenda filter template"""
        def _assert_button_ok(btn, expected_label=None, expected_filter_item=None, 
                              expected_filter_keywords=None):
            """Test button properties"""
            self.assertIn(btn.text(), expected_label)
            self.assertEqual(btn.attr('data-filter-item'), expected_filter_item)
            self.assertEqual(btn.attr('data-filter-keywords'), expected_filter_keywords)

        template = Template('{% include "meeting/agenda_filter.html" %}')

        # Test with/without custom button text
        context = Context({'customize_button_text': None, 'filter_categories': []})
        q = PyQuery(template.render(context))
        self.assertIn('Customize...', q('h4.panel-title').text())
        self.assertEqual(q('table'), [])  # no filter_categories, so no button table

        context['customize_button_text'] = 'My custom text...'
        q = PyQuery(template.render(context))
        self.assertIn(context['customize_button_text'], q('h4.panel-title').text())
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
        self.assertIn(context['customize_button_text'], q('h4.panel-title').text())
        self.assertNotEqual(q('table'), [])  # should now have table
        
        # Check that buttons are present for the expected things
        header_row = q('thead tr')
        self.assertEqual(len(header_row), 1)
        button_row = q('tbody tr')
        self.assertEqual(len(button_row), 1)

        # verify correct headers
        header_cells = header_row('th')
        self.assertEqual(len(header_cells), 6)  # 4 columns and 2 spacers
        header_buttons = header_cells('button.pickview')
        self.assertEqual(len(header_buttons), 3)  # last column has blank header, so only 3
        
        # verify buttons
        button_cells = button_row('td')
    
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
        # Skip column index 2, which is a spacer column
        _assert_button_ok(header_cells.eq(3)('button.keyword2'),
                          expected_label='area2',
                          expected_filter_item='keyword2')

        buttons = button_cells.eq(3)('button.pickview')
        self.assertEqual(len(buttons), 2)  # two children
        _assert_button_ok(buttons('.keyword20'),
                          expected_label='child20',
                          expected_filter_item='keyword20',
                          expected_filter_keywords='keyword2,bof')
        _assert_button_ok(buttons('.keyword21'),
                          expected_label='child21',
                          expected_filter_item='keyword21',
                          expected_filter_keywords='keyword2')

        # area3 (no label for this one)
        # Skip column index 4, which is a spacer column
        self.assertEqual([], header_cells.eq(5)('button'))  # no header button
        buttons = button_cells.eq(5)('button.pickview')
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

    def test_proceedings(self):
        """Proceedings should be displayed correctly"""
        meeting = make_meeting_test_data(meeting=MeetingFactory(type_id='ietf', number='100'))
        session = Session.objects.filter(meeting=meeting, group__acronym="mars").first()
        GroupEventFactory(group=session.group,type='status_update')
        SessionPresentationFactory(document__type_id='recording',session=session)
        SessionPresentationFactory(document__type_id='recording',session=session,document__title="Audio recording for tests")

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
                urlreverse('ietf.meeting.views.proceedings_progress_report', kwargs=dict(num=meeting.number)))
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

    def test_proceedings_no_agenda(self):
        # Meeting number must be larger than the last special-cased proceedings (currently 96)
        meeting = MeetingFactory(type_id='ietf',populate_schedule=False,date=datetime.date.today(), number='100')
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

    @override_settings(STATS_REGISTRATION_ATTENDEES_JSON_URL='https://ietf.example.com/{number}')
    @requests_mock.Mocker()
    def test_proceedings_attendees(self, mock):
        make_meeting_test_data()
        meeting = MeetingFactory(type_id='ietf', date=datetime.date(2016,7,14), number="97")
        mock.get(
            settings.STATS_REGISTRATION_ATTENDEES_JSON_URL.format(number=meeting.number),
            text=json.dumps([{"LastName": "Smith", "FirstName": "John", "Company": "ABC", "Country": "US"}]),
        )
        finalize(meeting)
        url = urlreverse('ietf.meeting.views.proceedings_attendees',kwargs={'num':97})
        response = self.client.get(url)
        self.assertContains(response, 'Attendee List')
        q = PyQuery(response.content)
        self.assertEqual(1,len(q("#id_attendees tbody tr")))

    @override_settings(STATS_REGISTRATION_ATTENDEES_JSON_URL='https://ietf.example.com/{number}')
    @requests_mock.Mocker()
    def test_proceedings_overview(self, mock):
        '''Test proceedings IETF Overview page.
        Note: old meetings aren't supported so need to add a new meeting then test.
        '''
        make_meeting_test_data()
        meeting = MeetingFactory(type_id='ietf', date=datetime.date(2016,7,14), number="97")
        mock.get(
            settings.STATS_REGISTRATION_ATTENDEES_JSON_URL.format(number=meeting.number),
            text=json.dumps([{"LastName": "Smith", "FirstName": "John", "Company": "ABC", "Country": "US"}]),
        )
        finalize(meeting)
        url = urlreverse('ietf.meeting.views.proceedings_overview',kwargs={'num':97})
        response = self.client.get(url)
        self.assertContains(response, 'The Internet Engineering Task Force')

    def test_proceedings_progress_report(self):
        make_meeting_test_data()
        MeetingFactory(type_id='ietf', date=datetime.date(2016,4,3), number="96")
        MeetingFactory(type_id='ietf', date=datetime.date(2016,7,14), number="97")

        url = urlreverse('ietf.meeting.views.proceedings_progress_report',kwargs={'num':97})
        response = self.client.get(url)
        self.assertContains(response, 'Progress Report')

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
        return MeetingFactory(type_id='ietf', number='123', date=datetime.date.today())

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
            mat = self.upload_proceedings_material_test(
                meeting,
                mat_type,
                {'file': self._proceedings_file(), 'external_url': ''},
            )
            self.assertEqual(mat.get_href(), f'{mat.document.name}:00')

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
        r = self.client.post(pm_doc_url, {'file': self._proceedings_file(), 'external_url': ''})
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
        r = self.client.post(pm_url_url, {'file': self._proceedings_file(), 'external_url': ''})
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