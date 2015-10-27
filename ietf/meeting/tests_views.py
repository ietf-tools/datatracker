import os
import shutil
import datetime
import urlparse

from django.core.urlresolvers import reverse as urlreverse
from django.conf import settings

from pyquery import PyQuery

from ietf.doc.models import Document
from ietf.meeting.models import Session, TimeSlot
from ietf.meeting.test_data import make_meeting_test_data
from ietf.utils.test_utils import TestCase, login_testing_unauthorized

class MeetingTests(TestCase):
    def setUp(self):
        self.materials_dir = os.path.abspath(settings.TEST_MATERIALS_DIR)
        if not os.path.exists(self.materials_dir):
            os.mkdir(self.materials_dir)
        settings.AGENDA_PATH = self.materials_dir

    def tearDown(self):
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
        slot = TimeSlot.objects.get(sessionassignments__session=session)

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

        # CSV
        r = self.client.get(urlreverse("ietf.meeting.views.agenda", kwargs=dict(num=meeting.number, ext=".csv")))
        self.assertEqual(r.status_code, 200)
        agenda_content = r.content
        self.assertTrue(session.group.acronym in agenda_content)
        self.assertTrue(session.group.name in agenda_content)
        self.assertTrue(session.group.parent.acronym.upper() in agenda_content)
        self.assertTrue(slot.location.name in agenda_content)

        self.assertTrue(session.materials.get(type='agenda').external_url in r.content)
        self.assertTrue(session.materials.filter(type='slides').exclude(states__type__slug='slides',states__slug='deleted').first().external_url in r.content)
        self.assertFalse(session.materials.filter(type='slides',states__type__slug='slides',states__slug='deleted').first().external_url in r.content)

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

        self.assertTrue(session.agenda().get_absolute_url() in r.content)
        self.assertTrue(session.materials.filter(type='slides').exclude(states__type__slug='slides',states__slug='deleted').first().get_absolute_url() in r.content)
        # TODO - the ics view uses .all on a queryset in a view so it's showing the deleted slides.
        #self.assertFalse(session.materials.filter(type='slides',states__type__slug='slides',states__slug='deleted').first().get_absolute_url() in r.content)

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
        self.assertTrue(all([x in r.content for x in ['mars','IESG Breakfast','Test Room','Breakfast Room']]))

    def test_agenda_by_type(self):
        meeting = make_meeting_test_data()

        url = urlreverse("ietf.meeting.views.agenda_by_type",kwargs=dict(num=meeting.number))
        login_testing_unauthorized(self,"secretary",url)
        r = self.client.get(url)
        self.assertTrue(all([x in r.content for x in ['mars','IESG Breakfast','Test Room','Breakfast Room']]))

        url = urlreverse("ietf.meeting.views.agenda_by_type",kwargs=dict(num=meeting.number,type='session'))
        r = self.client.get(url)
        self.assertTrue(all([x in r.content for x in ['mars','Test Room']]))
        self.assertFalse(any([x in r.content for x in ['IESG Breakfast','Breakfast Room']]))

        url = urlreverse("ietf.meeting.views.agenda_by_type",kwargs=dict(num=meeting.number,type='lead'))
        r = self.client.get(url)
        self.assertFalse(any([x in r.content for x in ['mars','Test Room']]))
        self.assertTrue(all([x in r.content for x in ['IESG Breakfast','Breakfast Room']]))

    def test_agenda_room_view(self):
        meeting = make_meeting_test_data()
        url = urlreverse("ietf.meeting.views.room_view",kwargs=dict(num=meeting.number))
        login_testing_unauthorized(self,"secretary",url)
        r = self.client.get(url)
        self.assertTrue(all([x in r.content for x in ['mars','IESG Breakfast','Test Room','Breakfast Room']]))

    def test_session_details(self):
        meeting = make_meeting_test_data()
        url = urlreverse("ietf.meeting.views.session_details", kwargs=dict(num=meeting.number, acronym="mars"))
        r = self.client.get(url)
        self.assertTrue(all([x in r.content for x in ('slides','agenda','minutes')]))
        self.assertFalse('deleted' in r.content)

    def test_materials(self):
        meeting = make_meeting_test_data()
        session = Session.objects.filter(meeting=meeting, group__acronym="mars").first()

        self.write_materials_files(meeting, session)
        
        # session agenda
        r = self.client.get(urlreverse("ietf.meeting.views.session_agenda",
                                       kwargs=dict(num=meeting.number, session=session.group.acronym)))
        self.assertEqual(r.status_code, 200)
        self.assertTrue("1. WG status" in r.content)

        # early materials page
        r = self.client.get(urlreverse("ietf.meeting.views.current_materials"))
        self.assertEqual(r.status_code, 302)
        self.assertTrue(meeting.number in r["Location"])

        r = self.client.get(urlreverse("ietf.meeting.views.materials", kwargs=dict(meeting_num=meeting.number)))
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        row = q('#content td div:contains("%s")' % str(session.group.acronym)).closest("tr")
        self.assertTrue(row.find('a:contains("Agenda")'))
        self.assertTrue(row.find('a:contains("Minutes")'))
        self.assertTrue(row.find('a:contains("Slideshow")'))
        self.assertFalse(row.find("a:contains(\"Bad Slideshow\")"))

        # FIXME: missing tests of .pdf/.tar generation (some code can
        # probably be lifted from similar tests in iesg/tests.py)

    def test_feed(self):
        meeting = make_meeting_test_data()
        session = Session.objects.filter(meeting=meeting, group__acronym="mars").first()

        r = self.client.get("/feed/wg-proceedings/")
        self.assertEqual(r.status_code, 200)
        self.assertTrue("agenda" in r.content)
        self.assertTrue(session.group.acronym in r.content)

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
        self.assertTrue("load_assignments" in r.content)

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
        self.assertTrue(meeting.room_set.all().first().name in r.content)

    def test_slot_to_the_right(self):
        meeting = make_meeting_test_data()
        session = Session.objects.filter(meeting=meeting, group__acronym="mars").first()
        mars_scheduled = session.timeslotassignments.get()
        mars_slot = TimeSlot.objects.get(sessionassignments__session=session)
        mars_ends = mars_slot.time + mars_slot.duration

        session = Session.objects.filter(meeting=meeting, group__acronym="ames").first()
        ames_slot_qs = TimeSlot.objects.filter(sessionassignments__session=session)

        ames_slot_qs.update(time=mars_ends + datetime.timedelta(seconds=11 * 60))
        self.assertTrue(not mars_slot.slot_to_the_right)
        self.assertTrue(not mars_scheduled.slot_to_the_right)

        ames_slot_qs.update(time=mars_ends + datetime.timedelta(seconds=10 * 60))
        self.assertTrue(mars_slot.slot_to_the_right)
        self.assertTrue(mars_scheduled.slot_to_the_right)
