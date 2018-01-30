# Copyright The IETF Trust 2016, All Rights Reserved
# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function

from pyquery import PyQuery

from django.urls import reverse as urlreverse

import debug                            # pyflakes:ignore

from ietf.mailinglists.factories import ListFactory
from ietf.utils.test_utils import TestCase
from ietf.utils.test_data import make_test_data


class MailingListTests(TestCase):
    def test_groups(self):
        draft = make_test_data()
        group = draft.group
        url = urlreverse("ietf.mailinglists.views.groups")

        # only those with an archive
        group.list_archive = ""
        group.save()
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q("#content a:contains(\"%s\")" % group.acronym)), 0)

        # successful get
        group.list_archive = "https://example.com/foo"
        group.save()
        r = self.client.get(url)
        q = PyQuery(r.content)
        self.assertEqual(len(q("#content a:contains(\"%s\")" % group.acronym)), 1)


    def test_nonwg(self):
        lists = ListFactory.create_batch(7)
        url = urlreverse("ietf.mailinglists.views.nonwg")

        r = self.client.get(url)
        for l in lists:
            if l.advertised:
                self.assertContains(r, l.name)
                self.assertContains(r, l.description)
            else:
                self.assertNotContains(r, l.name, html=True)
                self.assertNotContains(r, l.description, html=True)
