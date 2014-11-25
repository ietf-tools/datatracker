import json

from django.core.urlresolvers import reverse as urlreverse


from ietf.utils.test_utils import TestCase
from ietf.utils.test_data import make_test_data

class PersonTests(TestCase):
    def test_ajax_search_emails(self):
        draft = make_test_data()
        person = draft.ad

        r = self.client.get(urlreverse("ietf.person.views.ajax_select2_search", kwargs={ "model_name": "email"}), dict(q=person.name))
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.content)
        self.assertEqual(data[0]["id"], person.email_address())
