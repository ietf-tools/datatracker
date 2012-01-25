from django.core.urlresolvers import reverse
from django.test import TestCase
from sec.drafts.models import *

class DraftsTest(TestCase):

    # ------- Test View -------- #
    def test_search(self):
        url = reverse('drafts_search')
        response = self.client.get(url)
        self.assertEquals(response.status_code, 200)

    # test draft revision wrong basename
    # test draft revision wrong rev number
