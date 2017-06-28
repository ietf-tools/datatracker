from django.urls import reverse

from ietf.utils.test_utils import TestCase
from ietf.person.models import Person
from ietf.utils.test_data import make_test_data


SECR_USER='secretary'

class RolodexTestCase(TestCase):
    def test_main(self):
        "Main Test"
        url = reverse('ietf.secr.rolodex.views.search')
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_view(self):
        "View Test"
        make_test_data()
        person = Person.objects.all()[0]
        url = reverse('ietf.secr.rolodex.views.view', kwargs={'id':person.id})
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_add(self):
        make_test_data()
        url = reverse('ietf.secr.rolodex.views.add')
        add_proceed_url = reverse('ietf.secr.rolodex.views.add_proceed') + '?name=Joe+Smith'
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        response = self.client.post(url, {'name':'Joe Smith'})
        self.assertRedirects(response, add_proceed_url)
        post_data = {
            'name': 'Joe Smith',
            'ascii': 'Joe Smith',
            'ascii_short': 'Joe S',
            'affiliation': 'IETF',
            'address': '100 First Ave',
            'email': 'joes@exanple.com',
            'submit': 'Submit',
        }
        response = self.client.post(add_proceed_url, post_data)
        person = Person.objects.get(name='Joe Smith')
        view_url = reverse('ietf.secr.rolodex.views.view', kwargs={'id':person.pk})
        self.assertRedirects(response, view_url)
        
