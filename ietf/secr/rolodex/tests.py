from django.core.urlresolvers import reverse

from ietf.utils.test_utils import TestCase
from ietf.person.models import Person
from ietf.utils.test_data import make_test_data


SECR_USER='secretary'

class RolodexTestCase(TestCase):
    def test_main(self):
        "Main Test"
        url = reverse('rolodex')
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_view(self):
        "View Test"
        make_test_data()
        person = Person.objects.all()[0]
        url = reverse('rolodex_view', kwargs={'id':person.id})
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)


