# Copyright The IETF Trust 2013-2022, All Rights Reserved
# -*- coding: utf-8 -*-


import datetime

from django.urls import reverse

import debug                            # pyflakes:ignore

from ietf.utils.test_utils import TestCase
from ietf.group.factories import GroupFactory, RoleFactory
from ietf.meeting.models import Session, ResourceAssociation, SchedulingEvent, Constraint
from ietf.meeting.factories import MeetingFactory, SessionFactory
from ietf.name.models import ConstraintName, TimerangeName
from ietf.person.factories import PersonFactory
from ietf.person.models import Person
from ietf.secr.sreq.forms import SessionForm
from ietf.utils.mail import outbox, empty_outbox, get_payload_text, send_mail
from ietf.utils.timezone import date_today


from pyquery import PyQuery

SECR_USER='secretary'

class SreqUrlTests(TestCase):
    def test_urls(self):
        MeetingFactory(type_id='ietf',date=date_today())

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
        meeting = MeetingFactory(type_id='ietf', date=date_today())
        SessionFactory.create_batch(2, meeting=meeting, status_id='sched')
        SessionFactory.create_batch(2, meeting=meeting, status_id='disappr')
        # Several unscheduled groups come from make_immutable_base_data
        url = reverse('ietf.secr.sreq.views.main')
        self.client.login(username="secretary", password="secretary+password")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        sched = r.context['scheduled_groups']
        self.assertEqual(len(sched), 2)
        unsched = r.context['unscheduled_groups']
        self.assertEqual(len(unsched), 12)

    def test_approve(self):
        meeting = MeetingFactory(type_id='ietf', date=date_today())
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
        meeting = MeetingFactory(type_id='ietf', date=date_today())
        ad = Person.objects.get(user__username='ad')
        area = RoleFactory(name_id='ad', person=ad, group__type_id='area').group
        session = SessionFactory(meeting=meeting, group__parent=area, group__acronym='mars', status_id='sched')
        url = reverse('ietf.secr.sreq.views.cancel', kwargs={'acronym':'mars'})
        self.client.login(username="ad", password="ad+password")
        r = self.client.get(url)
        self.assertRedirects(r,reverse('ietf.secr.sreq.views.main'))
        self.assertEqual(SchedulingEvent.objects.filter(session=session).order_by('-id')[0].status_id, 'deleted')

    def test_cancel_notification_msg(self):
        to = "<iesg-secretary@ietf.org>"
        subject = "Dummy subject"
        template = "sreq/session_cancel_notification.txt"
        meeting = MeetingFactory(type_id="ietf", date=date_today())
        requester = PersonFactory(name="James O'Rourke", user__username="jimorourke")
        context = {"meeting": meeting, "requester": requester}
        cc = "cc.a@example.com, cc.b@example.com"
        bcc = "bcc@example.com"

        msg = send_mail(
            None,
            to,
            None,
            subject,
            template,
            context,
            cc=cc,
            bcc=bcc,
        )
        self.assertEqual(requester.name, "James O'Rourke")  # note ' (single quote) in the name
        self.assertIn(
            f"A request to cancel a meeting session has just been submitted by {requester.name}.",
            get_payload_text(msg),
        )

    def test_edit(self):
        meeting = MeetingFactory(type_id='ietf', date=date_today())
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
        attendees = 10
        comments = 'need lights'
        mars_sessions = meeting.session_set.filter(group__acronym='mars')
        empty_outbox()
        post_data = {'num_session':'2',
                     'attendees': attendees,
                     'constraint_chair_conflict':iabprog.acronym,
                     'session_time_relation': 'subsequent-days',
                     'adjacent_with_wg': group2.acronym,
                     'joint_with_groups': group3.acronym + ' ' + group4.acronym,
                     'joint_for_session': '2',
                     'timeranges': ['thursday-afternoon-early', 'thursday-afternoon-late'],
                     'session_set-TOTAL_FORMS': '3',  # matches what view actually sends, even with only 2 filled in
                     'session_set-INITIAL_FORMS': '1',
                     'session_set-MIN_NUM_FORMS': '1',
                     'session_set-MAX_NUM_FORMS': '3',
                     'session_set-0-id':mars_sessions[0].pk,
                     'session_set-0-name': mars_sessions[0].name,
                     'session_set-0-short': mars_sessions[0].short,
                     'session_set-0-purpose': mars_sessions[0].purpose_id,
                     'session_set-0-type': mars_sessions[0].type_id,
                     'session_set-0-requested_duration': '3600',
                     'session_set-0-on_agenda': mars_sessions[0].on_agenda,
                     'session_set-0-remote_instructions': mars_sessions[0].remote_instructions,
                     'session_set-0-attendees': attendees,
                     'session_set-0-comments': comments,
                     'session_set-0-DELETE': '',
                     # no session_set-1-id because it's a new request
                     'session_set-1-name': '',
                     'session_set-1-short': '',
                     'session_set-1-purpose': 'regular',
                     'session_set-1-type': 'regular',
                     'session_set-1-requested_duration': '3600',
                     'session_set-1-on_agenda': True,
                     'session_set-1-remote_instructions': mars_sessions[0].remote_instructions,
                     'session_set-1-attendees': attendees,
                     'session_set-1-comments': comments,
                     'session_set-1-DELETE': '',
                     'session_set-2-id': '',
                     'session_set-2-name': '',
                     'session_set-2-short': '',
                     'session_set-2-purpose': 'regular',
                     'session_set-2-type': 'regular',
                     'session_set-2-requested_duration': '',
                     'session_set-2-on_agenda': 'True',
                     'session_set-2-attendees': attendees,
                     'session_set-2-comments': '',
                     'session_set-2-DELETE': 'on',
                     'submit': 'Continue'}
        r = self.client.post(url, post_data, HTTP_HOST='example.com')
        redirect_url = reverse('ietf.secr.sreq.views.view', kwargs={'acronym': 'mars'})
        self.assertRedirects(r, redirect_url)

        # Check whether updates were stored in the database
        sessions = Session.objects.filter(meeting=meeting, group=mars).order_by("id")  # order to match edit() view
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
        self.assertEqual(set(sessions[1].joint_with_groups.all()), {group3, group4})

        # Check whether the updated data is visible on the view page
        r = self.client.get(redirect_url)
        self.assertContains(r, 'Schedule the sessions on subsequent days')
        self.assertContains(r, 'Thursday early afternoon, Thursday late afternoon')
        self.assertContains(r, group2.acronym)
        # The sessions can be in any order in the HTML, deal with that
        self.assertRegex(r.content.decode(), r'Second session with: ({} {}|{} {})'.format(group3.acronym, group4.acronym, group4.acronym, group3.acronym))

        # check that a notification was sent
        self.assertEqual(len(outbox), 1)
        notification_payload = get_payload_text(outbox[0])
        self.assertIn('1 Hour, 1 Hour', notification_payload)
        self.assertNotIn('1 Hour, 1 Hour, 1 Hour', notification_payload)

        # Edit again, changing the joint sessions and clearing some fields. The behaviour of
        # edit is different depending on whether previous joint sessions were recorded.
        empty_outbox()
        post_data = {'num_session':'2',
                     'attendees':attendees,
                     'constraint_chair_conflict':'',
                     'comments':'need lights',
                     'joint_with_groups': group2.acronym,
                     'joint_for_session': '1',
                     'session_set-TOTAL_FORMS': '3',  # matches what view actually sends, even with only 2 filled in
                     'session_set-INITIAL_FORMS': '2',
                     'session_set-MIN_NUM_FORMS': '1',
                     'session_set-MAX_NUM_FORMS': '3',
                     'session_set-0-id':sessions[0].pk,
                     'session_set-0-name': sessions[0].name,
                     'session_set-0-short': sessions[0].short,
                     'session_set-0-purpose': sessions[0].purpose_id,
                     'session_set-0-type': sessions[0].type_id,
                     'session_set-0-requested_duration': '3600',
                     'session_set-0-on_agenda': sessions[0].on_agenda,
                     'session_set-0-remote_instructions': sessions[0].remote_instructions,
                     'session_set-0-attendees': sessions[0].attendees,
                     'session_set-0-comments': sessions[1].comments,
                     'session_set-0-DELETE': '',
                     'session_set-1-id': sessions[1].pk,
                     'session_set-1-name': sessions[1].name,
                     'session_set-1-short': sessions[1].short,
                     'session_set-1-purpose': sessions[1].purpose_id,
                     'session_set-1-type': sessions[1].type_id,
                     'session_set-1-requested_duration': '3600',
                     'session_set-1-on_agenda': sessions[1].on_agenda,
                     'session_set-1-remote_instructions': sessions[1].remote_instructions,
                     'session_set-1-attendees': sessions[1].attendees,
                     'session_set-1-comments': sessions[1].comments,
                     'session_set-1-DELETE': '',
                     'session_set-2-id': '',
                     'session_set-2-name': '',
                     'session_set-2-short': '',
                     'session_set-2-purpose': 'regular',
                     'session_set-2-type': 'regular',
                     'session_set-2-requested_duration': '',
                     'session_set-2-on_agenda': 'True',
                     'session_set-2-attendees': attendees,
                     'session_set-2-comments': '',
                     'session_set-2-DELETE': 'on',
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

        # check that a notification was sent
        self.assertEqual(len(outbox), 1)
        notification_payload = get_payload_text(outbox[0])
        self.assertIn('1 Hour, 1 Hour', notification_payload)
        self.assertNotIn('1 Hour, 1 Hour, 1 Hour', notification_payload)

        # Check whether the updated data is visible on the view page
        r = self.client.get(redirect_url)
        self.assertContains(r, 'First session with: {}'.format(group2.acronym))


    def test_edit_constraint_bethere(self):
        meeting = MeetingFactory(type_id='ietf', date=date_today())
        mars = RoleFactory(name_id='chair', person__user__username='marschairman', group__acronym='mars').group
        session = SessionFactory(meeting=meeting, group=mars, status_id='sched')
        Constraint.objects.create(
            meeting=meeting,
            source=mars,
            person=Person.objects.get(user__username='marschairman'),
            name_id='bethere',
        )
        self.assertEqual(session.people_constraints.count(), 1)
        url = reverse('ietf.secr.sreq.views.edit', kwargs=dict(acronym='mars'))
        self.client.login(username='marschairman', password='marschairman+password')
        attendees = '10'
        ad = Person.objects.get(user__username='ad')
        post_data = {
            'num_session': '1',
            'attendees': attendees,
            'bethere': str(ad.pk),
            'constraint_chair_conflict':'',
            'comments':'',
            'joint_with_groups': '',
            'joint_for_session': '',
            'delete_conflict': 'on',
            'session_set-TOTAL_FORMS': '3',  # matches what view actually sends, even with only 2 filled in
            'session_set-INITIAL_FORMS': '1',
            'session_set-MIN_NUM_FORMS': '1',
            'session_set-MAX_NUM_FORMS': '3',
            'session_set-0-id':session.pk,
            'session_set-0-name': session.name,
            'session_set-0-short': session.short,
            'session_set-0-purpose': session.purpose_id,
            'session_set-0-type': session.type_id,
            'session_set-0-requested_duration': '3600',
            'session_set-0-on_agenda': session.on_agenda,
            'session_set-0-remote_instructions': session.remote_instructions,
            'session_set-0-attendees': attendees,
            'session_set-0-comments': '',
            'session_set-0-DELETE': '',
            'session_set-1-id': '',
            'session_set-1-name': '',
            'session_set-1-short': '',
            'session_set-1-purpose':'regular',
            'session_set-1-type':'regular',
            'session_set-1-requested_duration': '',
            'session_set-1-on_agenda': 'True',
            'session_set-1-attendees': attendees,
            'session_set-1-comments': '',
            'session_set-1-DELETE': 'on',
            'session_set-2-id': '',
            'session_set-2-name': '',
            'session_set-2-short': '',
            'session_set-2-purpose': 'regular',
            'session_set-2-type': 'regular',
            'session_set-2-requested_duration': '',
            'session_set-2-on_agenda': 'True',
            'session_set-2-attendees': attendees,
            'session_set-2-comments': '',
            'session_set-2-DELETE': 'on',
            'submit': 'Save',
        }
        r = self.client.post(url, post_data, HTTP_HOST='example.com')
        redirect_url = reverse('ietf.secr.sreq.views.view', kwargs={'acronym': 'mars'})
        self.assertRedirects(r, redirect_url)
        self.assertEqual([pc.person for pc in session.people_constraints.all()], [ad])

    def test_edit_inactive_conflicts(self):
        """Inactive conflicts should be displayed and removable"""
        meeting = MeetingFactory(type_id='ietf', date=date_today(), group_conflicts=['chair_conflict'])
        mars = RoleFactory(name_id='chair', person__user__username='marschairman', group__acronym='mars').group
        session = SessionFactory(meeting=meeting, group=mars, status_id='sched')
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

        attendees = '10'
        post_data = {
            'num_session': '1',
            'attendees': attendees,
            'constraint_chair_conflict':'',
            'comments':'',
            'joint_with_groups': '',
            'joint_for_session': '',
            'delete_conflict': 'on',
            'session_set-TOTAL_FORMS': '1',
            'session_set-INITIAL_FORMS': '1',
            'session_set-MIN_NUM_FORMS': '1',
            'session_set-MAX_NUM_FORMS': '3',
            'session_set-0-id':session.pk,
            'session_set-0-name': session.name,
            'session_set-0-short': session.short,
            'session_set-0-purpose': session.purpose_id,
            'session_set-0-type': session.type_id,
            'session_set-0-requested_duration': '3600',
            'session_set-0-on_agenda': session.on_agenda,
            'session_set-0-remote_instructions': session.remote_instructions,
            'session_set-0-attendees': attendees,
            'session_set-0-comments': '',
            'session_set-0-DELETE': '',
            'submit': 'Save',
        }
        r = self.client.post(url, post_data, HTTP_HOST='example.com')
        redirect_url = reverse('ietf.secr.sreq.views.view', kwargs={'acronym': 'mars'})
        self.assertRedirects(r, redirect_url)
        self.assertEqual(len(mars.constraint_source_set.filter(name_id='conflict')), 0)

    def test_tool_status(self):
        MeetingFactory(type_id='ietf', date=date_today())
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
        meeting = MeetingFactory(type_id='ietf', date=date_today())
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
        meeting = MeetingFactory(type_id='ietf', date=date_today())
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
        meeting = MeetingFactory(type_id='ietf', date=date_today())
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
        attendees = '10'
        comments = 'need projector'
        post_data = {'num_session':'1',
                     'attendees':attendees,
                     'constraint_chair_conflict':'',
                     'comments':comments,
                     'adjacent_with_wg': group2.acronym,
                     'timeranges': ['thursday-afternoon-early', 'thursday-afternoon-late'],
                     'joint_with_groups': group3.acronym + ' ' + group4.acronym,
                     'joint_for_session': '1',
                     'session_set-TOTAL_FORMS': '1',
                     'session_set-INITIAL_FORMS': '0',
                     'session_set-MIN_NUM_FORMS': '1',
                     'session_set-MAX_NUM_FORMS': '3',
                     # no 'session_set-0-id' to create a new session
                     'session_set-0-name': '',
                     'session_set-0-short': '',
                     'session_set-0-purpose': 'regular',
                     'session_set-0-type': 'regular',
                     'session_set-0-requested_duration': '3600',
                     'session_set-0-on_agenda': True,
                     'session_set-0-remote_instructions': '',
                     'session_set-0-attendees': attendees,
                     'session_set-0-comments': comments,
                     'session_set-0-DELETE': '',
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
        self.assertEqual(set(list(session.joint_with_groups.all())), set([group3, group4]))

    def test_submit_request_invalid(self):
        MeetingFactory(type_id='ietf', date=date_today())
        ad = Person.objects.get(user__username='ad')
        area = RoleFactory(name_id='ad', person=ad, group__type_id='area').group
        group = GroupFactory(parent=area)
        url = reverse('ietf.secr.sreq.views.new',kwargs={'acronym':group.acronym})
        attendees = '10'
        comments = 'need projector'
        post_data = {
            'num_session':'2',
            'attendees':attendees,
            'constraint_chair_conflict':'',
            'comments':comments,
            'session_set-TOTAL_FORMS': '1',
            'session_set-INITIAL_FORMS': '1',
            'session_set-MIN_NUM_FORMS': '1',
            'session_set-MAX_NUM_FORMS': '3',
            # no 'session_set-0-id' to create a new session
            'session_set-0-name': '',
            'session_set-0-short': '',
            'session_set-0-purpose': 'regular',
            'session_set-0-type': 'regular',
            'session_set-0-requested_duration': '3600',
            'session_set-0-on_agenda': True,
            'session_set-0-remote_instructions': '',
            'session_set-0-attendees': attendees,
            'session_set-0-comments': comments,
            'session_set-0-DELETE': '',
        }
        self.client.login(username="secretary", password="secretary+password")
        r = self.client.post(url,post_data)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('#session-request-form')),1)
        self.assertContains(r, 'Must provide data for all sessions')

    def test_submit_request_check_constraints(self):
        m1 = MeetingFactory(type_id='ietf', date=date_today() - datetime.timedelta(days=100))
        MeetingFactory(type_id='ietf', date=date_today(),
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
        session = SessionFactory(group=group, meeting=m1)

        self.client.login(username="secretary", password="secretary+password")

        url = reverse('ietf.secr.sreq.views.new',kwargs={'acronym':group.acronym})
        r = self.client.get(url + '?previous')
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        conflict1 = q('[name="constraint_chair_conflict"]').val()
        self.assertIn(still_active_group.acronym, conflict1)
        self.assertNotIn(inactive_group.acronym, conflict1)

        attendees = '10'
        comments = 'need projector'
        post_data = {'num_session':'1',
                     'attendees':attendees,
                     'constraint_chair_conflict': group.acronym,
                     'comments':comments,
                     'session_set-TOTAL_FORMS': '1',
                     'session_set-INITIAL_FORMS': '1',
                     'session_set-MIN_NUM_FORMS': '1',
                     'session_set-MAX_NUM_FORMS': '3',
                     # no 'session_set-0-id' to create a new session
                     'session_set-0-name': '',
                     'session_set-0-short': '',
                     'session_set-0-purpose': session.purpose_id,
                     'session_set-0-type': session.type_id,
                     'session_set-0-requested_duration': '3600',
                     'session_set-0-on_agenda': session.on_agenda,
                     'session_set-0-remote_instructions': session.remote_instructions,
                     'session_set-0-attendees': attendees,
                     'session_set-0-comments': comments,
                     'session_set-0-DELETE': '',
                     'submit': 'Continue'}
        r = self.client.post(url,post_data)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('#session-request-form')),1)
        self.assertContains(r, "Cannot declare a conflict with the same group")

    def test_request_notification(self):
        meeting = MeetingFactory(type_id='ietf', date=date_today())
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
        attendees = '10'
        post_data = {'num_session':'2',
                     'attendees':attendees,
                     'bethere':str(ad.pk),
                     'constraint_chair_conflict':group4.acronym,
                     'comments':'',
                     'resources': resource.pk,
                     'session_time_relation': 'subsequent-days',
                     'adjacent_with_wg': group2.acronym,
                     'joint_with_groups': group3.acronym,
                     'joint_for_session': '2',
                     'timeranges': ['thursday-afternoon-early', 'thursday-afternoon-late'],
                     'session_set-TOTAL_FORMS': '2',
                     'session_set-INITIAL_FORMS': '0',
                     'session_set-MIN_NUM_FORMS': '1',
                     'session_set-MAX_NUM_FORMS': '3',
                     # no 'session_set-0-id' for new session
                     'session_set-0-name': '',
                     'session_set-0-short': '',
                     'session_set-0-purpose': 'regular',
                     'session_set-0-type': 'regular',
                     'session_set-0-requested_duration': '3600',
                     'session_set-0-on_agenda': True,
                     'session_set-0-remote_instructions': '',
                     'session_set-0-attendees': attendees,
                     'session_set-0-comments': '',
                     'session_set-0-DELETE': '',
                     # no 'session_set-1-id' for new session
                     'session_set-1-name': '',
                     'session_set-1-short': '',
                     'session_set-1-purpose': 'regular',
                     'session_set-1-type': 'regular',
                     'session_set-1-requested_duration': '3600',
                     'session_set-1-on_agenda': True,
                     'session_set-1-remote_instructions': '',
                     'session_set-1-attendees': attendees,
                     'session_set-1-comments': '',
                     'session_set-1-DELETE': '',
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
        self.assertIn('1 Hour, 1 Hour', notification_payload)
        self.assertNotIn('1 Hour, 1 Hour, 1 Hour', notification_payload)
        self.assertNotIn('The third session requires your approval', notification_payload)

    def test_request_notification_msg(self):
        to = "<iesg-secretary@ietf.org>"
        subject = "Dummy subject"
        template = "sreq/session_request_notification.txt"
        header = "A new"
        meeting = MeetingFactory(type_id="ietf", date=date_today())
        requester = PersonFactory(name="James O'Rourke", user__username="jimorourke")
        context = {"header": header, "meeting": meeting, "requester": requester}
        cc = "cc.a@example.com, cc.b@example.com"
        bcc = "bcc@example.com"

        msg = send_mail(
            None,
            to,
            None,
            subject,
            template,
            context,
            cc=cc,
            bcc=bcc,
        )
        self.assertEqual(requester.name, "James O'Rourke")  # note ' (single quote) in the name
        self.assertIn(
            f"{header} meeting session request has just been submitted by {requester.name}.",
            get_payload_text(msg),
        )

    def test_request_notification_third_session(self):
        meeting = MeetingFactory(type_id='ietf', date=date_today())
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
        attendees = '10'
        post_data = {'num_session':'2',
                     'third_session': 'true',
                     'attendees':attendees,
                     'bethere':str(ad.pk),
                     'constraint_chair_conflict':group4.acronym,
                     'comments':'',
                     'resources': resource.pk,
                     'session_time_relation': 'subsequent-days',
                     'adjacent_with_wg': group2.acronym,
                     'joint_with_groups': group3.acronym,
                     'joint_for_session': '2',
                     'timeranges': ['thursday-afternoon-early', 'thursday-afternoon-late'],
                     'session_set-TOTAL_FORMS': '3',
                     'session_set-INITIAL_FORMS': '0',
                     'session_set-MIN_NUM_FORMS': '1',
                     'session_set-MAX_NUM_FORMS': '3',
                     # no 'session_set-0-id' for new session
                     'session_set-0-name': '',
                     'session_set-0-short': '',
                     'session_set-0-purpose': 'regular',
                     'session_set-0-type': 'regular',
                     'session_set-0-requested_duration': '3600',
                     'session_set-0-on_agenda': True,
                     'session_set-0-remote_instructions': '',
                     'session_set-0-attendees': attendees,
                     'session_set-0-comments': '',
                     'session_set-0-DELETE': '',
                     # no 'session_set-1-id' for new session
                     'session_set-1-name': '',
                     'session_set-1-short': '',
                     'session_set-1-purpose': 'regular',
                     'session_set-1-type': 'regular',
                     'session_set-1-requested_duration': '3600',
                     'session_set-1-on_agenda': True,
                     'session_set-1-remote_instructions': '',
                     'session_set-1-attendees': attendees,
                     'session_set-1-comments': '',
                     'session_set-1-DELETE': '',
                     # no 'session_set-2-id' for new session
                     'session_set-2-name': '',
                     'session_set-2-short': '',
                     'session_set-2-purpose': 'regular',
                     'session_set-2-type': 'regular',
                     'session_set-2-requested_duration': '3600',
                     'session_set-2-on_agenda': True,
                     'session_set-2-remote_instructions': '',
                     'session_set-2-attendees': attendees,
                     'session_set-2-comments': '',
                     'session_set-2-DELETE': '',
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
        self.assertEqual(len(sessions), 3)
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
        self.assertIn('1 Hour, 1 Hour, 1 Hour', notification_payload)
        self.assertIn('The third session requires your approval', notification_payload)

class LockAppTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.meeting = MeetingFactory(type_id='ietf', date=date_today(),session_request_lock_message='locked')
        self.group = GroupFactory(acronym='mars')
        RoleFactory(name_id='chair', group=self.group, person__user__username='marschairman')
        SessionFactory(group=self.group,meeting=self.meeting)

    def test_edit_request(self):
        url = reverse('ietf.secr.sreq.views.edit',kwargs={'acronym':self.group.acronym})
        self.client.login(username="secretary", password="secretary+password")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q(':disabled[name="submit"]')), 0)
        chair = self.group.role_set.filter(name_id='chair').first().person.user.username
        self.client.login(username=chair, password=f'{chair}+password')
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
        self.assertEqual(len(q(':enabled[name="edit"]')), 1)  # secretary can edit
        chair = self.group.role_set.filter(name_id='chair').first().person.user.username
        self.client.login(username=chair, password=f'{chair}+password')
        r = self.client.get(url,follow=True)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q(':disabled[name="edit"]')), 1)  # chair cannot edit

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
        MeetingFactory(type_id='ietf',date=date_today())
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
        super().setUp()
        self.meeting = MeetingFactory(type_id='ietf')
        self.group1 = GroupFactory()
        self.group2 = GroupFactory()
        self.group3 = GroupFactory()
        self.group4 = GroupFactory()
        self.group5 = GroupFactory()
        self.group6 = GroupFactory()

        attendees = '10'
        comments = 'need lights'
        self.valid_form_data = {
            'num_session': '2',
            'third_session': 'true',
            'attendees': attendees,
            'constraint_chair_conflict': self.group2.acronym,
            'constraint_tech_overlap': self.group3.acronym,
            'constraint_key_participant': self.group4.acronym,
            'comments': comments,
            'session_time_relation': 'subsequent-days',
            'adjacent_with_wg': self.group5.acronym,
            'joint_with_groups': self.group6.acronym,
            'joint_for_session': '3',
            'timeranges': ['thursday-afternoon-early', 'thursday-afternoon-late'],
            'submit': 'Continue',
            'session_set-TOTAL_FORMS': '3',
            'session_set-INITIAL_FORMS': '0',
            'session_set-MIN_NUM_FORMS': '1',
            'session_set-MAX_NUM_FORMS': '3',
            # no 'session_set-0-id' for new session
            'session_set-0-name': '',
            'session_set-0-short': '',
            'session_set-0-purpose': 'regular',
            'session_set-0-type': 'regular',
            'session_set-0-requested_duration': '3600',
            'session_set-0-on_agenda': True,
            'session_set-0-remote_instructions': '',
            'session_set-0-attendees': attendees,
            'session_set-0-comments': '',
            'session_set-0-DELETE': '',
            # no 'session_set-1-id' for new session
            'session_set-1-name': '',
            'session_set-1-short': '',
            'session_set-1-purpose': 'regular',
            'session_set-1-type': 'regular',
            'session_set-1-requested_duration': '3600',
            'session_set-1-on_agenda': True,
            'session_set-1-remote_instructions': '',
            'session_set-1-attendees': attendees,
            'session_set-1-comments': '',
            'session_set-1-DELETE': '',
            # no 'session_set-2-id' for new session
            'session_set-2-name': '',
            'session_set-2-short': '',
            'session_set-2-purpose': 'regular',
            'session_set-2-type': 'regular',
            'session_set-2-requested_duration': '3600',
            'session_set-2-on_agenda': True,
            'session_set-2-remote_instructions': '',
            'session_set-2-attendees': attendees,
            'session_set-2-comments': '',
            'session_set-2-DELETE': '',
        }
        
    def test_valid(self):
        # Test with three sessions
        form = SessionForm(data=self.valid_form_data, group=self.group1, meeting=self.meeting)
        self.assertTrue(form.is_valid())
        
        # Test with two sessions
        self.valid_form_data.update({
            'third_session': '',
            'session_set-TOTAL_FORMS': '2',
            'joint_for_session': '2'
        })
        form = SessionForm(data=self.valid_form_data, group=self.group1, meeting=self.meeting)
        self.assertTrue(form.is_valid())

        # Test with one session
        self.valid_form_data.update({
            'num_session': 1,
            'session_set-TOTAL_FORMS': '1',
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
            'session_set-TOTAL_FORMS': 1,
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
            'session_set-TOTAL_FORMS': '2',
            'num_session': 2,
            'joint_for_session': '3',
        })
        self.assertEqual(form.errors,
                         {
                             'joint_for_session': [
                                 'Session 3 can not be the joint session, the session has not been requested.']
                         })

        form = self._invalid_test_helper({
            'third_session': '',
            'session_set-TOTAL_FORMS': '1',
            'num_session': 1,
            'joint_for_session': '2',
            'session_time_relation': '',
        })
        self.assertEqual(form.errors,
                         {
                             'joint_for_session': [
                                 'Session 2 can not be the joint session, the session has not been requested.']
                         })
    
    def test_invalid_missing_session_length(self):
        form = self._invalid_test_helper({
            'session_set-TOTAL_FORMS': '2',
            'session_set-1-requested_duration': '',
            'third_session': 'false',
            'joint_for_session': None,
        })
        self.assertEqual(form.session_forms.errors,
                         [
                             {},
                             {'requested_duration': ['This field is required.']},
                         ])

        form = self._invalid_test_helper({
            'session_set-1-requested_duration': '',
            'session_set-2-requested_duration': '',
            'joint_for_session': None,
        })
        self.assertEqual(
            form.session_forms.errors,
            [
                {},
                {'requested_duration': ['This field is required.']},
                {'requested_duration': ['This field is required.']},
            ])

        form = self._invalid_test_helper({
            'session_set-2-requested_duration': '',
            'joint_for_session': None,
        })
        self.assertEqual(form.session_forms.errors,
                         [
                             {},
                             {},
                             {'requested_duration': ['This field is required.']},
                         ])

    def _invalid_test_helper(self, new_form_data):
        form_data = dict(self.valid_form_data, **new_form_data)
        form = SessionForm(data=form_data, group=self.group1, meeting=self.meeting)
        self.assertFalse(form.is_valid())
        return form
