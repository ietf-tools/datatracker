import json
import os
import shutil
import datetime
import urlparse
import random

import debug           # pyflakes:ignore

from django.core.urlresolvers import reverse as urlreverse
from django.conf import settings
from django.contrib.auth.models import User

from pyquery import PyQuery
from StringIO import StringIO

from ietf.doc.models import Document
from ietf.group.models import Group
from ietf.meeting.helpers import can_approve_interim_request, can_view_interim_request
from ietf.meeting.helpers import send_interim_approval_request
from ietf.meeting.helpers import send_interim_cancellation_notice
from ietf.meeting.helpers import send_interim_minutes_reminder
from ietf.meeting.models import Session, TimeSlot, Meeting
from ietf.meeting.test_data import make_meeting_test_data, make_interim_meeting
from ietf.name.models import SessionStatusName
from ietf.utils.test_utils import TestCase, login_testing_unauthorized, unicontent
from ietf.utils.mail import outbox
from ietf.utils.text import xslugify

from ietf.person.factories import PersonFactory
from ietf.group.factories import GroupFactory, GroupEventFactory
from ietf.meeting.factories import ( SessionFactory, SessionPresentationFactory, ScheduleFactory,
    MeetingFactory, FloorPlanFactory )
from ietf.doc.factories import DocumentFactory

