# Copyright The IETF Trust 2016-2020, All Rights Reserved
# -*- coding: utf-8 -*-

import debug    # pyflakes:ignore

from django.urls import reverse as urlreverse
from ietf.utils.test_utils import TestCase
from ietf.person.models import Person
from ietf.status.models import Status

class StatusTests(TestCase):
    def test_status_index(self):
        status = Status.objects.create(
            title = "my title 1",
            body = "my body 1",
            active = True,
            by = Person.objects.get(user__username='ad'),
        )
        status.save()

        url = urlreverse('ietf.status.views.status_latest_html')
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'my title 1')
        self.assertContains(r, 'my body 1')

        status.delete()

        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, 'my title 1')
        self.assertNotContains(r, 'my body 1')

    def test_no_status_json(self):
        url = urlreverse('ietf.status.views.status_latest_json')
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertFalse(data["hasMessage"])

        status = Status.objects.create(
            title = "my title 1",
            body = "my body 1",
            active = True,
            by = Person.objects.get(user__username='ad'),
        )
        status.save()

        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data["hasMessage"])
        self.assertEqual(data["title"], "my title 1")
        self.assertEqual(data["body"], "my body 1")
        self.assertEqual(data["slug"], '2024-7-8-my-title-1')
        self.assertEqual(data["url"], '/status/2024-7-8-my-title-1')
        self.assertEqual(data["by"], 'Areað Irector')

        status.delete()
