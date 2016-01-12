import datetime
import urllib

from pyquery import PyQuery

from django.core.urlresolvers import reverse as urlreverse

import debug                            # pyflakes:ignore

from ietf.doc.models import DocAlias
from ietf.ipr.mail import (process_response_email, get_reply_to, get_update_submitter_emails,
    get_pseudo_submitter, get_holders, get_update_cc_addrs)
from ietf.ipr.models import (IprDisclosureBase,GenericIprDisclosure,HolderIprDisclosure,
    ThirdPartyIprDisclosure,RelatedIpr)
from ietf.ipr.utils import get_genitive, get_ipr_summary
from ietf.message.models import Message
from ietf.utils.test_utils import TestCase, login_testing_unauthorized, unicontent
from ietf.utils.test_data import make_test_data
from ietf.utils.mail import outbox, empty_outbox
from ietf.mailtrigger.utils import gather_address_lists


class IprTests(TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass
    
    def test_get_genitive(self):
        self.assertEqual(get_genitive("Cisco"),"Cisco's")
        self.assertEqual(get_genitive("Ross"),"Ross'")
        
    def test_get_holders(self):
        make_test_data()
        ipr = IprDisclosureBase.objects.get(title='Statement regarding rights')
        update = HolderIprDisclosure.objects.create(
            by_id=1,
            title="Statement regarding rights Update",
            holder_legal_name="Native Martians United",
            state_id='pending',
            patent_info='US12345',
            holder_contact_name='Update Holder',
            holder_contact_email='update_holder@acme.com',
            licensing_id='royalty-free',
            submitter_name='George',
            submitter_email='george@acme.com',
        )
        RelatedIpr.objects.create(target=ipr,source=update,relationship_id='updates')
        result = get_holders(update)
        self.assertEqual(result,['update_holder@acme.com','george@acme.com'])
        
    def test_get_ipr_summary(self):
        make_test_data()
        ipr = IprDisclosureBase.objects.get(title='Statement regarding rights')
        self.assertEqual(get_ipr_summary(ipr),'draft-ietf-mars-test')
        
    def test_get_pseudo_submitter(self):
        make_test_data()
        ipr = IprDisclosureBase.objects.get(title='Statement regarding rights').get_child()
        self.assertEqual(get_pseudo_submitter(ipr),(ipr.submitter_name,ipr.submitter_email))
        ipr.submitter_name=''
        ipr.submitter_email=''
        self.assertEqual(get_pseudo_submitter(ipr),(ipr.holder_contact_name,ipr.holder_contact_email))
        ipr.holder_contact_name=''
        ipr.holder_contact_email=''
        self.assertEqual(get_pseudo_submitter(ipr),('UNKNOWN NAME - NEED ASSISTANCE HERE','UNKNOWN EMAIL - NEED ASSISTANCE HERE'))

    def test_get_update_cc_addrs(self):
        make_test_data()
        ipr = IprDisclosureBase.objects.get(title='Statement regarding rights')
        update = HolderIprDisclosure.objects.create(
            by_id=1,
            title="Statement regarding rights Update",
            holder_legal_name="Native Martians United",
            state_id='pending',
            patent_info='US12345',
            holder_contact_name='Update Holder',
            holder_contact_email='update_holder@acme.com',
            licensing_id='royalty-free',
            submitter_name='George',
            submitter_email='george@acme.com',
        )
        RelatedIpr.objects.create(target=ipr,source=update,relationship_id='updates')
        result = get_update_cc_addrs(update)
        self.assertEqual(result,'update_holder@acme.com,george@acme.com')
        
    def test_get_update_submitter_emails(self):
        make_test_data()
        ipr = IprDisclosureBase.objects.get(title='Statement regarding rights').get_child()
        update = HolderIprDisclosure.objects.create(
            by_id=1,
            title="Statement regarding rights Update",
            holder_legal_name="Native Martians United",
            state_id='pending',
            patent_info='US12345',
            holder_contact_name='George',
            holder_contact_email='george@acme.com',
            licensing_id='royalty-free',
            submitter_name='George',
            submitter_email='george@acme.com',
        )
        RelatedIpr.objects.create(target=ipr,source=update,relationship_id='updates')
        messages = get_update_submitter_emails(update)
        self.assertEqual(len(messages),1)
        self.assertTrue(messages[0].startswith('To: george@acme.com'))
        
    def test_showlist(self):
        make_test_data()
        ipr = IprDisclosureBase.objects.get(title='Statement regarding rights')
        r = self.client.get(urlreverse("ipr_showlist"))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(ipr.title in unicontent(r))

    def test_show_posted(self):
        make_test_data()
        ipr = IprDisclosureBase.objects.get(title='Statement regarding rights')
        r = self.client.get(urlreverse("ipr_show", kwargs=dict(id=ipr.pk)))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(ipr.title in unicontent(r))
        
    def test_show_parked(self):
        make_test_data()
        ipr = IprDisclosureBase.objects.get(title='Statement regarding rights')
        ipr.set_state('parked')
        r = self.client.get(urlreverse("ipr_show", kwargs=dict(id=ipr.pk)))
        self.assertEqual(r.status_code, 404)

    def test_show_pending(self):
        make_test_data()
        ipr = IprDisclosureBase.objects.get(title='Statement regarding rights')
        ipr.set_state('pending')
        r = self.client.get(urlreverse("ipr_show", kwargs=dict(id=ipr.pk)))
        self.assertEqual(r.status_code, 404)
        
    def test_show_rejected(self):
        make_test_data()
        ipr = IprDisclosureBase.objects.get(title='Statement regarding rights')
        ipr.set_state('rejected')
        r = self.client.get(urlreverse("ipr_show", kwargs=dict(id=ipr.pk)))
        self.assertEqual(r.status_code, 404)
        
    def test_show_removed(self):
        make_test_data()
        ipr = IprDisclosureBase.objects.get(title='Statement regarding rights')
        ipr.set_state('removed')
        r = self.client.get(urlreverse("ipr_show", kwargs=dict(id=ipr.pk)))
        self.assertEqual(r.status_code, 200)
        self.assertTrue('This IPR disclosure was removed' in unicontent(r))
        
    def test_iprs_for_drafts(self):
        draft = make_test_data()
        ipr = IprDisclosureBase.objects.get(title='Statement regarding rights')
        r = self.client.get(urlreverse("ietf.ipr.views.by_draft_txt"))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(draft.name in unicontent(r))
        self.assertTrue(str(ipr.pk) in unicontent(r))

    def test_iprs_for_drafts_recursive(self):
        draft = make_test_data()
        replaced = draft.all_related_that_doc(['replaces'])
        ipr = IprDisclosureBase.objects.get(title='Statement regarding rights')
        r = self.client.get(urlreverse("ietf.ipr.views.by_draft_recursive_txt"))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(draft.name in unicontent(r))
        for alias in replaced:
            self.assertTrue(alias.name in unicontent(r))
        self.assertTrue(str(ipr.pk) in unicontent(r))

    def test_about(self):
        r = self.client.get(urlreverse("ietf.ipr.views.about"))
        self.assertEqual(r.status_code, 200)
        self.assertTrue("File a disclosure" in unicontent(r))

    def test_search(self):
        draft = make_test_data()
        ipr = IprDisclosureBase.objects.get(title="Statement regarding rights").get_child()

        url = urlreverse("ipr_search")

        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(q("form input[name=draft]"))

        # find by id
        r = self.client.get(url + "?submit=draft&id=%s" % draft.name)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(ipr.title in unicontent(r))

        # find draft
        r = self.client.get(url + "?submit=draft&draft=%s" % draft.name)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(ipr.title in unicontent(r))

        # search + select document
        r = self.client.get(url + "?submit=draft&draft=draft")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(draft.name in unicontent(r))
        self.assertTrue(ipr.title not in unicontent(r))

        DocAlias.objects.create(name="rfc321", document=draft)

        # find RFC
        r = self.client.get(url + "?submit=rfc&rfc=321")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(ipr.title in unicontent(r))

        # find by patent owner
        r = self.client.get(url + "?submit=holder&holder=%s" % ipr.holder_legal_name)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(ipr.title in unicontent(r))
        
        # find by patent info
        r = self.client.get(url + "?submit=patent&patent=%s" % ipr.patent_info)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(ipr.title in unicontent(r))

        r = self.client.get(url + "?submit=patent&patent=US12345")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(ipr.title in unicontent(r))

        # find by group acronym
        r = self.client.get(url + "?submit=group&group=%s" % draft.group.pk)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(ipr.title in unicontent(r))

        # find by doc title
        r = self.client.get(url + "?submit=doctitle&doctitle=%s" % urllib.quote(draft.title))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(ipr.title in unicontent(r))

        # find by ipr title
        r = self.client.get(url + "?submit=iprtitle&iprtitle=%s" % urllib.quote(ipr.title))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(ipr.title in unicontent(r))

    def test_feed(self):
        make_test_data()
        ipr = IprDisclosureBase.objects.get(title='Statement regarding rights')
        r = self.client.get("/feed/ipr/")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(ipr.title in unicontent(r))

    def test_sitemap(self):
        make_test_data()
        ipr = IprDisclosureBase.objects.get(title='Statement regarding rights')
        r = self.client.get("/sitemap-ipr.xml")
        self.assertEqual(r.status_code, 200)
        self.assertTrue("/ipr/%s/" % ipr.pk in unicontent(r))

    def test_new_generic(self):
        """Add a new generic disclosure.  Note: submitter does not need to be logged in.
        """
        make_test_data()
        url = urlreverse("ietf.ipr.views.new", kwargs={ "type": "generic" })

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
        self.assertEqual(r.status_code, 200)
        self.assertTrue("Your IPR disclosure has been submitted" in unicontent(r))
        self.assertEqual(len(outbox),1)
        self.assertTrue('New IPR Submission' in outbox[0]['Subject'])
        self.assertTrue('ietf-ipr@' in outbox[0]['To'])

        iprs = IprDisclosureBase.objects.filter(title__icontains="General License Statement")
        self.assertEqual(len(iprs), 1)
        ipr = iprs[0]
        self.assertEqual(ipr.holder_legal_name, "Test Legal")
        self.assertEqual(ipr.state.slug, 'pending')
        self.assertTrue(isinstance(ipr.get_child(),GenericIprDisclosure))

    def test_new_specific(self):
        """Add a new specific disclosure.  Note: submitter does not need to be logged in.
        """
        draft = make_test_data()
        url = urlreverse("ietf.ipr.views.new", kwargs={ "type": "specific" })

        # successful post
        empty_outbox()
        r = self.client.post(url, {
            "holder_legal_name": "Test Legal",
            "holder_contact_name": "Test Holder",
            "holder_contact_email": "test@holder.com",
            "holder_contact_info": "555-555-0100",
            "ietfer_name": "Test Participant",
            "ietfer_contact_info": "555-555-0101",
            "iprdocrel_set-TOTAL_FORMS": 2,
            "iprdocrel_set-INITIAL_FORMS": 0,
            "iprdocrel_set-0-document": "%s" % draft.docalias_set.first().pk,
            "iprdocrel_set-0-revisions": '00',
            "iprdocrel_set-1-document": DocAlias.objects.filter(name__startswith="rfc").first().pk,
            "patent_info": "none",
            "has_patent_pending": False,
            "licensing": "royalty-free",
            "submitter_name": "Test Holder",
            "submitter_email": "test@holder.com",
            })
        self.assertEqual(r.status_code, 200)
        # print r.content
        self.assertTrue("Your IPR disclosure has been submitted" in unicontent(r))

        iprs = IprDisclosureBase.objects.filter(title__icontains=draft.name)
        self.assertEqual(len(iprs), 1)
        ipr = iprs[0]
        self.assertEqual(ipr.holder_legal_name, "Test Legal")
        self.assertEqual(ipr.state.slug, 'pending')
        self.assertTrue(isinstance(ipr.get_child(),HolderIprDisclosure))
        self.assertEqual(len(outbox),1)
        self.assertTrue('New IPR Submission' in outbox[0]['Subject'])
        self.assertTrue('ietf-ipr@' in outbox[0]['To'])

    def test_new_thirdparty(self):
        """Add a new third-party disclosure.  Note: submitter does not need to be logged in.
        """
        draft = make_test_data()
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
            "iprdocrel_set-0-document": "%s" % draft.docalias_set.first().pk,
            "iprdocrel_set-0-revisions": '00',
            "iprdocrel_set-1-document": DocAlias.objects.filter(name__startswith="rfc").first().pk,
            "patent_info": "none",
            "has_patent_pending": False,
            "licensing": "royalty-free",
            "submitter_name": "Test Holder",
            "submitter_email": "test@holder.com",
            })
        self.assertEqual(r.status_code, 200)
        self.assertTrue("Your IPR disclosure has been submitted" in unicontent(r))

        iprs = IprDisclosureBase.objects.filter(title__icontains="belonging to Test Legal")
        self.assertEqual(len(iprs), 1)
        ipr = iprs[0]
        self.assertEqual(ipr.holder_legal_name, "Test Legal")
        self.assertEqual(ipr.state.slug, "pending")
        self.assertTrue(isinstance(ipr.get_child(),ThirdPartyIprDisclosure))
        self.assertEqual(len(outbox),1)
        self.assertTrue('New IPR Submission' in outbox[0]['Subject'])
        self.assertTrue('ietf-ipr@' in outbox[0]['To'])

    def test_update(self):
        draft = make_test_data()
        original_ipr = IprDisclosureBase.objects.get(title='Statement regarding rights')
        url = urlreverse("ietf.ipr.views.new", kwargs={ "type": "specific" })

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
            "iprdocrel_set-0-document": "%s" % draft.docalias_set.first().pk,
            "iprdocrel_set-0-revisions": '00',
            "iprdocrel_set-1-document": DocAlias.objects.filter(name__startswith="rfc").first().pk,
            "patent_info": "none",
            "has_patent_pending": False,
            "licensing": "royalty-free",
            "submitter_name": "Test Holder",
            "submitter_email": "test@holder.com",
            })
        self.assertEqual(r.status_code, 200)
        self.assertTrue("Your IPR disclosure has been submitted" in unicontent(r))

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
        draft = make_test_data()
        url = urlreverse("ietf.ipr.views.new", kwargs={ "type": "specific" })

        # successful post
        empty_outbox()
        r = self.client.post(url, {
            "updates": "this is supposed to be an integer",
            "holder_legal_name": "Test Legal",
            "holder_contact_name": "Test Holder",
            "holder_contact_email": "test@holder.com",
            "iprdocrel_set-TOTAL_FORMS": 1,
            "iprdocrel_set-INITIAL_FORMS": 0,
            "iprdocrel_set-0-document": "%s" % draft.docalias_set.first().pk,
            "iprdocrel_set-0-revisions": '00',
            "patent_info": "none",
            "has_patent_pending": False,
            "licensing": "royalty-free",
            "submitter_name": "Test Holder",
            "submitter_email": "test@holder.com",
            })
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(q("#id_updates").parents(".form-group").hasClass("has-error"))

    def test_addcomment(self):
        make_test_data()
        ipr = IprDisclosureBase.objects.get(title='Statement regarding rights')
        url = urlreverse("ipr_add_comment", kwargs={ "id": ipr.id })
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
        self.assertEqual(r.status_code,200)
        self.assertTrue('Private comment' in unicontent(r))
        self.client.logout()
        r = self.client.get(url)
        self.assertFalse('Private comment' in unicontent(r))
        
    def test_addemail(self):
        make_test_data()
        ipr = IprDisclosureBase.objects.get(title='Statement regarding rights')
        url = urlreverse("ipr_add_email", kwargs={ "id": ipr.id })
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
        make_test_data()
        url = urlreverse("ipr_admin",kwargs={'state':'pending'})
        self.client.login(username="secretary", password="secretary+password")
                
        # test for presence of pending ipr
        ipr = IprDisclosureBase.objects.first()
        ipr.state_id = 'pending'
        ipr.save()
        num = IprDisclosureBase.objects.filter(state='pending').count()
        
        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        q = PyQuery(r.content)
        x = len(q('table.ipr-table tbody tr'))
        self.assertEqual(num,x)
        
    def test_admin_removed(self):
        make_test_data()
        url = urlreverse("ipr_admin",kwargs={'state':'removed'})
        self.client.login(username="secretary", password="secretary+password")
        
        # test for presence of pending ipr
        ipr = IprDisclosureBase.objects.first()
        ipr.state_id = 'removed'
        ipr.save()
        num = IprDisclosureBase.objects.filter(state__in=('removed','rejected')).count()
        
        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        q = PyQuery(r.content)
        x = len(q('table.ipr-table tbody tr'))
        self.assertEqual(num,x)
        
    def test_admin_parked(self):
        pass
    
    def test_post(self):
        make_test_data()
        ipr = IprDisclosureBase.objects.get(title='Statement regarding rights')
        url = urlreverse("ipr_post", kwargs={ "id": ipr.id })
        login_testing_unauthorized(self, "secretary", url)

        r = self.client.get(url,follow=True)
        self.assertEqual(r.status_code,200)
        len_before = len(outbox)
        # successful post
        self.client.login(username="secretary", password="secretary+password")
        r = self.client.get(url,follow=True)
        self.assertEqual(r.status_code,200)
        ipr = IprDisclosureBase.objects.get(title='Statement regarding rights')
        self.assertEqual(ipr.state.slug,'posted')
        url = urlreverse('ipr_notify',kwargs={ 'id':ipr.id, 'type':'posted'})
        r = self.client.get(url,follow=True)
        q = PyQuery(r.content)
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
        r = self.client.post(url, data )
        self.assertEqual(r.status_code,302)
        self.assertEqual(len(outbox),len_before+2)
        self.assertTrue('george@acme.com' in outbox[len_before]['To'])
        self.assertTrue('draft-ietf-mars-test@ietf.org' in outbox[len_before+1]['To'])
        self.assertTrue('mars-wg@ietf.org' in outbox[len_before+1]['Cc'])

    def test_process_response_email(self):
        # first send a mail
        make_test_data()
        ipr = IprDisclosureBase.objects.get(title='Statement regarding rights')
        url = urlreverse("ipr_email",kwargs={ "id": ipr.id })
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
        
        # test process response uninteresting message
        addrs = gather_address_lists('ipr_disclosure_submitted').as_strings()
        message_string = """To: {}
Cc: {}
From: joe@test.com
Date: {}
Subject: test
""".format(addrs.to, addrs.cc, datetime.datetime.now().ctime())
        result = process_response_email(message_string)
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
