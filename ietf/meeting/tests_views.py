import os
import shutil
import datetime
import urlparse

from django.core.urlresolvers import reverse as urlreverse
from django.conf import settings

from pyquery import PyQuery

from ietf.doc.models import Document
from ietf.group.models import Group
from ietf.meeting.models import Session, TimeSlot, Meeting
from ietf.meeting.test_data import make_meeting_test_data
from ietf.utils.test_utils import TestCase, login_testing_unauthorized, unicontent

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

    def test_agenda_by_type(self):
        meeting = make_meeting_test_data()

        url = urlreverse("ietf.meeting.views.agenda_by_type",kwargs=dict(num=meeting.number))
        login_testing_unauthorized(self,"secretary",url)
        r = self.client.get(url)
        self.assertTrue(all([x in unicontent(r) for x in ['mars','IESG Breakfast','Test Room','Breakfast Room']]))

        url = urlreverse("ietf.meeting.views.agenda_by_type",kwargs=dict(num=meeting.number,type='session'))
        r = self.client.get(url)
        self.assertTrue(all([x in unicontent(r) for x in ['mars','Test Room']]))
        self.assertFalse(any([x in unicontent(r) for x in ['IESG Breakfast','Breakfast Room']]))

        url = urlreverse("ietf.meeting.views.agenda_by_type",kwargs=dict(num=meeting.number,type='lead'))
        r = self.client.get(url)
        self.assertFalse(any([x in unicontent(r) for x in ['mars','Test Room']]))
        self.assertTrue(all([x in unicontent(r) for x in ['IESG Breakfast','Breakfast Room']]))

    def test_agenda_room_view(self):
        meeting = make_meeting_test_data()
        url = urlreverse("ietf.meeting.views.room_view",kwargs=dict(num=meeting.number))
        login_testing_unauthorized(self,"secretary",url)
        r = self.client.get(url)
        self.assertTrue(all([x in unicontent(r) for x in ['mars','IESG Breakfast','Test Room','Breakfast Room']]))

    def test_session_details(self):
        meeting = make_meeting_test_data()
        url = urlreverse("ietf.meeting.views.session_details", kwargs=dict(num=meeting.number, acronym="mars"))
        r = self.client.get(url)
        self.assertTrue(all([x in unicontent(r) for x in ('slides','agenda','minutes')]))
        self.assertFalse('deleted' in unicontent(r))

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

