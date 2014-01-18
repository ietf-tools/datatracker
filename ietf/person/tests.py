import os, shutil, datetime, json

import django.test
from django.core.urlresolvers import reverse as urlreverse

from pyquery import PyQuery

from ietf.utils.mail import outbox
from ietf.utils.test_utils import login_testing_unauthorized, TestCase
from ietf.utils.test_data import make_test_data

from ietf.name.models import *
from ietf.group.models import *
from ietf.person.models import *

class PersonTests(TestCase):
    def test_ajax_search_emails(self):
        draft = make_test_data()
        person = draft.ad

        r = self.client.get(urlreverse("ietf.person.views.ajax_search_emails"), dict(q=person.name))
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.content)
        self.assertEqual(data[0]["id"], person.email_address())
