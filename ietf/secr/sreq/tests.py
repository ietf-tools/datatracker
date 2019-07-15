# Copyright The IETF Trust 2013-2019, All Rights Reserved
# -*- coding: utf-8 -*-


from __future__ import absolute_import, print_function, unicode_literals

import datetime
import six

from django.urls import reverse

import debug                            # pyflakes:ignore

from ietf.utils.test_utils import TestCase
from ietf.group.factories import GroupFactory, RoleFactory
from ietf.meeting.models import Session, ResourceAssociation
from ietf.meeting.factories import MeetingFactory, SessionFactory
from ietf.person.models import Person
from ietf.utils.mail import outbox, empty_outbox

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
        SessionFactory.create_batch(2, meeting=meeting, status_id='unsched')
        # An additional unscheduled group comes from make_immutable_base_data
        url = reverse('ietf.secr.sreq.views.main')
        self.client.login(username="secretary", password="secretary+password")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        sched = r.context['scheduled_groups']
        unsched = r.context['unscheduled_groups']
        self.assertEqual(len(unsched),3)
        self.assertEqual(len(sched),2)

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
        session = Session.objects.get(pk=session.pk)
        self.assertEqual(session.status_id,'appr')
        
    def test_cancel(self):
        meeting = MeetingFactory(type_id='ietf', date=datetime.date.today())
        ad = Person.objects.get(user__username='ad')
        area = RoleFactory(name_id='ad', person=ad, group__type_id='area').group
        mars = SessionFactory(meeting=meeting, group__parent=area, group__acronym='mars', status_id='sched').group
        url = reverse('ietf.secr.sreq.views.cancel', kwargs={'acronym':'mars'})
        self.client.login(username="ad", password="ad+password")
        r = self.client.get(url)
        self.assertRedirects(r,reverse('ietf.secr.sreq.views.main'))
        sessions = Session.objects.filter(meeting=meeting, group=mars)
        self.assertEqual(sessions[0].status_id,'deleted')
    
    def test_edit(self):
        meeting = MeetingFactory(type_id='ietf', date=datetime.date.today())
        mars = RoleFactory(name_id='chair', person__user__username='marschairman', group__acronym='mars').group
        SessionFactory(meeting=meeting,group=mars,status_id='sched',scheduled=datetime.datetime.now())

        url = reverse('ietf.secr.sreq.views.edit', kwargs={'acronym':'mars'})
        self.client.login(username="marschairman", password="marschairman+password")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        post_data = {'num_session':'2',
                     'length_session1':'3600',
                     'length_session2':'3600',
                     'attendees':'10',
                     'conflict1':'',
                     'comments':'need lights',
                     'submit': 'Continue'}
        r = self.client.post(url, post_data, HTTP_HOST='example.com')
        self.assertRedirects(r,reverse('ietf.secr.sreq.views.view', kwargs={'acronym':'mars'}))
                   
    def test_tool_status(self):
        MeetingFactory(type_id='ietf', date=datetime.date.today())
        url = reverse('ietf.secr.sreq.views.tool_status')
        self.client.login(username="secretary", password="secretary+password")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        r = self.client.post(url, {'message':'locked', 'submit':'Lock'})
        self.assertRedirects(r,reverse('ietf.secr.sreq.views.main'))
        
class SubmitRequestCase(TestCase):
    def test_submit_request(self):
        meeting = MeetingFactory(type_id='ietf', date=datetime.date.today())
        ad = Person.objects.get(user__username='ad')
        area = RoleFactory(name_id='ad', person=ad, group__type_id='area').group
        group = GroupFactory(parent=area)
        session_count_before = Session.objects.filter(meeting=meeting, group=group).count()
        url = reverse('ietf.secr.sreq.views.new',kwargs={'acronym':group.acronym})
        confirm_url = reverse('ietf.secr.sreq.views.confirm',kwargs={'acronym':group.acronym})
        main_url = reverse('ietf.secr.sreq.views.main')
        post_data = {'num_session':'1',
                     'length_session1':'3600',
                     'attendees':'10',
                     'conflict1':'',
                     'comments':'need projector',
                     'submit': 'Continue'}
        self.client.login(username="secretary", password="secretary+password")
        r = self.client.post(url,post_data)
        self.assertEqual(r.status_code, 200)
        post_data['submit'] = 'Submit'
        r = self.client.post(confirm_url,post_data)
        self.assertRedirects(r, main_url)
        session_count_after = Session.objects.filter(meeting=meeting, group=group).count()
        self.assertTrue(session_count_after == session_count_before + 1)

        # test that second confirm does not add sessions
        r = self.client.post(confirm_url,post_data)
        self.assertRedirects(r, main_url)
        session_count_after = Session.objects.filter(meeting=meeting, group=group).count()
        self.assertTrue(session_count_after == session_count_before + 1)

    def test_submit_request_invalid(self):
        MeetingFactory(type_id='ietf', date=datetime.date.today())
        ad = Person.objects.get(user__username='ad')
        area = RoleFactory(name_id='ad', person=ad, group__type_id='area').group
        group = GroupFactory(parent=area)
        url = reverse('ietf.secr.sreq.views.new',kwargs={'acronym':group.acronym})
        post_data = {'num_session':'2',
                     'length_session1':'3600',
                     'attendees':'10',
                     'conflict1':'',
                     'comments':'need projector'}
        self.client.login(username="secretary", password="secretary+password")
        r = self.client.post(url,post_data)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('#session-request-form')),1)
        self.assertContains(r, 'You must enter a length for all sessions')

    def test_request_notification(self):
        meeting = MeetingFactory(type_id='ietf', date=datetime.date.today())
        ad = Person.objects.get(user__username='ad')
        area = GroupFactory(type_id='area')
        RoleFactory(name_id='ad', person=ad, group=area)
        group = GroupFactory(acronym='ames', parent=area)
        RoleFactory(name_id='chair', group=group, person__user__username='ameschairman')
        resource = ResourceAssociation.objects.create(name_id='project')
        # Bit of a test data hack - the fixture now has no used resources to pick from
        resource.name.used=True
        resource.name.save()

        url = reverse('ietf.secr.sreq.views.new',kwargs={'acronym':group.acronym})
        confirm_url = reverse('ietf.secr.sreq.views.confirm',kwargs={'acronym':group.acronym})
        len_before = len(outbox)
        post_data = {'num_session':'1',
                     'length_session1':'3600',
                     'attendees':'10',
                     'bethere':str(ad.pk),
                     'conflict1':'',
                     'comments':'',
                     'resources': resource.pk,
                     'submit': 'Continue'}
        self.client.login(username="ameschairman", password="ameschairman+password")
        # submit
        r = self.client.post(url,post_data)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue('Confirm' in six.ensure_text(q("title")))
        # confirm
        post_data['submit'] = 'Submit'
        r = self.client.post(confirm_url,post_data)
        self.assertRedirects(r, reverse('ietf.secr.sreq.views.main'))
        self.assertEqual(len(outbox),len_before+1)
        notification = outbox[-1]
        notification_payload = six.ensure_text(notification.get_payload(decode=True),"utf-8","replace")
        session = Session.objects.get(meeting=meeting,group=group)
        self.assertEqual(session.resources.count(),1)
        self.assertEqual(session.people_constraints.count(),1)
        resource = session.resources.first()
        self.assertTrue(resource.desc in notification_payload)
        self.assertTrue(ad.ascii_name() in notification_payload)

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
