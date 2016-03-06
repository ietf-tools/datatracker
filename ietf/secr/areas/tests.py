from django.core.urlresolvers import reverse

from ietf.group.models import Group, GroupEvent
from ietf.person.models import Person
from ietf.utils.test_utils import TestCase
from ietf.utils.test_data import make_test_data


SECR_USER='secretary'

def augment_data():
    system = Person.objects.get(name="(System)")
    area = Group.objects.get(acronym='farfut')
    GroupEvent.objects.create(group=area,
                              type='started',
                              by=system)
                              
class SecrAreasTestCase(TestCase):
    def test_main(self):
        "Main Test"
        make_test_data()
        url = reverse('areas')
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_view(self):
        "View Test"
        make_test_data()
        augment_data()
        areas = Group.objects.filter(type='area',state='active')
        url = reverse('areas_view', kwargs={'name':areas[0].acronym})
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
