from django.core.urlresolvers import reverse

from ietf.utils.test_utils import TestCase
from ietf.group.models import Group
#from ietf.meeting.models import Session
#from ietf.utils.test_data import make_test_data
from ietf.meeting.test_data import make_meeting_test_data as make_test_data
from ietf.utils.mail import outbox, empty_outbox

from pyquery import PyQuery

SECR_USER='secretary'

class SreqUrlTests(TestCase):
    def test_urls(self):
        make_test_data()

        self.client.login(username="secretary", password="secretary+password")

        r = self.client.get("/secr/")
        self.assertEqual(r.status_code, 200)

        r = self.client.get("/secr/sreq/")
        self.assertEqual(r.status_code, 200)

        testgroup=Group.objects.filter(type_id='wg').first()
        r = self.client.get("/secr/sreq/%s/new/" % testgroup.acronym)
        self.assertEqual(r.status_code, 200)

class MainTestCase(TestCase):
    def test_main(self):
        make_test_data()
        url = reverse('sessions')
        self.client.login(username="secretary", password="secretary+password")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        sched = r.context['scheduled_groups']
        unsched = r.context['unscheduled_groups']
        self.failUnless(len(unsched) == 0)
        self.failUnless(len(sched) > 0)

class SubmitRequestCase(TestCase):
    def test_submit_request(self):
        make_test_data()
        acronym = Group.objects.all()[0].acronym
        url = reverse('sessions_new',kwargs={'acronym':acronym})
        post_data = {'id_num_session':'1',
                     'id_length_session1':'3600',
                     'id_attendees':'10',
                     'id_conflict1':'',
                     'id_comments':'need projector'}
        self.client.login(username="secretary", password="secretary+password")
        r = self.client.post(url,post_data)
        self.assertEqual(r.status_code, 200)
"""
        #assert False, self.client.session..__dict__
        
        url = reverse('sessions_confirm',kwargs={'acronym':acronym})
        #s = self.client.session
        #s['session_form'] = post_data
        r = self.client.get(url)
        assert False, r.content
"""

class LockAppTestCase(TestCase):
    def test_edit_request(self):
        meeting = make_test_data()
        meeting.session_request_lock_message='locked'
        meeting.save()
        group = Group.objects.get(acronym='mars')
        url = reverse('sessions_edit',kwargs={'acronym':group.acronym})
        self.client.login(username="secretary", password="secretary+password")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q(':disabled[name="submit"]')), 1)
    
    def test_view_request(self):
        meeting = make_test_data()
        meeting.session_request_lock_message='locked'
        meeting.save()
        group = Group.objects.get(acronym='mars')
        url = reverse('sessions_view',kwargs={'acronym':group.acronym})
        self.client.login(username="secretary", password="secretary+password")
        r = self.client.get(url,follow=True)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q(':disabled[name="edit"]')), 1)
        
    def test_new_request(self):
        meeting = make_test_data()
        meeting.session_request_lock_message='locked'
        meeting.save()
        group = Group.objects.get(acronym='mars')
        url = reverse('sessions_new',kwargs={'acronym':group.acronym})
        
        # try as WG Chair
        self.client.login(username="marschairman", password="marschairman+password")
        r = self.client.get(url,follow=True)
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

        make_test_data()
        group = Group.objects.get(acronym='mars')
        url = reverse('sessions_no_session',kwargs={'acronym':group.acronym}) 
        self.client.login(username="secretary", password="secretary+password")

        empty_outbox()

        r = self.client.get(url,follow=True)
        # If the view invoked by that get throws an exception (such as an integrity error),
        # the traceback from this test will talk about a TransactionManagementError and
        # yell about executing queries before the end of an 'atomic' block

        # This is a sign of a problem - a get shouldn't have a side-effect like this one does
        self.assertEqual(r.status_code, 200)
        self.assertTrue('A message was sent to notify not having a session' in r.content)

        r = self.client.get(url,follow=True)
        self.assertEqual(r.status_code, 200)
        self.assertTrue('is already marked as not meeting' in r.content)

        self.assertEqual(len(outbox),1)
        self.assertTrue('Not having a session' in outbox[0]['Subject'])
        self.assertTrue('session-request@' in outbox[0]['To'])

class RetrievePreviousCase(TestCase):
    pass



    # test error if already scheduled
    # test get previous exists/doesn't exist
    # test that groups scheduled and unscheduled add up to total groups
    # test access by unauthorized
