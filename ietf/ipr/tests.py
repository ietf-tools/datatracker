# Copyright The IETF Trust 2009-2023, All Rights Reserved
# -*- coding: utf-8 -*-


import datetime
import mock
import re

from pyquery import PyQuery
from urllib.parse import quote, urlparse
from zoneinfo import ZoneInfo

from django.conf import settings
from django.test.utils import override_settings
from django.urls import reverse as urlreverse
from django.utils import timezone

import debug                            # pyflakes:ignore

from ietf.api.views import EmailIngestionError
from ietf.doc.factories import (
    DocumentFactory,
    WgDraftFactory,
    WgRfcFactory,
    RfcFactory,
    NewRevisionDocEventFactory
)
from ietf.doc.utils import prettify_std_name
from ietf.group.factories import RoleFactory
from ietf.ipr.factories import (
    HolderIprDisclosureFactory,
    GenericIprDisclosureFactory,
    IprDisclosureBaseFactory,
    IprDocRelFactory,
    IprEventFactory
)
from ietf.ipr.forms import DraftForm, HolderIprDisclosureForm
from ietf.ipr.mail import (process_response_email, get_reply_to, get_update_submitter_emails,
                           get_pseudo_submitter, get_holders, get_update_cc_addrs, UndeliverableIprResponseError)
from ietf.ipr.models import (IprDisclosureBase, GenericIprDisclosure, HolderIprDisclosure,
                             ThirdPartyIprDisclosure, IprEvent)
from ietf.ipr.templatetags.ipr_filters import no_revisions_message
from ietf.ipr.utils import get_genitive, get_ipr_summary, ingest_response_email
from ietf.mailtrigger.utils import gather_address_lists
from ietf.message.factories import MessageFactory
from ietf.message.models import Message
from ietf.utils.mail import outbox, empty_outbox, get_payload_text
from ietf.utils.test_utils import TestCase, login_testing_unauthorized
from ietf.utils.text import text_to_dict
from ietf.utils.timezone import date_today


def make_data_from_content(content):
    q = PyQuery(content)
    data = dict()
    for name in ['form-TOTAL_FORMS','form-INITIAL_FORMS','form-MIN_NUM_FORMS','form-MAX_NUM_FORMS']:
        data[name] = q('form input[name=%s]'%name).val()
    for i in range(0,int(data['form-TOTAL_FORMS'])):
        name = 'form-%d-type' % i
        data[name] = q('form input[name=%s]'%name).val()
        text_name = 'form-%d-text' % i
        data[text_name] = q('form textarea[name=%s]'%text_name).html().strip()
        # Do not try to use
        #data[text_name] = q('form textarea[name=%s]'%text_name).text()
        # .text does not work - the field will likely contain <> characters
    return data

