# Copyright The IETF Trust 2012-2020, All Rights Reserved
# -*- coding: utf-8 -*-


from pyquery import PyQuery

from django.urls import reverse

import debug                            # pyflakes:ignore

from ietf.utils.test_utils import TestCase

class ReleasePagesTest(TestCase):

    def test_release(self):
        url = reverse('ietf.release.views.release', kwargs={'version':'6.0.0'})
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

    def test_stats(self):
        url = reverse('ietf.release.views.stats')

        r = self.client.get(url)
        q = PyQuery(r.content)
        # grab the script element text, split off the json data
        s = q('#coverage-data').text()
        self.assertIn("type: 'line',", s)
        self.assertIn('"data": [[1426018457000, ', s)

        s = q('#frequency-data').text()
        self.assertIn("type: 'column',", s)
        self.assertIn('"data": [[2007, 7], ', s)

