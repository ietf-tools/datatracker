from django.core.urlresolvers import reverse

from ietf.utils.test_utils import TestCase
from ietf.group.models import Group
from ietf.utils.test_data import make_test_data

#from pyquery import PyQuery

SECR_USER='secretary'

class SreqUrlTests(TestCase):
    def test_urls(self):
        draft = make_test_data()

        self.client.login(username="secretary", password="secretary+password")

        r = self.client.get("/secr/")
        self.assertEqual(r.status_code, 200)

        r = self.client.get("/secr/sreq/")
        self.assertEqual(r.status_code, 200)

        r = self.client.get("/secr/sreq/%s/new/" % draft.group.acronym)
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
        self.failUnless(len(sched) == 0)
        self.failUnless(len(unsched) > 0)

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
class EditRequestCase(TestCase):
    pass
    
class NotMeetingCase(TestCase):
    pass

class RetrievePreviousCase(TestCase):
    pass



    # test error if already scheduled
    # test get previous exists/doesn't exist
    # test that groups scheduled and unscheduled add up to total groups
    # test locking function, access by unauthorized
