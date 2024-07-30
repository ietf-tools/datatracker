# Copyright The IETF Trust 2024, All Rights Reserved
# -*- coding: utf-8 -*-

import debug    # pyflakes:ignore

from django.urls import reverse as urlreverse
from ietf.utils.test_utils import TestCase
from ietf.person.models import Person
from ietf.status.models import Status

class StatusTests(TestCase):
    def test_status_latest_html(self):
        status = Status.objects.create(
            title = "my title 1",
            body = "my body 1",
            active = True,
            by = Person.objects.get(user__username='ad'),
            slug = "2024-1-1-my-title-1"
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

    def test_status_latest_json(self):
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
            slug = "2024-1-1-my-title-1"
        )
        status.save()

        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data["hasMessage"])
        self.assertEqual(data["title"], "my title 1")
        self.assertEqual(data["body"], "my body 1")
        self.assertEqual(data["slug"], '2024-1-1-my-title-1')
        self.assertEqual(data["url"], '/status/2024-1-1-my-title-1')

        status.delete()

    def test_status_latest_redirect(self):
        url = urlreverse('ietf.status.views.status_latest_redirect')
        r = self.client.get(url)
        # without a Status it should return Not Found
        self.assertEqual(r.status_code, 404)

        status = Status.objects.create(
            title = "my title 1",
            body = "my body 1",
            active = True,
            by = Person.objects.get(user__username='ad'),
            slug = "2024-1-1-my-title-1"
        )
        status.save()

        r = self.client.get(url)
        # with a Status it should redirect
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.headers["Location"], "/status/2024-1-1-my-title-1")
        
        status.delete()

    def test_status_page(self):
        slug = "2024-1-1-my-unique-slug"
        r = self.client.get(f'/status/{slug}/')
        # without a Status it should return Not Found
        self.assertEqual(r.status_code, 404)

        # status without `page` markdown should still 200
        status = Status.objects.create(
            title = "my title 1",
            body = "my body 1",
            active = True,
            by = Person.objects.get(user__username='ad'),
            slug = slug
        )
        status.save()

        r = self.client.get(f'/status/{slug}/')
        self.assertEqual(r.status_code, 200)
        
        status.delete()

        test_string = 'a string that'
        status = Status.objects.create(
            title = "my title 1",
            body = "my body 1",
            active = True,
            by = Person.objects.get(user__username='ad'),
            slug = slug,
            page = f"# {test_string}"
        )
        status.save()

        r = self.client.get(f'/status/{slug}/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, test_string)
        
        status.delete()
