# Copyright The IETF Trust 2016, All Rights Reserved

from django.core.urlresolvers import reverse as urlreverse

from pyquery import PyQuery

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


