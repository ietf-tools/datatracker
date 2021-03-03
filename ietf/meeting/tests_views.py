# Copyright The IETF Trust 2009-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import datetime
import io
import json
import os
import random
import re
import shutil

from unittest import skipIf
from mock import patch
from pyquery import PyQuery
from io import StringIO, BytesIO
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urlsplit

from django.urls import reverse as urlreverse
from django.conf import settings
from django.contrib.auth.models import User
from django.test import Client, override_settings
from django.db.models import F
from django.http import QueryDict
from django.template import Context, Template

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
from ietf.meeting.views import session_draft_list, parse_agenda_filter_params
from ietf.name.models import SessionStatusName, ImportantDateName, RoleName
from ietf.utils.decorators import skip_coverage
from ietf.utils.mail import outbox, empty_outbox, get_payload_text
from ietf.utils.test_utils import TestCase, login_testing_unauthorized, unicontent
from ietf.utils.text import xslugify

from ietf.person.factories import PersonFactory
from ietf.group.factories import GroupFactory, GroupEventFactory, RoleFactory
from ietf.meeting.factories import ( SessionFactory, SessionPresentationFactory, ScheduleFactory,
    MeetingFactory, FloorPlanFactory, TimeSlotFactory, SlideSubmissionFactory )
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


class MeetingTests(TestCase):
    def setUp(self):
        self.materials_dir = self.tempdir('materials')
        self.id_dir = self.tempdir('id')
        self.archive_dir = self.tempdir('id-archive')
        #
        os.mkdir(os.path.join(self.archive_dir, "unknown_ids"))
        os.mkdir(os.path.join(self.archive_dir, "deleted_tombstones"))
        os.mkdir(os.path.join(self.archive_dir, "expired_without_tombstone"))
        #
        self.saved_agenda_path = settings.AGENDA_PATH
        self.saved_id_dir = settings.INTERNET_DRAFT_PATH
        self.saved_archive_dir = settings.INTERNET_DRAFT_ARCHIVE_DIR
        #
        settings.AGENDA_PATH = self.materials_dir
        settings.INTERNET_DRAFT_PATH = self.id_dir
        settings.INTERNET_DRAFT_ARCHIVE_DIR = self.archive_dir


    def tearDown(self):
        shutil.rmtree(self.id_dir)
        shutil.rmtree(self.archive_dir)
        shutil.rmtree(self.materials_dir)
        #
        settings.AGENDA_PATH = self.saved_agenda_path
        settings.INTERNET_DRAFT_PATH = self.saved_id_dir
        settings.INTERNET_DRAFT_ARCHIVE_DIR = self.saved_archive_dir


    def write_materials_file(self, meeting, doc, content):
        path = os.path.join(self.materials_dir, "%s/%s/%s" % (meeting.number, doc.type_id, doc.uploaded_filename))

        dirname = os.path.dirname(path)
        if not os.path.exists(dirname):
            os.makedirs(dirname)

        with io.open(path, "w") as f:
            f.write(content)

    def write_materials_files(self, meeting, session):

        draft = Document.objects.filter(type="draft", group=session.group).first()

        self.write_materials_file(meeting, session.materials.get(type="agenda"),
                                  "1. WG status (15 minutes)\n\n2. Status of %s\n\n" % draft.name)

        self.write_materials_file(meeting, session.materials.get(type="minutes"),
                                  "1. More work items underway\n\n2. The draft will be finished before next meeting\n\n")

        self.write_materials_file(meeting, session.materials.filter(type="slides").exclude(states__type__slug='slides',states__slug='deleted').first(),
                                  "This is a slideshow")
        

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
        self.assertContains(r, session.group.acronym)
        self.assertContains(r, session.group.name)
        self.assertContains(r, slot.location.name)
        self.assertContains(r, "BEGIN:VTIMEZONE")
        self.assertContains(r, "END:VTIMEZONE")        

        self.assertContains(r, session.agenda().get_href())
        self.assertContains(r, session.materials.filter(type='slides').exclude(states__type__slug='slides',states__slug='deleted').first().get_href())
        # TODO - the ics view uses .all on a queryset in a view so it's showing the deleted slides.
        #self.assertNotContains(r, session.materials.filter(type='slides',states__type__slug='slides',states__slug='deleted').first().get_absolute_url())

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
        venus_session = Session.objects.create(
            meeting=meeting,
            group=venus,
            attendees=10,
            requested_duration=datetime.timedelta(minutes=60),
            type_id='regular',
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
                    ('text/html,text/plain,text/markdown',  'text/html',     '<li><p>More work items underway</p></li>'),
                    ('text/markdown,text/html,text/plain',  'text/markdown', '1. More work items underway'),
                    ('text/plain,text/markdown, text/html', 'text/plain',    '1. More work items underway'),
                    ('text/html',                           'text/html',     '<li><p>More work items underway</p></li>'),
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

    def test_proceedings(self):
        meeting = make_meeting_test_data()
        session = Session.objects.filter(meeting=meeting, group__acronym="mars").first()
        GroupEventFactory(group=session.group,type='status_update')
        SessionPresentationFactory(document__type_id='recording',session=session)
        SessionPresentationFactory(document__type_id='recording',session=session,document__title="Audio recording for tests")

        self.write_materials_files(meeting, session)

        url = urlreverse("ietf.meeting.views.proceedings", kwargs=dict(num=meeting.number))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

    def test_proceedings_acknowledgements(self):
        make_meeting_test_data()
        meeting = MeetingFactory(type_id='ietf', date=datetime.date(2016,7,14), number="96")
        meeting.acknowledgements = 'test acknowledgements'
        meeting.save()
        url = urlreverse('ietf.meeting.views.proceedings_acknowledgements',kwargs={'num':meeting.number})
        response = self.client.get(url)
        self.assertContains(response, 'test acknowledgements')

    @patch('ietf.meeting.utils.requests.get')
    def test_proceedings_attendees(self, mockobj):
        mockobj.return_value.text = b'[{"LastName":"Smith","FirstName":"John","Company":"ABC","Country":"US"}]'
        mockobj.return_value.json = lambda: json.loads(b'[{"LastName":"Smith","FirstName":"John","Company":"ABC","Country":"US"}]')
        make_meeting_test_data()
        meeting = MeetingFactory(type_id='ietf', date=datetime.date(2016,7,14), number="96")
        finalize(meeting)
        url = urlreverse('ietf.meeting.views.proceedings_attendees',kwargs={'num':96})
        response = self.client.get(url)
        self.assertContains(response, 'Attendee List')
        q = PyQuery(response.content)
        self.assertEqual(1,len(q("#id_attendees tbody tr")))

    @patch('urllib.request.urlopen')
    def test_proceedings_overview(self, mock_urlopen):
        '''Test proceedings IETF Overview page.
        Note: old meetings aren't supported so need to add a new meeting then test.
        '''
        mock_urlopen.return_value = BytesIO(b'[{"LastName":"Smith","FirstName":"John","Company":"ABC","Country":"US"}]')
        make_meeting_test_data()
        meeting = MeetingFactory(type_id='ietf', date=datetime.date(2016,7,14), number="96")
        finalize(meeting)
        url = urlreverse('ietf.meeting.views.proceedings_overview',kwargs={'num':96})
        response = self.client.get(url)
        self.assertContains(response, 'The Internet Engineering Task Force')

    def test_proceedings_progress_report(self):
        make_meeting_test_data()
        MeetingFactory(type_id='ietf', date=datetime.date(2016,4,3), number="95")
        MeetingFactory(type_id='ietf', date=datetime.date(2016,7,14), number="96")

        url = urlreverse('ietf.meeting.views.proceedings_progress_report',kwargs={'num':96})
        response = self.client.get(url)
        self.assertContains(response, 'Progress Report')

    def test_feed(self):
        meeting = make_meeting_test_data()
        session = Session.objects.filter(meeting=meeting, group__acronym="mars").first()

        r = self.client.get("/feed/wg-proceedings/")
        self.assertContains(r, "agenda")
        self.assertContains(r, session.group.acronym)

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

        # Should be a 'non-area events' link showing appropriate types        
        non_area_labels = [
            'BoF', 'EDU', 'Hackathon', 'IEPG', 'IESG', 'IETF', 'Plenary', 'Secretariat', 'Tools',
        ]
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
            querystring='?show=plenary,secretariat,ames&hide=reg',
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
    def setUp(self):
        # make sure we have the colors of the area
        from ietf.group.colors import fg_group_colors, bg_group_colors
        area_upper = "FARFUT"
        fg_group_colors[area_upper] = "#333"
        bg_group_colors[area_upper] = "#aaa"

    def test_edit_schedule(self):
        meeting = make_meeting_test_data()
 
        self.client.login(username="secretary", password="secretary+password")
        r = self.client.get(urlreverse("ietf.meeting.views.edit_schedule", kwargs=dict(num=meeting.number)))
        self.assertContains(r, "load_assignments")
 
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

        base_session = Session.objects.create(meeting=meeting, group=Group.objects.get(acronym="irg"),
                                              attendees=20, requested_duration=datetime.timedelta(minutes=30),
                                              type_id='regular')
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
            'type': assignment.timeslot.type_id,
            'name': assignment.timeslot.name,
            'agenda_note': "New Test Note",
            'action': 'edit-timeslot',
        })
        self.assertNoFormPostErrors(r)

        assignment.session.refresh_from_db()
        self.assertEqual(assignment.session.agenda_note, "New Test Note")


    def test_new_meeting_schedule(self):
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

        # copy
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

    def test_save_agenda_as_and_read_permissions(self):
        meeting = make_meeting_test_data()

        # try to get non-existing agenda
        url = urlreverse("ietf.meeting.views.edit_schedule", kwargs=dict(num=meeting.number,
                                                                       owner=meeting.schedule.owner_email(),
                                                                       name="foo"))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 404)

        # save as new name (requires valid existing agenda)
        url = urlreverse("ietf.meeting.views.edit_schedule", kwargs=dict(num=meeting.number,
                                                                       owner=meeting.schedule.owner_email(),
                                                                       name=meeting.schedule.name))
        self.client.login(username="ad", password="ad+password")
        r = self.client.post(url, {
            'savename': "foo",
            'saveas': "saveas",
            })
        self.assertEqual(r.status_code, 302)
        # Verify that we actually got redirected to a new place.
        self.assertNotEqual(urlparse(r.url).path, url)

        # get
        schedule = meeting.get_schedule_by_name("foo")
        url = urlreverse("ietf.meeting.views.edit_schedule", kwargs=dict(num=meeting.number,
                                                                       owner=schedule.owner_email(),
                                                                       name="foo"))
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

    def test_save_agenda_broken_names(self):
        meeting = make_meeting_test_data()

        # save as new name (requires valid existing agenda)
        url = urlreverse("ietf.meeting.views.edit_schedule", kwargs=dict(num=meeting.number,
                                                                       owner=meeting.schedule.owner_email(),
                                                                       name=meeting.schedule.name))
        self.client.login(username="ad", password="ad+password")
        r = self.client.post(url, {
            'savename': "/no/this/should/not/work/it/is/too/long",
            'saveas': "saveas",
            })
        self.assertEqual(r.status_code, 302)
        self.assertEqual(urlparse(r.url).path, url)
        # TODO: Verify that an error message was in fact returned.

        r = self.client.post(url, {
            'savename': "/invalid/chars/",
            'saveas': "saveas",
            })
        # TODO: Verify that an error message was in fact returned.
        self.assertEqual(r.status_code, 302)
        self.assertEqual(urlparse(r.url).path, url)

        # Non-ASCII alphanumeric characters
        r = self.client.post(url, {
            'savename': "f\u00E9ling",
            'saveas': "saveas",
            })
        # TODO: Verify that an error message was in fact returned.
        self.assertEqual(r.status_code, 302)
        self.assertEqual(urlparse(r.url).path, url)
        

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
        self.assertTrue(q('h2#session_%s span#session-buttons-%s' % (session.id, session.id)), 
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
        session3 = Session.objects.create(meeting=meeting, group=Group.objects.get(acronym='mars'),
                               attendees=10, requested_duration=datetime.timedelta(minutes=70),
                               type_id='regular')
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
    def setUp(self):
        self.materials_dir = self.tempdir('materials')
        self.saved_agenda_path = settings.AGENDA_PATH
        settings.AGENDA_PATH = self.materials_dir

    def tearDown(self):
        settings.AGENDA_PATH = self.saved_agenda_path
        shutil.rmtree(self.materials_dir)

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

        r = self.client.post(urlreverse("ietf.meeting.views.interim_request"),data)
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

        r = self.client.post(urlreverse("ietf.meeting.views.interim_request"),data)
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

        r = self.client.post(urlreverse("ietf.meeting.views.interim_request"),data)

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

        r = self.client.post(urlreverse("ietf.meeting.views.interim_request"),data)
        
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

    def test_interim_request_cancel(self):
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

        # test cancelling before announcement
        self.client.login(username="marschairman", password="marschairman+password")
        length_before = len(outbox)
        r = self.client.post(url, {'comments': comments})
        self.assertRedirects(r, urlreverse('ietf.meeting.views.upcoming'))
        for session in meeting.session_set.with_current_status():
            self.assertEqual(session.current_status,'canceledpa')
            self.assertEqual(session.agenda_note, comments)
        self.assertEqual(len(outbox), length_before)     # no email notice

        # test cancelling after announcement
        meeting = add_event_info_to_session_qs(Session.objects.filter(meeting__type='interim', group__acronym='mars')).filter(current_status='sched').first().meeting
        url = urlreverse('ietf.meeting.views.interim_request_cancel', kwargs={'number': meeting.number})
        r = self.client.post(url, {'comments': comments})
        self.assertRedirects(r, urlreverse('ietf.meeting.views.upcoming'))
        for session in meeting.session_set.with_current_status():
            self.assertEqual(session.current_status,'canceled')
            self.assertEqual(session.agenda_note, comments)
        self.assertEqual(len(outbox), length_before + 1)
        self.assertIn('Interim Meeting Cancelled', outbox[-1]['Subject'])

    def test_interim_request_session_cancel(self):
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

        # Add a second session
        SessionFactory(meeting=meeting, status_id='apprw')

        # ensure fail unauthorized
        url = urlreverse('ietf.meeting.views.interim_request_session_cancel', kwargs={'sessionid': session.pk})
        self.client.login(username="ameschairman", password="ameschairman+password")
        r = self.client.post(url, {'comments': comments})
        self.assertEqual(r.status_code, 403)
        
        # test cancelling before announcement
        self.client.login(username="marschairman", password="marschairman+password")
        length_before = len(outbox)
        canceled_count_before = meeting.session_set.with_current_status().filter(
            current_status__in=['canceled', 'canceledpa']).count()
        r = self.client.post(url, {'comments': comments})
        self.assertRedirects(r, urlreverse('ietf.meeting.views.interim_request_details', 
                                           kwargs={'number': meeting.number}))
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
        session = Session.objects.with_current_status().filter(
            meeting__type='interim', group__acronym='mars', current_status='sched').first()
        meeting = session.meeting
        
        # Try to cancel when there's only one session in the meeting
        url = urlreverse('ietf.meeting.views.interim_request_session_cancel', kwargs={'sessionid': session.pk})
        r = self.client.post(url, {'comments': comments})
        self.assertEqual(r.status_code, 409)

        # Add another session
        SessionFactory(meeting=meeting, status_id='sched')  # two sessions so canceling a session makes sense

        canceled_count_before = meeting.session_set.with_current_status().filter(
            current_status__in=['canceled', 'canceledpa']).count()
        r = self.client.post(url, {'comments': comments})
        self.assertRedirects(r, urlreverse('ietf.meeting.views.interim_request_details',
                                           kwargs={'number': meeting.number}))
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
    def setUp(self):
        pass

    def tearDown(self):
        pass

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
    def setUp(self):
        pass

    def tearDown(self):
        pass

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
    @patch('urllib.request.urlopen')
    def test_finalize_proceedings(self, mock_urlopen):
        mock_urlopen.return_value = BytesIO(b'[{"LastName":"Smith","FirstName":"John","Company":"ABC","Country":"US"}]')
        make_meeting_test_data()
        meeting = Meeting.objects.filter(type_id='ietf').order_by('id').last()
        meeting.session_set.filter(group__acronym='mars').first().sessionpresentation_set.create(document=Document.objects.filter(type='draft').first(),rev=None)

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

    def setUp(self):
        self.materials_dir = self.tempdir('materials')
        self.staging_dir = self.tempdir('staging')
        if not os.path.exists(self.materials_dir):
            os.mkdir(self.materials_dir)
        self.saved_agenda_path = settings.AGENDA_PATH
        settings.AGENDA_PATH = self.materials_dir
        self.saved_staging_path = settings.SLIDE_STAGING_PATH
        settings.SLIDE_STAGING_PATH = self.staging_dir

    def tearDown(self):
        settings.AGENDA_PATH = self.saved_agenda_path
        settings.SLIDE_STAGING_PATH = self.saved_staging_path
        shutil.rmtree(self.materials_dir)
        shutil.rmtree(self.staging_dir)

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
            url = url=urlreverse('ietf.meeting.views.session_details', kwargs={'num':session.meeting.number, 'acronym': session.group.acronym})
            top = '/meeting/%s/' % session.meeting.number
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
            url = url=urlreverse('ietf.meeting.views.session_details', kwargs={'num':session.meeting.number, 'acronym': session.group.acronym})
            top = '/meeting/%s/' % session.meeting.number
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


class SessionTests(TestCase):

    def test_meeting_requests(self):
        meeting = MeetingFactory(type_id='ietf')
        area = GroupFactory(type_id='area')
        requested_session = SessionFactory(meeting=meeting,group__parent=area,status_id='schedw',add_to_schedule=False)
        not_meeting = SessionFactory(meeting=meeting,group__parent=area,status_id='notmeet',add_to_schedule=False)
        url = urlreverse('ietf.meeting.views.meeting_requests',kwargs={'num':meeting.number})
        r = self.client.get(url)
        self.assertContains(r, requested_session.group.acronym)
        self.assertContains(r, not_meeting.group.acronym)

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
    def setUp(self):
        self.materials_dir = self.tempdir('materials')
        #
        self.saved_agenda_path = settings.AGENDA_PATH
        #
        settings.AGENDA_PATH = self.materials_dir

    def tearDown(self):
        shutil.rmtree(self.materials_dir)
        #
        settings.AGENDA_PATH = self.saved_agenda_path

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
                            is_bof=False,
                        ),
                        dict(
                            label='child01',
                            keyword='keyword01',
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
                            is_bof=False,
                        ),
                        dict(
                            label='child11',
                            keyword='keyword11',
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
                            is_bof=True,
                        ),
                        dict(
                            label='child21',
                            keyword='keyword21',
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
                            is_bof=False,
                        ),
                        dict(
                            label='child31',
                            keyword='keyword31',
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

