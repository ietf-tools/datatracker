from django.core.urlresolvers import reverse

from ietf.utils.test_utils import TestCase
from ietf.utils.test_data import make_test_data


SECR_USER='secretary'

class MainTestCase(TestCase):
    def test_main(self):
        "Main Test"
        make_test_data()
        url = reverse('ipradmin')
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 301)
"""
    def test_view(self):
        "View Test"
        draft = make_test_data()
        drafts = Document.objects.filter(type='draft')
        url = reverse('drafts_view', kwargs={'id':drafts[0].name})
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
"""
