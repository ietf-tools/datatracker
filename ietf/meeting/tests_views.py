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
from ietf.utils.test_utils import TestCase

class MeetingTests(TestCase):
    def setUp(self):
        self.materials_dir = os.path.abspath("tmp-meeting-materials-dir")
        if not os.path.exists(self.materials_dir):
            os.mkdir(self.materials_dir)
        settings.AGENDA_PATH = self.materials_dir

    def tearDown(self):
        if os.path.exists(self.materials_dir):
            shutil.rmtree(self.materials_dir)

    def write_materials_file(self, meeting, doc, content):
        path = os.path.join(self.materials_dir, "%s/%s/%s" % (meeting.number, doc.type_id, doc.external_url))

        dirname = os.path.dirname(path)
        if not os.path.exists(dirname):
            os.makedirs(dirname)

        with open(path, "w") as f:
            f.write(content)

    def test_agenda(self):
        meeting = make_meeting_test_data()
        session = Session.objects.filter(meeting=meeting, group__acronym="mars").first()
        slot = TimeSlot.objects.get(scheduledsession__session=session)

        time_interval = "%s-%s" % (slot.time.strftime("%H%M"), (slot.time + slot.duration).strftime("%H%M"))

        # plain
        r = self.client.get(urlreverse("ietf.meeting.views.agenda", kwargs=dict(num=meeting.number)))
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        agenda_content = q("#agenda").html()
        self.assertTrue(session.group.acronym in agenda_content)
        self.assertTrue(session.group.name in agenda_content)
        self.assertTrue(session.group.parent.acronym.upper() in agenda_content)
        self.assertTrue(slot.location.name in agenda_content)
        self.assertTrue(time_interval in agenda_content)

        # mobile
        r = self.client.get(urlreverse("ietf.meeting.views.agenda", kwargs=dict(num=meeting.number)),
                            { '_testiphone': "1" })
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        agenda_content = q("#agenda").html()
        self.assertTrue(session.group.acronym in agenda_content)
        self.assertTrue(session.group.name[:10] in agenda_content)
        self.assertTrue(slot.location.name in agenda_content)
        self.assertTrue(time_interval in agenda_content)

        # text
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

        # iCal
        r = self.client.get(urlreverse("ietf.meeting.views.ical_agenda", kwargs=dict(num=meeting.number))
                            + "?" + session.group.parent.acronym.upper())
        self.assertEqual(r.status_code, 200)
        agenda_content = r.content
        self.assertTrue(session.group.acronym in agenda_content)
        self.assertTrue(session.group.name in agenda_content)
        self.assertTrue(slot.location.name in agenda_content)

        # week view
        r = self.client.get(urlreverse("ietf.meeting.views.week_view", kwargs=dict(num=meeting.number)))
        self.assertEqual(r.status_code, 200)
        agenda_content = r.content
        self.assertTrue(session.group.acronym in agenda_content)
        self.assertTrue(slot.location.name in agenda_content)

    def test_materials(self):
        meeting = make_meeting_test_data()
        session = Session.objects.filter(meeting=meeting, group__acronym="mars").first()
        draft = Document.objects.filter(type="draft", group=session.group).first()

        self.write_materials_file(meeting, session.materials.get(type="agenda"),
                                  "1. WG status (15 minutes)\n\n2. Status of %s\n\n" % draft.name)

        self.write_materials_file(meeting, session.materials.get(type="minutes"),
                                  "1. More work items underway\n\n2. The draft will be finished before next meeting\n\n")

        self.write_materials_file(meeting, session.materials.get(type="slides"),
                                  "This is a slideshow")
        
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
        #debug.show('r.content')
        q = PyQuery(r.content)
        row = q('.ietf-materials b:contains("%s")' % str(session.group.acronym.upper())).closest("tr")
        self.assertTrue(row.find("a:contains(\"Agenda\")"))
        self.assertTrue(row.find("a:contains(\"Minutes\")"))
        self.assertTrue(row.find("a:contains(\"Slideshow\")"))

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
        self.assertTrue("load_scheduledsessions" in r.content)

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
        mars_scheduled = session.scheduledsession_set.get()
        mars_slot = TimeSlot.objects.get(scheduledsession__session=session)
        mars_ends = mars_slot.time + mars_slot.duration

        session = Session.objects.filter(meeting=meeting, group__acronym="ames").first()
        ames_slot_qs = TimeSlot.objects.filter(scheduledsession__session=session)

        ames_slot_qs.update(time=mars_ends + datetime.timedelta(seconds=11 * 60))
        self.assertTrue(not mars_slot.slot_to_the_right)
        self.assertTrue(not mars_scheduled.slot_to_the_right)

        ames_slot_qs.update(time=mars_ends + datetime.timedelta(seconds=10 * 60))
        self.assertTrue(mars_slot.slot_to_the_right)
        self.assertTrue(mars_scheduled.slot_to_the_right)
