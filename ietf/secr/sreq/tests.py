# Copyright The IETF Trust 2013-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import datetime

from django.urls import reverse

import debug                            # pyflakes:ignore

from ietf.utils.test_utils import TestCase
from ietf.group.factories import GroupFactory, RoleFactory
from ietf.meeting.models import Session, ResourceAssociation, SchedulingEvent, Constraint
from ietf.meeting.factories import MeetingFactory, SessionFactory
from ietf.name.models import ConstraintName, TimerangeName
from ietf.person.models import Person
from ietf.secr.sreq.forms import SessionForm
from ietf.utils.mail import outbox, empty_outbox, get_payload_text

from pyquery import PyQuery

SECR_USER='secretary'

class SreqUrlTests(TestCase):
    def test_urls(self):
        MeetingFactory(type_id='ietf',date=datetime.date.today())

        self.client.login(username="secretary", password="secretary+password")

        r = self.client.get("/secr/")
        self.assertEqual(r.status_code, 200)

        r = self.client.get("/secr/sreq/")
        self.assertEqual(r.status_code, 200)

        testgroup=GroupFactory()
        r = self.client.get("/secr/sreq/%s/new/" % testgroup.acronym)
        self.assertEqual(r.status_code, 200)

class SessionRequestTestCase(TestCase):
    def test_main(self):
        meeting = MeetingFactory(type_id='ietf', date=datetime.date.today())
        SessionFactory.create_batch(2, meeting=meeting, status_id='sched')
        SessionFactory.create_batch(2, meeting=meeting, status_id='disappr')
        # An additional unscheduled group comes from make_immutable_base_data
        url = reverse('ietf.secr.sreq.views.main')
        self.client.login(username="secretary", password="secretary+password")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        sched = r.context['scheduled_groups']
        self.assertEqual(len(sched), 2)
        unsched = r.context['unscheduled_groups']
        self.assertEqual(len(unsched), 8)

    def test_approve(self):
        meeting = MeetingFactory(type_id='ietf', date=datetime.date.today())
        ad = Person.objects.get(user__username='ad')
        area = RoleFactory(name_id='ad', person=ad, group__type_id='area').group
        mars = GroupFactory(parent=area, acronym='mars')
        # create session waiting for approval
        session = SessionFactory(meeting=meeting, group=mars, status_id='apprw')
        url = reverse('ietf.secr.sreq.views.approve', kwargs={'acronym':'mars'})
        self.client.login(username="ad", password="ad+password")
        r = self.client.get(url)
        self.assertRedirects(r,reverse('ietf.secr.sreq.views.view', kwargs={'acronym':'mars'}))
        self.assertEqual(SchedulingEvent.objects.filter(session=session).order_by('-id')[0].status_id, 'appr')
        
    def test_cancel(self):
        meeting = MeetingFactory(type_id='ietf', date=datetime.date.today())
        ad = Person.objects.get(user__username='ad')
        area = RoleFactory(name_id='ad', person=ad, group__type_id='area').group
        session = SessionFactory(meeting=meeting, group__parent=area, group__acronym='mars', status_id='sched')
        url = reverse('ietf.secr.sreq.views.cancel', kwargs={'acronym':'mars'})
        self.client.login(username="ad", password="ad+password")
        r = self.client.get(url)
        self.assertRedirects(r,reverse('ietf.secr.sreq.views.main'))
        self.assertEqual(SchedulingEvent.objects.filter(session=session).order_by('-id')[0].status_id, 'deleted')

    def test_edit(self):
        meeting = MeetingFactory(type_id='ietf', date=datetime.date.today())
        mars = RoleFactory(name_id='chair', person__user__username='marschairman', group__acronym='mars').group
        group2 = GroupFactory()
        group3 = GroupFactory()
        group4 = GroupFactory()
        iabprog = GroupFactory(type_id='program')

        SessionFactory(meeting=meeting,group=mars,status_id='sched')

        url = reverse('ietf.secr.sreq.views.edit', kwargs={'acronym':'mars'})
        self.client.login(username="marschairman", password="marschairman+password")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        post_data = {'num_session':'2',
                     'length_session1':'3600',
                     'length_session2':'3600',
                     'attendees':'10',
                     'constraint_chair_conflict':iabprog.acronym,
                     'comments':'need lights',
                     'session_time_relation': 'subsequent-days',
                     'adjacent_with_wg': group2.acronym,
                     'joint_with_groups': group3.acronym + ' ' + group4.acronym,
                     'joint_for_session': '2',
                     'timeranges': ['thursday-afternoon-early', 'thursday-afternoon-late'],
                     'submit': 'Continue'}
        r = self.client.post(url, post_data, HTTP_HOST='example.com')
        redirect_url = reverse('ietf.secr.sreq.views.view', kwargs={'acronym': 'mars'})
        self.assertRedirects(r, redirect_url)

        # Check whether updates were stored in the database
        sessions = Session.objects.filter(meeting=meeting, group=mars)
        self.assertEqual(len(sessions), 2)
        session = sessions[0]

        self.assertEqual(session.constraints().get(name='chair_conflict').target.acronym, iabprog.acronym)
        self.assertEqual(session.constraints().get(name='time_relation').time_relation, 'subsequent-days')
        self.assertEqual(session.constraints().get(name='wg_adjacent').target.acronym, group2.acronym)
        self.assertEqual(
            list(session.constraints().get(name='timerange').timeranges.all().values('name')),
            list(TimerangeName.objects.filter(name__in=['thursday-afternoon-early', 'thursday-afternoon-late']).values('name'))
        )
        self.assertFalse(sessions[0].joint_with_groups.count())
        self.assertEqual(list(sessions[1].joint_with_groups.all()), [group3, group4])

        # Check whether the updated data is visible on the view page
        r = self.client.get(redirect_url)
        self.assertContains(r, 'Schedule the sessions on subsequent days')
        self.assertContains(r, 'Thursday early afternoon, Thursday late afternoon')
        self.assertContains(r, group2.acronym)
        self.assertContains(r, 'Second session with: {} {}'.format(group3.acronym, group4.acronym))

        # Edit again, changing the joint sessions and clearing some fields. The behaviour of
        # edit is different depending on whether previous joint sessions were recorded.
        post_data = {'num_session':'2',
                     'length_session1':'3600',
                     'length_session2':'3600',
                     'attendees':'10',
                     'constraint_chair_conflict':'',
                     'comments':'need lights',
                     'joint_with_groups': group2.acronym,
                     'joint_for_session': '1',
                     'submit': 'Continue'}
        r = self.client.post(url, post_data, HTTP_HOST='example.com')
        self.assertRedirects(r, redirect_url)

        # Check whether updates were stored in the database
        sessions = Session.objects.filter(meeting=meeting, group=mars)
        self.assertEqual(len(sessions), 2)
        session = sessions[0]
        self.assertFalse(session.constraints().filter(name='time_relation'))
        self.assertFalse(session.constraints().filter(name='wg_adjacent'))
        self.assertFalse(session.constraints().filter(name='timerange'))
        self.assertEqual(list(sessions[0].joint_with_groups.all()), [group2])
        self.assertFalse(sessions[1].joint_with_groups.count())

        # Check whether the updated data is visible on the view page
        r = self.client.get(redirect_url)
        self.assertContains(r, 'First session with: {}'.format(group2.acronym))

    def test_edit_inactive_conflicts(self):
        """Inactive conflicts should be displayed and removable"""
        meeting = MeetingFactory(type_id='ietf', date=datetime.date.today(), group_conflicts=['chair_conflict'])
        mars = RoleFactory(name_id='chair', person__user__username='marschairman', group__acronym='mars').group
        SessionFactory(meeting=meeting, group=mars, status_id='sched')
        other_group = GroupFactory()
        Constraint.objects.create(
            meeting=meeting,
            name_id='conflict',  # not in group_conflicts for the meeting
            source=mars,
            target=other_group,
        )

        url = reverse('ietf.secr.sreq.views.edit', kwargs=dict(acronym='mars'))
        self.client.login(username='marschairman', password='marschairman+password')
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)

        # check that the inactive session is displayed
        found = q('input#id_delete_conflict[type="checkbox"]')
        self.assertEqual(len(found), 1)
        delete_checkbox = found[0]
        # check that the label on the checkbox is correct
        self.assertIn('Delete this conflict', delete_checkbox.tail)
        # check that the target is displayed correctly in the UI
        self.assertIn(other_group.acronym, delete_checkbox.find('../input[@type="text"]').value)

        post_data = {
            'num_session': '1',
            'length_session1': '3600',
            'attendees': '10',
            'constraint_chair_conflict':'',
            'comments':'',
            'joint_with_groups': '',
            'joint_for_session': '',
            'submit': 'Save',
            'delete_conflict': 'on',
        }
        r = self.client.post(url, post_data, HTTP_HOST='example.com')
        redirect_url = reverse('ietf.secr.sreq.views.view', kwargs={'acronym': 'mars'})
        self.assertRedirects(r, redirect_url)
        self.assertEqual(len(mars.constraint_source_set.filter(name_id='conflict')), 0)

    def test_tool_status(self):
        MeetingFactory(type_id='ietf', date=datetime.date.today())
        url = reverse('ietf.secr.sreq.views.tool_status')
        self.client.login(username="secretary", password="secretary+password")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        r = self.client.post(url, {'message':'locked', 'submit':'Lock'})
        self.assertRedirects(r,reverse('ietf.secr.sreq.views.main'))

    def test_new_req_constraint_types(self):
        """Configurable constraint types should be handled correctly in a new request

        Relies on SessionForm representing constraint values with element IDs
        like id_constraint_<ConstraintName slug>
        """
        meeting = MeetingFactory(type_id='ietf', date=datetime.date.today())
        RoleFactory(name_id='chair', person__user__username='marschairman', group__acronym='mars')
        url = reverse('ietf.secr.sreq.views.new', kwargs=dict(acronym='mars'))
        self.client.login(username="marschairman", password="marschairman+password")

        for expected in [
            ['conflict', 'conflic2', 'conflic3'],
            ['chair_conflict', 'tech_overlap', 'key_participant'],
        ]:
            meeting.group_conflict_types.clear()
            for slug in expected:
                meeting.group_conflict_types.add(ConstraintName.objects.get(slug=slug))

            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)
            q = PyQuery(r.content)
            self.assertCountEqual(
                [elt.attr('id') for elt in q.items('*[id^=id_constraint_]')],
                ['id_constraint_{}'.format(conf_name) for conf_name in expected],
            )

    def test_edit_req_constraint_types(self):
        """Editing a request constraint should show the expected constraints"""
        meeting = MeetingFactory(type_id='ietf', date=datetime.date.today())
        SessionFactory(group__acronym='mars',
                       status_id='schedw',
                       meeting=meeting,
                       add_to_schedule=False)
        RoleFactory(name_id='chair', person__user__username='marschairman', group__acronym='mars')

        url = reverse('ietf.secr.sreq.views.edit', kwargs=dict(acronym='mars'))
        self.client.login(username='marschairman', password='marschairman+password')

        for expected in [
            ['conflict', 'conflic2', 'conflic3'],
            ['chair_conflict', 'tech_overlap', 'key_participant'],
        ]:
            meeting.group_conflict_types.clear()
            for slug in expected:
                meeting.group_conflict_types.add(ConstraintName.objects.get(slug=slug))

            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)
            q = PyQuery(r.content)
            self.assertCountEqual(
                [elt.attr('id') for elt in q.items('*[id^=id_constraint_]')],
                ['id_constraint_{}'.format(conf_name) for conf_name in expected],
            )

