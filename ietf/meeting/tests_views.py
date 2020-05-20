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
from urllib.parse import urlparse

from django.urls import reverse as urlreverse
from django.conf import settings
from django.contrib.auth.models import User
from django.test import Client, override_settings
from django.db.models import F

import debug           # pyflakes:ignore

from ietf.doc.models import Document
from ietf.group.models import Group, Role, GroupFeatures
from ietf.group.utils import can_manage_group
from ietf.person.models import Person
from ietf.meeting.helpers import can_approve_interim_request, can_view_interim_request
from ietf.meeting.helpers import send_interim_approval_request
from ietf.meeting.helpers import send_interim_cancellation_notice
from ietf.meeting.helpers import send_interim_minutes_reminder, populate_important_dates, update_important_dates
from ietf.meeting.models import Session, TimeSlot, Meeting, SchedTimeSessAssignment, Schedule, SessionPresentation, SlideSubmission, SchedulingEvent, Room, Constraint, ConstraintName
from ietf.meeting.test_data import make_meeting_test_data, make_interim_meeting
from ietf.meeting.utils import finalize, condition_slide_order
from ietf.meeting.utils import add_event_info_to_session_qs
from ietf.meeting.views import session_draft_list
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


if os.path.exists(settings.GHOSTSCRIPT_COMMAND):
    skip_pdf_tests = False
    skip_message = ""
