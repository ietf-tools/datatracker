from pyquery import PyQuery

from django.urls import reverse

import debug                            # pyflakes:ignore

from ietf.utils.test_utils import TestCase
from ietf.doc.models import StateType

class HelpPageTests(TestCase):

    def test_state_index(self):
        url = reverse('ietf.help.views.state_index')
        r = self.client.get(url)
        q = PyQuery(r.content)
        content = [ e.text for e in q('#content table td a ') ]
        names = StateType.objects.values_list('slug', flat=True)
        # The following doesn't cover all doc types, only a selection
        for name in names:
            if not '-' in name:
                self.assertIn(name, content)

        
    def test_personal_information_help(self):
        r = self.client.get('/help/personal-information')
        self.assertContains(r, 'personal information')
        self.assertContains(r, 'GDPR')
