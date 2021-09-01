# Copyright The IETF Trust 2009-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import datetime


from pyquery import PyQuery
from urllib.parse import quote, urlparse

from django.urls import reverse as urlreverse

import debug                            # pyflakes:ignore

from ietf.doc.models import DocAlias
from ietf.doc.factories import DocumentFactory, WgDraftFactory, IndividualDraftFactory, WgRfcFactory
from ietf.group.factories import RoleFactory
from ietf.ipr.factories import HolderIprDisclosureFactory, GenericIprDisclosureFactory, IprEventFactory
from ietf.ipr.mail import (process_response_email, get_reply_to, get_update_submitter_emails,
    get_pseudo_submitter, get_holders, get_update_cc_addrs)
from ietf.ipr.models import (IprDisclosureBase,GenericIprDisclosure,HolderIprDisclosure,
    ThirdPartyIprDisclosure)
from ietf.ipr.utils import get_genitive, get_ipr_summary
from ietf.mailtrigger.utils import gather_address_lists
from ietf.message.models import Message
from ietf.utils.mail import outbox, empty_outbox, get_payload_text
from ietf.utils.test_utils import TestCase, login_testing_unauthorized
from ietf.utils.text import text_to_dict


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
    def setUp(self):
        pass

    def tearDown(self):
        pass
    
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

    def test_iprs_for_drafts_recursive(self):
        draft = WgDraftFactory(relations=[('replaces', IndividualDraftFactory())])
        ipr = HolderIprDisclosureFactory(docs=[draft,])
        replaced = draft.all_related_that_doc('replaces')
        r = self.client.get(urlreverse("ietf.ipr.views.by_draft_recursive_txt"))
        self.assertContains(r, draft.name)
        for alias in replaced:
            self.assertContains(r, alias.name)
        self.assertContains(r, str(ipr.pk))

    def test_about(self):
        r = self.client.get(urlreverse("ietf.ipr.views.about"))
        self.assertContains(r, "File a disclosure")

    def test_search(self):
        WgDraftFactory() # The test matching the prefix "draft" needs more than one thing to find
        draft = WgDraftFactory()
        ipr = HolderIprDisclosureFactory(docs=[draft,],patent_info='Number: US12345\nTitle: A method of transfering bits\nInventor: A. Nonymous\nDate: 2000-01-01')

        url = urlreverse("ietf.ipr.views.search")

        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(q("form input[name=draft]"))

        # find by id
        r = self.client.get(url + "?submit=draft&id=%s" % draft.name)
        self.assertContains(r, ipr.title)

        # find draft
        r = self.client.get(url + "?submit=draft&draft=%s" % draft.name)
        self.assertContains(r, ipr.title)

        # search + select document
        r = self.client.get(url + "?submit=draft&draft=draft")
        self.assertContains(r, draft.name)
        self.assertNotContains(r, ipr.title)

        DocAlias.objects.create(name="rfc321").docs.add(draft)

        # find RFC
        r = self.client.get(url + "?submit=rfc&rfc=321")
        self.assertContains(r, ipr.title)

        # find by patent owner
        r = self.client.get(url + "?submit=holder&holder=%s" % ipr.holder_legal_name)
        self.assertContains(r, ipr.title)
        
        # find by patent infoj
        r = self.client.get(url + "?submit=patent&patent=%s" % quote(ipr.patent_info))
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
        url = urlreverse("ietf.ipr.views.new", kwargs={ "type": "generic" })
        r = self.client.get(url)
        self.assertEqual(r.status_code,302)
        self.assertEqual(urlparse(r["Location"]).path, urlreverse("ietf.ipr.views.new", kwargs={ "type": "general"}))


    def test_new_general(self):
        """Add a new general disclosure.  Note: submitter does not need to be logged in.
        """
        url = urlreverse("ietf.ipr.views.new", kwargs={ "type": "general" })

        # invalid post
        r = self.client.post(url, {
            "holder_legal_name": "Test Legal",
            })
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(len(q("form .has-error")) > 0)

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
        WgRfcFactory()
        url = urlreverse("ietf.ipr.views.new", kwargs={ "type": "specific" })

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
            "iprdocrel_set-0-document": "%s" % draft.docalias.first().pk,
            "iprdocrel_set-0-revisions": '00',
            "iprdocrel_set-1-document": DocAlias.objects.filter(name__startswith="rfc").first().pk,
            "patent_number": "SE12345678901",
            "patent_inventor": "A. Nonymous",
            "patent_title": "A method of transfering bits",
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
        for item in ['SE12345678901','A method of transfering bits','2000-01-01']:
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

    def test_new_thirdparty(self):
        """Add a new third-party disclosure.  Note: submitter does not need to be logged in.
        """
        draft = WgDraftFactory()
        WgRfcFactory()
        url = urlreverse("ietf.ipr.views.new", kwargs={ "type": "third-party" })

        # successful post
        empty_outbox()
        r = self.client.post(url, {
            "holder_legal_name": "Test Legal",
            "ietfer_name": "Test Participant",
            "ietfer_contact_email": "test@ietfer.com",
            "ietfer_contact_info": "555-555-0101",
            "iprdocrel_set-TOTAL_FORMS": 2,
            "iprdocrel_set-INITIAL_FORMS": 0,
            "iprdocrel_set-0-document": "%s" % draft.docalias.first().pk,
            "iprdocrel_set-0-revisions": '00',
            "iprdocrel_set-1-document": DocAlias.objects.filter(name__startswith="rfc").first().pk,
            "patent_number": "SE12345678901",
            "patent_inventor": "A. Nonymous",
            "patent_title": "A method of transfering bits",
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
        for item in ['SE12345678901','A method of transfering bits','2000-01-01' ]:
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

        #url = urlreverse("ietf.ipr.views.new", kwargs={ "type": "specific" })
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
            "iprdocrel_set-0-document": "%s" % draft.docalias.first().pk,
            "iprdocrel_set-0-revisions": '00',
            "iprdocrel_set-INITIAL_FORMS": 0,
            "iprdocrel_set-TOTAL_FORMS": 1,
            "licensing": "royalty-free",
            "patent_date": "2000-01-01",
            "patent_inventor": "A. Nonymous",
            "patent_number": "SE12345678901",
            "patent_title": "A method of transfering bits",
            "submitter_email": "test@holder.com",
            "submitter_name": "Test Holder",
            "updates": "",
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
        WgRfcFactory()
        original_ipr = HolderIprDisclosureFactory(docs=[draft,])

        # get
        url = urlreverse("ietf.ipr.views.update", kwargs={ "id": original_ipr.id })
        r = self.client.get(url)
        self.assertContains(r, original_ipr.title)

        #url = urlreverse("ietf.ipr.views.new", kwargs={ "type": "specific" })
        # successful post
        empty_outbox()
        r = self.client.post(url, {
            "updates": str(original_ipr.pk),
            "holder_legal_name": "Test Legal",
            "holder_contact_name": "Test Holder",
            "holder_contact_email": "test@holder.com",
            "holder_contact_info": "555-555-0100",
            "ietfer_name": "Test Participant",
            "ietfer_contact_info": "555-555-0101",
            "iprdocrel_set-TOTAL_FORMS": 2,
            "iprdocrel_set-INITIAL_FORMS": 0,
            "iprdocrel_set-0-document": "%s" % draft.docalias.first().pk,
            "iprdocrel_set-0-revisions": '00',
            "iprdocrel_set-1-document": DocAlias.objects.filter(name__startswith="rfc").first().pk,
            "patent_number": "SE12345678901",
            "patent_inventor": "A. Nonymous",
            "patent_title": "A method of transfering bits",
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
        url = urlreverse("ietf.ipr.views.new", kwargs={ "type": "specific" })

        empty_outbox()
        r = self.client.post(url, {
            "updates": "this is supposed to be an integer",
            "holder_legal_name": "Test Legal",
            "holder_contact_name": "Test Holder",
            "holder_contact_email": "test@holder.com",
            "iprdocrel_set-TOTAL_FORMS": 1,
            "iprdocrel_set-INITIAL_FORMS": 0,
            "iprdocrel_set-0-document": "%s" % draft.docalias.first().pk,
            "iprdocrel_set-0-revisions": '00',
            "patent_number": "SE12345678901",
            "patent_inventor": "A. Nonymous",
            "patent_title": "A method of transfering bits",
            "patent_date": "2000-01-01",
            "has_patent_pending": False,
            "licensing": "royalty-free",
            "submitter_name": "Test Holder",
            "submitter_email": "test@holder.com",
            })
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(q("#id_updates").parents(".form-group").hasClass("has-error"))

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
        num = IprDisclosureBase.objects.filter(state__in=('removed','rejected')).count()
        
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
        self.assertIn('posted on '+datetime.date.today().strftime("%Y-%m-%d"), get_payload_text(outbox[len_before]).replace('\n',' '))
        self.assertTrue('draft-ietf-mars-test@ietf.org' in outbox[len_before+1]['To'])
        self.assertTrue('mars-wg@ietf.org' in outbox[len_before+1]['Cc'])
        self.assertIn('Secretariat on '+ipr.get_latest_event_submitted().time.strftime("%Y-%m-%d"), get_payload_text(outbox[len_before+1]).replace('\n',' '))

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
        self.assertIn('Secretariat on '+ipr.get_latest_event_submitted().time.strftime("%Y-%m-%d"), get_payload_text(outbox[1]).replace('\n',' '))

    def test_process_response_email(self):
        # first send a mail
        ipr = HolderIprDisclosureFactory()
        url = urlreverse('ietf.ipr.views.email',kwargs={ "id": ipr.id })
        self.client.login(username="secretary", password="secretary+password")
        yesterday = datetime.date.today() - datetime.timedelta(1)
        data = dict(
            to='joe@test.com',
            frm='ietf-ipr@ietf.org',
            subject='test',
            reply_to=get_reply_to(),
            body='Testing.',
            response_due=yesterday.isoformat())
        empty_outbox()
        r = self.client.post(url,data,follow=True)
        #print r.content
        self.assertEqual(r.status_code,200)
        q = Message.objects.filter(reply_to=data['reply_to'])
        self.assertEqual(q.count(),1)
        event = q[0].msgevents.first()
        self.assertTrue(event.response_past_due())
        self.assertEqual(len(outbox), 1)
        self.assertTrue('joe@test.com' in outbox[0]['To'])
        
        # test process response uninteresting messages
        addrs = gather_address_lists('ipr_disclosure_submitted').as_strings()
        uninteresting_message_strings = [
            ("To: {to}\nCc: {cc}\nFrom: joe@test.com\nDate: {date}\nSubject: test\n"),
            ("Cc: {cc}\nFrom: joe@test.com\nDate: {date}\nSubject: test\n"),  # no To
            ("To: {to}\nFrom: joe@test.com\nDate: {date}\nSubject: test\n"),  # no Cc
            ("From: joe@test.com\nDate: {date}\nSubject: test\n"),  # no To or Cc
            ("Cc: {cc}\nDate: {date}\nSubject: test\n"),  # no To
            ("To: {to}\nDate: {date}\nSubject: test\n"),  # no Cc
            ("Date: {date}\nSubject: test\n"),  # no To or Cc
        ]
        for message_string in uninteresting_message_strings:
            result = process_response_email(
                message_string.format(
                    to=addrs.to,
                    cc=addrs.cc,
                    date=datetime.datetime.now().ctime()
                )
            )
            self.assertIsNone(result)
        
        # test process response
        message_string = """To: {}
From: joe@test.com
Date: {}
Subject: test
""".format(data['reply_to'],datetime.datetime.now().ctime())
        result = process_response_email(message_string)

        self.assertIsInstance(result,Message)
        self.assertFalse(event.response_past_due())

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
            'iprdocrel_set-INITIAL_FORMS' : 1,
            'iprdocrel_set-0-id': disclosure.pk,
            "iprdocrel_set-0-document": disclosure.docs.first().pk,
            "iprdocrel_set-0-revisions": disclosure.docs.first().document.rev,
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
        # A 'posted' IprEvent must create a corresponding DocEvent  
        IprEventFactory(type_id='posted', disclosure=ipr)
        self.assertEqual(1, doc.docevent_set.filter(type='posted_related_ipr').count(),
                         'Creating "posted" IprEvent did not create a "posted_related_ipr" DocEvent')
        self.assertEqual(0, doc.docevent_set.filter(type='removed_related_ipr').count(),
                         'Creating "posted" IprEvent created a "removed_related_ipr" DocEvent')
        # A 'removed' IprEvent must create a corresponding DocEvent
        IprEventFactory(type_id='removed', disclosure=ipr)
        self.assertEqual(1, doc.docevent_set.filter(type='posted_related_ipr').count(),
                         'Creating "removed" IprEvent created a "posted_related_ipr" DocEvent')
        self.assertEqual(1, doc.docevent_set.filter(type='removed_related_ipr').count(),
                         'Creating "removed" IprEvent did not create a "removed_related_ipr" DocEvent')
        # The DocEvent descriptions must refer to the IprEvents
        posted_docevent = doc.docevent_set.filter(type='posted_related_ipr').first()
        self.assertIn(ipr.title, posted_docevent.desc, 
                      'IprDisclosure title does not appear in DocEvent desc when posted')
        removed_docevent = doc.docevent_set.filter(type='removed_related_ipr').first()
        self.assertIn(ipr.title, removed_docevent.desc,
                      'IprDisclosure title does not appear in DocEvent desc when removed')
        