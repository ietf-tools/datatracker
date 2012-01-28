from django.core.urlresolvers import reverse
from django.test import TestCase
from django.contrib.auth.models import User

from ietf.group.models import Group
from ietf.ietfauth.decorators import has_role

from pyquery import PyQuery

SEC_USER='rcross'
WG_USER=''
AD_USER=''

class MainTestCase(TestCase):
    fixtures = ['names', 
                'test-meeting',
                'test-group',
                'test-person',
                'test-user',
                'test-email',
                'test-role']
    
    # ------- Test View -------- #
    def test_main(self):
        url = reverse('sessions')
        r = self.client.get(url,REMOTE_USER=SEC_USER)
        self.assertEquals(r.status_code, 200)
        #assert False, (r.context)
        sched = r.context['scheduled_groups']
        unsched = r.context['unscheduled_groups']
        self.failUnless(len(sched) == 0)
        self.failUnless(len(unsched) == 5)
        #ancp = Group.objects.get(acronym='ancp')
        paws = Group.objects.get(acronym='paws')
        #self.failUnless(ancp in sched)
        self.failUnless(paws in unsched)
        #assert False, r.content
        #user = User.objects.get(username='rcross')
        #self.failUnless(has_role(user,'Secretariat'))

class SubmitRequestCase(TestCase):
    fixtures = ['names', 
                'test-meeting',
                'test-group',
                'test-person',
                'test-user',
                'test-email',
                'test-role']
    
    def test_submit_request(self):
        url = reverse('sessions_new',kwargs={'acronym':'ancp'})
        post_data = {'id_num_session':'1',
                     'id_length_session1':'3600',
                     'id_attendees':'10',
                     'id_conflict1':'core',
                     'id_comments':'need projector'}
        self.client.login(remote_user='rcross')
        r = self.client.post(url,post_data)
        self.assertEquals(r.status_code, 200)
        #assert False, self.client.session..__dict__
        
        url = reverse('sessions_confirm',kwargs={'acronym':'ancp'})
        #s = self.client.session
        #s['session_form'] = post_data
        r = self.client.get(url)
        assert False, r.content

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