class MeetingTests(TestCase):
    def setUp(self):
        self.materials_dir = os.path.abspath(settings.TEST_MATERIALS_DIR)
        if not os.path.exists(self.materials_dir):
            os.mkdir(self.materials_dir)
        self.saved_agenda_path = settings.AGENDA_PATH
        settings.AGENDA_PATH = self.materials_dir

    def tearDown(self):
        settings.AGENDA_PATH = self.saved_agenda_path
        shutil.rmtree(self.materials_dir)

    def write_materials_file(self, meeting, doc, content):
        path = os.path.join(self.materials_dir, "%s/%s/%s" % (meeting.number, doc.type_id, doc.external_url))

        dirname = os.path.dirname(path)
        if not os.path.exists(dirname):
            os.makedirs(dirname)

        with open(path, "w") as f:
            f.write(content)

    def write_materials_files(self, meeting, session):

        draft = Document.objects.filter(type="draft", group=session.group).first()

        self.write_materials_file(meeting, session.materials.get(type="agenda"),
                                  "1. WG status (15 minutes)\n\n2. Status of %s\n\n" % draft.name)

        self.write_materials_file(meeting, session.materials.get(type="minutes"),
                                  "1. More work items underway\n\n2. The draft will be finished before next meeting\n\n")

        self.write_materials_file(meeting, session.materials.filter(type="slides").exclude(states__type__slug='slides',states__slug='deleted').first(),
                                  "This is a slideshow")
        

    def test_agenda(self):
        meeting = make_meeting_test_data()
        session = Session.objects.filter(meeting=meeting, group__acronym="mars").first()
        slot = TimeSlot.objects.get(sessionassignments__session=session,sessionassignments__schedule=meeting.agenda)

        self.write_materials_files(meeting, session)

        time_interval = "%s-%s" % (slot.time.strftime("%H:%M").lstrip("0"), (slot.time + slot.duration).strftime("%H:%M").lstrip("0"))

        # plain
        r = self.client.get(urlreverse("ietf.meeting.views.agenda", kwargs=dict(num=meeting.number)))
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        agenda_content = q("#content").html()
        self.assertTrue(session.group.acronym in agenda_content)
        self.assertTrue(session.group.name in agenda_content)
        self.assertTrue(session.group.parent.acronym.upper() in agenda_content)
        self.assertTrue(slot.location.name in agenda_content)
        self.assertTrue(time_interval in agenda_content)

        # Make sure there's a frame for the agenda and it points to the right place
        self.assertTrue(any([session.materials.get(type='agenda').href() in x.attrib["data-src"] for x in q('tr div.modal-body  div.frame')])) 

        # Make sure undeleted slides are present and deleted slides are not
        self.assertTrue(any([session.materials.filter(type='slides').exclude(states__type__slug='slides',states__slug='deleted').first().title in x.text for x in q('tr div.modal-body ul a')]))
        self.assertFalse(any([session.materials.filter(type='slides',states__type__slug='slides',states__slug='deleted').first().title in x.text for x in q('tr div.modal-body ul a')]))

        # text
        # the rest of the results don't have as nicely formatted times
        time_interval = time_interval.replace(":", "")

        r = self.client.get(urlreverse("ietf.meeting.views.agenda", kwargs=dict(num=meeting.number, ext=".txt")))
        self.assertEqual(r.status_code, 200)
        agenda_content = r.content
        self.assertTrue(session.group.acronym in agenda_content)
        self.assertTrue(session.group.name in agenda_content)
        self.assertTrue(session.group.parent.acronym.upper() in agenda_content)
        self.assertTrue(slot.location.name in agenda_content)

        self.assertTrue(time_interval in agenda_content)

        r = self.client.get(urlreverse("ietf.meeting.views.agenda", kwargs=dict(num=meeting.number,name=meeting.unofficial_schedule.name,owner=meeting.unofficial_schedule.owner.email())))
        self.assertEqual(r.status_code, 200)
        self.assertTrue('not the official schedule' in unicontent(r))

        # CSV
        r = self.client.get(urlreverse("ietf.meeting.views.agenda", kwargs=dict(num=meeting.number, ext=".csv")))
        self.assertEqual(r.status_code, 200)
        agenda_content = r.content
        self.assertTrue(session.group.acronym in agenda_content)
        self.assertTrue(session.group.name in agenda_content)
        self.assertTrue(session.group.parent.acronym.upper() in agenda_content)
        self.assertTrue(slot.location.name in agenda_content)

        self.assertTrue(session.materials.get(type='agenda').external_url in unicontent(r))
        self.assertTrue(session.materials.filter(type='slides').exclude(states__type__slug='slides',states__slug='deleted').first().external_url in unicontent(r))
        self.assertFalse(session.materials.filter(type='slides',states__type__slug='slides',states__slug='deleted').first().external_url in unicontent(r))

        # iCal
        r = self.client.get(urlreverse("ietf.meeting.views.ical_agenda", kwargs=dict(num=meeting.number))
                            + "?" + session.group.parent.acronym.upper())
        self.assertEqual(r.status_code, 200)
        agenda_content = r.content
        self.assertTrue(session.group.acronym in agenda_content)
        self.assertTrue(session.group.name in agenda_content)
        self.assertTrue(slot.location.name in agenda_content)
        self.assertTrue("BEGIN:VTIMEZONE" in agenda_content)
        self.assertTrue("END:VTIMEZONE" in agenda_content)        

        self.assertTrue(session.agenda().get_absolute_url() in unicontent(r))
        self.assertTrue(session.materials.filter(type='slides').exclude(states__type__slug='slides',states__slug='deleted').first().get_absolute_url() in unicontent(r))
        # TODO - the ics view uses .all on a queryset in a view so it's showing the deleted slides.
        #self.assertFalse(session.materials.filter(type='slides',states__type__slug='slides',states__slug='deleted').first().get_absolute_url() in unicontent(r))

        # week view
        r = self.client.get(urlreverse("ietf.meeting.views.week_view", kwargs=dict(num=meeting.number)))
        self.assertEqual(r.status_code, 200)
        agenda_content = r.content
        self.assertTrue(session.group.acronym in agenda_content)
        self.assertTrue(slot.location.name in agenda_content)

    def test_agenda_by_room(self):
        meeting = make_meeting_test_data()
        url = urlreverse("ietf.meeting.views.agenda_by_room",kwargs=dict(num=meeting.number))
        login_testing_unauthorized(self,"secretary",url)
        r = self.client.get(url)
        self.assertTrue(all([x in unicontent(r) for x in ['mars','IESG Breakfast','Test Room','Breakfast Room']]))

        url = urlreverse("ietf.meeting.views.agenda_by_room",kwargs=dict(num=meeting.number,name=meeting.unofficial_schedule.name,owner=meeting.unofficial_schedule.owner.email()))
        r = self.client.get(url)
        self.assertTrue(all([x in unicontent(r) for x in ['mars','Test Room',]]))
        self.assertFalse('IESG Breakfast' in unicontent(r))

    def test_agenda_by_type(self):
        meeting = make_meeting_test_data()

        url = urlreverse("ietf.meeting.views.agenda_by_type",kwargs=dict(num=meeting.number))
        login_testing_unauthorized(self,"secretary",url)
        r = self.client.get(url)
        self.assertTrue(all([x in unicontent(r) for x in ['mars','IESG Breakfast','Test Room','Breakfast Room']]))

        url = urlreverse("ietf.meeting.views.agenda_by_type",kwargs=dict(num=meeting.number,name=meeting.unofficial_schedule.name,owner=meeting.unofficial_schedule.owner.email()))
        r = self.client.get(url)
        self.assertTrue(all([x in unicontent(r) for x in ['mars','Test Room',]]))
        self.assertFalse('IESG Breakfast' in unicontent(r))

        url = urlreverse("ietf.meeting.views.agenda_by_type",kwargs=dict(num=meeting.number,type='session'))
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
        self.assertEqual(r.status_code,200)
        self.assertTrue(all([x in unicontent(r) for x in ['mars','Test Room','Breakfast Room']]))
        self.assertFalse('IESG Breakfast' in unicontent(r))


    def test_agenda_week_view(self):
        meeting = make_meeting_test_data()
        url = urlreverse("ietf.meeting.views.week_view",kwargs=dict(num=meeting.number)) + "#farfut"
        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        self.assertTrue(all([x in unicontent(r) for x in ['var IETF', 'setAgendaColor', 'draw_calendar', ]]))

    def test_materials(self):
        meeting = make_meeting_test_data()
        session = Session.objects.filter(meeting=meeting, group__acronym="mars").first()

        self.write_materials_files(meeting, session)
        
        # session agenda
        r = self.client.get(urlreverse("ietf.meeting.views.session_agenda",
                                       kwargs=dict(num=meeting.number, session=session.group.acronym)))
        self.assertEqual(r.status_code, 200)
        self.assertTrue("1. WG status" in unicontent(r))

        # early materials page
        r = self.client.get(urlreverse("ietf.meeting.views.current_materials"))
        self.assertEqual(r.status_code, 302)
        self.assertTrue(meeting.number in r["Location"])

        # test with explicit meeting number in url
        r = self.client.get(urlreverse("ietf.meeting.views.materials", kwargs=dict(num=meeting.number)))
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        row = q('#content td div:contains("%s")' % str(session.group.acronym)).closest("tr")
        self.assertTrue(row.find('a:contains("Agenda")'))
        self.assertTrue(row.find('a:contains("Minutes")'))
        self.assertTrue(row.find('a:contains("Slideshow")'))
        self.assertFalse(row.find("a:contains(\"Bad Slideshow\")"))

        #test with no meeting number in url
        r = self.client.get(urlreverse("ietf.meeting.views.materials", kwargs=dict()))
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        row = q('#content td div:contains("%s")' % str(session.group.acronym)).closest("tr")
        self.assertTrue(row.find('a:contains("Agenda")'))
        self.assertTrue(row.find('a:contains("Minutes")'))
        self.assertTrue(row.find('a:contains("Slideshow")'))
        self.assertFalse(row.find("a:contains(\"Bad Slideshow\")"))

        # FIXME: missing tests of .pdf/.tar generation (some code can
        # probably be lifted from similar tests in iesg/tests.py)

    def test_proceedings(self):
        meeting = make_meeting_test_data()
        session = Session.objects.filter(meeting=meeting, group__acronym="mars").first()
        GroupEventFactory(group=session.group,type='status_update')
        SessionPresentationFactory(document__type_id='recording',session=session)
        SessionPresentationFactory(document__type_id='recording',session=session,document__title="Audio recording for tests")

        self.write_materials_files(meeting, session)

        url = urlreverse("ietf.meeting.views.proceedings", kwargs=dict(num=meeting.number))
        login_testing_unauthorized(self,"secretary",url)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

    def test_proceedings_acknowledgements(self):
        meeting = make_meeting_test_data()
        url = urlreverse('ietf.meeting.views.proceedings_acknowledgements',kwargs={'num':meeting.number})
        login_testing_unauthorized(self,"secretary",url)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

    def test_feed(self):
        meeting = make_meeting_test_data()
        session = Session.objects.filter(meeting=meeting, group__acronym="mars").first()

        r = self.client.get("/feed/wg-proceedings/")
        self.assertEqual(r.status_code, 200)
        self.assertTrue("agenda" in unicontent(r))
        self.assertTrue(session.group.acronym in unicontent(r))

