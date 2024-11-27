# Copyright The IETF Trust 2013-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import datetime

from pyquery import PyQuery

import debug         # pyflakes:ignore

from django.urls import reverse
from django.utils import timezone

from ietf.group.models import Group, GroupEvent
from ietf.meeting.factories import MeetingFactory
from ietf.meeting.models import Meeting, Room, TimeSlot, SchedTimeSessAssignment, Session, SchedulingEvent
from ietf.meeting.test_data import make_meeting_test_data
from ietf.name.models import ConstraintName, SessionStatusName
from ietf.person.models import Person
from ietf.secr.meetings.forms import get_times
from ietf.utils.mail import outbox
from ietf.utils.test_utils import TestCase 


class SecrMeetingTestCase(TestCase):
    settings_temp_path_overrides = TestCase.settings_temp_path_overrides + ['AGENDA_PATH']

    def test_main(self):
        "Main Test"
        meeting = make_meeting_test_data()
        url = reverse('ietf.secr.meetings.views.main')
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        response = self.client.post(url, {'meeting':meeting.number})
        url = reverse('ietf.secr.meetings.views.view', kwargs={'meeting_id':meeting.number})
        self.assertRedirects(response,url)

    def test_view(self):
        "View Test"
        meeting = make_meeting_test_data()
        url = reverse('ietf.secr.meetings.views.view', kwargs={'meeting_id':meeting.number})
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        q = PyQuery(response.content)
        self.assertEqual({option.get('value') for option in q('#id_schedule_selector option:not([value=""])')}, {'base', 'test-schedule', 'test-unofficial-schedule'})
         
    def test_add_meeting(self):
        "Add Meeting"
        meeting = make_meeting_test_data()
        number = int(meeting.number) + 1
        count = Meeting.objects.count()
        url = reverse('ietf.secr.meetings.views.add')
        post_data = dict(
            number=number,city='Toronto',date='2014-07-20',country='CA',
            time_zone='America/New_York',venue_name='Hilton',
            days=6,
            venue_addr='100 First Ave',
            idsubmit_cutoff_day_offset_00=13,
            idsubmit_cutoff_day_offset_01=20,
            idsubmit_cutoff_time_utc     =datetime.timedelta(hours=23, minutes=59, seconds=59),
            idsubmit_cutoff_warning_days =datetime.timedelta(days=21),
            submission_start_day_offset=90,
            submission_cutoff_day_offset=26,
            submission_correction_day_offset=50,
            group_conflict_types=('conflict', 'conflic2', 'key_participant'),
        )

        self.client.login(username='secretary', password='secretary+password')
        response = self.client.post(url, post_data, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Meeting.objects.count(),count + 1)
        new_meeting = Meeting.objects.get(number=number)
        
        self.assertTrue(new_meeting.schedule)
        self.assertEqual(new_meeting.schedule.name, 'sec-retary-1')
        self.assertTrue(new_meeting.schedule.base)
        self.assertEqual(new_meeting.schedule.base.name, 'base')
        self.assertEqual(new_meeting.attendees, None)
        self.assertCountEqual(
            [cn.slug for cn in new_meeting.group_conflict_types.all()],
            post_data['group_conflict_types'],
        )
        self.assertEqual(
            new_meeting.session_request_lock_message, 
            "Session requests for this meeting have not yet opened.",
        )

    def test_add_meeting_default_conflict_types(self):
        """Add meeting should default to same conflict types as previous meeting"""
        def _run_test(mtg):
            url = reverse('ietf.secr.meetings.views.add')
            r = self.client.get(url)
            q = PyQuery(r.content)
            selected_items = q('#id_group_conflict_types input[checked]')
            selected_values = [si.value for si in selected_items]
            expected_values = [cn.slug for cn in mtg.group_conflict_types.all()]
            self.assertCountEqual(selected_values, expected_values)

        self.client.login(username='secretary', password='secretary+password')

        meeting = MeetingFactory(type_id='ietf', group_conflicts=[])  # start with no conflicts selected
        _run_test(meeting)

        # enable one
        meeting.group_conflict_types.add(ConstraintName.objects.filter(is_group_conflict=True).first())
        self.assertEqual(meeting.group_conflict_types.count(), 1)
        _run_test(meeting)

        # enable a few ([::2] selects every other)
        meeting.group_conflict_types.clear()
        for cn in ConstraintName.objects.filter(is_group_conflict=True)[::2]:
            meeting.group_conflict_types.add(cn)
        self.assertGreater(meeting.group_conflict_types.count(), 1)
        _run_test(meeting)

    def test_edit_meeting(self):
        "Edit Meeting"
        meeting = make_meeting_test_data()
        url = reverse('ietf.secr.meetings.views.edit_meeting',kwargs={'meeting_id':meeting.number})
        post_data = dict(number=meeting.number,
                         date='2014-07-20',
                         city='Toronto',
                         time_zone='America/Toronto',
                         days=7,
                         idsubmit_cutoff_day_offset_00=13,
                         idsubmit_cutoff_day_offset_01=20,
                         idsubmit_cutoff_time_utc     =datetime.timedelta(hours=23, minutes=59, seconds=59),
                         idsubmit_cutoff_warning_days =datetime.timedelta(days=21),
                         submission_start_day_offset=90,
                         submission_cutoff_day_offset=26,
                         submission_correction_day_offset=50,
                         attendees=1234,
                         group_conflict_types=[
                             cn.slug for cn in ConstraintName.objects.filter(
                                 is_group_conflict=True
                             ).exclude(
                                 meeting=meeting,  # replace original set with those not assigned to the meeting
                             )
                         ]
                    )
        self.assertGreater(len(post_data['group_conflict_types']), 0)  # test should include at least one
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.post(url, post_data, follow=True)
        self.assertEqual(response.status_code, 200)
        meeting = Meeting.objects.get(number=meeting.number)
        self.assertEqual(meeting.city,'Toronto')
        self.assertEqual(meeting.attendees,1234)
        self.assertCountEqual(
            [cn.slug for cn in meeting.group_conflict_types.all()],
            post_data['group_conflict_types'],
        )
        
    def test_notifications(self):
        "Test Notifications"
        meeting = make_meeting_test_data()
        mars_group = Group.objects.get(acronym='mars')
        ames_group = Group.objects.get(acronym='ames')
        ames_stsa = meeting.schedule.assignments.get(session__group=ames_group)
        assert SchedulingEvent.objects.filter(session=ames_stsa.session).order_by('-id')[0].status_id == 'schedw'
        mars_stsa = meeting.schedule.assignments.get(session__group=mars_group)
        SchedulingEvent.objects.create(session=mars_stsa.session, status=SessionStatusName.objects.get(slug='appr'), by=Person.objects.get(name="(System)"))
        url = reverse('ietf.secr.meetings.views.notifications',kwargs={'meeting_id':72})
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        q = PyQuery(response.content)
        self.assertEqual(q('#id_notification_list').html(),'ames, mars')

        # test that only changes since last notification show up
        now = timezone.now()
        then = timezone.now()+datetime.timedelta(hours=1)
        person = Person.objects.get(name="(System)")
        GroupEvent.objects.create(group=mars_group,time=now,type='sent_notification',
                                  by=person,desc='sent scheduled notification for %s' % meeting)
        ss = meeting.schedule.assignments.get(session__group=ames_group)
        ss.modified = then
        ss.save()
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        q = PyQuery(response.content)
        self.assertEqual(q('#id_notification_list').html(),'ames')
        
        # test post: email goes out, status changed
        mailbox_before = len(outbox)
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(outbox), mailbox_before + 1)
        ames_stsa = meeting.schedule.assignments.get(session__group=ames_group)
        self.assertEqual(SchedulingEvent.objects.filter(session=ames_stsa.session).order_by('-id')[0].status_id, 'sched')
        mars_stsa = meeting.schedule.assignments.get(session__group=mars_group)
        self.assertEqual(SchedulingEvent.objects.filter(session=mars_stsa.session).order_by('-id')[0].status_id, 'sched')

    def test_meetings_rooms(self):
        meeting = make_meeting_test_data()
        url = reverse('ietf.secr.meetings.views.rooms',kwargs={'meeting_id':72,'schedule_name':'test-schedule'})
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        q = PyQuery(response.content)
        self.assertEqual(len(q("#id_rooms_table tr input[type='checkbox']")),meeting.room_set.count()+1)
        
        # test delete
        # first unschedule sessions so we can delete
        SchedTimeSessAssignment.objects.filter(schedule__in=[meeting.schedule, meeting.schedule.base, meeting.unofficial_schedule]).delete()
        self.client.login(username="secretary", password="secretary+password")
        post_dict = {
            'room-TOTAL_FORMS':  q('input[name="room-TOTAL_FORMS"]').val(),
            'room-INITIAL_FORMS': q('input[name="room-INITIAL_FORMS"]').val(),
        }
        for i in range(meeting.room_set.count()):
            for attr in ['meeting','id','name','capacity','DELETE']:
                key = 'room-%d-%s' % (i,attr)
                post_dict[key] = q('input[name="%s"]' % key).val()
        response = self.client.post(url, post_dict)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Room.objects.filter(meeting=meeting).count(),0)
        
    def test_meetings_times(self):
        make_meeting_test_data()
        url = reverse('ietf.secr.meetings.views.times',kwargs={'meeting_id':72,'schedule_name':'test-schedule'})
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        response = self.client.post(url, {
            'day': 0,
            'time':'08:00',
            'duration':'01:00',
            'name':'Test Morning Session'
        }, follow=True)
        self.assertRedirects(response, url)
        self.assertContains(response, 'Test Morning Session')

    def test_meetings_times_delete(self):
        meeting = make_meeting_test_data()
        qs = TimeSlot.objects.filter(meeting=meeting,type='regular')
        before = qs.count()
        expected_deletion_count = qs.filter(time=qs.first().time).count() 
        url = reverse('ietf.secr.meetings.views.times_delete',kwargs={
            'meeting_id':meeting.number,
            'schedule_name':meeting.schedule.name,
            'time':qs.first().time.astimezone(meeting.tz()).strftime("%Y:%m:%d:%H:%M")
        })
        redirect_url = reverse('ietf.secr.meetings.views.times',kwargs={
            'meeting_id':meeting.number,
            'schedule_name':meeting.schedule.name
        })
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        response = self.client.post(url, {'post':'yes'})
        self.assertRedirects(response, redirect_url)
        after = TimeSlot.objects.filter(meeting=meeting,type='regular').count()
        self.assertEqual(after,before - expected_deletion_count)
        
    def test_meetings_times_edit(self):
        meeting = make_meeting_test_data()
        timeslot = TimeSlot.objects.filter(meeting=meeting,type='regular').first()
        url = reverse('ietf.secr.meetings.views.times_edit',kwargs={
            'meeting_id':72,
            'schedule_name':'test-schedule',
            'time':timeslot.time.astimezone(meeting.tz()).strftime("%Y:%m:%d:%H:%M")
        })
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.post(url, {
            'day':'1',
            'time':'08:00',
            'duration':'09:00',
            'name':'Testing'
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(TimeSlot.objects.filter(meeting=meeting,name='Testing'))
        
    def test_meetings_misc_sessions(self):
        make_meeting_test_data()
        url = reverse('ietf.secr.meetings.views.misc_sessions',kwargs={'meeting_id':72,'schedule_name':'test-schedule'})
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
    
    def test_meetings_misc_session_add_valid(self):
        meeting = make_meeting_test_data()
        room = meeting.room_set.first()
        group = Group.objects.get(acronym='secretariat')
        url = reverse('ietf.secr.meetings.views.misc_sessions',kwargs={'meeting_id':72,'schedule_name':'test-schedule'})
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.post(url, {
            'day':'1',
            'time':'08:00',
            'duration':'02:00',
            'name':'Testing',
            'short':'test',
            'purpose_0': 'admin',  # purpose
            'purpose_1':'reg',  # type
            'group':group.pk,
            'location': room.pk,
            'remote_instructions': 'http://webex.com/foobar',
        })
        self.assertRedirects(response, url)
        session = Session.objects.filter(meeting=meeting, name='Testing').first()
        self.assertTrue(session)

        self.assertEqual(session.timeslotassignments.first().timeslot.location, room)

    def test_meetings_misc_session_add_invalid(self):
        make_meeting_test_data()
        group = Group.objects.get(acronym='secretariat')
        url = reverse('ietf.secr.meetings.views.misc_sessions',kwargs={'meeting_id':72,'schedule_name':'test-schedule'})
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.post(url, {
            'day':'1',
            'time':'08:00',
            'duration':'10',
            'name':'Testing',
            'short':'test',
            'type':'reg',
            'group':group.pk,
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'invalid format')

    def test_meetings_misc_session_edit(self):
        meeting = make_meeting_test_data()
        session = meeting.session_set.exclude(name='').first()   # get first misc session
        timeslot = session.official_timeslotassignment().timeslot
        url = reverse('ietf.secr.meetings.views.misc_session_edit',kwargs={'meeting_id':72,'schedule_name':meeting.schedule.name,'slot_id':timeslot.pk})
        redirect_url = reverse('ietf.secr.meetings.views.misc_sessions',kwargs={'meeting_id':72,'schedule_name':'test-schedule'})
        new_time = (timeslot.time + datetime.timedelta(days=1)).astimezone(meeting.tz())
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        response = self.client.post(url, {
            'name':'IETF Hackathon',
            'short':'hackathon',
            'location':timeslot.location.id,
            'group':session.group.id,
            'time':new_time.strftime('%H:%M'),
            'duration':'01:00',
            'day':'2',
            'purpose_0': 'coding',  # purpose
            'purpose_1': 'other',  # type
            'remote_instructions': 'http://webex.com/foobar',
        })
        self.assertRedirects(response, redirect_url)
        session = Session.objects.get(pk=session.pk)  # get a clean instance to avoid cache problems
        timeslot = session.official_timeslotassignment().timeslot
        self.assertEqual(timeslot.time, new_time)

    def test_meetings_misc_session_delete(self):
        meeting = make_meeting_test_data()
        schedule = meeting.schedule.base
        slot = schedule.assignments.filter(timeslot__type='reg').first().timeslot
        url = reverse('ietf.secr.meetings.views.misc_session_delete', kwargs={'meeting_id':meeting.number,'schedule_name':schedule.name,'slot_id':slot.id})
        target = reverse('ietf.secr.meetings.views.misc_sessions', kwargs={'meeting_id':meeting.number,'schedule_name':schedule.name})
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        response = self.client.post(url, {'post':'yes'})
        self.assertRedirects(response, target)
        self.assertFalse(schedule.assignments.filter(timeslot=slot))

    def test_meetings_misc_session_cancel(self):
        meeting = make_meeting_test_data()
        schedule = meeting.schedule.base
        slot = schedule.assignments.filter(timeslot__type='reg').first().timeslot
        url = reverse('ietf.secr.meetings.views.misc_session_cancel', kwargs={'meeting_id':meeting.number,'schedule_name':schedule.name,'slot_id':slot.id})
        redirect_url = reverse('ietf.secr.meetings.views.misc_sessions', kwargs={'meeting_id':meeting.number,'schedule_name':schedule.name})
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        response = self.client.post(url, {'post':'yes'})
        self.assertRedirects(response, redirect_url)
        session = slot.sessionassignments.filter(schedule=schedule).first().session
        self.assertEqual(SchedulingEvent.objects.filter(session=session).order_by('-id')[0].status_id, 'canceled')

    def test_meetings_regular_session_edit(self):
        meeting = make_meeting_test_data()
        session = Session.objects.filter(meeting=meeting,group__acronym='mars').first()
        url = reverse('ietf.secr.meetings.views.regular_session_edit', kwargs={'meeting_id':meeting.number,'schedule_name':meeting.schedule.name,'session_id':session.id})
        redirect_url = reverse('ietf.secr.meetings.views.regular_sessions', kwargs={'meeting_id':meeting.number,'schedule_name':meeting.schedule.name})
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        response = self.client.post(url, {'agenda_note':'TEST'})
        self.assertRedirects(response, redirect_url)
        session = Session.objects.get(id=session.id)
        self.assertEqual(session.agenda_note, 'TEST')

    # ----------------------
    # Unit Tests
    # -----------------------
    def test_get_times(self):
        meeting = make_meeting_test_data()
        timeslot = meeting.timeslot_set.filter(type='regular').first()
        day = (timeslot.time.weekday() + 1) % 7 + 1  # fix up to match django __week_day filter
        times = get_times(meeting,day)
        values = [ x[0] for x in times ]
        self.assertTrue(times)
        self.assertTrue(timeslot.time.strftime('%H%M') in values)
