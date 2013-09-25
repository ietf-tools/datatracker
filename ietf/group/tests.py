import os, shutil, datetime

import django.test
from django.core.urlresolvers import reverse as urlreverse

from pyquery import PyQuery

from ietf.utils.mail import outbox
from ietf.utils.test_utils import login_testing_unauthorized
from ietf.utils.test_data import make_test_data

from ietf.name.models import *
from ietf.group.models import *
from ietf.person.models import *

class StreamTests(django.test.TestCase):
    fixtures = ['names']

    def test_stream_edit(self):
        make_test_data()

        stream_acronym = "ietf"

        url = urlreverse("ietf.group.views.stream_edit", kwargs=dict(acronym=stream_acronym))
        login_testing_unauthorized(self, "secretary", url)

        # get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        r = self.client.post(url, dict(delegates="ad2@ietf.org"))
        self.assertEqual(r.status_code, 302)
        self.assertTrue(Role.objects.filter(name="delegate", group__acronym=stream_acronym, email__address="ad2@ietf.org"))
