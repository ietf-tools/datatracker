# Copyright The IETF Trust 2013-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import io
import os

import debug    # pyflakes:ignore

from pyquery import PyQuery
from io import StringIO
from textwrap import wrap

from django.conf import settings
from django.urls import reverse as urlreverse

from ietf.doc.factories import ( DocumentFactory, IndividualRfcFactory,
    WgRfcFactory, DocEventFactory, WgDraftFactory )
from ietf.doc.models import ( Document, State, DocEvent,
    BallotPositionDocEvent, NewRevisionDocEvent, TelechatDocEvent, WriteupDocEvent )
from ietf.doc.utils import create_ballot_if_not_open
from ietf.doc.views_status_change import default_approval_text
from ietf.group.models import Person
from ietf.iesg.models import TelechatDate
from ietf.utils.test_utils import TestCase
from ietf.utils.mail import outbox, empty_outbox, get_payload_text
from ietf.utils.test_utils import login_testing_unauthorized


class StatusChangeTests(TestCase):
    def test_start_review(self):

        url = urlreverse('ietf.doc.views_status_change.start_rfc_status_change')
        login_testing_unauthorized(self, "secretary", url)

        # normal get should succeed and get a reasonable form
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('form select[name=create_in_state]')),1)

        ad_strpk = str(Person.objects.get(name='Areað Irector').pk)
        state_strpk = str(State.objects.get(slug='adrev',type__slug='statchg').pk)        

        # faulty posts

        ## Must set a name
        r = self.client.post(url,dict(document_name="",title="Bogus Title",ad=ad_strpk,create_in_state=state_strpk,notify='ipu@ietf.org'))
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(len(q('form .is-invalid')) > 0)

        ## Must not choose a document name that already exists
        r = self.client.post(url,dict(document_name="imaginary-mid-review",title="Bogus Title",ad=ad_strpk,create_in_state=state_strpk,notify='ipu@ietf.org'))
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(len(q('form .is-invalid')) > 0)

        ## Must set a title
        r = self.client.post(url,dict(document_name="bogus",title="",ad=ad_strpk,create_in_state=state_strpk,notify='ipu@ietf.org'))
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(len(q('form .is-invalid')) > 0)

        # successful status change starts

        r = self.client.post(url,dict(
            document_name="imaginary-new",title="A new imaginary status change",ad=ad_strpk,
            create_in_state=state_strpk,notify='ipu@ietf.org',new_relation_row_blah="rfc9999",
            statchg_relation_row_blah="tois")
        )
        self.assertEqual(r.status_code, 302)
        status_change = Document.objects.get(name='status-change-imaginary-new')        
        self.assertEqual(status_change.get_state('statchg').slug,'adrev')
        self.assertEqual(status_change.rev,'00')
        self.assertEqual(status_change.ad.name,'Areað Irector')
        self.assertEqual(status_change.notify,'ipu@ietf.org')
        self.assertTrue(status_change.relateddocument_set.filter(relationship__slug='tois',target__name='rfc9999'))

        # Verify that it's possible to start a status change without a responsible ad.
        r = self.client.post(url,dict(
            document_name="imaginary-new2",title="A new imaginary status change",
            create_in_state=state_strpk,notify='ipu@ietf.org',new_relation_row_blah="rfc9999",
            statchg_relation_row_blah="tois")
        )
        self.assertEqual(r.status_code, 302)
        status_change = Document.objects.get(name='status-change-imaginary-new2')
        self.assertIsNone(status_change.ad)        

        # Verify that the right thing happens if a control along the way uppercases RFC
        r = self.client.post(url,dict(
            document_name="imaginary-new3",title="A new imaginary status change",
            create_in_state=state_strpk,notify='ipu@ietf.org',new_relation_row_blah="RFC9999",
            statchg_relation_row_blah="tois")
        )
        self.assertEqual(r.status_code, 302)
        status_change = Document.objects.get(name='status-change-imaginary-new3')
        self.assertTrue(status_change.relateddocument_set.filter(relationship__slug='tois',target__name='rfc9999'))


    def test_change_state(self):

        doc = Document.objects.get(name='status-change-imaginary-mid-review')
        url = urlreverse('ietf.doc.views_status_change.change_state',kwargs=dict(name=doc.name))

        login_testing_unauthorized(self, "ad", url)

        # normal get 
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('form select[name=new_state]')),1)
        
        # faulty post
        r = self.client.post(url,dict(new_state=""))
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(len(q('form .is-invalid')) > 0)

        # successful change to AD Review
        adrev_pk = str(State.objects.get(slug='adrev',type__slug='statchg').pk)
        r = self.client.post(url,dict(new_state=adrev_pk,comment='RDNK84ZD'))
        self.assertEqual(r.status_code, 302)
        doc = Document.objects.get(name='status-change-imaginary-mid-review')
        self.assertEqual(doc.get_state('statchg').slug,'adrev')
        self.assertTrue(doc.latest_event(DocEvent,type="added_comment").desc.startswith('RDNK84ZD'))
        self.assertFalse(doc.active_ballot())

        # successful change to Last Call Requested
        messages_before = len(outbox)
        doc.ad = Person.objects.get(user__username='ad')
        doc.save_with_history([DocEvent.objects.create(doc=doc, rev=doc.rev, type="changed_document", by=Person.objects.get(user__username="secretary"), desc="Test")])
        lc_req_pk = str(State.objects.get(slug='lc-req',type__slug='statchg').pk)
        r = self.client.post(url,dict(new_state=lc_req_pk))
        self.assertEqual(r.status_code, 200)
        doc = Document.objects.get(name='status-change-imaginary-mid-review')
        self.assertEqual(doc.get_state('statchg').slug,'lc-req')
        self.assertEqual(len(outbox), messages_before + 1)
        self.assertTrue('Last Call:' in outbox[-1]['Subject'])

        # successful change to IESG Evaluation 
        iesgeval_pk = str(State.objects.get(slug='iesgeval',type__slug='statchg').pk)
        r = self.client.post(url,dict(new_state=iesgeval_pk,comment='TGmZtEjt'))
        self.assertEqual(r.status_code, 302)
        doc = Document.objects.get(name='status-change-imaginary-mid-review')
        self.assertEqual(doc.get_state('statchg').slug,'iesgeval')
        self.assertTrue(doc.latest_event(DocEvent,type="added_comment").desc.startswith('TGmZtEjt'))
        self.assertTrue(doc.active_ballot())
        self.assertEqual(doc.latest_event(BallotPositionDocEvent, type="changed_ballot_position").pos_id,'yes')

        # try to change to an AD-forbidden state
        appr_sent_pk = str(State.objects.get(used=True, slug='appr-sent',type__slug='statchg').pk)
        r = self.client.post(url, dict(new_state=appr_sent_pk, comment='xyzzy'))
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(q('form .invalid-feedback'))

        # try again as secretariat
        self.client.logout()
        login_testing_unauthorized(self, 'secretary', url)
        r = self.client.post(url, dict(new_state=appr_sent_pk, comment='xyzzy'))
        self.assertEqual(r.status_code, 302)
        doc = Document.objects.get(name='status-change-imaginary-mid-review')
        self.assertEqual(doc.get_state('statchg').slug, 'appr-sent')

    def test_edit_notices(self):
        doc = Document.objects.get(name='status-change-imaginary-mid-review')
        url = urlreverse('ietf.doc.views_doc.edit_notify;status-change',kwargs=dict(name=doc.name))

        login_testing_unauthorized(self, "ad", url)

        # normal get 
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('form textarea[name=notify]')), 1)
        self.assertEqual(doc.notify, q('form textarea[name=notify]')[0].value.strip())

        # change notice list
        newlist = '"Foo Bar" <foo@bar.baz.com>'
        r = self.client.post(url,dict(notify=newlist,save_addresses="1"))
        self.assertEqual(r.status_code,302)
        doc = Document.objects.get(name='status-change-imaginary-mid-review')
        self.assertEqual(doc.notify,newlist)
        self.assertTrue(doc.latest_event(DocEvent,type="added_comment").desc.startswith('Notification list changed'))       

        # Some additional setup so there's something to put in a generated notify list
        doc.relateddocument_set.create(target=Document.objects.get(name='rfc9999'),relationship_id='tois')
        doc.relateddocument_set.create(target=Document.objects.get(name='rfc9998'),relationship_id='tohist')

        # Ask the form to regenerate the list
        r = self.client.post(url,dict(regenerate_addresses="1"))
        self.assertEqual(r.status_code,200)
        doc = Document.objects.get(name='status-change-imaginary-mid-review')
        # Regenerate does not save!
        self.assertEqual(doc.notify,newlist)
        q = PyQuery(r.content)
        formlist = q('form textarea[name=notify]')[0].value.strip()
        self.assertEqual("", formlist)

    def test_edit_title(self):
        doc = Document.objects.get(name='status-change-imaginary-mid-review')
        url = urlreverse('ietf.doc.views_status_change.edit_title',kwargs=dict(name=doc.name))

        login_testing_unauthorized(self, "ad", url)

        # normal get 
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('input[name=title]')),1)

        # change title
        r = self.client.post(url,dict(title='New title'))
        self.assertEqual(r.status_code,302)
        doc = Document.objects.get(name='status-change-imaginary-mid-review')
        self.assertEqual(doc.title,'New title')
        self.assertTrue(doc.latest_event(DocEvent,type="added_comment").desc.startswith('Title changed'))       

    def test_edit_ad(self):
        doc = Document.objects.get(name='status-change-imaginary-mid-review')
        url = urlreverse('ietf.doc.views_status_change.edit_ad',kwargs=dict(name=doc.name))

        login_testing_unauthorized(self, "ad", url)

        # normal get 
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('select[name=ad]')),1)

        # change ads
        ad2 = Person.objects.get(name='Ad No2')
        r = self.client.post(url,dict(ad=str(ad2.pk)))
        self.assertEqual(r.status_code,302)
        doc = Document.objects.get(name='status-change-imaginary-mid-review')
        self.assertEqual(doc.ad,ad2)
        self.assertTrue(doc.latest_event(DocEvent,type="added_comment").desc.startswith('Shepherding AD changed'))       

    def test_edit_telechat_date(self):
        doc = Document.objects.get(name='status-change-imaginary-mid-review')
        url = urlreverse('ietf.doc.views_doc.telechat_date;status-change',kwargs=dict(name=doc.name))

        login_testing_unauthorized(self, "ad", url)

        # normal get 
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('select[name=telechat_date]')),1)

        # set a date
        self.assertFalse(doc.latest_event(TelechatDocEvent, "scheduled_for_telechat"))
        telechat_date = TelechatDate.objects.active().order_by('date')[0].date
        r = self.client.post(url,dict(telechat_date=telechat_date.isoformat()))
        self.assertEqual(r.status_code,302)
        doc = Document.objects.get(name='status-change-imaginary-mid-review')
        self.assertEqual(doc.latest_event(TelechatDocEvent, "scheduled_for_telechat").telechat_date,telechat_date)

        # move it forward a telechat (this should NOT set the returning item bit)
        telechat_date = TelechatDate.objects.active().order_by('date')[1].date
        r = self.client.post(url,dict(telechat_date=telechat_date.isoformat()))
        self.assertEqual(r.status_code,302)
        doc = Document.objects.get(name='status-change-imaginary-mid-review')
        self.assertFalse(doc.returning_item())

        # set the returning item bit without changing the date
        r = self.client.post(url,dict(telechat_date=telechat_date.isoformat(),returning_item="on"))
        self.assertEqual(r.status_code,302)
        doc = Document.objects.get(name='status-change-imaginary-mid-review')
        self.assertTrue(doc.returning_item())

        # clear the returning item bit
        r = self.client.post(url,dict(telechat_date=telechat_date.isoformat()))
        self.assertEqual(r.status_code,302)
        doc = Document.objects.get(name='status-change-imaginary-mid-review')
        self.assertFalse(doc.returning_item())

        # Take the doc back off any telechat
        r = self.client.post(url,dict(telechat_date=""))
        self.assertEqual(r.status_code, 302)
        doc = Document.objects.get(name='status-change-imaginary-mid-review')
        self.assertEqual(doc.latest_event(TelechatDocEvent, "scheduled_for_telechat").telechat_date,None)

    def test_edit_lc(self):
        doc = Document.objects.get(name='status-change-imaginary-mid-review')
        url = urlreverse('ietf.doc.views_status_change.last_call',kwargs=dict(name=doc.name))

        login_testing_unauthorized(self, "ad", url)

        # additional setup
        doc.relateddocument_set.create(target=Document.objects.get(name='rfc9999'),relationship_id='tois')
        doc.relateddocument_set.create(target=Document.objects.get(name='rfc9998'),relationship_id='tohist')
        doc.ad = Person.objects.get(name='Ad No2')
        doc.save_with_history([DocEvent.objects.create(doc=doc, rev=doc.rev, type="changed_document", by=Person.objects.get(user__username="secretary"), desc="Test")])
        
        # get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('form.edit-last-call-text')),1)

        self.assertContains(r,  'RFC9999 from Proposed Standard to Internet Standard')
        self.assertContains(r,  'RFC9998 from Informational to Historic')
        
        # save
        r = self.client.post(url,dict(last_call_text="Bogus last call text",save_last_call_text="1"))
        self.assertEqual(r.status_code, 200)

        last_call_event = doc.latest_event(WriteupDocEvent, type="changed_last_call_text")
        self.assertEqual(last_call_event.text,"Bogus last call text")

        # reset
        r = self.client.post(url,dict(regenerate_last_call_text="1"))
        self.assertEqual(r.status_code,200)
        self.assertContains(r,  'RFC9999 from Proposed Standard to Internet Standard')
        self.assertContains(r,  'RFC9998 from Informational to Historic')
        q = PyQuery(r.content)
        self.assertEqual(len(q("button[name='send_last_call_request']")), 1)

        # Make sure request LC isn't offered with no responsible AD.
        doc.ad = None
        doc.save_with_history([DocEventFactory(doc=doc)])
        r = self.client.get(url)
        self.assertEqual(r.status_code,200) 
        q = PyQuery(r.content)
        self.assertEqual(len(q("button[name='send_last_call_request']")), 0)
        doc.ad = Person.objects.get(name='Ad No2')
        doc.save_with_history([DocEventFactory(doc=doc)])

        # request last call
        messages_before = len(outbox)
        r = self.client.post(url,dict(last_call_text='stuff',send_last_call_request='Save+and+Request+Last+Call'))
        self.assertEqual(r.status_code,200)
        self.assertContains(r,  'Last call requested')
        self.assertEqual(len(outbox), messages_before + 1)
        self.assertTrue('Last Call:' in outbox[-1]['Subject'])
        self.assertTrue('Last Call Request has been submitted' in ''.join(wrap(outbox[-1].as_string(), width=2**16)))


    def test_approve(self):
        doc = Document.objects.get(name='status-change-imaginary-mid-review')
        url = urlreverse('ietf.doc.views_status_change.approve',kwargs=dict(name=doc.name))

        login_testing_unauthorized(self, "secretary", url)
        
        # Some additional setup
        doc.relateddocument_set.create(target=Document.objects.get(name='rfc9999'),relationship_id='tois')
        doc.relateddocument_set.create(target=Document.objects.get(name='rfc9998'),relationship_id='tohist')
        create_ballot_if_not_open(None, doc, Person.objects.get(user__username="secretary"), "statchg")
        doc.set_state(State.objects.get(slug='appr-pend',type='statchg'))

        # get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('[type=submit]:contains("Send announcement")')), 1)
        # There should be two messages to edit
        self.assertEqual(q('input#id_form-TOTAL_FORMS').val(),'2')
        self.assertContains(r,  '(rfc9999) to Internet Standard')
        self.assertContains(r,  '(rfc9998) to Historic')
        
        # submit
        messages_before = len(outbox)
        msg0=default_approval_text(doc,doc.relateddocument_set.all()[0])
        msg1=default_approval_text(doc,doc.relateddocument_set.all()[1])
        r = self.client.post(url,{'form-0-announcement_text':msg0,'form-1-announcement_text':msg1,'form-TOTAL_FORMS':'2','form-INITIAL_FORMS':'2','form-MAX_NUM_FORMS':''})
        self.assertEqual(r.status_code, 302)

        doc = Document.objects.get(name='status-change-imaginary-mid-review')
        self.assertEqual(doc.get_state_slug(),'appr-sent')
        self.assertFalse(doc.ballot_open("statchg"))
        
        self.assertEqual(len(outbox), messages_before + 2)
        self.assertTrue('Action:' in outbox[-1]['Subject'])
        self.assertTrue('ietf-announce' in outbox[-1]['To'])
        self.assertTrue('rfc-editor' in outbox[-1]['Cc'])
        self.assertTrue('(rfc9998) to Historic' in ''.join(wrap(outbox[-1].as_string()+outbox[-2].as_string(), 2**16)))
        self.assertTrue('(rfc9999) to Internet Standard' in ''.join(wrap(outbox[-1].as_string()+outbox[-2].as_string(),2**16)))

        self.assertTrue(doc.latest_event(DocEvent,type="added_comment").desc.startswith('The following approval message was sent'))

    def approval_pend_notice_test_helper(self, role):
        """Test notification email when review state changed to the appr-pend state"""
        doc = Document.objects.get(name='status-change-imaginary-mid-review')
        url = urlreverse('ietf.doc.views_status_change.change_state',kwargs=dict(name=doc.name))

        # Add some status change related documents
        doc.relateddocument_set.create(target=Document.objects.get(name='rfc9999'),relationship_id='tois')
        doc.relateddocument_set.create(target=Document.objects.get(name='rfc9998'),relationship_id='tohist')
        # And a non-status change related document
        doc.relateddocument_set.create(target=Document.objects.get(name='rfc14'),relationship_id='updates')

        login_testing_unauthorized(self, role, url)
        empty_outbox()

        # Issue the request
        appr_pend_pk = str(State.objects.get(used=True,
                                                 slug='appr-pend',
                                                 type__slug='statchg').pk)
        r = self.client.post(url,dict(new_state=appr_pend_pk,comment='some comment or other'))

        # Check the results
        self.assertEqual(r.status_code, 302)

        if role == 'ad':
            self.assertEqual(len(outbox), 1)
            notification = outbox[0]
            self.assertIn(doc.title, notification['Subject'])
            self.assertIn('iesg-secretary@ietf.org', notification['To'])
            self.assertTrue(notification['Subject'].startswith('Approved:'))
            notification_text = get_payload_text(notification)
            self.assertIn('The AD has approved changing the status', notification_text)
            self.assertIn(Document.objects.get(name='rfc9999').name, notification_text)
            self.assertIn(Document.objects.get(name='rfc9998').name, notification_text)
            self.assertNotIn(Document.objects.get(name='rfc14').name, notification_text)
            self.assertNotIn('No value found for', notification_text)  # make sure all interpolation values were set
        else:
            self.assertEqual(len(outbox), 0)

    def test_approval_pend_notice_ad(self):
        """Test that an approval notice is sent to secretariat when AD approves status change"""
        self.approval_pend_notice_test_helper('ad')

    def test_no_approval_pend_notice_secr(self):
        """Test that no approval notice is sent when secretariat approves status change"""
        self.approval_pend_notice_test_helper('secretariat')

    def test_edit_relations(self):
        doc = Document.objects.get(name='status-change-imaginary-mid-review')
        url = urlreverse('ietf.doc.views_status_change.edit_relations',kwargs=dict(name=doc.name))

        login_testing_unauthorized(self, "secretary", url)
        
        # Some additional setup
        doc.relateddocument_set.create(target=Document.objects.get(name='rfc9999'),relationship_id='tois')
        doc.relateddocument_set.create(target=Document.objects.get(name='rfc9998'),relationship_id='tohist')

        # get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('#content [type=submit]:contains("Save")')),1)
        # There should be three rows on the form
        self.assertEqual(len(q('#content .input-group')),3)

        # Try to add a relation to an RFC that doesn't exist
        r = self.client.post(url,dict(new_relation_row_blah="rfc9997",
                                      statchg_relation_row_blah="tois"))
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(len(q('form ul.errorlist')) > 0)

       # Try to add a relation leaving the relation type blank
        r = self.client.post(url,dict(new_relation_row_blah="rfc9999",
                                      statchg_relation_row_blah=""))
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(len(q('form ul.errorlist')) > 0)

       # Try to add a relation with an unknown relationship type
        r = self.client.post(url,dict(new_relation_row_blah="rfc9999",
                                      statchg_relation_row_blah="badslug"))
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(len(q('form ul.errorlist')) > 0)
        
        # Successful change of relations
        r = self.client.post(url,dict(new_relation_row_blah="rfc9999",
                                      statchg_relation_row_blah="toexp",
                                      new_relation_row_foo="rfc9998",
                                      statchg_relation_row_foo="tobcp",
                                      new_relation_row_nob="rfc14",
                                      statchg_relation_row_nob="tohist"))
        self.assertEqual(r.status_code, 302)
        doc = Document.objects.get(name='status-change-imaginary-mid-review')
        self.assertEqual(doc.relateddocument_set.count(),3)
        def verify_relations(doc,target_name,status):
            target_doc=doc.relateddocument_set.filter(target__name=target_name)
            self.assertTrue(target_doc)
            self.assertEqual(target_doc.count(),1)
            self.assertEqual(target_doc[0].relationship.slug,status)
        verify_relations(doc,'rfc9999','toexp' )
        verify_relations(doc,'rfc9998','tobcp' )
        verify_relations(doc,'rfc14'  ,'tohist')
        self.assertTrue(doc.latest_event(DocEvent,type="added_comment").desc.startswith('Affected RFC list changed.'))       

    def test_clear_ballot(self):
        doc = Document.objects.get(name='status-change-imaginary-mid-review')
        url = urlreverse('ietf.doc.views_ballot.clear_ballot',kwargs=dict(name=doc.name, ballot_type_slug="statchg"))
        login_testing_unauthorized(self, "secretary", url)
        
        # Some additional setup
        doc.relateddocument_set.create(target=Document.objects.get(name='rfc9999'),relationship_id='tois')
        doc.relateddocument_set.create(target=Document.objects.get(name='rfc9998'),relationship_id='tohist')
        create_ballot_if_not_open(None, doc, Person.objects.get(user__username="secretary"), "statchg")
        doc.set_state(State.objects.get(slug='iesgeval',type='statchg'))
        old_ballot = doc.ballot_open("statchg")
        self.assertIsNotNone(old_ballot)
        
        r = self.client.post(url, dict())
        self.assertEqual(r.status_code,302)
        new_ballot = doc.ballot_open("statchg")
        self.assertIsNotNone(new_ballot)
        self.assertNotEqual(new_ballot, old_ballot)
        self.assertEqual(doc.get_state_slug("statchg"),"iesgeval")

    def test_clear_deferred_ballot(self):
        doc = Document.objects.get(name='status-change-imaginary-mid-review')
        url = urlreverse('ietf.doc.views_ballot.clear_ballot',kwargs=dict(name=doc.name, ballot_type_slug="statchg"))
        login_testing_unauthorized(self, "secretary", url)
        
        # Some additional setup
        doc.relateddocument_set.create(target=Document.objects.get(name='rfc9999'),relationship_id='tois')
        doc.relateddocument_set.create(target=Document.objects.get(name='rfc9998'),relationship_id='tohist')
        create_ballot_if_not_open(None, doc, Person.objects.get(user__username="secretary"), "statchg")
        doc.set_state(State.objects.get(slug='defer',type='statchg'))
        old_ballot = doc.ballot_open("statchg")
        self.assertIsNotNone(old_ballot)
        
        r = self.client.post(url, dict())
        self.assertEqual(r.status_code,302)
        new_ballot = doc.ballot_open("statchg")
        self.assertIsNotNone(new_ballot)
        self.assertNotEqual(new_ballot, old_ballot)
        self.assertEqual(doc.get_state_slug("statchg"),"iesgeval")

    def setUp(self):
        super().setUp()
        IndividualRfcFactory(rfc_number=14,std_level_id='unkn') # draft was never issued

        rfc = WgRfcFactory(rfc_number=9999,std_level_id='ps')
        draft = WgDraftFactory(name='draft-ietf-random-thing')
        draft.relateddocument_set.create(relationship_id="became_rfc", target=rfc)

        rfc = WgRfcFactory(rfc_number=9998,std_level_id='inf')
        draft = WgDraftFactory(name='draft-ietf-random-other-thing')
        draft.relateddocument_set.create(relationship_id="became_rfc", target=rfc)

        DocumentFactory(type_id='statchg',name='status-change-imaginary-mid-review',notify='notify@example.org')

