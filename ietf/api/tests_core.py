# Copyright The IETF Trust 2024, All Rights Reserved
"""Core API tests"""
from django.urls import reverse as urlreverse
from rest_framework.test import APIClient

from ietf.person.factories import PersonFactory
from ietf.utils.test_utils import TestCase


class CoreApiTestCase(TestCase):
    client_class = APIClient


class PersonTests(CoreApiTestCase):
    def test_person_detail(self):
        person = PersonFactory()
        other_person = PersonFactory()
        url = urlreverse("ietf.api.core_api.person-detail", kwargs={"pk": person.pk})
        r = self.client.get(url, format="json")
        self.assertEqual(r.status_code, 403, "Must be logged in")
        self.client.login(
            username=other_person.user.username, password=other_person.user.username + "+password"
        )
        r = self.client.get(url, format="json")
        self.assertEqual(r.status_code, 403, "Can only retrieve self")
        self.client.login(
            username=person.user.username, password=person.user.username + "+password"
        )
        r = self.client.get(url, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(
            r.data,
            {
                "id": person.pk,
                "name": person.name,
                "emails": [
                    {
                        "person": person.pk,
                        "address": email.address,
                        "primary": email.primary,
                        "active": email.active,
                        "origin": email.origin,
                    }
                    for email in person.email_set.all()
                ],
            },
        )
