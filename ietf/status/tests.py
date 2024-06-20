# Copyright The IETF Trust 2016-2020, All Rights Reserved
# -*- coding: utf-8 -*-

import debug    # pyflakes:ignore

from django.urls import reverse as urlreverse
from ietf.utils.test_utils import TestCase

class StatusTests(TestCase):
    def test_status_index(self):
        url = urlreverse(ietf.status.views.status_index)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

