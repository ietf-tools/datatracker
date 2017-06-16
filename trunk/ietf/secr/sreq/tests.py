from django.urls import reverse

import debug                            # pyflakes:ignore

from ietf.utils.test_utils import TestCase, unicontent
from ietf.group.models import Group
from ietf.meeting.models import Meeting, Session, ResourceAssociation
from ietf.meeting.test_data import make_meeting_test_data
from ietf.utils.mail import outbox, empty_outbox
from ietf.utils.test_data import make_test_data

from pyquery import PyQuery

SECR_USER='secretary'

class SreqUrlTests(TestCase):
    def test_urls(self):
        make_meeting_test_data()

        self.client.login(username="secretary", password="secretary+password")

        r = self.client.get("/secr/")
        self.assertEqual(r.status_code, 200)

        r = self.client.get("/secr/sreq/")
        self.assertEqual(r.status_code, 200)

        testgroup=Group.objects.filter(type_id='wg').first()
        r = self.client.get("/secr/sreq/%s/new/" % testgroup.acronym)
        self.assertEqual(r.status_code, 200)

class SessionRequestTestCase(TestCase):
    def test_main(self):
        make_meeting_test_data()
        url = reverse('ietf.secr.sreq.views.main')
        self.client.login(username="secretary", password="secretary+password")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        sched = r.context['scheduled_groups']
        unsched = r.context['unscheduled_groups']
        self.assertEqual(len(unsched),3)
        self.assertEqual(len(sched),2)

class SubmitRequestCase(TestCase):
    def test_submit_request(self):
        make_test_data()
        group = Group.objects.get(acronym='mars')
        url = reverse('ietf.secr.sreq.views.new',kwargs={'acronym':group.acronym})
        post_data = {'num_session':'1',
                     'length_session1':'3600',
                     'attendees':'10',
                     'conflict1':'',
                     'comments':'need projector'}
        self.client.login(username="secretary", password="secretary+password")
        r = self.client.post(url,post_data)
        self.assertRedirects(r, reverse('ietf.secr.sreq.views.confirm', kwargs={'acronym':group.acronym}))

    def test_submit_request_invalid(self):
        make_test_data()
        group = Group.objects.get(acronym='mars')
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
        self.assertTrue('You must enter a length for all sessions' in unicontent(r))

    def test_request_notification(self):
        make_test_data()
        meeting = Meeting.objects.filter(type='ietf').first()
        group = Group.objects.get(acronym='ames')
        ad = group.parent.role_set.filter(name='ad').first().person
        resource = ResourceAssociation.objects.first()
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
                     'resources': resource.pk}
        self.client.login(username="ameschairman", password="ameschairman+password")
        # submit
        r = self.client.post(url,post_data)
        self.assertRedirects(r, confirm_url)
        # confirm
        r = self.client.post(confirm_url,{'submit':'Submit'})
        self.assertRedirects(r, reverse('ietf.secr.sreq.views.main'))
        self.assertEqual(len(outbox),len_before+1)
        notification = outbox[-1]
        notification_payload = unicode(notification.get_payload(decode=True),"utf-8","replace")
        session = Session.objects.get(meeting=meeting,group=group)
        self.assertEqual(session.resources.count(),1)
        self.assertEqual(session.people_constraints.count(),1)
        resource = session.resources.first()
        self.assertTrue(resource.desc in notification_payload)
        self.assertTrue(ad.ascii_name() in notification_payload)

class LockAppTestCase(TestCase):
    def test_edit_request(self):
        meeting = make_meeting_test_data()
        meeting.session_request_lock_message='locked'
        meeting.save()
        group = Group.objects.get(acronym='mars')
        url = reverse('ietf.secr.sreq.views.edit',kwargs={'acronym':group.acronym})
        self.client.login(username="secretary", password="secretary+password")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q(':disabled[name="submit"]')), 1)
    
    def test_view_request(self):
        meeting = make_meeting_test_data()
        meeting.session_request_lock_message='locked'
        meeting.save()
        group = Group.objects.get(acronym='mars')
        url = reverse('ietf.secr.sreq.views.view',kwargs={'acronym':group.acronym})
        self.client.login(username="secretary", password="secretary+password")
        r = self.client.get(url,follow=True)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q(':disabled[name="edit"]')), 1)
        
    def test_new_request(self):
        meeting = make_meeting_test_data()
        meeting.session_request_lock_message='locked'
        meeting.save()
        group = Group.objects.get(acronym='mars')
        url = reverse('ietf.secr.sreq.views.new',kwargs={'acronym':group.acronym})
        
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
        
class EditRequestCase(TestCase):
    pass
    
class NotMeetingCase(TestCase):

    def test_not_meeting(self):
        make_meeting_test_data()
        group = Group.objects.get(acronym='mars')
        url = reverse('ietf.secr.sreq.views.no_session',kwargs={'acronym':group.acronym}) 
        self.client.login(username="secretary", password="secretary+password")

        empty_outbox()

        r = self.client.get(url,follow=True)
        # If the view invoked by that get throws an exception (such as an integrity error),
        # the traceback from this test will talk about a TransactionManagementError and
        # yell about executing queries before the end of an 'atomic' block

        # This is a sign of a problem - a get shouldn't have a side-effect like this one does
        self.assertEqual(r.status_code, 200)
        self.assertTrue('A message was sent to notify not having a session' in unicontent(r))

        r = self.client.get(url,follow=True)
        self.assertEqual(r.status_code, 200)
        self.assertTrue('is already marked as not meeting' in unicontent(r))

        self.assertEqual(len(outbox),1)
        self.assertTrue('Not having a session' in outbox[0]['Subject'])
        self.assertTrue('session-request@' in outbox[0]['To'])

class RetrievePreviousCase(TestCase):
    pass



    # test error if already scheduled
    # test get previous exists/doesn't exist
    # test that groups scheduled and unscheduled add up to total groups
    # test access by unauthorized