class IprTests(TestCase):
    def test_get_genitive(self):
        self.assertEqual(get_genitive("Cisco"),"Cisco's")
        self.assertEqual(get_genitive("Ross"),"Ross'")
        
    def test_get_holders(self):
        ipr = HolderIprDisclosureFactory()
        update = HolderIprDisclosureFactory(updates=[ipr,])
        result = get_holders(update)
        self.assertEqual(set(result),set([ipr.holder_contact_email,update.holder_contact_email]))
        
    def test_get_ipr_summary(self):
        ipr = HolderIprDisclosureFactory(docs=[WgDraftFactory(),])
        self.assertEqual(get_ipr_summary(ipr),ipr.docs.first().name)
        
    def test_get_pseudo_submitter(self):
        ipr = HolderIprDisclosureFactory()
        self.assertEqual(get_pseudo_submitter(ipr),(ipr.submitter_name,ipr.submitter_email))
        ipr.submitter_name=''
        ipr.submitter_email=''
        self.assertEqual(get_pseudo_submitter(ipr),(ipr.holder_contact_name,ipr.holder_contact_email))
        ipr.holder_contact_name=''
        ipr.holder_contact_email=''
        self.assertEqual(get_pseudo_submitter(ipr),('UNKNOWN NAME - NEED ASSISTANCE HERE','UNKNOWN EMAIL - NEED ASSISTANCE HERE'))

    def test_get_update_cc_addrs(self):
        ipr = HolderIprDisclosureFactory()
        update = HolderIprDisclosureFactory(updates=[ipr,])
        result = get_update_cc_addrs(update)
        self.assertEqual(set(result.split(',')),set([update.holder_contact_email,ipr.submitter_email,ipr.holder_contact_email]))
        
    def test_get_update_submitter_emails(self):
        ipr = HolderIprDisclosureFactory()
        update = HolderIprDisclosureFactory(updates=[ipr,])
        messages = get_update_submitter_emails(update)
        self.assertEqual(len(messages),1)
        self.assertTrue(messages[0].startswith('To: %s' % ipr.submitter_email))
        
    def test_showlist(self):
        ipr = HolderIprDisclosureFactory()
        r = self.client.get(urlreverse("ietf.ipr.views.showlist"))
        self.assertContains(r, ipr.title)

    def test_show_posted(self):
        ipr = HolderIprDisclosureFactory()
        r = self.client.get(urlreverse("ietf.ipr.views.show", kwargs=dict(id=ipr.pk)))
        self.assertContains(r, ipr.title)
        
    def test_show_parked(self):
        ipr = HolderIprDisclosureFactory(state_id='parked')
        r = self.client.get(urlreverse("ietf.ipr.views.show", kwargs=dict(id=ipr.pk)))
        self.assertEqual(r.status_code, 403)

    def test_show_pending(self):
        ipr = HolderIprDisclosureFactory(state_id='pending')
        r = self.client.get(urlreverse("ietf.ipr.views.show", kwargs=dict(id=ipr.pk)))
        self.assertEqual(r.status_code, 403)
        
    def test_show_rejected(self):
        ipr = HolderIprDisclosureFactory(state_id='rejected')
        r = self.client.get(urlreverse("ietf.ipr.views.show", kwargs=dict(id=ipr.pk)))
        self.assertEqual(r.status_code, 403)
        
    def test_show_removed(self):
        ipr = HolderIprDisclosureFactory(state_id='removed')
        r = self.client.get(urlreverse("ietf.ipr.views.show", kwargs=dict(id=ipr.pk)))
        self.assertContains(r, 'This IPR disclosure was removed')
        
    def test_show_removed_objfalse(self):
        ipr = HolderIprDisclosureFactory(state_id='removed_objfalse')
        r = self.client.get(urlreverse("ietf.ipr.views.show", kwargs=dict(id=ipr.pk)))
        self.assertContains(r, 'This IPR disclosure was removed as objectively false')
        
    def test_ipr_history(self):
        ipr = HolderIprDisclosureFactory()
        r = self.client.get(urlreverse("ietf.ipr.views.history", kwargs=dict(id=ipr.pk)))
        self.assertContains(r, ipr.title)

    def test_iprs_for_drafts(self):
        draft=WgDraftFactory()
        ipr = HolderIprDisclosureFactory(docs=[draft,])
        r = self.client.get(urlreverse("ietf.ipr.views.by_draft_txt"))
        self.assertContains(r, draft.name)
        self.assertContains(r, str(ipr.pk))

    def test_about(self):
        r = self.client.get(urlreverse("ietf.ipr.views.about"))
        self.assertContains(r, "File a disclosure")

    def test_search(self):
        WgDraftFactory() # The test matching the prefix "draft" needs more than one thing to find
        draft = WgDraftFactory()
        ipr = HolderIprDisclosureFactory(docs=[draft,],patent_info='Number: US12345\nTitle: A method of transferring bits\nInventor: A. Nonymous\nDate: 2000-01-01')

        url = urlreverse("ietf.ipr.views.search")

        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(q("form input[name=draft]"))

        # find by id
        r = self.client.get(url + "?submit=draft&id=%s" % draft.name)
        self.assertContains(r, ipr.title)

        # find by id, mixed case letters
        r = self.client.get(url + "?submit=draft&id=%s" % draft.name.swapcase())
        self.assertContains(r, ipr.title)

        # find draft
        r = self.client.get(url + "?submit=draft&draft=%s" % draft.name)
        self.assertContains(r, ipr.title)

        # find draft, mixed case letters
        r = self.client.get(url + "?submit=draft&draft=%s" % draft.name.swapcase())
        self.assertContains(r, ipr.title)

        # search + select document
        r = self.client.get(url + "?submit=draft&draft=draft")
        self.assertContains(r, draft.name)
        self.assertNotContains(r, ipr.title)

        rfc = RfcFactory(rfc_number=321)
        draft.relateddocument_set.create(relationship_id="became_rfc",target=rfc)

        # find RFC
        r = self.client.get(url + "?submit=rfc&rfc=321")
        self.assertContains(r, ipr.title)

        rfc_new = RfcFactory(rfc_number=322)
        rfc_new.relateddocument_set.create(relationship_id="obs", target=rfc)

        # find RFC 322 which obsoletes RFC 321 whose draft has IPR
        r = self.client.get(url + "?submit=rfc&rfc=322")
        self.assertContains(r, ipr.title)
        self.assertContains(r, "Total number of IPR disclosures found: <b>1</b>")
        self.assertContains(r, "Total number of documents searched: <b>3</b>.")
        self.assertContains(
            r,
            f'Results for <a href="/doc/{rfc_new.name}/">{prettify_std_name(rfc_new.name)}</a> ("{rfc_new.title}")',
            html=True,
        )
        self.assertContains(
            r,
            f'Results for <a href="/doc/{rfc.name}/">{prettify_std_name(rfc.name)}</a> ("{rfc.title}"), '
            f'which was obsoleted by <a href="/doc/{rfc_new.name}/">{prettify_std_name(rfc_new.name)}</a> ("{rfc_new.title}")',
            html=True,
        )
        self.assertContains(
            r,
            f'Results for <a href="/doc/{draft.name}/">{prettify_std_name(draft.name)}</a> ("{draft.title}"), '
            f'which became rfc <a href="/doc/{rfc.name}/">{prettify_std_name(rfc.name)}</a> ("{rfc.title}")',
            html=True,
        )

        # find by patent owner
        r = self.client.get(url + "?submit=holder&holder=%s" % ipr.holder_legal_name)
        self.assertContains(r, ipr.title)
        
        # find by patent info
        r = self.client.get(url + "?submit=patent&patent=%s" % quote(ipr.patent_info.partition("\n")[0]))
        self.assertContains(r, ipr.title)

        r = self.client.get(url + "?submit=patent&patent=US12345")
        self.assertContains(r, ipr.title)

        # find by group acronym
        r = self.client.get(url + "?submit=group&group=%s" % draft.group.pk)
        self.assertContains(r, ipr.title)

        # find by doc title
        r = self.client.get(url + "?submit=doctitle&doctitle=%s" % quote(draft.title))
        self.assertContains(r, ipr.title)

        # find by ipr title
        r = self.client.get(url + "?submit=iprtitle&iprtitle=%s" % quote(ipr.title))
        self.assertContains(r, ipr.title)

    def test_search_null_characters(self):
        """IPR search gracefully rejects null characters in parameters"""
        # Not a combinatorially exhaustive set, but tries to exercise all the parameters
        bad_params = [
            "option=document_search&document_search=draft-\x00stuff"
            "submit=dra\x00ft",
            "submit=draft&id=some\x00id",
            "submit=draft&id_document_tag=some\x00id",
            "submit=draft&id=someid&state=re\x00moved",
            "submit=draft&id=someid&state=posted&state=re\x00moved",
            "submit=draft&id=someid&state=removed&draft=draft-no\x00tvalid",
            "submit=rfc&rfc=rfc\x00123",
        ]
        url = urlreverse("ietf.ipr.views.search")
        for query_params in bad_params:
            r = self.client.get(f"{url}?{query_params}")
            self.assertEqual(r.status_code, 400, f"querystring '{query_params}' should be rejected")
        
    def test_feed(self):
        ipr = HolderIprDisclosureFactory()
        r = self.client.get("/feed/ipr/")
        self.assertContains(r, ipr.title)

    def test_sitemap(self):
        ipr = HolderIprDisclosureFactory()
        r = self.client.get("/sitemap-ipr.xml")
        self.assertContains(r, "/ipr/%s/" % ipr.pk)

    def test_new_generic(self):
        """Ensure new-generic redirects to new-general"""
        url = urlreverse("ietf.ipr.views.new", kwargs={ "_type": "generic" })
        r = self.client.get(url)
        self.assertEqual(r.status_code,302)
        self.assertEqual(urlparse(r["Location"]).path, urlreverse("ietf.ipr.views.new", kwargs={ "_type": "general"}))


    def test_new_general(self):
        """Add a new general disclosure.  Note: submitter does not need to be logged in.
        """
        url = urlreverse("ietf.ipr.views.new", kwargs={ "_type": "general" })

        # invalid post
        r = self.client.post(url, {
            "holder_legal_name": "Test Legal",
            })
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(len(q("form .is-invalid")) > 0)

        # successful post
        empty_outbox()
        r = self.client.post(url, {
            "holder_legal_name": "Test Legal",
            "holder_contact_name": "Test Holder",
            "holder_contact_email": "test@holder.com",
            "holder_contact_info": "555-555-0100",
            "submitter_name": "Test Holder",
            "submitter_email": "test@holder.com",
            "notes": "some notes"
            })
        self.assertContains(r, "Your IPR disclosure has been submitted")
        self.assertEqual(len(outbox),1)
        self.assertTrue('New IPR Submission' in outbox[0]['Subject'])
        self.assertTrue('ietf-ipr@' in outbox[0]['To'])

        iprs = IprDisclosureBase.objects.filter(title__icontains="General License Statement")
        self.assertEqual(len(iprs), 1)
        ipr = iprs[0]
        self.assertEqual(ipr.holder_legal_name, "Test Legal")
        self.assertEqual(ipr.state.slug, 'pending')
        self.assertTrue(isinstance(ipr.get_child(), GenericIprDisclosure))

    def test_new_specific(self):
        """Add a new specific disclosure.  Note: submitter does not need to be logged in.
        """
        draft = WgDraftFactory()
        rfc = WgRfcFactory()
        url = urlreverse("ietf.ipr.views.new", kwargs={ "_type": "specific" })

        # successful post
        empty_outbox()
        data = {
            "holder_legal_name": "Test Legal",
            "holder_contact_name": "Test Holder",
            "holder_contact_email": "test@holder.com",
            "holder_contact_info": "555-555-0100",
            "ietfer_name": "Test Participant",
            "ietfer_contact_info": "555-555-0101",
            "iprdocrel_set-TOTAL_FORMS": 2,
            "iprdocrel_set-INITIAL_FORMS": 0,
            "iprdocrel_set-0-document": draft.pk,
            "iprdocrel_set-0-revisions": '00',
            "iprdocrel_set-1-document": rfc.pk,
            "patent_number": "SE12345678901",
            "patent_inventor": "A. Nonymous",
            "patent_title": "A method of transferring bits",
            "patent_date": "2000-01-01",
            "has_patent_pending": False,
            "licensing": "royalty-free",
            "submitter_name": "Test Holder",
            "submitter_email": "test@holder.com",
        }
        r = self.client.post(url, data)
        self.assertContains(r, "Your IPR disclosure has been submitted")

        iprs = IprDisclosureBase.objects.filter(title__icontains=draft.name)
        self.assertEqual(len(iprs), 1)
        ipr = iprs[0]
        self.assertEqual(ipr.holder_legal_name, "Test Legal")
        self.assertEqual(ipr.state.slug, 'pending')
        for item in ['SE12345678901','A method of transferring bits','2000-01-01']:
            self.assertIn(item, ipr.get_child().patent_info)
        self.assertTrue(isinstance(ipr.get_child(),HolderIprDisclosure))
        self.assertEqual(len(outbox),1)
        self.assertTrue('New IPR Submission' in outbox[0]['Subject'])
        self.assertTrue('ietf-ipr@' in outbox[0]['To'])

        # Check some additional application number formats:
        for patent_number in [
                'PCT/EP2019/123456',    # WO application
                'PCT/EP05/12345',       # WO application, old
                'ATA123/2012',          # Austria
                'AU2011901234',         # Australia
                'BE2010/0912',          # Belgium
                'CA1234567',            # Canada
                ]:
            data['patent_number'] = patent_number
            r = self.client.post(url, data)
            self.assertContains(r, "Your IPR disclosure has been submitted", msg_prefix="Checked patent number: %s" % patent_number)

    def test_new_specific_no_revision(self):
        draft = WgDraftFactory()
        rfc = WgRfcFactory()
        url = urlreverse("ietf.ipr.views.new", kwargs={ "_type": "specific" })

        # successful post
        empty_outbox()
        data = {
            "holder_legal_name": "Test Legal",
            "holder_contact_name": "Test Holder",
            "holder_contact_email": "test@holder.com",
            "holder_contact_info": "555-555-0100",
            "ietfer_name": "Test Participant",
            "ietfer_contact_info": "555-555-0101",
            "iprdocrel_set-TOTAL_FORMS": 2,
            "iprdocrel_set-INITIAL_FORMS": 0,
            "iprdocrel_set-0-document": draft.pk,
            "iprdocrel_set-1-document": rfc.pk,
            "patent_number": "SE12345678901",
            "patent_inventor": "A. Nonymous",
            "patent_title": "A method of transferring bits",
            "patent_date": "2000-01-01",
            "has_patent_pending": False,
            "licensing": "royalty-free",
            "submitter_name": "Test Holder",
            "submitter_email": "test@holder.com",
        }
        r = self.client.post(url, data)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(q("#id_iprdocrel_set-0-revisions").hasClass("is-invalid"))

    def test_new_thirdparty(self):
        """Add a new third-party disclosure.  Note: submitter does not need to be logged in.
        """
        draft = WgDraftFactory()
        rfc = WgRfcFactory()
        url = urlreverse("ietf.ipr.views.new", kwargs={ "_type": "third-party" })

        # successful post
        empty_outbox()
        r = self.client.post(url, {
            "holder_legal_name": "Test Legal",
            "ietfer_name": "Test Participant",
            "ietfer_contact_email": "test@ietfer.com",
            "ietfer_contact_info": "555-555-0101",
            "iprdocrel_set-TOTAL_FORMS": 2,
            "iprdocrel_set-INITIAL_FORMS": 0,
            "iprdocrel_set-0-document": draft.pk,
            "iprdocrel_set-0-revisions": '00',
            "iprdocrel_set-1-document": rfc.pk,
            "patent_number": "SE12345678901",
            "patent_inventor": "A. Nonymous",
            "patent_title": "A method of transferring bits",
            "patent_date": "2000-01-01",
            "has_patent_pending": False,
            "licensing": "royalty-free",
            "submitter_name": "Test Holder",
            "submitter_email": "test@holder.com",
            })
        self.assertContains(r, "Your IPR disclosure has been submitted")

        iprs = IprDisclosureBase.objects.filter(title__icontains="belonging to Test Legal")
        self.assertEqual(len(iprs), 1)
        ipr = iprs[0]
        self.assertEqual(ipr.holder_legal_name, "Test Legal")
        self.assertEqual(ipr.state.slug, "pending")
        for item in ['SE12345678901','A method of transferring bits','2000-01-01' ]:
            self.assertIn(item, ipr.get_child().patent_info)
        self.assertTrue(isinstance(ipr.get_child(),ThirdPartyIprDisclosure))
        self.assertEqual(len(outbox),1)
        self.assertTrue('New IPR Submission' in outbox[0]['Subject'])
        self.assertTrue('ietf-ipr@' in outbox[0]['To'])

    def test_edit(self):
        draft = WgDraftFactory()
        original_ipr = HolderIprDisclosureFactory(docs=[draft,])

        # get
        url = urlreverse("ietf.ipr.views.edit", kwargs={ "id": original_ipr.id })
        login_testing_unauthorized(self, "secretary", url)
        r = self.client.get(url)
        self.assertContains(r, original_ipr.holder_legal_name)

        #url = urlreverse("ietf.ipr.views.new", kwargs={ "_type": "specific" })
        # successful post
        empty_outbox()
        post_data = {
            "has_patent_pending": False,
            "holder_contact_email": "test@holder.com",
            "holder_contact_info": "555-555-0100",
            "holder_contact_name": "Test Holder",
            "holder_legal_name": "Test Legal",
            "ietfer_contact_info": "555-555-0101",
            "ietfer_name": "Test Participant",
            "iprdocrel_set-0-document": draft.pk,
            "iprdocrel_set-0-revisions": '00',
            "iprdocrel_set-INITIAL_FORMS": 0,
            "iprdocrel_set-TOTAL_FORMS": 1,
            "licensing": "royalty-free",
            "patent_date": "2000-01-01",
            "patent_inventor": "A. Nonymous",
            "patent_number": "SE12345678901",
            "patent_title": "A method of transferring bits",
            "submitter_email": "test@holder.com",
            "submitter_name": "Test Holder",
            "updates": [],
        }
        r = self.client.post(url, post_data, follow=True)
        self.assertContains(r, "Disclosure modified")

        iprs = IprDisclosureBase.objects.filter(title__icontains=draft.name)
        self.assertEqual(len(iprs), 1)
        ipr = iprs[0].get_child()
        self.assertEqual(ipr.holder_legal_name, "Test Legal")
        patent_info_dict = dict( (k.replace('patent_','').capitalize(), v) for k, v in list(post_data.items()) if k.startswith('patent_') )
        self.assertEqual(text_to_dict(ipr.patent_info), patent_info_dict)
        self.assertEqual(ipr.state.slug, 'posted')

        self.assertEqual(len(outbox),0)

    def test_update(self):
        draft = WgDraftFactory()
        rfc = WgRfcFactory()
        original_ipr = HolderIprDisclosureFactory(docs=[draft,])

        # get
        url = urlreverse("ietf.ipr.views.update", kwargs={ "id": original_ipr.id })
        r = self.client.get(url)
        self.assertContains(r, original_ipr.title)

        #url = urlreverse("ietf.ipr.views.new", kwargs={ "_type": "specific" })
        # successful post
        empty_outbox()
        r = self.client.post(url, {
            "updates": [original_ipr.pk],
            "holder_legal_name": "Test Legal",
            "holder_contact_name": "Test Holder",
            "holder_contact_email": "test@holder.com",
            "holder_contact_info": "555-555-0100",
            "ietfer_name": "Test Participant",
            "ietfer_contact_info": "555-555-0101",
            "iprdocrel_set-TOTAL_FORMS": 2,
            "iprdocrel_set-INITIAL_FORMS": 0,
            "iprdocrel_set-0-document": draft.pk,
            "iprdocrel_set-0-revisions": '00',
            "iprdocrel_set-1-document": rfc.pk,
            "patent_number": "SE12345678901",
            "patent_inventor": "A. Nonymous",
            "patent_title": "A method of transferring bits",
            "patent_date": "2000-01-01",
            "has_patent_pending": False,
            "licensing": "royalty-free",
            "submitter_name": "Test Holder",
            "submitter_email": "test@holder.com",
            })
        self.assertContains(r, "Your IPR disclosure has been submitted")

        iprs = IprDisclosureBase.objects.filter(title__icontains=draft.name)
        self.assertEqual(len(iprs), 1)
        ipr = iprs[0]
        self.assertEqual(ipr.holder_legal_name, "Test Legal")
        self.assertEqual(ipr.state.slug, 'pending')

        self.assertTrue(ipr.relatedipr_source_set.filter(target=original_ipr))
        self.assertEqual(len(outbox),1)
        self.assertTrue('New IPR Submission' in outbox[0]['Subject'])
        self.assertTrue('ietf-ipr@' in outbox[0]['To'])

    def test_update_bad_post(self):
        draft = WgDraftFactory()
        url = urlreverse("ietf.ipr.views.new", kwargs={ "_type": "specific" })

        empty_outbox()
        r = self.client.post(url, {
            "updates": "this is supposed to be an array of integers",
            "holder_legal_name": "Test Legal",
            "holder_contact_name": "Test Holder",
            "holder_contact_email": "test@holder.com",
            "iprdocrel_set-TOTAL_FORMS": 1,
            "iprdocrel_set-INITIAL_FORMS": 0,
            "iprdocrel_set-0-document": draft.pk,
            "iprdocrel_set-0-revisions": '00',
            "patent_number": "SE12345678901",
            "patent_inventor": "A. Nonymous",
            "patent_title": "A method of transferring bits",
            "patent_date": "2000-01-01",
            "has_patent_pending": False,
            "licensing": "royalty-free",
            "submitter_name": "Test Holder",
            "submitter_email": "test@holder.com",
            })
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(q("#id_updates").parents(".row").hasClass("is-invalid"))

    def test_addcomment(self):
        ipr = HolderIprDisclosureFactory()
        url = urlreverse('ietf.ipr.views.add_comment', kwargs={ "id": ipr.id })
        self.client.login(username="secretary", password="secretary+password")
        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        
        # public comment
        comment = 'Test comment'
        r = self.client.post(url, dict(comment=comment))
        self.assertEqual(r.status_code,302)
        qs = ipr.iprevent_set.filter(type='comment',desc=comment)
        self.assertTrue(qs.count(),1)
        
        # private comment
        r = self.client.post(url, dict(comment='Private comment',private=True),follow=True)
        self.assertContains(r, 'Private comment')
        self.client.logout()
        r = self.client.get(url, follow=True)
        self.assertNotContains(r, 'Private comment')
        
    def test_addemail(self):
        ipr = HolderIprDisclosureFactory()
        url = urlreverse('ietf.ipr.views.add_email', kwargs={ "id": ipr.id })
        self.client.login(username="secretary", password="secretary+password")
        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        
        # post
        r = self.client.post(url, {
            "direction": 'incoming',
            "message": """From: test@acme.com
To: ietf-ipr@ietf.org
Subject: RE: The Cisco Statement
Date: Wed, 24 Sep 2014 14:25:02 -0700

Hello,

I would like to revoke this declaration.
"""})
        msg = Message.objects.get(frm='test@acme.com')
        qs = ipr.iprevent_set.filter(type='msgin',message=msg)
        self.assertTrue(qs.count(),1)
        
    def test_admin_pending(self):
        HolderIprDisclosureFactory(state_id='pending')
        url = urlreverse('ietf.ipr.views.admin',kwargs={'state':'pending'})
        self.client.login(username="secretary", password="secretary+password")
                
        # test for presence of pending ipr
        num = IprDisclosureBase.objects.filter(state='pending').count()
        
        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        q = PyQuery(r.content)
        x = len(q('table.ipr-table tbody tr'))
        self.assertEqual(num,x)
        
    def test_admin_removed(self):
        HolderIprDisclosureFactory(state_id='removed')
        url = urlreverse('ietf.ipr.views.admin',kwargs={'state':'removed'})
        self.client.login(username="secretary", password="secretary+password")
        
        # test for presence of pending ipr
        num = IprDisclosureBase.objects.filter(state__in=('removed','removed_objfalse','rejected')).count()
        
        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        q = PyQuery(r.content)
        x = len(q('table.ipr-table tbody tr'))
        self.assertEqual(num,x)
        
    def test_admin_parked(self):
        pass
    
    def test_post(self):
        ipr = HolderIprDisclosureFactory(state_id='pending')
        url = urlreverse('ietf.ipr.views.state', kwargs={'id':ipr.id})
        login_testing_unauthorized(self,"secretary",url)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        r = self.client.post(url,{'state':'posted'})
        self.assertEqual(r.status_code, 302)
        ipr = HolderIprDisclosure.objects.get(id=ipr.id)
        self.assertTrue(ipr.iprevent_set.filter(type='posted').exists())

    def test_notify(self):
        doc = WgDraftFactory(group__acronym='mars-wg', name='draft-ietf-mars-test')
        old_ipr = HolderIprDisclosureFactory(docs=[doc,], submitter_email='george@acme.com')
        IprEventFactory(type_id='submitted', disclosure=old_ipr)
        IprEventFactory(type_id='posted', disclosure=old_ipr)
        ipr = HolderIprDisclosureFactory(docs=[doc,], submitter_email='george@acme.com', updates=[old_ipr])
        IprEventFactory(type_id='submitted', disclosure=ipr)
        IprEventFactory(type_id='posted', disclosure=ipr)
        url = urlreverse('ietf.ipr.views.post', kwargs={ "id": ipr.id })
        login_testing_unauthorized(self, "secretary", url)

        r = self.client.get(url,follow=True)
        self.assertEqual(r.status_code,200)
        len_before = len(outbox)
        # successful post
        self.client.login(username="secretary", password="secretary+password")
        r = self.client.get(url,follow=True)
        self.assertEqual(r.status_code,200)
        ipr = IprDisclosureBase.objects.get(pk=ipr.pk)
        self.assertEqual(ipr.state.slug,'posted')
        url = urlreverse('ietf.ipr.views.notify',kwargs={ 'id':ipr.id, 'type':'posted'})
        r = self.client.get(url,follow=True)
        self.assertEqual(r.status_code,200)
        data = make_data_from_content(r.content)
        r = self.client.post(url, data )
        self.assertEqual(r.status_code,302)
        self.assertEqual(len(outbox),len_before+2)
        self.assertTrue('george@acme.com' in outbox[len_before]['To'])
        self.assertIn('posted on '+date_today().strftime("%Y-%m-%d"), get_payload_text(outbox[len_before]).replace('\n',' '))
        self.assertTrue('draft-ietf-mars-test@ietf.org' in outbox[len_before+1]['To'])
        self.assertTrue('mars-wg@ietf.org' in outbox[len_before+1]['Cc'])
        self.assertIn(
            'Secretariat on ' + ipr.get_latest_event_submitted().time.astimezone(ZoneInfo(settings.TIME_ZONE)).strftime("%Y-%m-%d"),
            get_payload_text(outbox[len_before + 1]).replace('\n', ' ')
        )
        self.assertIn(f'{settings.IDTRACKER_BASE_URL}{urlreverse("ietf.ipr.views.showlist")}', get_payload_text(outbox[len_before]).replace('\n',' '))
        self.assertIn(f'{settings.IDTRACKER_BASE_URL}{urlreverse("ietf.ipr.views.show",kwargs=dict(id=ipr.pk))}', get_payload_text(outbox[len_before+1]).replace('\n',' '))

    def test_notify_generic(self):
        RoleFactory(name_id='ad',group__acronym='gen')
        ipr = GenericIprDisclosureFactory(submitter_email='foo@example.com')
        IprEventFactory(type_id='submitted', disclosure=ipr)
        IprEventFactory(type_id='posted', disclosure=ipr)
        url = urlreverse('ietf.ipr.views.notify',kwargs={ 'id':ipr.id, 'type':'posted'})
        empty_outbox()
        login_testing_unauthorized(self, 'secretary', url)
        r = self.client.get(url, follow=True)
        self.assertTrue(r.status_code, 200)
        data = make_data_from_content(r.content)
        r = self.client.post(url, data )
        self.assertEqual(r.status_code,302)
        self.assertEqual(len(outbox),2)
        self.assertIn(
            'Secretariat on ' + ipr.get_latest_event_submitted().time.astimezone(ZoneInfo(settings.TIME_ZONE)).strftime("%Y-%m-%d"),
            get_payload_text(outbox[1]).replace('\n',' '),
        )
        self.assertIn(f'{settings.IDTRACKER_BASE_URL}{urlreverse("ietf.ipr.views.showlist")}', get_payload_text(outbox[1]).replace('\n',' '))

    def send_ipr_email_helper(self) -> tuple[str, IprEvent, HolderIprDisclosure]:
        ipr = HolderIprDisclosureFactory()
        url = urlreverse('ietf.ipr.views.email',kwargs={ "id": ipr.id })
        self.client.login(username="secretary", password="secretary+password")
        yesterday = date_today() - datetime.timedelta(1)
        data = dict(
            to='joe@test.com',
            frm='ietf-ipr@ietf.org',
            subject='test',
            reply_to=get_reply_to(),
            body='Testing.',
            response_due=yesterday.isoformat())
        empty_outbox()
        r = self.client.post(url,data,follow=True)
        self.assertEqual(r.status_code,200)
        q = Message.objects.filter(reply_to=data['reply_to'])
        self.assertEqual(q.count(),1)
        event = q[0].msgevents.first()
        assert event is not None
        self.assertTrue(event.response_past_due())
        self.assertEqual(len(outbox), 1)
        self.assertTrue('joe@test.com' in outbox[0]['To'])
        return data['reply_to'], event, ipr

    uninteresting_ipr_message_strings = [
        ("To: {to}\nCc: {cc}\nFrom: joe@test.com\nDate: {date}\nSubject: test\n"),
        ("Cc: {cc}\nFrom: joe@test.com\nDate: {date}\nSubject: test\n"),  # no To
        ("To: {to}\nFrom: joe@test.com\nDate: {date}\nSubject: test\n"),  # no Cc
        ("From: joe@test.com\nDate: {date}\nSubject: test\n"),  # no To or Cc
        ("Cc: {cc}\nDate: {date}\nSubject: test\n"),  # no To
        ("To: {to}\nDate: {date}\nSubject: test\n"),  # no Cc
        ("Date: {date}\nSubject: test\n"),  # no To or Cc
    ]

    def test_process_response_email(self):
        # first send a mail
        reply_to, event, _ = self.send_ipr_email_helper()

        # test process response uninteresting messages
        addrs = gather_address_lists('ipr_disclosure_submitted').as_strings()
        for message_string in self.uninteresting_ipr_message_strings:
            process_response_email(
                message_string.format(
                    to=addrs.to,
                    cc=addrs.cc,
                    date=timezone.now().ctime()
                )
            )

        # test process response
        message_string = """To: {}
From: joe@test.com
Date: {}
Subject: test
""".format(reply_to, timezone.now().ctime())
        process_response_email(message_string)
        self.assertFalse(event.response_past_due())

        # test with an unmatchable message identifier
        bad_reply_to = re.sub(
            r"\+.{16}@",
            '+0123456789abcdef@',
            reply_to,
        )
        self.assertNotEqual(reply_to, bad_reply_to)
        message_string = f"""To: {bad_reply_to}
        From: joe@test.com
        Date: {timezone.now().ctime()}
        Subject: test
        """
        with self.assertRaises(UndeliverableIprResponseError):
            process_response_email(message_string)

    def test_process_response_email_with_invalid_encoding(self):
        """Interesting emails with invalid encoding should be handled"""
        reply_to, _, disclosure = self.send_ipr_email_helper()
        # test process response
        message_string = """To: {}
From: joe@test.com
Date: {}
Subject: test
""".format(reply_to, timezone.now().ctime())
        message_bytes = message_string.encode('utf8') + b'\nInvalid stuff: \xfe\xff\n'
        process_response_email(message_bytes)
        result = IprEvent.objects.filter(disclosure=disclosure).first().message  # newest
        # \ufffd is a rhombus character with an inverse ?, used to replace invalid characters
        self.assertEqual(result.body, 'Invalid stuff: \ufffd\ufffd\n\n',  # not sure where the extra \n is from
                         'Invalid characters should be replaced with \ufffd characters')

    def test_process_response_email_uninteresting_with_invalid_encoding(self):
        """Uninteresting emails with invalid encoding should be quietly dropped"""
        self.send_ipr_email_helper()
        addrs = gather_address_lists('ipr_disclosure_submitted').as_strings()
        for message_string in self.uninteresting_ipr_message_strings:
            message_bytes = message_string.format(
                                to=addrs.to,
                                cc=addrs.cc,
                                date=timezone.now().ctime(),
            ).encode('utf8') + b'\nInvalid stuff: \xfe\xff\n'
            process_response_email(message_bytes)

    @override_settings(ADMINS=(("Some Admin", "admin@example.com"),))
    @mock.patch("ietf.ipr.utils.process_response_email")
    def test_ingest_response_email(self, mock_process_response_email):
        message = b"What a nice message"
        mock_process_response_email.side_effect = ValueError("ouch!")
        with self.assertRaises(EmailIngestionError) as context:
            ingest_response_email(message)
        self.assertIsNone(context.exception.email_recipients)  # default recipients
        self.assertIsNotNone(context.exception.email_body)  # body set
        self.assertIsNotNone(context.exception.email_original_message)  # original message attached
        self.assertEqual(context.exception.email_attach_traceback, True)
        self.assertTrue(mock_process_response_email.called)
        self.assertEqual(mock_process_response_email.call_args, mock.call(message))
        mock_process_response_email.reset_mock()
        
        mock_process_response_email.side_effect = UndeliverableIprResponseError
        mock_process_response_email.return_value = None
        with self.assertRaises(EmailIngestionError) as context:
            ingest_response_email(message)
        self.assertIsNone(context.exception.as_emailmessage())  # should not send an email on a clean rejection
        self.assertTrue(mock_process_response_email.called)
        self.assertEqual(mock_process_response_email.call_args, mock.call(message))
        mock_process_response_email.reset_mock()

        mock_process_response_email.side_effect = None
        mock_process_response_email.return_value = None  # ignored message
        ingest_response_email(message)  # should not raise an exception
        self.assertIsNone(context.exception.as_emailmessage())  # should not send an email on ignored message
        self.assertTrue(mock_process_response_email.called)
        self.assertEqual(mock_process_response_email.call_args, mock.call(message))
        mock_process_response_email.reset_mock()

        # successful operation
        mock_process_response_email.return_value = MessageFactory()
        ingest_response_email(message)
        self.assertTrue(mock_process_response_email.called)
        self.assertEqual(mock_process_response_email.call_args, mock.call(message))

    def test_ajax_search(self):
        url = urlreverse('ietf.ipr.views.ajax_search')
        response=self.client.get(url+'?q=disclosure')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.get('Content-Type'),'application/json')

    def test_edit_using_factory(self):
        disclosure = HolderIprDisclosureFactory(docs=[DocumentFactory(type_id='draft')])
        patent_dict = text_to_dict(disclosure.patent_info)
        url = urlreverse('ietf.ipr.views.edit',kwargs={'id':disclosure.pk})
        login_testing_unauthorized(self, "secretary", url)
        response = self.client.get(url)
        self.assertEqual(response.status_code,200)
        post_data = {
            'iprdocrel_set-TOTAL_FORMS' : 1,
            'iprdocrel_set-INITIAL_FORMS' : 0,
            'iprdocrel_set-0-id': '',
            "iprdocrel_set-0-document": disclosure.docs.first().pk,
            "iprdocrel_set-0-revisions": disclosure.docs.first().rev,
            'holder_legal_name': disclosure.holder_legal_name,
            'patent_number': patent_dict['Number'],
            'patent_title': patent_dict['Title'],
            'patent_date' : patent_dict['Date'],
            'patent_inventor' : patent_dict['Inventor'],
            'licensing' : disclosure.licensing.slug,
        }
        response = self.client.post(url,post_data)
        self.assertEqual(response.status_code,302)
        disclosure = HolderIprDisclosure.objects.get(pk=disclosure.pk)
        self.assertEqual(disclosure.compliant,False)

    def test_docevent_creation(self):
        """Test that IprEvent creation triggers DocEvent creation"""
        doc = DocumentFactory()
        ipr = HolderIprDisclosureFactory(docs=[doc])
        # Document starts with no ipr-related events
        self.assertEqual(0, doc.docevent_set.filter(type='posted_related_ipr').count(),
                         'New Document already has a "posted_related_ipr" DocEvent')
        self.assertEqual(0, doc.docevent_set.filter(type='removed_related_ipr').count(),
                         'New Document already has a "removed_related_ipr" DocEvent')
        self.assertEqual(0, doc.docevent_set.filter(type='removed_objfalse_related_ipr').count(),
                         'New Document already has a "removed_objfalse_related_ipr" DocEvent')
        # A 'posted' IprEvent must create a corresponding DocEvent  
        IprEventFactory(type_id='posted', disclosure=ipr)
        self.assertEqual(1, doc.docevent_set.filter(type='posted_related_ipr').count(),
                         'Creating "posted" IprEvent did not create a "posted_related_ipr" DocEvent')
        self.assertEqual(0, doc.docevent_set.filter(type='removed_related_ipr').count(),
                         'Creating "posted" IprEvent created a "removed_related_ipr" DocEvent')
        self.assertEqual(0, doc.docevent_set.filter(type='removed_objfalse_related_ipr').count(),
                         'Creating "posted" IprEvent created a "removed_objfalse_related_ipr" DocEvent')
        # A 'removed' IprEvent must create a corresponding DocEvent
        IprEventFactory(type_id='removed', disclosure=ipr)
        self.assertEqual(1, doc.docevent_set.filter(type='posted_related_ipr').count(),
                         'Creating "removed" IprEvent created a "posted_related_ipr" DocEvent')
        self.assertEqual(1, doc.docevent_set.filter(type='removed_related_ipr').count(),
                         'Creating "removed" IprEvent did not create a "removed_related_ipr" DocEvent')
        # A 'removed_objfalse' IprEvent must create a corresponding DocEvent
        IprEventFactory(type_id='removed_objfalse', disclosure=ipr)
        self.assertEqual(1, doc.docevent_set.filter(type='posted_related_ipr').count(),
                         'Creating "removed_objfalse" IprEvent created a "posted_related_ipr" DocEvent')
        self.assertEqual(1, doc.docevent_set.filter(type='removed_objfalse_related_ipr').count(),
                         'Creating "removed_objfalse" IprEvent did not create a "removed_objfalse_related_ipr" DocEvent')
        # The DocEvent descriptions must refer to the IprEvents
        posted_docevent = doc.docevent_set.filter(type='posted_related_ipr').first()
        self.assertIn(ipr.title, posted_docevent.desc, 
                      'IprDisclosure title does not appear in DocEvent desc when posted')
        removed_docevent = doc.docevent_set.filter(type='removed_related_ipr').first()
        self.assertIn(ipr.title, removed_docevent.desc,
                      'IprDisclosure title does not appear in DocEvent desc when removed')
        removed_objfalse_docevent = doc.docevent_set.filter(type='removed_objfalse_related_ipr').first()
        self.assertIn(ipr.title, removed_objfalse_docevent.desc,
                      'IprDisclosure title does not appear in DocEvent desc when removed as objectively false')

    def test_no_revisions_message(self):
        draft = WgDraftFactory(rev="02")
        now = timezone.now()
        for rev in range(0,3):
            NewRevisionDocEventFactory(doc=draft, rev=f"{rev:02d}", time=now-datetime.timedelta(days=30*(2-rev)))
        
        # Disclosure has non-empty revisions field on its related draft
        iprdocrel = IprDocRelFactory(document=draft)
        IprEventFactory(type_id="posted",time=now,disclosure=iprdocrel.disclosure)
        self.assertEqual(
            no_revisions_message(iprdocrel),
            ""
        )

        # Disclosure has more than one revision, none called out, disclosure after submissions
        iprdocrel = IprDocRelFactory(document=draft, revisions="")
        IprEventFactory(type_id="posted",time=now,disclosure=iprdocrel.disclosure)
        self.assertEqual(
            no_revisions_message(iprdocrel),
            "No revisions for this Internet-Draft were specified in this disclosure. The Internet-Draft's revision was 02 at the time this disclosure was posted. Contact the discloser or patent holder if there are questions about which revisions this disclosure pertains to."
        )

        # Disclosure has more than one revision, none called out, disclosure after 01
        iprdocrel = IprDocRelFactory(document=draft, revisions="")
        e = IprEventFactory(type_id="posted",disclosure=iprdocrel.disclosure)
        e.time = now-datetime.timedelta(days=15)
        e.save()
        self.assertEqual(
            no_revisions_message(iprdocrel),
            "No revisions for this Internet-Draft were specified in this disclosure. The Internet-Draft's revision was 01 at the time this disclosure was posted. Contact the discloser or patent holder if there are questions about which revisions this disclosure pertains to."
        )

        # Disclosure has more than one revision, none called out, disclosure was before the 00
        iprdocrel = IprDocRelFactory(document=draft, revisions="")
        e = IprEventFactory(type_id="posted",disclosure=iprdocrel.disclosure)
        e.time = now-datetime.timedelta(days=180)
        e.save()
        self.assertEqual(
            no_revisions_message(iprdocrel),
            "No revisions for this Internet-Draft were specified in this disclosure. The Internet-Draft's initial submission was after this disclosure was posted. Contact the discloser or patent holder if there are questions about which revisions this disclosure pertains to."
        )

        # disclosed draft has no NewRevisionDocEvents
        draft = WgDraftFactory(rev="20")
        draft.docevent_set.all().delete()
        iprdocrel = IprDocRelFactory(document=draft, revisions="")
        IprEventFactory(type_id="posted",disclosure=iprdocrel.disclosure)
        self.assertEqual(
            no_revisions_message(iprdocrel),
            "No revisions for this Internet-Draft were specified in this disclosure. The Internet-Draft's revision at the time this disclosure was posted could not be determined. Contact the discloser or patent holder if there are questions about which revisions this disclosure pertains to."
        )

        # disclosed draft has only one revision
        draft = WgDraftFactory(rev="00")
        iprdocrel = IprDocRelFactory(document=draft, revisions="")
        IprEventFactory(type_id="posted",disclosure=iprdocrel.disclosure)
        self.assertEqual(
            no_revisions_message(iprdocrel),
            "No revisions for this Internet-Draft were specified in this disclosure. However, there is only one revision of this Internet-Draft."
        )


