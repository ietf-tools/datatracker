from django.core.urlresolvers import reverse
from django.test import TestCase
from sec.drafts.models import *

class DraftsTest(TestCase):
    fixtures = [ 'acronym.json' ]

    # ------- Test Fixture ----- #
    def test_fixture(self):
        """Test that the fixture loaded"""
        c = Acronym.objects.all().count()
        self.assertEquals(c,4)

    # ------- Test View -------- #
    def test_search(self):
        url = reverse('drafts_search')
        response = self.client.get(url)
        self.assertEquals(response.status_code, 200)