else:
    import sys
    skip_pdf_tests = True
    skip_message = ("Skipping pdf test: The binary for ghostscript wasn't found in the\n       "
                    "location indicated in settings.py.")
    sys.stderr.write("     "+skip_message+'\n')

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

        # Make sure there's a frame for the agenda and it points to the right place
        self.assertTrue(any([session.materials.get(type='agenda').get_href() in x.attrib["data-src"] for x in q('tr div.modal-body  div.frame')])) 

        # Make sure undeleted slides are present and deleted slides are not
        self.assertTrue(any([session.materials.filter(type='slides').exclude(states__type__slug='slides',states__slug='deleted').first().title in x.text for x in q('tr div.modal-body ul a')]))
        self.assertFalse(any([session.materials.filter(type='slides',states__type__slug='slides',states__slug='deleted').first().title in x.text for x in q('tr div.modal-body ul a')]))

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

        self.assertContains(r, session.materials.get(type='agenda').uploaded_filename)
        self.assertContains(r, session.materials.filter(type='slides').exclude(states__type__slug='slides',states__slug='deleted').first().uploaded_filename)
        self.assertNotContains(r, session.materials.filter(type='slides',states__type__slug='slides',states__slug='deleted').first().uploaded_filename)

        # iCal
        r = self.client.get(urlreverse("ietf.meeting.views.agenda_ical", kwargs=dict(num=meeting.number))
                            + "?" + session.group.parent.acronym.upper())
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
        url = urlreverse("ietf.meeting.views.week_view",kwargs=dict(num=meeting.number)) + "#farfut"
        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        self.assertTrue(all([x in unicontent(r) for x in ['var all_items', 'maximize', 'draw_calendar', ]]))

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
        response = self.client.post(url, {
                'name':schedule.name,
                'visible':True,
                'public':True,
            }
        )
        self.assertEqual(response.status_code,302)
        schedule = Schedule.objects.get(pk=schedule.pk)
        self.assertTrue(schedule.visible)
        self.assertTrue(schedule.public)

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

        p = Person.objects.all().first()

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
        
        # check we have the grid and everything set up as a baseline -
        # the Javascript tests check that the Javascript can work with
        # it
        url = urlreverse("ietf.meeting.views.edit_meeting_schedule", kwargs=dict(num=meeting.number))
        r = self.client.get(url)
        q = PyQuery(r.content)

        room = Room.objects.get(meeting=meeting, session_types='regular')
        self.assertTrue(q(".room-name:contains(\"{}\")".format(room.name)))
        self.assertTrue(q(".room-name:contains(\"{}\")".format(room.capacity)))

        timeslots = TimeSlot.objects.filter(meeting=meeting, type='regular')
        self.assertTrue(q("#timeslot{}".format(timeslots[0].pk)))

        for s in [s1, s2]:
            e = q("#session{}".format(s.pk))

            # info in the movable entity
            self.assertIn(s.group.acronym, e.find(".session-label").text())
            if s.comments:
                self.assertTrue(e.find(".comments"))
            if s.attendees is not None:
                self.assertIn(str(s.attendees), e.find(".attendees").text())
            self.assertTrue(e.hasClass("parent-{}".format(s.group.parent.acronym)))

            # session info for the panel
            self.assertIn(str(s.requested_duration.total_seconds() / 60.0 / 60), e.find(".session-info label").text())

            event = SchedulingEvent.objects.filter(session=s).order_by("id").first()
            if event:
                self.assertTrue(e.find("div:contains(\"{}\")".format(event.by.plain_name())))

            if s.comments:
                self.assertIn(s.comments, e.find(".comments").text())

            # constraints
            constraints = e.find(".constraints > span")
            s_other = s2 if s == s1 else s1
            self.assertEqual(len(constraints), 2)
            self.assertEqual(constraints.eq(0).attr("data-sessions"), str(s_other.pk))
            self.assertEqual(constraints.eq(1).attr("data-sessions"), str(s_other.pk))
            self.assertEqual(constraints.find(".encircled").text(), "1")
            self.assertEqual(constraints.find(".fa-user-o").parent().text(), "1") # 1 person in the constraint

        self.assertTrue(q("em:contains(\"You can't edit this schedule\")"))

        # can't change anything
        r = self.client.post(url, {
            'action': 'assign',
            'timeslot': timeslots[0].pk,
            'session': s1.pk,
        })
        self.assertEqual(r.status_code, 403)
        
        # turn us into owner
        meeting.schedule.owner = Person.objects.get(user__username="secretary")
        meeting.schedule.save()

        url = urlreverse("ietf.meeting.views.edit_meeting_schedule", kwargs=dict(num=meeting.number, owner=meeting.schedule.owner_email(), name=meeting.schedule.name))
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
        self.assertEqual(r.content, b"OK")
        self.assertEqual(SchedTimeSessAssignment.objects.get(schedule=meeting.schedule, session=s1).timeslot, timeslots[0])

        # move assignment
        r = self.client.post(url, {
            'action': 'assign',
            'timeslot': timeslots[1].pk,
            'session': s1.pk,
        })
        self.assertEqual(r.content, b"OK")
        self.assertEqual(SchedTimeSessAssignment.objects.get(schedule=meeting.schedule, session=s1).timeslot, timeslots[1])

        # unassign
        r = self.client.post(url, {
            'action': 'unassign',
            'session': s1.pk,
        })
        self.assertEqual(r.content, b"OK")
        self.assertEqual(list(SchedTimeSessAssignment.objects.filter(schedule=meeting.schedule, session=s1)), [])


    def test_copy_meeting_schedule(self):
        meeting = make_meeting_test_data()

        self.client.login(username="secretary", password="secretary+password")

        url = urlreverse("ietf.meeting.views.copy_meeting_schedule", kwargs=dict(num=meeting.number, owner=meeting.schedule.owner_email(), name=meeting.schedule.name))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        # copy
        r = self.client.post(url, {
            'name': "newtest",
            'public': "on",
        })
        self.assertNoFormPostErrors(r)

        new_schedule = Schedule.objects.get(meeting=meeting, owner__user__username='secretary', name='newtest')
        self.assertEqual(new_schedule.public, True)
        self.assertEqual(new_schedule.visible, False)

        old_assignments = {(a.session_id, a.timeslot_id) for a in SchedTimeSessAssignment.objects.filter(schedule=meeting.schedule)}
        for a in SchedTimeSessAssignment.objects.filter(schedule=new_schedule):
            self.assertIn((a.session_id, a.timeslot_id), old_assignments)
            # FIXME: test extendedfrom is copied correctly

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
        self.mtg = MeetingFactory(type_id='ietf')
        ScheduleFactory(meeting=self.mtg,name='Empty-Schedule')

    def test_list_schedules(self):
        url = urlreverse('ietf.meeting.views.list_schedules',kwargs={'num':self.mtg.number})
        login_testing_unauthorized(self,"secretary",url)
        r = self.client.get(url)
        self.assertTrue(r.status_code, 200)

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

    def check_interim_tabs(self, url):
        '''Helper function to check interim meeting list tabs'''
        # no logged in -  no tabs
        r = self.client.get(url)
        q = PyQuery(r.content)
        self.assertEqual(len(q("ul.nav-tabs")), 0)
        # plain user -  no tabs
        username = "plain"
        self.client.login(username=username, password=username + "+password")
        r = self.client.get(url)
        q = PyQuery(r.content)
        self.assertEqual(len(q("ul.nav-tabs")), 0)
        self.client.logout()
        # privileged user
        username = "ad"
        self.client.login(username=username, password=username + "+password")
        r = self.client.get(url)
        q = PyQuery(r.content)
        self.assertEqual(len(q("a:contains('Pending')")), 1)
        self.assertEqual(len(q("a:contains('Announce')")), 0)
        self.client.logout()
        # secretariat
        username = "secretary"
        self.client.login(username=username, password=username + "+password")
        r = self.client.get(url)
        q = PyQuery(r.content)
        self.assertEqual(len(q("a:contains('Pending')")), 1)
        self.assertEqual(len(q("a:contains('Announce')")), 1)
        self.client.logout()

    def test_interim_announce(self):
        make_meeting_test_data()
        url = urlreverse("ietf.meeting.views.interim_announce")
        meeting = Meeting.objects.filter(type='interim', session__group__acronym='mars').first()
        session = meeting.session_set.first()
        SchedulingEvent.objects.create(
            session=session,
            status=SessionStatusName.objects.get(slug='scheda'),
            by=Person.objects.get(name='(System)')
        )
        login_testing_unauthorized(self, "secretary", url)
        r = self.client.get(url)
        self.assertContains(r, meeting.number)

    def test_interim_skip_announcement(self):
        make_meeting_test_data()
        group = Group.objects.get(acronym='irg')
        date = datetime.date.today() + datetime.timedelta(days=30)
        meeting = make_interim_meeting(group=group, date=date, status='scheda')
        url = urlreverse("ietf.meeting.views.interim_skip_announcement", kwargs={'number': meeting.number})
        login_testing_unauthorized(self, "secretary", url)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        
        # check post
        len_before = len(outbox)
        r = self.client.post(url)
        self.assertRedirects(r, urlreverse('ietf.meeting.views.interim_announce'))
        self.assertEqual(add_event_info_to_session_qs(meeting.session_set).first().current_status, 'sched')
        self.assertEqual(len(outbox), len_before)
        
    def test_interim_send_announcement(self):
        make_meeting_test_data()
        meeting = add_event_info_to_session_qs(Session.objects.filter(meeting__type='interim', group__acronym='mars')).filter(current_status='apprw').first().meeting
        meeting.time_zone = 'America/Los_Angeles'
        meeting.save()
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
        self.assertIn('WG Virtual Meeting', outbox[-1]['Subject'])
        self.assertIn('09:00 to 09:20 America/Los_Angeles', get_payload_text(outbox[-1]))
        self.assertIn('(17:00 to 17:20 UTC)', get_payload_text(outbox[-1]))

    def test_interim_approve_by_ad(self):
        make_meeting_test_data()
        meeting = add_event_info_to_session_qs(Session.objects.filter(meeting__type='interim', group__acronym='mars')).filter(current_status='apprw').first().meeting
        url = urlreverse('ietf.meeting.views.interim_request_details', kwargs={'number': meeting.number})
        length_before = len(outbox)
        login_testing_unauthorized(self, "ad", url)
        r = self.client.post(url, {'approve': 'approve'})
        self.assertRedirects(r, urlreverse('ietf.meeting.views.interim_pending'))
        for session in add_event_info_to_session_qs(meeting.session_set.all()):
            self.assertEqual(session.current_status, 'scheda')
        self.assertEqual(len(outbox), length_before + 1)
        self.assertIn('ready for announcement', outbox[-1]['Subject'])

    def test_interim_approve_by_secretariat(self):
        make_meeting_test_data()
        meeting = add_event_info_to_session_qs(Session.objects.filter(meeting__type='interim', group__acronym='mars')).filter(current_status='apprw').first().meeting
        url = urlreverse('ietf.meeting.views.interim_request_details', kwargs={'number': meeting.number})
        login_testing_unauthorized(self, "secretary", url)
        r = self.client.post(url, {'approve': 'approve'})
        self.assertRedirects(r, urlreverse('ietf.meeting.views.interim_send_announcement', kwargs={'number': meeting.number}))
        for session in add_event_info_to_session_qs(meeting.session_set.all()):
            self.assertEqual(session.current_status, 'scheda')

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

    def test_upcoming(self):
        make_meeting_test_data()
        url = urlreverse("ietf.meeting.views.upcoming")
        today = datetime.date.today()
        add_event_info_to_session_qs(Session.objects.filter(meeting__type='interim', group__acronym='mars')).filter(current_status='apprw').first()
        mars_interim = add_event_info_to_session_qs(Session.objects.filter(meeting__type='interim', meeting__date__gt=today, group__acronym='mars')).filter(current_status='sched').first().meeting
        ames_interim = add_event_info_to_session_qs(Session.objects.filter(meeting__type='interim', meeting__date__gt=today, group__acronym='ames')).filter(current_status='canceled').first().meeting
        r = self.client.get(url)
        self.assertContains(r, mars_interim.number)
        self.assertContains(r, ames_interim.number)
        self.assertContains(r, 'IETF 72')
        # cancelled session
        q = PyQuery(r.content)
        self.assertIn('CANCELLED', q('tr>td.text-right>span').text())
        self.check_interim_tabs(url)

    def test_upcoming_ical(self):
        make_meeting_test_data()
        url = urlreverse("ietf.meeting.views.upcoming_ical")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get('Content-Type'), "text/calendar")
        self.assertEqual(r.content.count(b'UID'), 7)
        # check filtered output
        url = url + '?filters=mars'
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get('Content-Type'), "text/calendar")
        # print r.content
        self.assertEqual(r.content.count(b'UID'), 2)


    def test_upcoming_json(self):
        make_meeting_test_data()
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

    def do_interim_request_single_virtual(self):
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
        # check notice to secretariat
        self.assertEqual(len(outbox), length_before + 1)
        return meeting

    @override_settings(VIRTUAL_INTERIMS_REQUIRE_APPROVAL = True)
    def test_interim_request_single_virtual_settings_approval_required(self):
        meeting = self.do_interim_request_single_virtual()
        self.assertEqual(meeting.session_set.last().schedulingevent_set.last().status_id,'apprw')
        self.assertIn('New Interim Meeting Request', outbox[-1]['Subject'])
        self.assertIn('session-request@ietf.org', outbox[-1]['To'])
        self.assertIn('aread@example.org', outbox[-1]['Cc'])

    @override_settings(VIRTUAL_INTERIMS_REQUIRE_APPROVAL = False)
    def test_interim_request_single_virtual_settings_approval_not_required(self):
        meeting = self.do_interim_request_single_virtual()
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

    def test_interim_request_series(self):
        make_meeting_test_data()
        meeting_count_before = Meeting.objects.filter(type='interim').count()
        date = datetime.date.today() + datetime.timedelta(days=30)
        date2 = date + datetime.timedelta(days=1)
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


    def test_interim_pending(self):
        make_meeting_test_data()
        url = urlreverse('ietf.meeting.views.interim_pending')
        count = len(set(s.meeting_id for s in add_event_info_to_session_qs(Session.objects.filter(meeting__type='interim')).filter(current_status='apprw')))

        # unpriviledged user
        login_testing_unauthorized(self,"plain",url)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 403) 
        
        # secretariat
        login_testing_unauthorized(self,"secretary",url)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q("#pending-interim-meetings-table tr"))-1, count)
        self.client.logout()


    def test_can_approve_interim_request(self):
        make_meeting_test_data()
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
        make_meeting_test_data()
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
        make_meeting_test_data()
        meeting = add_event_info_to_session_qs(Session.objects.filter(meeting__type='interim', group__acronym='mars')).filter(current_status='apprw').first().meeting
        url = urlreverse('ietf.meeting.views.interim_request_details',kwargs={'number':meeting.number})
        login_testing_unauthorized(self,"secretary",url)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

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

    def test_interim_request_disapprove(self):
        make_meeting_test_data()
        meeting = add_event_info_to_session_qs(Session.objects.filter(meeting__type='interim', group__acronym='mars')).filter(current_status='apprw').first().meeting
        url = urlreverse('ietf.meeting.views.interim_request_details',kwargs={'number':meeting.number})
        login_testing_unauthorized(self,"secretary",url)
        r = self.client.post(url,{'disapprove':'Disapprove'})
        self.assertRedirects(r, urlreverse('ietf.meeting.views.interim_pending'))
        for session in add_event_info_to_session_qs(meeting.session_set.all()):
            self.assertEqual(session.current_status,'disappr')

    def test_interim_request_cancel(self):
        make_meeting_test_data()
        meeting = add_event_info_to_session_qs(Session.objects.filter(meeting__type='interim', group__acronym='mars')).filter(current_status='apprw').first().meeting
        url = urlreverse('ietf.meeting.views.interim_request_details', kwargs={'number': meeting.number})
        self.client.login(username="marschairman", password="marschairman+password")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q("a.btn:contains('Cancel')")), 1)
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
        for session in add_event_info_to_session_qs(meeting.session_set.all()):
            self.assertEqual(session.current_status,'canceledpa')
            self.assertEqual(session.agenda_note, comments)
        self.assertEqual(len(outbox), length_before)     # no email notice
        # test cancelling after announcement
        meeting = add_event_info_to_session_qs(Session.objects.filter(meeting__type='interim', group__acronym='mars')).filter(current_status='sched').first().meeting
        url = urlreverse('ietf.meeting.views.interim_request_cancel', kwargs={'number': meeting.number})
        r = self.client.post(url, {'comments': comments})
        self.assertRedirects(r, urlreverse('ietf.meeting.views.upcoming'))
        for session in add_event_info_to_session_qs(meeting.session_set.all()):
            self.assertEqual(session.current_status,'canceled')
            self.assertEqual(session.agenda_note, comments)
        self.assertEqual(len(outbox), length_before + 1)
        self.assertIn('Interim Meeting Cancelled', outbox[-1]['Subject'])

    def test_interim_request_edit_no_notice(self):
        '''Edit a request.  No notice should go out if it hasn't been announced yet'''
        make_meeting_test_data()
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
        make_meeting_test_data()
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
        make_meeting_test_data()
        meeting = add_event_info_to_session_qs(Session.objects.filter(meeting__type='interim', group__acronym='mars')).filter(current_status='apprw').first().meeting
        url = urlreverse('ietf.meeting.views.interim_request_details',kwargs={'number':meeting.number})

        # unprivileged user
        login_testing_unauthorized(self,"plain",url)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 403)

    def test_send_interim_approval_request(self):
        make_meeting_test_data()
        meeting = add_event_info_to_session_qs(Session.objects.filter(meeting__type='interim', group__acronym='mars')).filter(current_status='apprw').first().meeting
        length_before = len(outbox)
        send_interim_approval_request(meetings=[meeting])
        self.assertEqual(len(outbox),length_before+1)
        self.assertIn('New Interim Meeting Request', outbox[-1]['Subject'])

    def test_send_interim_cancellation_notice(self):
        make_meeting_test_data()
        meeting = add_event_info_to_session_qs(Session.objects.filter(meeting__type='interim', group__acronym='mars')).filter(current_status='sched').first().meeting
        length_before = len(outbox)
        send_interim_cancellation_notice(meeting=meeting)
        self.assertEqual(len(outbox),length_before+1)
        self.assertIn('Interim Meeting Cancelled', outbox[-1]['Subject'])

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
        make_meeting_test_data()
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
        make_meeting_test_data()
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
        chair = RoleFactory(group=submission.session.group,name_id='chair').person
        url = urlreverse('ietf.meeting.views.approve_proposed_slides', kwargs={'slidesubmission_id':submission.pk,'num':submission.session.meeting.number})
        login_testing_unauthorized(self, chair.user.username, url)
        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        r = self.client.post(url,dict(title='some title',disapprove="disapprove"))
        self.assertEqual(r.status_code,302)
        self.assertEqual(SlideSubmission.objects.count(), 0)

    def test_approve_proposed_slides(self):
        submission = SlideSubmissionFactory()
        session = submission.session
        session.meeting.importantdate_set.create(name_id='revsub',date=datetime.date.today()+datetime.timedelta(days=20))
        chair = RoleFactory(group=submission.session.group,name_id='chair').person
        url = urlreverse('ietf.meeting.views.approve_proposed_slides', kwargs={'slidesubmission_id':submission.pk,'num':submission.session.meeting.number})
        login_testing_unauthorized(self, chair.user.username, url)
        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        r = self.client.post(url,dict(title='different title',approve='approve'))
        self.assertEqual(r.status_code,302)
        self.assertEqual(SlideSubmission.objects.count(), 0)
        self.assertEqual(session.sessionpresentation_set.count(),1)
        self.assertEqual(session.sessionpresentation_set.first().document.title,'different title')

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

        (first_submission, second_submission) = SlideSubmission.objects.filter(session=session).order_by('id')

        approve_url = urlreverse('ietf.meeting.views.approve_proposed_slides', kwargs={'slidesubmission_id':second_submission.pk,'num':second_submission.session.meeting.number})
        login_testing_unauthorized(self, chair.user.username, approve_url)
        r = self.client.post(approve_url,dict(title=submission.title,approve='approve'))
        self.assertEqual(r.status_code,302)

        disapprove_url = urlreverse('ietf.meeting.views.approve_proposed_slides', kwargs={'slidesubmission_id':first_submission.pk,'num':first_submission.session.meeting.number})
        r = self.client.post(disapprove_url,dict(title='some title',disapprove="disapprove"))
        self.assertEqual(r.status_code,302)
        self.client.logout()

        self.assertEqual(SlideSubmission.objects.count(),0)
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

        r = self.client.post(urlreverse("ietf.meeting.views.interim_request"),data)
        self.assertRedirects(r,urlreverse('ietf.meeting.views.upcoming'))
        meeting = Meeting.objects.order_by('id').last()
        self.assertEqual(meeting.type_id,'interim')
        self.assertEqual(meeting.date,date)
        self.assertEqual(meeting.number,'interim-%s-%s-%s' % (date.year, group.acronym, next_num))
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
        for gf in GroupFeatures.objects.filter(has_meetings=True):
            session = SessionFactory(
                group__type_id = gf.type_id,
                meeting__type_id='interim', 
                meeting__date = datetime.datetime.today()+datetime.timedelta(days=30),
                status_id='sched',
            )
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)
            q = PyQuery(r.content)
            self.assertIn(session.meeting.number, q('.interim-meeting-link').text())


    def test_appears_on_pending(self):
        url = urlreverse('ietf.meeting.views.interim_pending')
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
            for role_name in gf.groupman_roles:
                role = RoleFactory(group=group, name_id=role_name)
                self.client.login(username=role.person.user.username, password=role.person.user.username+'+password')
                r = self.client.get(url)
                self.assertEqual(r.status_code, 200)
                q = PyQuery(r.content)
                self.assertIn(session.meeting.number, q('.interim-meeting-link').text())
                self.client.logout()
            for authrole in gf.groupman_authroles:
                role = self.create_role_for_authrole(authrole)
                self.client.login(username=role.person.user.username, password=role.person.user.username+'+password')
                r = self.client.get(url)
                self.assertEqual(r.status_code, 200)
                q = PyQuery(r.content)
                self.assertIn(session.meeting.number, q('.interim-meeting-link').text())
                self.client.logout()


    def test_appears_on_announce(self):
        url = urlreverse('ietf.meeting.views.interim_announce')
        login_testing_unauthorized(self,"secretary",url)
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

