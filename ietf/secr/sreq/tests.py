from django.core.urlresolvers import reverse

from ietf.utils.test_utils import TestCase
from ietf.group.models import Group
#from ietf.meeting.models import Session
#from ietf.utils.test_data import make_test_data
from ietf.meeting.test_data import make_meeting_test_data as make_test_data

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
        self.client.login(username="secretary", password="secretary+password")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 302)
        
class EditRequestCase(TestCase):
    pass
    
class NotMeetingCase(TestCase):
    pass

class RetrievePreviousCase(TestCase):
    pass



    # test error if already scheduled
    # test get previous exists/doesn't exist
    # test that groups scheduled and unscheduled add up to total groups
    # test access by unauthorized
