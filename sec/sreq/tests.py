from django.core.urlresolvers import reverse
from django.test import TestCase

from ietf.group.models import Group

from pyquery import PyQuery


class MainTestCase(TestCase):
    fixtures = ['names']
    
    # ------- Test View -------- #
    def test_main(self):
        url = reverse('sessions')
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        sched = r.context['scheduled_groups']
        unsched = r.contect['unscheduled_groups']
        ancp = Group.objects.get(acronym='ancp')
        alto = Group.objects.get(acronym='alto')
        self.failUnless(ancp in sched)
        self.failUnless(alto in unsched)

    # test error if already scheduled
    # test get previous exists/doesn't exist
    # test that groups scheduled and unscheduled add up to total groups
    # test locking function, access by unauthorized
