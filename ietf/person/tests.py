import json

from django.core.urlresolvers import reverse as urlreverse


from ietf.utils.test_utils import TestCase
from ietf.utils.test_data import make_test_data

from ietf.person.factories import EmailFactory,PersonFactory

class PersonTests(TestCase):
    def test_ajax_search_emails(self):
        draft = make_test_data()
        person = draft.ad

        r = self.client.get(urlreverse("ietf.person.views.ajax_select2_search", kwargs={ "model_name": "email"}), dict(q=person.name))
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.content)
        self.assertEqual(data[0]["id"], person.email_address())

    def test_default_email(self):
        person = PersonFactory()
        primary = EmailFactory(person=person,primary=True,active=True)
        EmailFactory(person=person,primary=False,active=True)
        EmailFactory(person=person,primary=False,active=False)
        self.assertTrue(primary.address in person.formatted_email())