class SubmitRequestCase(TestCase):
    def setUp(self):
        super(SubmitRequestCase, self).setUp()
        # Ensure meeting numbers are predictable. Temporarily needed while basing
        # constraint types on meeting number, expected to go away when #2770 is resolved.
        MeetingFactory.reset_sequence(0)

    def test_submit_request(self):
        meeting = MeetingFactory(type_id='ietf', date=datetime.date.today())
        ad = Person.objects.get(user__username='ad')
        area = RoleFactory(name_id='ad', person=ad, group__type_id='area').group
        group = GroupFactory(parent=area)
        group2 = GroupFactory(parent=area)
        group3 = GroupFactory(parent=area)
        group4 = GroupFactory(parent=area)
        session_count_before = Session.objects.filter(meeting=meeting, group=group).count()
        url = reverse('ietf.secr.sreq.views.new',kwargs={'acronym':group.acronym})
        confirm_url = reverse('ietf.secr.sreq.views.confirm',kwargs={'acronym':group.acronym})
        main_url = reverse('ietf.secr.sreq.views.main')
        post_data = {'num_session':'1',
                     'length_session1':'3600',
                     'attendees':'10',
                     'constraint_chair_conflict':'',
                     'comments':'need projector',
                     'adjacent_with_wg': group2.acronym,
                     'timeranges': ['thursday-afternoon-early', 'thursday-afternoon-late'],
                     'joint_with_groups': group3.acronym + ' ' + group4.acronym,
                     'joint_for_session': '1',
                     'submit': 'Continue'}
        self.client.login(username="secretary", password="secretary+password")
        r = self.client.post(url,post_data)
        self.assertEqual(r.status_code, 200)

        # Verify the contents of the confirm view
        self.assertContains(r, 'Thursday early afternoon, Thursday late afternoon')
        self.assertContains(r, group2.acronym)
        self.assertContains(r, 'First session with: {} {}'.format(group3.acronym, group4.acronym))

        post_data['submit'] = 'Submit'
        r = self.client.post(confirm_url,post_data)
        self.assertRedirects(r, main_url)
        session_count_after = Session.objects.filter(meeting=meeting, group=group, type='regular').count()
        self.assertEqual(session_count_after, session_count_before + 1)

        # test that second confirm does not add sessions
        r = self.client.post(confirm_url,post_data)
        self.assertRedirects(r, main_url)
        session_count_after = Session.objects.filter(meeting=meeting, group=group, type='regular').count()
        self.assertEqual(session_count_after, session_count_before + 1)
        
        # Verify database content
        session = Session.objects.get(meeting=meeting, group=group)
        self.assertEqual(session.constraints().get(name='wg_adjacent').target.acronym, group2.acronym)
        self.assertEqual(
            list(session.constraints().get(name='timerange').timeranges.all().values('name')),
            list(TimerangeName.objects.filter(name__in=['thursday-afternoon-early', 'thursday-afternoon-late']).values('name'))
        )
        self.assertEqual(list(session.joint_with_groups.all()), [group3, group4])

    def test_submit_request_invalid(self):
        MeetingFactory(type_id='ietf', date=datetime.date.today())
        ad = Person.objects.get(user__username='ad')
        area = RoleFactory(name_id='ad', person=ad, group__type_id='area').group
        group = GroupFactory(parent=area)
        url = reverse('ietf.secr.sreq.views.new',kwargs={'acronym':group.acronym})
        post_data = {'num_session':'2',
                     'length_session1':'3600',
                     'attendees':'10',
                     'constraint_chair_conflict':'',
                     'comments':'need projector'}
        self.client.login(username="secretary", password="secretary+password")
        r = self.client.post(url,post_data)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('#session-request-form')),1)
        self.assertContains(r, 'You must enter a length for all sessions')

    def test_submit_request_check_constraints(self):
        m1 = MeetingFactory(type_id='ietf', date=datetime.date.today() - datetime.timedelta(days=100))
        MeetingFactory(type_id='ietf', date=datetime.date.today(),
                       group_conflicts=['chair_conflict', 'conflic2', 'conflic3'])
        ad = Person.objects.get(user__username='ad')
        area = RoleFactory(name_id='ad', person=ad, group__type_id='area').group
        group = GroupFactory(parent=area)
        still_active_group = GroupFactory(parent=area)
        Constraint.objects.create(
            meeting=m1,
            source=group,
            target=still_active_group,
            name_id='chair_conflict',
        )
        inactive_group = GroupFactory(parent=area, state_id='conclude')
        inactive_group.save()
        Constraint.objects.create(
            meeting=m1,
            source=group,
            target=inactive_group,
            name_id='chair_conflict',
        )
        SessionFactory(group=group, meeting=m1)

        self.client.login(username="secretary", password="secretary+password")

        url = reverse('ietf.secr.sreq.views.new',kwargs={'acronym':group.acronym})
        r = self.client.get(url + '?previous')
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        conflict1 = q('[name="constraint_chair_conflict"]').val()
        self.assertIn(still_active_group.acronym, conflict1)
        self.assertNotIn(inactive_group.acronym, conflict1)

        post_data = {'num_session':'1',
                     'length_session1':'3600',
                     'attendees':'10',
                     'constraint_chair_conflict': group.acronym,
                     'comments':'need projector',
                     'submit': 'Continue'}
        r = self.client.post(url,post_data)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('#session-request-form')),1)
        self.assertContains(r, "Cannot declare a conflict with the same group")

    def test_request_notification(self):
        meeting = MeetingFactory(type_id='ietf', date=datetime.date.today())
        ad = Person.objects.get(user__username='ad')
        area = GroupFactory(type_id='area')
        RoleFactory(name_id='ad', person=ad, group=area)
        group = GroupFactory(acronym='ames', parent=area)
        group2 = GroupFactory(acronym='ames2', parent=area)
        group3 = GroupFactory(acronym='ames2', parent=area)
        group4 = GroupFactory(acronym='ames3', parent=area)
        RoleFactory(name_id='chair', group=group, person__user__username='ameschairman')
        resource = ResourceAssociation.objects.create(name_id='project')
        # Bit of a test data hack - the fixture now has no used resources to pick from
        resource.name.used=True
        resource.name.save()

        url = reverse('ietf.secr.sreq.views.new',kwargs={'acronym':group.acronym})
        confirm_url = reverse('ietf.secr.sreq.views.confirm',kwargs={'acronym':group.acronym})
        len_before = len(outbox)
        post_data = {'num_session':'2',
                     'length_session1':'3600',
                     'length_session2':'3600',
                     'attendees':'10',
                     'bethere':str(ad.pk),
                     'constraint_chair_conflict':group4.acronym,
                     'comments':'',
                     'resources': resource.pk,
                     'session_time_relation': 'subsequent-days',
                     'adjacent_with_wg': group2.acronym,
                     'joint_with_groups': group3.acronym,
                     'joint_for_session': '2',
                     'timeranges': ['thursday-afternoon-early', 'thursday-afternoon-late'],
                     'submit': 'Continue'}
        self.client.login(username="ameschairman", password="ameschairman+password")
        # submit
        r = self.client.post(url,post_data)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue('Confirm' in str(q("title")), r.context['form'].errors)
        # confirm
        post_data['submit'] = 'Submit'
        r = self.client.post(confirm_url,post_data)
        self.assertRedirects(r, reverse('ietf.secr.sreq.views.main'))
        self.assertEqual(len(outbox),len_before+1)
        notification = outbox[-1]
        notification_payload = get_payload_text(notification)
        sessions = Session.objects.filter(meeting=meeting,group=group)
        self.assertEqual(len(sessions), 2)
        session = sessions[0]
        
        self.assertEqual(session.resources.count(),1)
        self.assertEqual(session.people_constraints.count(),1)
        self.assertEqual(session.constraints().get(name='time_relation').time_relation, 'subsequent-days')
        self.assertEqual(session.constraints().get(name='wg_adjacent').target.acronym, group2.acronym)
        self.assertEqual(
            list(session.constraints().get(name='timerange').timeranges.all().values('name')),
            list(TimerangeName.objects.filter(name__in=['thursday-afternoon-early', 'thursday-afternoon-late']).values('name'))
        )
        resource = session.resources.first()
        self.assertTrue(resource.desc in notification_payload)
        self.assertTrue('Schedule the sessions on subsequent days' in notification_payload)
        self.assertTrue(group2.acronym in notification_payload)
        self.assertTrue("Can't meet: Thursday early afternoon, Thursday late" in notification_payload)
        self.assertTrue('Second session joint with: {}'.format(group3.acronym) in notification_payload)
        self.assertTrue(ad.ascii_name() in notification_payload)
        self.assertIn(ConstraintName.objects.get(slug='chair_conflict').name, notification_payload)
        self.assertIn(group.acronym, notification_payload)