class EditTests(TestCase):
    def setUp(self):
        # make sure we have the colors of the area
        from ietf.group.colors import fg_group_colors, bg_group_colors
        area_upper = "FARFUT"
        fg_group_colors[area_upper] = "#333"
        bg_group_colors[area_upper] = "#aaa"

    def test_edit_agenda(self):
        meeting = make_meeting_test_data()

        self.client.login(username="secretary", password="secretary+password")
        r = self.client.get(urlreverse("ietf.meeting.views.edit_agenda", kwargs=dict(num=meeting.number)))
        self.assertEqual(r.status_code, 200)
        self.assertTrue("load_assignments" in unicontent(r))

    def test_save_agenda_as_and_read_permissions(self):
        meeting = make_meeting_test_data()

        # try to get non-existing agenda
        url = urlreverse("ietf.meeting.views.edit_agenda", kwargs=dict(num=meeting.number,
                                                                       owner=meeting.agenda.owner_email(),
                                                                       name="foo"))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 404)

        # save as new name (requires valid existing agenda)
        url = urlreverse("ietf.meeting.views.edit_agenda", kwargs=dict(num=meeting.number,
                                                                       owner=meeting.agenda.owner_email(),
                                                                       name=meeting.agenda.name))
        self.client.login(username="ad", password="ad+password")
        r = self.client.post(url, {
            'savename': "foo",
            'saveas': "saveas",
            })
        self.assertEqual(r.status_code, 302)
        # Verify that we actually got redirected to a new place.
        self.assertNotEqual(urlparse.urlparse(r.url).path, url)

        # get
        schedule = meeting.get_schedule_by_name("foo")
        url = urlreverse("ietf.meeting.views.edit_agenda", kwargs=dict(num=meeting.number,
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
        url = urlreverse("ietf.meeting.views.edit_agenda", kwargs=dict(num=meeting.number,
                                                                       owner=meeting.agenda.owner_email(),
                                                                       name=meeting.agenda.name))
        self.client.login(username="ad", password="ad+password")
        r = self.client.post(url, {
            'savename': "/no/this/should/not/work/it/is/too/long",
            'saveas': "saveas",
            })
        self.assertEqual(r.status_code, 302)
        self.assertEqual(urlparse.urlparse(r.url).path, url)
        # TODO: Verify that an error message was in fact returned.

        r = self.client.post(url, {
            'savename': "/invalid/chars/",
            'saveas': "saveas",
            })
        # TODO: Verify that an error message was in fact returned.
        self.assertEqual(r.status_code, 302)
        self.assertEqual(urlparse.urlparse(r.url).path, url)

        # Non-ASCII alphanumeric characters
        r = self.client.post(url, {
            'savename': u"f\u00E9ling",
            'saveas': "saveas",
            })
        # TODO: Verify that an error message was in fact returned.
        self.assertEqual(r.status_code, 302)
        self.assertEqual(urlparse.urlparse(r.url).path, url)
        

    def test_edit_timeslots(self):
        meeting = make_meeting_test_data()

        self.client.login(username="secretary", password="secretary+password")
        r = self.client.get(urlreverse("ietf.meeting.views.edit_timeslots", kwargs=dict(num=meeting.number)))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(meeting.room_set.all().first().name in unicontent(r))

    def test_slot_to_the_right(self):
        meeting = make_meeting_test_data()
        session = Session.objects.filter(meeting=meeting, group__acronym="mars").first()
        mars_scheduled = session.timeslotassignments.get(schedule__name='test-agenda')
        mars_slot = TimeSlot.objects.get(sessionassignments__session=session,sessionassignments__schedule__name='test-agenda')
        mars_ends = mars_slot.time + mars_slot.duration

        session = Session.objects.filter(meeting=meeting, group__acronym="ames").first()
        ames_slot_qs = TimeSlot.objects.filter(sessionassignments__session=session,sessionassignments__schedule__name='test-agenda')

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
        self.assertFalse('deleted' in unicontent(r))
        
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
        self.assertEqual(r.status_code, 200)
        self.assertTrue(old_draft.name in unicontent(r))

        r = self.client.post(url,dict(drafts=[new_draft.name,old_draft.name]))
        self.assertTrue(r.status_code, 200)
        q=PyQuery(r.content)
        self.assertTrue(q('form .alert-danger:contains("Already linked:")'))

        self.assertEqual(1,session.sessionpresentation_set.count())
        r = self.client.post(url,dict(drafts=[new_draft.name,]))
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

    def test_list_agendas(self):
        url = urlreverse('ietf.meeting.views.list_agendas',kwargs={'num':self.mtg.number})
        login_testing_unauthorized(self,"secretary",url)
        r = self.client.get(url)
        self.assertTrue(r.status_code, 200)

    def test_delete_schedule(self):
        url = urlreverse('ietf.meeting.views.delete_schedule',
                         kwargs={'num':self.mtg.number,
                                 'owner':self.mtg.agenda.owner.email_address(),
                                 'name':self.mtg.agenda.name,
                         })
        login_testing_unauthorized(self,"secretary",url)
        r = self.client.get(url)
        self.assertTrue(r.status_code, 403)
        r = self.client.post(url,{'save':1})
        self.assertTrue(r.status_code, 403)
        self.assertEqual(self.mtg.schedule_set.count(),2)
        self.mtg.agenda=None
        self.mtg.save()
        r = self.client.get(url)
        self.assertTrue(r.status_code, 200)
        r = self.client.post(url,{'save':1})
        self.assertTrue(r.status_code, 302)
        self.assertEqual(self.mtg.schedule_set.count(),1)

    def test_make_schedule_official(self):
        schedule = self.mtg.schedule_set.exclude(id=self.mtg.agenda.id).first()
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
        self.assertEqual(mtg.agenda,schedule)

# -------------------------------------------------
# Interim Meeting Tests
# -------------------------------------------------

class InterimTests(TestCase):
    def setUp(self):
        self.materials_dir = os.path.abspath(settings.TEST_MATERIALS_DIR)
        if not os.path.exists(self.materials_dir):
            os.mkdir(self.materials_dir)
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
        session.status = SessionStatusName.objects.get(slug='scheda')
        session.save()
        login_testing_unauthorized(self, "secretary", url)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(meeting.number in r.content)

    def test_interim_send_announcement(self):
        make_meeting_test_data()
        meeting = Meeting.objects.filter(type='interim', session__status='apprw', session__group__acronym='mars').first()
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
        self.assertTrue('WG Virtual Meeting' in outbox[-1]['Subject'])

    def test_interim_approve_by_ad(self):
        make_meeting_test_data()
        meeting = Meeting.objects.filter(type='interim', session__status='apprw', session__group__acronym='mars').first()
        url = urlreverse('ietf.meeting.views.interim_request_details', kwargs={'number': meeting.number})
        length_before = len(outbox)
        login_testing_unauthorized(self, "ad", url)
        r = self.client.post(url, {'approve': 'approve'})
        self.assertRedirects(r, urlreverse('ietf.meeting.views.interim_pending'))
        for session in meeting.session_set.all():
            self.assertEqual(session.status.slug, 'scheda')
        self.assertEqual(len(outbox), length_before + 1)
        self.assertTrue('ready for announcement' in outbox[-1]['Subject'])

    def test_interim_approve_by_secretariat(self):
        make_meeting_test_data()
        meeting = Meeting.objects.filter(type='interim', session__status='apprw', session__group__acronym='mars').first()
        url = urlreverse('ietf.meeting.views.interim_request_details', kwargs={'number': meeting.number})
        login_testing_unauthorized(self, "secretary", url)
        r = self.client.post(url, {'approve': 'approve'})
        self.assertRedirects(r, urlreverse('ietf.meeting.views.interim_send_announcement', kwargs={'number': meeting.number}))
        for session in meeting.session_set.all():
            self.assertEqual(session.status.slug, 'scheda')

    def test_upcoming(self):
        make_meeting_test_data()
        url = urlreverse("ietf.meeting.views.upcoming")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        today = datetime.date.today()
        mars_interim = Meeting.objects.filter(date__gt=today, type='interim', session__group__acronym='mars', session__status='sched').first()
        ames_interim = Meeting.objects.filter(date__gt=today, type='interim', session__group__acronym='ames', session__status='canceled').first()
        self.assertTrue(mars_interim.number in r.content)
        self.assertTrue(ames_interim.number in r.content)
        self.assertTrue('IETF - 42' in r.content)
        # cancelled session
        q = PyQuery(r.content)
        self.assertTrue('CANCELLED' in q('[id*="-ames"]').text())
        self.check_interim_tabs(url)

    def test_upcoming_ical(self):
        make_meeting_test_data()
        url = urlreverse("ietf.meeting.views.upcoming_ical")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get('Content-Type'), "text/calendar")
        self.assertEqual(r.content.count('UID'), 5)
        # check filtered output
        url = url + '?filters=mars'
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get('Content-Type'), "text/calendar")
        # print r.content
        self.assertEqual(r.content.count('UID'), 2)


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
        self.assertEqual(Group.objects.filter(type__in=('wg', 'rg'), state__in=('active', 'proposed')).count(),
            len(q("#id_group option")) - 1)  # -1 for options placeholder


    def test_interim_request_single_virtual(self):
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
        self.assertEqual(meeting.number,'interim-%s-%s-%s' % (date.year,group.acronym,'01'))
        self.assertEqual(meeting.city,'')
        self.assertEqual(meeting.country,'')
        self.assertEqual(meeting.time_zone,'UTC')
        session = meeting.session_set.first()
        self.assertEqual(session.remote_instructions,remote_instructions)
        self.assertEqual(session.agenda_note,agenda_note)
        self.assertEqual(session.status.slug,'scheda')
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
        self.assertTrue('interim meeting ready for announcement' in outbox[-1]['Subject'])
        self.assertTrue('iesg-secretary@ietf.org' in outbox[-1]['To'])

    def test_interim_request_single_in_person(self):
        make_meeting_test_data()
        group = Group.objects.get(acronym='mars')
        date = datetime.date.today() + datetime.timedelta(days=30)
        time = datetime.datetime.now().time().replace(microsecond=0,second=0)
        dt = datetime.datetime.combine(date, time)
        duration = datetime.timedelta(hours=3)
        city = 'San Francisco'
        country = 'US'
        time_zone = 'US/Pacific'
        remote_instructions = 'Use webex'
        agenda = 'Intro. Slides. Discuss.'
        agenda_note = 'On second level'
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
        self.assertEqual(meeting.number,'interim-%s-%s-%s' % (date.year,group.acronym,'01'))
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
        time_zone = 'US/Pacific'
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
        
        self.assertRedirects(r,urlreverse('ietf.meeting.views.upcoming'))
        meeting = Meeting.objects.order_by('id').last()
        self.assertEqual(meeting.type_id,'interim')
        self.assertEqual(meeting.date,date)
        self.assertEqual(meeting.number,'interim-%s-%s-%s' % (date.year,group.acronym,'01'))
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
        time_zone = 'US/Pacific'
        remote_instructions = 'Use webex'
        agenda = 'Intro. Slides. Discuss.'
        agenda_note = 'On second level'
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
        self.assertEqual(meeting.number,'interim-%s-%s-%s' % (date.year,group.acronym,'01'))
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
        self.assertEqual(meeting.number,'interim-%s-%s-%s' % (date.year,group.acronym,'02'))
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
        count = Meeting.objects.filter(type='interim',session__status='apprw').distinct().count()

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
        meeting = Meeting.objects.filter(type='interim',session__status='apprw',session__group=group).first()
        self.assertFalse(can_approve_interim_request(meeting=meeting,user=user))
        # Secretariat
        user = User.objects.get(username='secretary')
        self.assertTrue(can_approve_interim_request(meeting=meeting,user=user))
        # related AD
        user = User.objects.get(username='ad')
        self.assertTrue(can_approve_interim_request(meeting=meeting,user=user))
        # other AD
        user = User.objects.get(username='ops-ad')
        self.assertFalse(can_approve_interim_request(meeting=meeting,user=user))
        # WG Chair
        user = User.objects.get(username='marschairman')
        self.assertFalse(can_approve_interim_request(meeting=meeting,user=user))

    def test_can_view_interim_request(self):
        make_meeting_test_data()
        # unprivileged user
        user = User.objects.get(username='plain')
        group = Group.objects.get(acronym='mars')
        meeting = Meeting.objects.filter(type='interim',session__status='apprw',session__group=group).first()
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

    def test_interim_request_details(self):
        make_meeting_test_data()
        meeting = Meeting.objects.filter(type='interim',session__status='apprw',session__group__acronym='mars').first()
        url = urlreverse('ietf.meeting.views.interim_request_details',kwargs={'number':meeting.number})
        login_testing_unauthorized(self,"secretary",url)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

    def test_interim_request_disapprove(self):
        make_meeting_test_data()
        meeting = Meeting.objects.filter(type='interim',session__status='apprw',session__group__acronym='mars').first()
        url = urlreverse('ietf.meeting.views.interim_request_details',kwargs={'number':meeting.number})
        login_testing_unauthorized(self,"secretary",url)
        r = self.client.post(url,{'disapprove':'Disapprove'})
        self.assertRedirects(r, urlreverse('ietf.meeting.views.interim_pending'))
        for session in meeting.session_set.all():
            self.assertEqual(session.status_id,'disappr')

    def test_interim_request_cancel(self):
        make_meeting_test_data()
        meeting = Meeting.objects.filter(type='interim', session__status='apprw', session__group__acronym='mars').first()
        url = urlreverse('ietf.meeting.views.interim_request_details', kwargs={'number': meeting.number})
        # ensure no cancel button for unauthorized user
        self.client.login(username="ameschairman", password="ameschairman+password")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q("a.btn:contains('Cancel')")), 0)
        # ensure cancel button for authorized user
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
        for session in meeting.session_set.all():
            self.assertEqual(session.status_id, 'canceledpa')
            self.assertEqual(session.agenda_note, comments)
        self.assertEqual(len(outbox), length_before)     # no email notice
        # test cancelling after announcement
        meeting = Meeting.objects.filter(type='interim', session__status='sched', session__group__acronym='mars').first()
        url = urlreverse('ietf.meeting.views.interim_request_cancel', kwargs={'number': meeting.number})
        r = self.client.post(url, {'comments': comments})
        self.assertRedirects(r, urlreverse('ietf.meeting.views.upcoming'))
        for session in meeting.session_set.all():
            self.assertEqual(session.status_id, 'canceled')
            self.assertEqual(session.agenda_note, comments)
        self.assertEqual(len(outbox), length_before + 1)
        self.assertTrue('Interim Meeting Cancelled' in outbox[-1]['Subject'])

    def test_interim_request_edit_no_notice(self):
        '''Edit a request.  No notice should go out if it hasn't been announced yet'''
        make_meeting_test_data()
        meeting = Meeting.objects.filter(type='interim', session__status='apprw', session__group__acronym='mars').first()
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
                'session_set-0-requested_duration':formset_initial['requested_duration'],
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
        meeting = Meeting.objects.filter(type='interim', session__status='sched', session__group__acronym='mars').first()
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
                'session_set-0-requested_duration':formset_initial['requested_duration'],
                'session_set-0-remote_instructions':formset_initial['remote_instructions'],
                #'session_set-0-agenda':formset_initial['agenda'],
                'session_set-0-agenda_note':formset_initial['agenda_note'],
                'session_set-TOTAL_FORMS':1,
                'session_set-INITIAL_FORMS':1}
        data.update(form_initial)
        r = self.client.post(url, data)
        self.assertRedirects(r, urlreverse('ietf.meeting.views.interim_request_details', kwargs={'number': meeting.number}))
        self.assertEqual(len(outbox),length_before+1)
        self.assertTrue('CHANGED' in outbox[-1]['Subject'])
        session = meeting.session_set.first()
        timeslot = session.official_timeslotassignment().timeslot
        self.assertEqual(timeslot.time,new_time)
        
    def test_interim_request_details_permissions(self):
        make_meeting_test_data()
        meeting = Meeting.objects.filter(type='interim',session__status='apprw',session__group__acronym='mars').first()
        url = urlreverse('ietf.meeting.views.interim_request_details',kwargs={'number':meeting.number})

        # unprivileged user
        login_testing_unauthorized(self,"plain",url)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 403)

    def test_send_interim_approval_request(self):
        make_meeting_test_data()
        meeting = Meeting.objects.filter(type='interim',session__status='apprw',session__group__acronym='mars').first()
        length_before = len(outbox)
        send_interim_approval_request(meetings=[meeting])
        self.assertEqual(len(outbox),length_before+1)
        self.assertTrue('New Interim Meeting Request' in outbox[-1]['Subject'])

    def test_send_interim_cancellation_notice(self):
        make_meeting_test_data()
        meeting = Meeting.objects.filter(type='interim',session__status='sched',session__group__acronym='mars').first()
        length_before = len(outbox)
        send_interim_cancellation_notice(meeting=meeting)
        self.assertEqual(len(outbox),length_before+1)
        self.assertTrue('Interim Meeting Cancelled' in outbox[-1]['Subject'])

    def test_send_interim_minutes_reminder(self):
        make_meeting_test_data()
        group = Group.objects.get(acronym='mars')
        date = datetime.datetime.today() - datetime.timedelta(days=10)
        meeting = make_interim_meeting(group=group, date=date, status='sched')
        length_before = len(outbox)
        send_interim_minutes_reminder(meeting=meeting)
        self.assertEqual(len(outbox),length_before+1)
        self.assertTrue('Action Required: Minutes' in outbox[-1]['Subject'])


