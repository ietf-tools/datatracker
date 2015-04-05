from pyquery import PyQuery

from django.core.urlresolvers import reverse

import debug                            # pyflakes:ignore

from ietf.utils.test_utils import TestCase

class ReleasePagesTest(TestCase):

    def test_release(self):
        url = reverse('ietf.release.views.release')
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        releases = [ e.text.strip() for e in q('#content table td a') if e.text ]
        for num in ["2.00", "3.00", "4.00", "5.0.0"]:
            self.assertIn(num, releases)
        
    def test_about(self):
        url = reverse('ietf.release.views.release')+"about"
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        text = q('#content').text()
        for word in ["About", "2.00", "3.00", "4.00", "5.0.0"]:
            self.assertIn(word, text)
        self.assertGreater(len(q('#content a')), 16)

    def test_todo(self):
        url = reverse('ietf.release.views.release')+"todo"
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)


