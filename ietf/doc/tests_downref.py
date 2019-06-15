# Copyright The IETF Trust 2017-2019, All Rights Reserved
# -*- coding: utf-8 -*-

from __future__ import unicode_literals

from django.urls import reverse as urlreverse
from pyquery import PyQuery

import debug    # pyflakes:ignore

from ietf.doc.factories import WgDraftFactory, WgRfcFactory
from ietf.doc.models import Document, DocAlias, RelatedDocument, State
from ietf.person.factories import PersonFactory
from ietf.utils.test_utils import TestCase
from ietf.utils.test_utils import login_testing_unauthorized, unicontent

class Downref(TestCase):

    def setUp(self):
        PersonFactory(name='Plain Man',user__username='plain')
        WgDraftFactory(name='draft-ietf-mars-test')
        doc = WgDraftFactory(name='draft-ietf-mars-approved-document',states=[('draft-iesg','rfcqueue')])
        rfc = WgRfcFactory(alias2__name='rfc9998')
        RelatedDocument.objects.create(source=doc, target=rfc.docalias.get(name='rfc9998'),relationship_id='downref-approval')

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

    def test_downref_last_call(self):
        draft = WgDraftFactory(name='draft-ietf-mars-ready-for-lc-document',intended_std_level_id='ps',states=[('draft-iesg','iesg-eva')])
        WgDraftFactory(name='draft-ietf-mars-another-approved-document',states=[('draft-iesg','rfcqueue')])
        rfc9999 = WgRfcFactory(alias2__name='rfc9999', std_level_id=None)
        RelatedDocument.objects.create(source=draft, target=rfc9999.docalias.get(name='rfc9999'), relationship_id='refnorm')
        url = urlreverse('ietf.doc.views_ballot.lastcalltext', kwargs=dict(name=draft.name))
        login_testing_unauthorized(self, "secretary", url)

        # the announcement text should call out the downref to RFC 9999
        r = self.client.post(url, dict(regenerate_last_call_text="1"))
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        text = q("[name=last_call_text]").text()
        self.assertIn('The document contains these normative downward references', text)

        # now, the announcement text about the downref to RFC 9999 should be gone
        RelatedDocument.objects.create(source=draft, target=rfc9999.docalias.get(name='rfc9999'),relationship_id='downref-approval')
        r = self.client.post(url, dict(regenerate_last_call_text="1"))
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        text = q("[name=last_call_text]").text()
        self.assertNotIn('The document contains these normative downward references', text)
