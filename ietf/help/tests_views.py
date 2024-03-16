from django.urls import reverse

import debug                            # pyflakes:ignore

from ietf.utils.test_utils import TestCase

class HelpPageTests(TestCase):

    def test_state_index(self):
        url = reverse('ietf.help.views.state_index')
        r = self.client.get(url)
        # Make sure you get at least a redirect
        self.assertEqual(r.status_code,301)
