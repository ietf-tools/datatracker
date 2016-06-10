import json
from pyquery import PyQuery

from django.core.urlresolvers import reverse as urlreverse

import debug                            # pyflakes:ignore

from ietf.person.factories import EmailFactory,PersonFactory
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

    def test_default_email(self):
        person = PersonFactory()
        primary = EmailFactory(person=person,primary=True,active=True)
        EmailFactory(person=person,primary=False,active=True)
        EmailFactory(person=person,primary=False,active=False)
        self.assertTrue(primary.address in person.formatted_email())

    def test_profile(self):
        person = PersonFactory(with_bio=True)

        self.assertTrue(person.photo is not None)
        self.assertTrue(person.photo.name is not None)

        url = urlreverse("ietf.person.views.profile", kwargs={ "email_or_name": person.plain_name()})
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertIn(person.photo_name(), r.content)
        q = PyQuery(r.content)
        self.assertIn("Photo of %s"%person, q("div.bio-text img.bio-photo").attr("alt"))

        bio_text  = q("div.bio-text").text()
        self.assertIsNotNone(bio_text)

        photo_url = q("div.bio-text img.bio-photo").attr("src")
        r = self.client.get(photo_url)
        self.assertEqual(r.status_code, 200)