class DraftFormTests(TestCase):
    def setUp(self):
        super().setUp()
        self.disclosure = IprDisclosureBaseFactory()
        self.draft = WgDraftFactory.create_batch(10)[-1]
        self.rfc = RfcFactory()

    def test_revisions_valid(self):
        post_data = {
            # n.b., "document" is a SearchableDocumentField, which is a multiple choice field limited
            # to a single choice. Its value must be an array of pks with one element.
            "document": [str(self.draft.pk)],
            "disclosure": str(self.disclosure.pk),
        }
        # The revisions field is just a char field that allows descriptions of the applicable
        # document revisions. It's usually just a rev or "00-02", but the form allows anything
        # not empty. The secretariat will review the value before the disclosure is posted so
        # minimal validation is ok here.
        self.assertTrue(DraftForm(post_data | {"revisions": "00"}).is_valid())
        self.assertTrue(DraftForm(post_data | {"revisions": "00-02"}).is_valid())
        self.assertTrue(DraftForm(post_data | {"revisions": "01,03, 05"}).is_valid())
        self.assertTrue(DraftForm(post_data | {"revisions": "all but 01"}).is_valid())
        # RFC instead of draft - allow empty / missing revisions
        post_data["document"] = [str(self.rfc.pk)]
        self.assertTrue(DraftForm(post_data).is_valid())
        self.assertTrue(DraftForm(post_data | {"revisions": ""}).is_valid())

    def test_revisions_invalid(self):
        missing_rev_error_msg = (
            "Revisions of this Internet-Draft for which this disclosure is relevant must be specified."
        )
        null_char_error_msg = "Null characters are not allowed."
        
        post_data = {
            # n.b., "document" is a SearchableDocumentField, which is a multiple choice field limited
            # to a single choice. Its value must be an array of pks with one element.
            "document": [str(self.draft.pk)],
            "disclosure": str(self.disclosure.pk),
        }
        self.assertFormError(
            DraftForm(post_data), "revisions", missing_rev_error_msg
        )
        self.assertFormError(
            DraftForm(post_data | {"revisions": ""}), "revisions", missing_rev_error_msg
        )
        self.assertFormError(
            DraftForm(post_data | {"revisions": "1\x00"}),
            "revisions",
            [null_char_error_msg, missing_rev_error_msg],
        )
        # RFC instead of draft still validates the revisions field
        self.assertFormError(
            DraftForm(post_data | {"document": [str(self.rfc.pk)], "revisions": "1\x00"}),
            "revisions",
            null_char_error_msg,
        )


