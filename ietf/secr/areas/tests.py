from django.urls import reverse

from ietf.group.factories import GroupFactory, GroupEventFactory
from ietf.group.models import Group, GroupEvent
from ietf.person.models import Person
from ietf.utils.test_utils import TestCase


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
        GroupFactory(type_id='area')
        url = reverse('ietf.secr.areas.views.list_areas')
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_view(self):
        "View Test"
        area = GroupEventFactory(type='started',group__type_id='area').group
        url = reverse('ietf.secr.areas.views.view', kwargs={'name':area.acronym})
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

