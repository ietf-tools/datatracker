from django.core.urlresolvers import reverse
from django.test import TestCase

class SessionsTest(TestCase):
    # ------- Test View -------- #
    def test_main(self):
        url = reverse('sessions')
        response = self.client.get(url)
        self.assertEquals(response.status_code, 200)

