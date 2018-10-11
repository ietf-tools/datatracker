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

    def test_add(self):
        "Add Test"
        url = reverse('ietf.secr.areas.views.add')
        self.client.login(username="secretary", password="secretary+password")
        data = {'acronym':'ta',
             'name':'Test Area',
             'state':'active',
             'start_date':'2017-01-01',
             'awp-TOTAL_FORMS':'2',
             'awp-INITIAL_FORMS':'0',
             'submit':'Save'}
        response = self.client.post(url,data)
        self.assertRedirects(response, reverse('ietf.secr.areas.views.list_areas'))
        area = Group.objects.get(acronym='ta')
        iesg = Group.objects.get(acronym='iesg')
        self.assertTrue(area.parent == iesg)