class InterimTests(TestCase):
    def test_upcoming(self):
        make_meeting_test_data()
        r = self.client.get("/meeting/upcoming/")
        self.assertEqual(r.status_code, 200)
        today = datetime.date.today()
        mars_interim = Meeting.objects.filter(date__gt=today,type='interim',number__contains='mars').first()
        ames_interim = Meeting.objects.filter(date__gt=today,type='interim',number__contains='ames').first()
        self.assertTrue(mars_interim.number in r.content)
        self.assertTrue(ames_interim.number in r.content)
        # cancelled session
        q = PyQuery(r.content)
        self.assertTrue('CANCELLED' in q('[id*="-ames"]').text())

    def test_upcoming_ics(self):
        make_meeting_test_data()
        r = self.client.get("/meeting/upcoming.ics/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get('Content-Type'),"text/calendar")

    def test_interim_request_permissions(self):
        '''Ensure only authorized users see link to request interim meeting'''
        # test unauthorized
        upcoming_url = urlreverse("ietf.meeting.views.upcoming")
        request_url = urlreverse("ietf.meeting.views.interim_request")
        r = self.client.get(upcoming_url)
        self.assertNotContains(r,'Request new interim meeting')
        r = self.client.get(request_url)
        self.assertRedirects(r, '/accounts/login/?next=/meeting/interim/request/')

        # test authorized
        self.client.login(username="secretary", password="secretary+password")
        r = self.client.get(upcoming_url)
        self.assertContains(r,'Request new interim meeting')
        r = self.client.get(request_url)
        self.assertEqual(r.status_code, 200)

    def test_interim_request_options(self):
        make_meeting_test_data()

        # secretariat can request for any group
        self.client.login(username="secretary", password="secretary+password")
        r = self.client.get("/meeting/interim/request/")
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(Group.objects.filter(type__in=('wg','rg'),state='active').count(),
            len(q("#id_group option")) -1 )  # -1 for options placeholder

    def test_interim_request_single(self):
        make_meeting_test_data()
        group = Group.objects.get(acronym='mars')
        date = datetime.date.today() + datetime.timedelta(days=30)
        time = datetime.datetime.now().time().replace(microsecond=0,second=0)
        dt = datetime.datetime.combine(date, time)
        duration = datetime.timedelta(hours=3)
        city = 'San Francisco'
        country = 'US'
        timezone = 'US/Pacific'
        remote_instructions = 'Use webex'
        agenda = 'Intro. Slides. Discuss.'
        agenda_note = 'On second level'
        self.client.login(username="secretary", password="secretary+password")
        data = {'group':group.pk,
                'meeting_type':'single',
                'form-0-date':date.strftime("%Y-%m-%d"),
                'form-0-time':time.strftime('%H:%M'),
                'form-0-duration':'03:00:00',
                'form-0-city':city,
                'form-0-country':country,
                'form-0-timezone':timezone,
                'form-0-remote_instructions':remote_instructions,
                'form-0-agenda':agenda,
                'form-0-agenda_note':agenda_note,
                'form-TOTAL_FORMS':1,
                'form-INITIAL_FORMS':0}

        r = self.client.post(urlreverse("ietf.meeting.views.interim_request"),data)
        
        self.assertRedirects(r,urlreverse('ietf.meeting.views.upcoming'))
        meeting = Meeting.objects.order_by('id').last()
        self.assertEqual(meeting.type_id,'interim')
        self.assertEqual(meeting.date,date)
        self.assertEqual(meeting.number,'interim-%s-%s-%s' % (date.year,group.acronym,1))
        self.assertEqual(meeting.city,city)
        self.assertEqual(meeting.country,country)
        self.assertEqual(meeting.time_zone,timezone)
        self.assertEqual(meeting.agenda_note,agenda_note)
        session = meeting.session_set.first()
        self.assertEqual(session.remote_instructions,remote_instructions)
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
        timezone = 'US/Pacific'
        remote_instructions = 'Use webex'
        agenda = 'Intro. Slides. Discuss.'
        agenda_note = 'On second level'
        self.client.login(username="secretary", password="secretary+password")
        data = {'group':group.pk,
                'meeting_type':'multi-day',
                'form-0-date':date.strftime("%Y-%m-%d"),
                'form-0-time':time.strftime('%H:%M'),
                'form-0-duration':'03:00:00',
                'form-0-city':city,
                'form-0-country':country,
                'form-0-timezone':timezone,
                'form-0-remote_instructions':remote_instructions,
                'form-0-agenda':agenda,
                'form-0-agenda_note':agenda_note,
                'form-1-date':date2.strftime("%Y-%m-%d"),
                'form-1-time':time.strftime('%H:%M'),
                'form-1-duration':'03:00:00',
                'form-1-city':city,
                'form-1-country':country,
                'form-1-timezone':timezone,
                'form-1-remote_instructions':remote_instructions,
                'form-1-agenda':agenda,
                'form-1-agenda_note':agenda_note,
                'form-TOTAL_FORMS':2,
                'form-INITIAL_FORMS':0}

        r = self.client.post(urlreverse("ietf.meeting.views.interim_request"),data)
        
        self.assertRedirects(r,urlreverse('ietf.meeting.views.upcoming'))
        meeting = Meeting.objects.order_by('id').last()
        self.assertEqual(meeting.type_id,'interim')
        self.assertEqual(meeting.date,date)
        self.assertEqual(meeting.number,'interim-%s-%s-%s' % (date.year,group.acronym,1))
        self.assertEqual(meeting.city,city)
        self.assertEqual(meeting.country,country)
        self.assertEqual(meeting.time_zone,timezone)
        self.assertEqual(meeting.agenda_note,agenda_note)
        self.assertEqual(meeting.session_set.count(),2)
        for session in meeting.session_set.all():
            self.assertEqual(session.remote_instructions,remote_instructions)
            timeslot = session.official_timeslotassignment().timeslot
            self.assertEqual(timeslot.time,dt2)
            self.assertEqual(timeslot.duration,duration)

