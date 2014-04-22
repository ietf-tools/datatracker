from django.conf import settings
from django.core.urlresolvers import reverse
from ietf.utils.test_utils import TestCase

from ietf.person.models import Person
from ietf.group.models import Group, GroupEvent
from ietf.meeting.models import Meeting, Schedule, Room, TimeSlot, ScheduledSession
from ietf.utils.mail import outbox
from ietf.meeting.test_data import make_meeting_test_data

from pyquery import PyQuery

import datetime
import os
import shutil

class MainTestCase(TestCase):
    def setUp(self):
        self.bluesheet_dir = os.path.abspath("tmp-bluesheet-dir")
        self.bluesheet_path = os.path.join(self.bluesheet_dir,'blue_sheet.rtf')
        os.mkdir(self.bluesheet_dir)
        settings.SECR_BLUE_SHEET_PATH = self.bluesheet_path
        
    def tearDown(self):
        shutil.rmtree(self.bluesheet_dir)
        
    def test_main(self):
        "Main Test"
        url = reverse('meetings')
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_view(self):
        "View Test"
        meeting = make_meeting_test_data()
        url = reverse('meetings_view', kwargs={'meeting_id':meeting.number})
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        q = PyQuery(response.content)
        self.assertEqual(len(q('#id_schedule_selector option')),2)
         
    def test_add_meeting(self):
        "Add Meeting"
        url = reverse('meetings_add')
        post_data = dict(number=1,city='Toronto',date='2014-07-20',country='CA',
                         time_zone='America/New_York',venue_name='Hilton',
                         venue_addr='100 First Ave')
        self.client.login(username='secretary', password='secretary+password')
        response = self.client.post(url, post_data, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Meeting.objects.count(),1)
        self.assertEqual(Schedule.objects.count(),1)

    def test_edit_meeting(self):
        "Edit Meeting"
        Meeting.objects.create(number=1,
                               type_id='ietf',
                               date=datetime.datetime(2014,7,20))
        url = reverse('meetings_edit_meeting',kwargs={'meeting_id':1})
        post_data = dict(number='1',date='2014-07-20',city='Toronto')
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.post(url, post_data,follow=True)
        self.assertEqual(response.status_code, 200)
        meeting = Meeting.objects.get(number=1)
        self.assertEqual(meeting.city,'Toronto')

    def test_blue_sheets(self):
        "Test Bluesheets"
        meeting = make_meeting_test_data()
        url = reverse('meetings_blue_sheet',kwargs={'meeting_id':meeting.number})
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        url = reverse('meetings_blue_sheet_generate',kwargs={'meeting_id':meeting.number})
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(os.path.exists(self.bluesheet_path))
        
    def test_notifications(self):
        "Test Notifications"
        meeting = make_meeting_test_data()
        url = reverse('meetings_notifications',kwargs={'meeting_id':42})
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        q = PyQuery(response.content)
        self.assertEqual(q('#id_notification_list').html(),'ames,mars')
        
        # test that only changes since last notification show up
        mars_group = Group.objects.get(acronym='mars')
        ames_group = Group.objects.get(acronym='ames')
        now = datetime.datetime.now()
        then = datetime.datetime.now()+datetime.timedelta(hours=1)
        person = Person.objects.get(name="(System)")
        GroupEvent.objects.create(group=mars_group,time=now,type='sent_notification',
                                  by=person,desc='sent scheduled notification for %s' % meeting)
        ss = meeting.agenda.scheduledsession_set.get(session__group=ames_group)
        ss.modified = then
        ss.save()
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        q = PyQuery(response.content)
        self.assertEqual(q('#id_notification_list').html(),'ames')
        
        # test that email goes out
        mailbox_before = len(outbox)
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(outbox), mailbox_before + 1)
        
    def test_meetings_select(self):
        make_meeting_test_data()
        url = reverse('meetings_select',kwargs={'meeting_id':42,'schedule_name':'test-agenda'})
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
    
    def test_meetings_rooms(self):
        meeting = make_meeting_test_data()
        url = reverse('meetings_rooms',kwargs={'meeting_id':42,'schedule_name':'test-agenda'})
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        q = PyQuery(response.content)
        self.assertEqual(len(q("#id_rooms_table tr")),2)
        
        # test delete
        # first unschedule sessions so we can delete
        ScheduledSession.objects.filter(schedule=meeting.agenda).delete()
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.post(url, {
            'room-TOTAL_FORMS':  q('input[name="room-TOTAL_FORMS"]').val(),
            'room-INITIAL_FORMS': q('input[name="room-INITIAL_FORMS"]').val(),
            'room-0-meeting': q('input[name="room-0-meeting"]').val(),
            'room-0-id': q('input[name="room-0-id"]').val(),
            'room-0-name': q('input[name="room-0-name"]').val(),
            'room-0-capacity': q('input[name="room-0-capacity"]').val(),
            'room-0-DELETE': 'on'
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Room.objects.filter(meeting=meeting).count(),0)
        
    def test_meetings_times(self):
        make_meeting_test_data()
        url = reverse('meetings_times',kwargs={'meeting_id':42,'schedule_name':'test-agenda'})
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        
    def test_meetings_times_delete(self):
        meeting = make_meeting_test_data()
        qs = TimeSlot.objects.filter(meeting=meeting,type='session')
        before = qs.count()
        url = reverse('meetings_times_delete',kwargs={
            'meeting_id':42,
            'schedule_name':'test-agenda',
            'time':qs.first().time.strftime("%Y:%m:%d:%H:%M")
        })
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        after = TimeSlot.objects.filter(meeting=meeting,type='session').count()
        self.assertEqual(after,before - (Room.objects.filter(meeting=meeting).count()))
        
    def test_meetings_times_edit(self):
        meeting = make_meeting_test_data()
        timeslot = TimeSlot.objects.filter(meeting=meeting,type='session').first()
        url = reverse('meetings_times_edit',kwargs={
            'meeting_id':42,
            'schedule_name':'test-agenda',
            'time':timeslot.time.strftime("%Y:%m:%d:%H:%M")
        })
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.post(url, {
            'day':'1',
            'time':'08:00',
            'duration_hours':'1',
            'duration_minutes':'0',
            'name':'Testing'
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(TimeSlot.objects.filter(meeting=meeting,name='Testing'))
        
    def test_meetings_nonsession(self):
        make_meeting_test_data()
        url = reverse('meetings_non_session',kwargs={'meeting_id':42,'schedule_name':'test-agenda'})
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
    
    def test_meetings_select_group(self):
        make_meeting_test_data()
        url = reverse('meetings_select_group',kwargs={'meeting_id':42,'schedule_name':'test-agenda'})
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        q = PyQuery(response.content)
        self.assertEqual(len(q("#id_scheduled_sessions")),1)
    
    # def test_meetings_schedule():
    