class AjaxTests(TestCase):
    def test_ajax_get_utc(self):
        # test bad queries
        url = urlreverse('ietf.meeting.views.ajax_get_utc') + "?date=2016-1-1&time=badtime&timezone=UTC"
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.content)
        self.assertEqual(data["error"], True)
        url = urlreverse('ietf.meeting.views.ajax_get_utc') + "?date=2016-1-1&time=25:99&timezone=UTC"
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.content)
        self.assertEqual(data["error"], True)
        # test good query
        url = urlreverse('ietf.meeting.views.ajax_get_utc') + "?date=2016-1-1&time=12:00&timezone=US/Pacific"
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.content)
        self.assertTrue('timezone' in data)
        self.assertTrue('time' in data)
        self.assertTrue('utc' in data)
        self.assertTrue('error' not in data)
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
        url = urlreverse('ietf.meeting.views.json_agenda',kwargs={'num':meeting.number})
        r = self.client.get(url)
        self.assertEqual(r.status_code,200)

class FinalizeProceedingsTests(TestCase):
    def test_finalize_proceedings(self):
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
 
class BluesheetsTests(TestCase):

    def setUp(self):
        self.materials_dir = os.path.abspath(settings.TEST_MATERIALS_DIR)
        if not os.path.exists(self.materials_dir):
            os.mkdir(self.materials_dir)
        self.saved_agenda_path = settings.AGENDA_PATH
        settings.AGENDA_PATH = self.materials_dir

    def tearDown(self):
        settings.AGENDA_PATH = self.saved_agenda_path
        shutil.rmtree(self.materials_dir)

    def test_upload_blusheets(self):
        session = SessionFactory(meeting__type_id='ietf')
        url = urlreverse('ietf.meeting.views.upload_session_bluesheets',kwargs={'num':session.meeting.number,'session_id':session.id})
        login_testing_unauthorized(self,"secretary",url)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertFalse(q("div.alert"))
        self.assertFalse(session.sessionpresentation_set.exists())
        test_file = StringIO('this is some text for a test')
        test_file.name = "not_really.pdf"
        r = self.client.post(url,dict(file=test_file))
        self.assertEqual(r.status_code, 302)
        bs_doc = session.sessionpresentation_set.filter(document__type_id='bluesheets').first().document
        self.assertEqual(bs_doc.rev,'00')
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(q("div.alert"))
        test_file = StringIO('this is some different text for a test')
        test_file.name = "also_not_really.pdf"
        r = self.client.post(url,dict(file=test_file))
        self.assertEqual(r.status_code, 302)
        bs_doc = Document.objects.get(pk=bs_doc.pk)
        self.assertEqual(bs_doc.rev,'01')
         
    def test_upload_bluesheets_interim(self):
        session=SessionFactory(meeting__type_id='interim')
        url = urlreverse('ietf.meeting.views.upload_session_bluesheets',kwargs={'num':session.meeting.number,'session_id':session.id})
        login_testing_unauthorized(self,"secretary",url)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertFalse(q("div.alert"))
        self.assertFalse(session.sessionpresentation_set.exists())
        test_file = StringIO('this is some text for a test')
        test_file.name = "not_really.pdf"
        r = self.client.post(url,dict(file=test_file))
        self.assertEqual(r.status_code, 302)
        bs_doc = session.sessionpresentation_set.filter(document__type_id='bluesheets').first().document
        self.assertEqual(bs_doc.rev,'00')
