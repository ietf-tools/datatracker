from django.core.urlresolvers import reverse
from django.test import TestCase

from ietf.doc.models import Document
from ietf.utils.test_data import make_test_data

from pyquery import PyQuery

SECR_USER='secretary'

class MainTestCase(TestCase):
    fixtures = ['names']
                
    def test_main(self):
        "Main Test"
        draft = make_test_data()
        url = reverse('drafts')
        response = self.client.get(url, REMOTE_USER=SECR_USER)
        self.assertEquals(response.status_code, 200)

    def test_view(self):
        "View Test"
        draft = make_test_data()
        drafts = Document.objects.filter(type='draft')
        url = reverse('drafts_view', kwargs={'id':drafts[0].name})
        response = self.client.get(url, REMOTE_USER=SECR_USER)
        self.assertEquals(response.status_code, 200)