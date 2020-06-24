# Copyright The IETF Trust 2017-2020, All Rights Reserved
# -*- coding: utf-8 -*-


from django.urls import reverse as urlreverse
from pyquery import PyQuery

import debug    # pyflakes:ignore

from ietf.doc.factories import WgDraftFactory, WgRfcFactory
from ietf.doc.models import RelatedDocument, State
from ietf.person.factories import PersonFactory
from ietf.utils.test_utils import TestCase
from ietf.utils.test_utils import login_testing_unauthorized

class Downref(TestCase):

    def setUp(self):
        PersonFactory(name='Plain Man',user__username='plain')
        self.draft = WgDraftFactory(name='draft-ietf-mars-test')
        self.draftalias = self.draft.docalias.get(name='draft-ietf-mars-test')
        self.doc = WgDraftFactory(name='draft-ietf-mars-approved-document',states=[('draft-iesg','rfcqueue')])
        self.docalias = self.doc.docalias.get(name='draft-ietf-mars-approved-document')
        self.rfc = WgRfcFactory(alias2__name='rfc9998')
        self.rfcalias = self.rfc.docalias.get(name='rfc9998')
        RelatedDocument.objects.create(source=self.doc, target=self.rfcalias, relationship_id='downref-approval')

    def test_downref_registry(self):
        url = urlreverse('ietf.doc.views_downref.downref_registry')

        # normal - get the table without the "Add downref" button
        self.client.login(username="plain", password="plain+password")
        r = self.client.get(url)
        self.assertContains(r, '<h1>Downref registry</h1>')
        self.assertNotContains(r, 'Add downref')

        # secretariat - get the table with the "Add downref" button
        self.client.login(username='secretary', password='secretary+password')
        r = self.client.get(url)
        self.assertContains(r, '<h1>Downref registry</h1>')
        self.assertContains(r, 'Add downref')

        # area director - get the table with the "Add downref" button
        self.client.login(username='ad', password='ad+password')
        r = self.client.get(url)
        self.assertContains(r, '<h1>Downref registry</h1>')
        self.assertContains(r, 'Add downref')

    def test_downref_registry_add(self):
        url = urlreverse('ietf.doc.views_downref.downref_registry_add')
        login_testing_unauthorized(self, "plain", url)

        # secretariat - get the form to add entries to the registry
        self.client.login(username='secretary', password='secretary+password')
        r = self.client.get(url)
        self.assertContains(r, '<h1>Add entry to the downref registry</h1>')
        self.assertContains(r, 'Save downref')

        # area director - get the form to add entries to the registry
        self.client.login(username='ad', password='ad+password')
        r = self.client.get(url)
        self.assertContains(r, '<h1>Add entry to the downref registry</h1>')
        self.assertContains(r, 'Save downref')

        # error - already in the downref registry
        r = self.client.post(url, dict(rfc=self.rfcalias.pk, drafts=(self.doc.pk, )))
        self.assertContains(r, 'Downref is already in the registry')

        # error - source is not in an approved state
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        r = self.client.post(url, dict(rfc=self.rfcalias.pk, drafts=(self.draft.pk, )))
        self.assertContains(r, 'Draft is not yet approved')

        # error - the target is not a normative reference of the source
        self.draft.set_state(State.objects.get(used=True, type="draft-iesg", slug="pub"))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        r = self.client.post(url, dict(rfc=self.rfcalias.pk, drafts=(self.draft.pk, )))
        self.assertContains(r, 'There does not seem to be a normative reference to RFC')
        self.assertContains(r, 'Save downref anyway')

        # normal - approve the document so the downref is now okay
        RelatedDocument.objects.create(source=self.draft, target=self.rfcalias, relationship_id='refnorm')
        draft_de_count_before = self.draft.docevent_set.count()
        rfc_de_count_before = self.rfc.docevent_set.count()

        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        r = self.client.post(url, dict(rfc=self.rfcalias.pk, drafts=(self.draft.pk, )))
        self.assertEqual(r.status_code, 302)
        newurl = urlreverse('ietf.doc.views_downref.downref_registry')
        r = self.client.get(newurl)
        self.assertContains(r, '<a href="/doc/draft-ietf-mars-test')
        self.assertTrue(RelatedDocument.objects.filter(source=self.draft, target=self.rfcalias, relationship_id='downref-approval'))
        self.assertEqual(self.draft.docevent_set.count(), draft_de_count_before + 1)
        self.assertEqual(self.rfc.docevent_set.count(), rfc_de_count_before + 1)

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