class LockAppTestCase(TestCase):
    def setUp(self):
        self.meeting = MeetingFactory(type_id='ietf', date=datetime.date.today(),session_request_lock_message='locked')
        self.group = GroupFactory(acronym='mars')
        RoleFactory(name_id='chair', group=self.group, person__user__username='marschairman')
        SessionFactory(group=self.group,meeting=self.meeting)

    def test_edit_request(self):
        url = reverse('ietf.secr.sreq.views.edit',kwargs={'acronym':self.group.acronym})
        self.client.login(username="secretary", password="secretary+password")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q(':disabled[name="submit"]')), 1)
    
    def test_view_request(self):
        url = reverse('ietf.secr.sreq.views.view',kwargs={'acronym':self.group.acronym})
        self.client.login(username="secretary", password="secretary+password")
        r = self.client.get(url,follow=True)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q(':disabled[name="edit"]')), 1)
        
    def test_new_request(self):
        url = reverse('ietf.secr.sreq.views.new',kwargs={'acronym':self.group.acronym})
        
        # try as WG Chair
        self.client.login(username="marschairman", password="marschairman+password")
        r = self.client.get(url, follow=True)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('#session-request-form')),0)
        
        # try as Secretariat
        self.client.login(username="secretary", password="secretary+password")
        r = self.client.get(url,follow=True)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('#session-request-form')),1)
    