class HolderIprDisclosureFormTests(TestCase):
    def setUp(self):
        super().setUp()
        # Checkboxes that are False are left out of the Form data, not sent back at all. These are
        # commented out - if they were checked, their value would be "on".
        self.data = {
            "holder_legal_name": "Test Legal",
            "holder_contact_name": "Test Holder",
            "holder_contact_email": "test@holder.com",
            "holder_contact_info": "555-555-0100",
            "ietfer_name": "Test Participant",
            "ietfer_contact_info": "555-555-0101",
            "iprdocrel_set-TOTAL_FORMS": 2,
            "iprdocrel_set-INITIAL_FORMS": 0,
            "iprdocrel_set-0-document": "1234",  # fake id - validates but won't save()
            "iprdocrel_set-0-revisions": '00',
            "iprdocrel_set-1-document": "4567",  # fake id - validates but won't save()
            # "is_blanket_disclosure": "on", 
            "patent_number": "SE12345678901",
            "patent_inventor": "A. Nonymous",
            "patent_title": "A method of transferring bits",
            "patent_date": "2000-01-01",
            # "has_patent_pending": "on",
            "licensing": "reasonable",
            "submitter_name": "Test Holder",
            "submitter_email": "test@holder.com",
        }
        
    def test_blanket_disclosure_licensing_restrictions(self):
        """when is_blanket_disclosure is True only royalty-free licensing is valid
        
        Most of the form functionality is tested via the views in IprTests above. More thorough testing
        of validation ought to move here so we don't have to exercise the whole Django plumbing repeatedly.
        """       
        self.assertTrue(HolderIprDisclosureForm(data=self.data).is_valid())       
        self.data["is_blanket_disclosure"] = "on"
        self.assertFalse(HolderIprDisclosureForm(data=self.data).is_valid())       
        self.data["licensing"] = "royalty-free"
        self.assertTrue(HolderIprDisclosureForm(data=self.data).is_valid())       

    def test_patent_details_required_unless_blanket(self):
        self.assertTrue(HolderIprDisclosureForm(data=self.data).is_valid())
        patent_fields = ["patent_number", "patent_inventor", "patent_title", "patent_date"]
        # any of the fields being missing should invalidate the form
        for pf in patent_fields:
            val = self.data.pop(pf)
            self.assertFalse(HolderIprDisclosureForm(data=self.data).is_valid())
            self.data[pf] = val

        # should be optional if is_blanket_disclosure is True
        self.data["is_blanket_disclosure"] = "on"
        self.data["licensing"] = "royalty-free"  # also needed for a blanket disclosure
        for pf in patent_fields:
            val = self.data.pop(pf)
            self.assertTrue(HolderIprDisclosureForm(data=self.data).is_valid())
            self.data[pf] = val
