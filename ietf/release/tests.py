# Copyright The IETF Trust 2012-2022, All Rights Reserved
# -*- coding: utf-8 -*-


from pyquery import PyQuery

from django.urls import reverse

import debug                            # pyflakes:ignore

from ietf.utils.test_utils import TestCase

class ReleasePagesTest(TestCase):
    def test_about(self):
        url = reverse('ietf.release.views.release')+"about"
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        text = q('#content').text()
        for word in ["About", "2.00", "3.00", "4.00", "5.0.0", "6.0.0", "7.0.0", "8.0.0"]:
            self.assertIn(word, text)