class NotMeetingCase(TestCase):
    def test_not_meeting(self):
        MeetingFactory(type_id='ietf',date=datetime.date.today())
        group = GroupFactory(acronym='mars')
        url = reverse('ietf.secr.sreq.views.no_session',kwargs={'acronym':group.acronym}) 
        self.client.login(username="secretary", password="secretary+password")

        empty_outbox()

        r = self.client.get(url,follow=True)
        # If the view invoked by that get throws an exception (such as an integrity error),
        # the traceback from this test will talk about a TransactionManagementError and
        # yell about executing queries before the end of an 'atomic' block

        # This is a sign of a problem - a get shouldn't have a side-effect like this one does
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'A message was sent to notify not having a session')

        r = self.client.get(url,follow=True)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'is already marked as not meeting')

        self.assertEqual(len(outbox),1)
        self.assertTrue('Not having a session' in outbox[0]['Subject'])
        self.assertTrue('session-request@' in outbox[0]['To'])

class RetrievePreviousCase(TestCase):
    pass

    # test error if already scheduled
    # test get previous exists/doesn't exist
    # test that groups scheduled and unscheduled add up to total groups
    # test access by unauthorized


class SessionFormTest(TestCase):
    def setUp(self):
        self.meeting = MeetingFactory(type_id='ietf')
        self.group1 = GroupFactory()
        self.group2 = GroupFactory()
        self.group3 = GroupFactory()
        self.group4 = GroupFactory()
        self.group5 = GroupFactory()
        self.group6 = GroupFactory()

        self.valid_form_data = {
            'num_session': '2',
            'third_session': 'true',
            'length_session1': '3600',
            'length_session2': '3600',
            'length_session3': '3600',
            'attendees': '10',
            'constraint_chair_conflict': self.group2.acronym,
            'constraint_tech_overlap': self.group3.acronym,
            'constraint_key_participant': self.group4.acronym,
            'comments': 'need lights',
            'session_time_relation': 'subsequent-days',
            'adjacent_with_wg': self.group5.acronym,
            'joint_with_groups': self.group6.acronym,
            'joint_for_session': '3',
            'timeranges': ['thursday-afternoon-early', 'thursday-afternoon-late'],
            'submit': 'Continue'
        }
        
    def test_valid(self):
        # Test with three sessions
        form = SessionForm(data=self.valid_form_data, group=self.group1, meeting=self.meeting)
        self.assertTrue(form.is_valid())
        
        # Test with two sessions
        self.valid_form_data.update({
            'length_session3': '',
            'third_session': '',
            'joint_for_session': '2'
        })
        form = SessionForm(data=self.valid_form_data, group=self.group1, meeting=self.meeting)
        self.assertTrue(form.is_valid())

        # Test with one session
        self.valid_form_data.update({
            'length_session2': '',
            'num_session': 1,
            'joint_for_session': '1',
            'session_time_relation': '',
        })
        form = SessionForm(data=self.valid_form_data, group=self.group1, meeting=self.meeting)
        self.assertTrue(form.is_valid())
    
    def test_invalid_groups(self):
        new_form_data = {
            'constraint_chair_conflict': 'doesnotexist',
            'constraint_tech_overlap': 'doesnotexist',
            'constraint_key_participant': 'doesnotexist',
            'adjacent_with_wg': 'doesnotexist',
            'joint_with_groups': 'doesnotexist',
        }
        form = self._invalid_test_helper(new_form_data)
        self.assertEqual(set(form.errors.keys()), set(new_form_data.keys()))

    def test_valid_group_appears_in_multiple_conflicts(self):
        """Some conflict types allow overlapping groups"""
        new_form_data = {
            'constraint_chair_conflict': self.group2.acronym,
            'constraint_tech_overlap': self.group2.acronym,
        }
        self.valid_form_data.update(new_form_data)
        form = SessionForm(data=self.valid_form_data, group=self.group1, meeting=self.meeting)
        self.assertTrue(form.is_valid())

    def test_invalid_group_appears_in_multiple_conflicts(self):
        """Some conflict types do not allow overlapping groups"""
        self.meeting.group_conflict_types.clear()
        self.meeting.group_conflict_types.add(ConstraintName.objects.get(slug='conflict'))
        self.meeting.group_conflict_types.add(ConstraintName.objects.get(slug='conflic2'))
        new_form_data = {
            'constraint_conflict': self.group2.acronym,
            'constraint_conflic2': self.group2.acronym,
        }
        form = self._invalid_test_helper(new_form_data)
        self.assertEqual(form.non_field_errors(), ['%s appears in conflicts more than once' % self.group2.acronym])

    def test_invalid_conflict_with_self(self):
        new_form_data = {
            'constraint_chair_conflict': self.group1.acronym,
        }
        self._invalid_test_helper(new_form_data)

    def test_invalid_session_time_relation(self):
        form = self._invalid_test_helper({
            'third_session': '',
            'length_session2': '',
            'num_session': 1,
            'joint_for_session': '1',
        })
        self.assertEqual(form.errors,
                         {
                             'session_time_relation': ['Time between sessions can only be used when two '
                                                       'sessions are requested.']
                         })

    def test_invalid_joint_for_session(self):
        form = self._invalid_test_helper({
            'third_session': '',
            'num_session': 2,
            'joint_for_session': '3',
        })
        self.assertEqual(form.errors,
                         {
                             'joint_for_session': ['The third session can not be the joint session, '
                                                   'because you have not requested a third session.']
                         })

        form = self._invalid_test_helper({
            'third_session': '',
            'length_session2': '',
            'num_session': 1,
            'joint_for_session': '2',
            'session_time_relation': '',
        })
        self.assertEqual(form.errors,
                         {
                             'joint_for_session': ['The second session can not be the joint session, '
                                                   'because you have not requested a second session.']
                         })
    
    def test_invalid_missing_session_length(self):
        form = self._invalid_test_helper({
            'length_session2': '',
            'third_session': 'false',
            'joint_for_session': None,
        })
        self.assertEqual(form.errors,
                         {
                             'length_session2': ['You must enter a length for all sessions'],
                         })

        form = self._invalid_test_helper({
            'length_session2': '',
            'length_session3': '',
            'joint_for_session': None,
        })
        self.assertEqual(form.errors,
                         {
                             'length_session2': ['You must enter a length for all sessions'],
                             'length_session3': ['You must enter a length for all sessions'],
                         })

        form = self._invalid_test_helper({
            'length_session3': '',
            'joint_for_session': None,
        })
        self.assertEqual(form.errors,
                         {
                             'length_session3': ['You must enter a length for all sessions'],
                         })

    def _invalid_test_helper(self, new_form_data):
        form_data = dict(self.valid_form_data, **new_form_data)
        form = SessionForm(data=form_data, group=self.group1, meeting=self.meeting)
        self.assertFalse(form.is_valid())
        return form