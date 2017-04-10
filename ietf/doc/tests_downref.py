# Copyright The IETF Trust 2017, All Rights Reserved
# -*- coding: utf-8 -*-

from __future__ import unicode_literals

from django.core.urlresolvers import reverse as urlreverse

import debug    # pyflakes:ignore

from ietf.doc.models import Document, DocAlias, RelatedDocument, State
from ietf.utils.test_utils import TestCase
from ietf.utils.test_data  import make_test_data, make_downref_test_data
from ietf.utils.test_utils import login_testing_unauthorized, unicontent

class Downref(TestCase):
    def test_downref_registry(self):
        url = urlreverse('ietf.doc.views_downref.downref_registry')

        # normal - get the table without the "Add downref" button
        self.client.login(username="plain", password="plain+password")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        content = unicontent(r)
        self.assertTrue('<h1>Downref registry</h1>' in content)
        self.assertFalse('Add downref' in content)

        # secretariat - get the table with the "Add downref" button
        self.client.login(username='secretary', password='secretary+password')
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        content = unicontent(r)
        self.assertTrue('<h1>Downref registry</h1>' in content)
        self.assertTrue('Add downref' in content)

        # area director - get the table with the "Add downref" button
        self.client.login(username='ad', password='ad+password')
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        content = unicontent(r)
        self.assertTrue('<h1>Downref registry</h1>' in content)
        self.assertTrue('Add downref' in content)

    def test_downref_registry_add(self):
        url = urlreverse('ietf.doc.views_downref.downref_registry_add')
        login_testing_unauthorized(self, "plain", url)

        # secretariat - get the form to add entries to the registry
        self.client.login(username='secretary', password='secretary+password')
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        content = unicontent(r)
        self.assertTrue('<h1>Add entry to the downref registry</h1>' in content)
        self.assertTrue('Save downref' in content)

        # area director - get the form to add entries to the registry
        self.client.login(username='ad', password='ad+password')
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        content = unicontent(r)
        self.assertTrue('<h1>Add entry to the downref registry</h1>' in content)
        self.assertTrue('Save downref' in content)

        # error - already in the downref registry
        r = self.client.post(url, dict(rfc='rfc9998', drafts=('draft-ietf-mars-approved-document', )))
        self.assertEqual(r.status_code, 200)
        content = unicontent(r)
        self.assertTrue('Downref is already in the registry' in content)

        # error - source is not in an approved state
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        r = self.client.post(url, dict(rfc='rfc9998', drafts=('draft-ietf-mars-test', )))
        self.assertEqual(r.status_code, 200)
        content = unicontent(r)
        self.assertTrue('Draft is not yet approved' in content)

        # error - the target is not a normative reference of the source
        draft = Document.objects.get(name="draft-ietf-mars-test")
        draft.set_state(State.objects.get(used=True, type="draft-iesg", slug="pub"))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        r = self.client.post(url, dict(rfc='rfc9998', drafts=('draft-ietf-mars-test', )))
        self.assertEqual(r.status_code, 200)
        content = unicontent(r)
        self.assertTrue('There does not seem to be a normative reference to RFC' in content)
        self.assertTrue('Save downref anyway' in content)

        # normal - approve the document so the downref is now okay
        rfc = DocAlias.objects.get(name="rfc9998")
        RelatedDocument.objects.create(source=draft, target=rfc, relationship_id='refnorm')
        draft_de_count_before = draft.docevent_set.count()
        rfc_de_count_before = rfc.document.docevent_set.count()

        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        r = self.client.post(url, dict(rfc='rfc9998', drafts=('draft-ietf-mars-test', )))
        self.assertEqual(r.status_code, 302)
        newurl = urlreverse('ietf.doc.views_downref.downref_registry')
        r = self.client.get(newurl)
        self.assertEqual(r.status_code, 200)
        content = unicontent(r)
        self.assertTrue('<a href="/doc/draft-ietf-mars-test' in content)
        self.assertTrue(RelatedDocument.objects.filter(source=draft, target=rfc, relationship_id='downref-approval'))
        self.assertEqual(draft.docevent_set.count(), draft_de_count_before + 1)
        self.assertEqual(rfc.document.docevent_set.count(), rfc_de_count_before + 1)

    def setUp(self):
        make_test_data()
        make_downref_test_data()
