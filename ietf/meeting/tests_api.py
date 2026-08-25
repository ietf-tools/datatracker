# Copyright The IETF Trust 2026, All Rights Reserved
from django.test import override_settings
from django.urls import reverse as urlreverse

from ietf.person.factories import PersonFactory
from ietf.utils.test_utils import TestCase


class MeetingsAttendedByEmailTests(TestCase):
    VIEWNAME = "ietf.api.meeting.registration.attended"
    TOKEN_ENDPOINT = "ietf.api.meeting.registration.attended"

    def setUp(self):
        super().setUp()
        self.person = PersonFactory()

    @override_settings(APP_API_TOKENS={TOKEN_ENDPOINT: "valid-token"})
    def test_endpoint_is_plumbed(self):
        url = urlreverse(self.VIEWNAME, kwargs={"email": self.person.email_address()})
        # bad/missing API keys
        r = self.client.get(url)
        self.assertEqual(r.status_code, 403, "should require api key")
        r = self.client.get(url, headers={"X-Api-Key": "invalid-token"})
        self.assertEqual(r.status_code, 403, "should require valid api key")
        
        # valid request
        r = self.client.get(url, headers={"X-Api-Key": "valid-token"})
        self.assertEqual(r.status_code, 200, "should accept valid api key")
        self.assertEqual(r.json(), {"attended": []})

        # nonexistent person
        self.person.email_set.update(person=None)  # detach email
        self.person.delete()
        r = self.client.get(url, headers={"X-Api-Key": "valid-token"})
        self.assertEqual(r.status_code, 404, "404 for no such Person")

    
    