class StatusChangeSubmitTests(TestCase):
    settings_temp_path_overrides = TestCase.settings_temp_path_overrides + ['STATUS_CHANGE_PATH']
    def test_initial_submission(self):
        doc = Document.objects.get(name='status-change-imaginary-mid-review')
        url = urlreverse('ietf.doc.views_status_change.submit',kwargs=dict(name=doc.name))
        login_testing_unauthorized(self, "ad", url)

        # normal get
        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        q = PyQuery(r.content)
        self.assertTrue(q('textarea')[0].text.strip().startswith("Provide a description"))
        
        # Faulty posts using textbox
        # Right now, nothing to test - we let people put whatever the web browser will let them put into that textbox

        # sane post using textbox
        path = os.path.join(settings.STATUS_CHANGE_PATH, '%s-%s.txt' % (doc.name, doc.rev))
        self.assertEqual(doc.rev,'00')
        self.assertFalse(os.path.exists(path))
        r = self.client.post(url,dict(content="Some initial review text\n",submit_response="1"))
        self.assertEqual(r.status_code,302)
        doc = Document.objects.get(name='status-change-imaginary-mid-review')
        self.assertEqual(doc.rev,'00')
        with io.open(path) as f:
            self.assertEqual(f.read(),"Some initial review text\n")
        self.assertTrue( "mid-review-00" in doc.latest_event(NewRevisionDocEvent).desc)

    def test_subsequent_submission(self):
        doc = Document.objects.get(name='status-change-imaginary-mid-review')
        url = urlreverse('ietf.doc.views_status_change.submit',kwargs=dict(name=doc.name))
        login_testing_unauthorized(self, "ad", url)

        # A little additional setup 
        # doc.rev is u'00' per the test setup - double-checking that here - if it fails, the breakage is in setUp
        self.assertEqual(doc.rev,'00')
        path = os.path.join(settings.STATUS_CHANGE_PATH, '%s-%s.txt' % (doc.name, doc.rev))
        with io.open(path,'w') as f:
            f.write('This is the old proposal.')
            f.close()
        # Put the old proposal into IESG review (exercises ballot tab when looking at an older revision below)
        state_change_url = urlreverse('ietf.doc.views_status_change.change_state',kwargs=dict(name=doc.name))
        iesgeval_pk = str(State.objects.get(slug='iesgeval',type__slug='statchg').pk)
        r = self.client.post(state_change_url,dict(new_state=iesgeval_pk))
        self.assertEqual(r.status_code, 302)

        # normal get
        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        q = PyQuery(r.content)
        self.assertTrue(q('textarea')[0].text.strip().startswith("This is the old proposal."))

        # faulty posts trying to use file upload
        # Copied from wgtracker tests - is this really testing the server code, or is it testing
        #  how client.post populates Content-Type?
        test_file = StringIO("\x10\x11\x12") # post binary file
        test_file.name = "unnamed"
        r = self.client.post(url, dict(txt=test_file,submit_response="1"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "does not appear to be a text file")

        # sane post uploading a file
        test_file = StringIO("This is a new proposal.")
        test_file.name = "unnamed"
        r = self.client.post(url,dict(txt=test_file,submit_response="1"))
        self.assertEqual(r.status_code, 302)
        doc = Document.objects.get(name='status-change-imaginary-mid-review')
        self.assertEqual(doc.rev,'01')
        path = os.path.join(settings.STATUS_CHANGE_PATH, '%s-%s.txt' % (doc.name, doc.rev))
        with io.open(path) as f:
            self.assertEqual(f.read(),"This is a new proposal.")
            f.close()
        self.assertTrue( "mid-review-01" in doc.latest_event(NewRevisionDocEvent).desc)

        # verify reset text button works
        r = self.client.post(url,dict(reset_text="1"))
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(q('textarea')[0].text.strip().startswith("Provide a description"))

        # make sure we can see the old revision
        url = urlreverse('ietf.doc.views_doc.document_main',kwargs=dict(name=doc.name,rev='00'))
        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        self.assertContains(r, "This is the old proposal.")

    def setUp(self):
        super().setUp()
        DocumentFactory(type_id='statchg',name='status-change-imaginary-mid-review',notify='notify@example.org')
