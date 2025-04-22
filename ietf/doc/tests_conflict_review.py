# Copyright The IETF Trust 2012-2023, All Rights Reserved
# -*- coding: utf-8 -*-


import io
import os
from pathlib import Path

from pyquery import PyQuery
from textwrap import wrap

from django.conf import settings
from django.urls import reverse as urlreverse

import debug    # pyflakes:ignore

from ietf.doc.factories import IndividualDraftFactory, ConflictReviewFactory, RgDraftFactory
from ietf.doc.models import Document, DocEvent, NewRevisionDocEvent, BallotPositionDocEvent, TelechatDocEvent, State, DocTagName
from ietf.doc.storage_utils import retrieve_str
from ietf.doc.utils import create_ballot_if_not_open
from ietf.doc.views_conflict_review import default_approval_text
from ietf.group.models import Person
from ietf.iesg.models import TelechatDate
from ietf.name.models import StreamName
from ietf.utils.test_utils import TestCase
from ietf.utils.mail import outbox, empty_outbox, get_payload_text
from ietf.utils.test_utils import login_testing_unauthorized


class ConflictReviewTests(TestCase):
    def test_start_review_as_secretary(self):

        doc = Document.objects.get(name='draft-imaginary-independent-submission')
        url = urlreverse('ietf.doc.views_conflict_review.start_review',kwargs=dict(name=doc.name))

        login_testing_unauthorized(self, "secretary", url)
        
        # can't start conflict reviews on documents not in the ise or irtf streams 
        r = self.client.get(url)
        self.assertEqual(r.status_code, 404)

        doc.stream = StreamName.objects.get(slug='ise')
        doc.save_with_history([DocEvent.objects.create(doc=doc, rev=doc.rev, type="changed_stream", by=Person.objects.get(user__username="secretary"), desc="Test")])

        # normal get should succeed and get a reasonable form
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('form select[name=create_in_state]')),1)

        # faulty posts
        r = self.client.post(url,dict(create_in_state=""))
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(len(q('form .is-invalid')) > 0)
        self.assertEqual(Document.objects.filter(name='conflict-review-imaginary-independent-submission').count() , 0)

        r = self.client.post(url,dict(ad=""))
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(len(q('form .is-invalid')) > 0)
        self.assertEqual(Document.objects.filter(name='conflict-review-imaginary-independent-submission').count() , 0)
      
        # successful review start
        ad_strpk = str(Person.objects.get(name='Areað Irector').pk)
        state_strpk = str(State.objects.get(used=True, slug='needshep',type__slug='conflrev').pk)        
        r = self.client.post(url,dict(ad=ad_strpk,create_in_state=state_strpk,notify='ipu@ietf.org'))
        self.assertEqual(r.status_code, 302)
        review_doc = Document.objects.get(name='conflict-review-imaginary-independent-submission')
        self.assertEqual(review_doc.get_state('conflrev').slug,'needshep')
        self.assertEqual(review_doc.rev,'00')
        self.assertEqual(review_doc.ad.name,'Areað Irector')
        self.assertEqual(review_doc.notify,'ipu@ietf.org')
        doc = Document.objects.get(name='draft-imaginary-independent-submission')
        self.assertTrue(doc in [x.target for x in review_doc.relateddocument_set.filter(relationship__slug='conflrev')])

        self.assertTrue(review_doc.latest_event(DocEvent,type="added_comment").desc.startswith("IETF conflict review requested"))
        self.assertTrue(doc.latest_event(DocEvent,type="added_comment").desc.startswith("IETF conflict review initiated"))
        self.assertTrue('Conflict Review requested' in outbox[-1]['Subject'])

        # verify you can't start a review when a review is already in progress
        r = self.client.post(url,dict(ad="Areað Irector",create_in_state="Needs Shepherd",notify='ipu@ietf.org'))
        self.assertEqual(r.status_code, 404)


    def test_start_review_as_stream_owner(self):

        doc = Document.objects.get(name='draft-imaginary-independent-submission')
        url = urlreverse('ietf.doc.views_conflict_review.start_review',kwargs=dict(name=doc.name))

        login_testing_unauthorized(self, "ise-chair", url)

        # can't start conflict reviews on documents not in a stream
        r = self.client.get(url)
        self.assertEqual(r.status_code, 404)


        # can't start conflict reviews on documents in some other stream
        doc.stream = StreamName.objects.get(slug='irtf')
        doc.save_with_history([DocEvent.objects.create(doc=doc, rev=doc.rev, type="changed_stream", by=Person.objects.get(user__username="secretary"), desc="Test")])
        r = self.client.get(url)
        self.assertEqual(r.status_code, 404)

        # successful get 
        doc.stream = StreamName.objects.get(slug='ise')
        doc.save_with_history([DocEvent.objects.create(doc=doc, rev=doc.rev, type="changed_stream", by=Person.objects.get(user__username="secretary"), desc="Test")])
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('form textarea[name=notify]')), 1)
        self.assertEqual(len(q('form select[name=ad]')),0)

        # successfully starts a review, and notifies the secretariat
        messages_before = len(outbox)
        r = self.client.post(url,dict(notify='ipu@ietf.org'))
        self.assertEqual(r.status_code, 302)
        review_doc = Document.objects.get(name='conflict-review-imaginary-independent-submission')
        self.assertEqual(review_doc.get_state('conflrev').slug,'needshep')
        self.assertEqual(review_doc.rev,'00')
        self.assertEqual(review_doc.telechat_date(),None)
        self.assertEqual(review_doc.ad.name,'Ietf Chair')
        self.assertEqual(review_doc.notify,'ipu@ietf.org')
        doc = Document.objects.get(name='draft-imaginary-independent-submission')
        self.assertTrue(doc in [x.target for x in review_doc.relateddocument_set.filter(relationship__slug='conflrev')])

        self.assertEqual(len(outbox), messages_before + 2)

        self.assertTrue('Conflict Review requested' in outbox[-1]['Subject'])
        self.assertTrue('drafts-eval@icann.org' in outbox[-1]['To'])

        self.assertTrue('Conflict Review requested' in outbox[-2]['Subject'])
        self.assertTrue('iesg-secretary@' in outbox[-2]['To'])


    def test_change_state(self):

        doc = Document.objects.get(name='conflict-review-imaginary-irtf-submission')
        url = urlreverse('ietf.doc.views_conflict_review.change_state',kwargs=dict(name=doc.name))

        login_testing_unauthorized(self, "ad", url)

        # normal get 
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('form select[name=review_state]')),1)
        
        # faulty post
        r = self.client.post(url,dict(review_state=""))
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(len(q('form .is-invalid')) > 0)

        # successful change to AD Review
        adrev_pk = str(State.objects.get(used=True, slug='adrev',type__slug='conflrev').pk)
        r = self.client.post(url,dict(review_state=adrev_pk,comment='RDNK84ZD'))
        self.assertEqual(r.status_code, 302)
        review_doc = Document.objects.get(name='conflict-review-imaginary-irtf-submission')
        self.assertEqual(review_doc.get_state('conflrev').slug,'adrev')
        self.assertTrue(review_doc.latest_event(DocEvent,type="added_comment").desc.startswith('RDNK84ZD'))
        self.assertFalse(review_doc.active_ballot())

        # successful change to IESG Evaluation 
        iesgeval_pk = str(State.objects.get(used=True, slug='iesgeval',type__slug='conflrev').pk)
        r = self.client.post(url,dict(review_state=iesgeval_pk,comment='TGmZtEjt'))
        self.assertEqual(r.status_code, 302)
        review_doc = Document.objects.get(name='conflict-review-imaginary-irtf-submission')
        self.assertEqual(review_doc.get_state('conflrev').slug,'iesgeval')
        self.assertTrue(review_doc.latest_event(DocEvent,type="added_comment").desc.startswith('TGmZtEjt'))
        self.assertTrue(review_doc.active_ballot())
        self.assertEqual(review_doc.latest_event(BallotPositionDocEvent, type="changed_ballot_position").pos_id,'yes')

        # try to change to an AD-forbidden state
        appr_noprob_sent_pk = str(State.objects.get(used=True, slug='appr-noprob-sent',type__slug='conflrev').pk)
        r = self.client.post(url,dict(review_state=appr_noprob_sent_pk,comment='xyzzy'))
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(q('form .invalid-feedback'))

        # try again as secretariat
        self.client.logout()
        login_testing_unauthorized(self, 'secretary', url)
        r = self.client.post(url,dict(review_state=appr_noprob_sent_pk,comment='xyzzy'))
        self.assertEqual(r.status_code, 302)
        review_doc = Document.objects.get(name='conflict-review-imaginary-irtf-submission')
        self.assertEqual(review_doc.get_state('conflrev').slug, 'appr-noprob-sent')


    def test_edit_notices(self):
        doc = Document.objects.get(name='conflict-review-imaginary-irtf-submission')
        url = urlreverse('ietf.doc.views_doc.edit_notify;conflict-review',kwargs=dict(name=doc.name))

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
        doc = Document.objects.get(name='conflict-review-imaginary-irtf-submission')
        self.assertEqual(doc.notify,newlist)
        self.assertTrue(doc.latest_event(DocEvent,type="added_comment").desc.startswith('Notification list changed'))       

        # Ask the form to regenerate the list
        r = self.client.post(url,dict(regenerate_addresses="1"))
        self.assertEqual(r.status_code,200)
        doc = Document.objects.get(name='conflict-review-imaginary-irtf-submission')
        # Regenerate does not save!
        self.assertEqual(doc.notify,newlist)
        q = PyQuery(r.content)
        self.assertEqual("", q('form textarea[name=notify]')[0].value.strip())

    def test_edit_ad(self):
        doc = Document.objects.get(name='conflict-review-imaginary-irtf-submission')
        url = urlreverse('ietf.doc.views_conflict_review.edit_ad',kwargs=dict(name=doc.name))

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
        doc = Document.objects.get(name='conflict-review-imaginary-irtf-submission')
        self.assertEqual(doc.ad,ad2)
        self.assertTrue(doc.latest_event(DocEvent,type="added_comment").desc.startswith('Shepherding AD changed'))       


    def test_edit_telechat_date(self):
        doc = Document.objects.get(name='conflict-review-imaginary-irtf-submission')
        url = urlreverse('ietf.doc.views_doc.telechat_date;conflict-review',kwargs=dict(name=doc.name))

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
        doc = Document.objects.get(name='conflict-review-imaginary-irtf-submission')
        self.assertEqual(doc.latest_event(TelechatDocEvent, "scheduled_for_telechat").telechat_date,telechat_date)

        # move it forward a telechat (this should NOT set the returning item bit)
        telechat_date = TelechatDate.objects.active().order_by('date')[1].date
        r = self.client.post(url,dict(telechat_date=telechat_date.isoformat()))
        self.assertEqual(r.status_code,302)
        doc = Document.objects.get(name='conflict-review-imaginary-irtf-submission')
        self.assertFalse(doc.returning_item())

        # set the returning item bit without changing the date
        r = self.client.post(url,dict(telechat_date=telechat_date.isoformat(),returning_item="on"))
        self.assertEqual(r.status_code,302)
        doc = Document.objects.get(name='conflict-review-imaginary-irtf-submission')
        self.assertTrue(doc.returning_item())

        # clear the returning item bit
        r = self.client.post(url,dict(telechat_date=telechat_date.isoformat()))
        self.assertEqual(r.status_code,302)
        doc = Document.objects.get(name='conflict-review-imaginary-irtf-submission')
        self.assertFalse(doc.returning_item())

        # Take the doc back off any telechat
        r = self.client.post(url,dict(telechat_date=""))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(doc.latest_event(TelechatDocEvent, "scheduled_for_telechat").telechat_date,None)

    def approve_test_helper(self,approve_type):

        doc = Document.objects.get(name='conflict-review-imaginary-irtf-submission')
        url = urlreverse('ietf.doc.views_conflict_review.approve_conflict_review',kwargs=dict(name=doc.name))

        login_testing_unauthorized(self, "secretary", url)
        
        # Some additional setup
        create_ballot_if_not_open(None, doc, Person.objects.get(name="Sec Retary"), "conflrev")
        doc.set_state(State.objects.get(used=True, slug=approve_type+'-pend',type='conflrev'))

        # get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('[type=submit]:contains("Send announcement")')), 1)
        if approve_type == 'appr-noprob':
            self.assertContains(r, 'IESG has no problem')
        else:
            self.assertContains(r, 'NOT be published')
        
        # submit
        empty_outbox()
        r = self.client.post(url,dict(announcement_text=default_approval_text(doc)))
        self.assertEqual(r.status_code, 302)

        doc = Document.objects.get(name='conflict-review-imaginary-irtf-submission')
        self.assertEqual(doc.get_state_slug(),approve_type+'-sent')
        self.assertFalse(doc.ballot_open("conflrev"))
        
        self.assertEqual(len(outbox), 1)
        self.assertIn('Results of IETF-conflict review', outbox[0]['Subject'])
        self.assertIn('irtf-chair', outbox[0]['To'])
        self.assertIn('ietf-announce@', outbox[0]['Cc'])
        self.assertIn('iana@', outbox[0]['Cc'])

        if approve_type == 'appr-noprob':
            self.assertIn( 'IESG has no problem', ''.join(wrap(get_payload_text(outbox[0]), 2**16)))
        else:
            self.assertIn( 'NOT be published', ''.join(wrap(get_payload_text(outbox[0]), 2**16)))

    def test_approve_reqnopub(self):
        """Test secretariat approving a conf review FROM the appr-reqnopub-pend state"""
        self.approve_test_helper('appr-reqnopub')

    def test_approve_noprob(self):
        """Test secretariat approving a conf review FROM the appr-reqnopub-pend state"""
        self.approve_test_helper('appr-noprob')

    def approval_pend_notice_test_helper(self, approve_type, role):
        """Test notification email when review state changed to a -pend state

        Sets up, clears outbox, and changes state. If notifications are sent,
        asserts basic properties common to all approve_types.

        Caller should inspect outbox to access notifications if any.
        """
        doc = Document.objects.get(name='conflict-review-imaginary-irtf-submission')
        url = urlreverse('ietf.doc.views_conflict_review.change_state',kwargs=dict(name=doc.name))

        login_testing_unauthorized(self, role, url)
        empty_outbox()

        # Issue the request
        pending_pk = str(State.objects.get(used=True,
                                                 slug=approve_type+'-pend',
                                                 type__slug='conflrev').pk)
        r = self.client.post(url,dict(review_state=pending_pk,comment='some comment or other'))

        # Check the results
        self.assertEqual(r.status_code, 302)

        # If we received a notification, check the common features for all approve_types
        if len(outbox) > 0:
            notification = outbox[0]
            self.assertIn(doc.title, notification['Subject'])
            self.assertIn('iesg-secretary@ietf.org', notification['To'])
            self.assertTrue(notification['Subject'].startswith('Approved:'))

    def test_approval_pend_notice_ad_reqnopub(self):
        """Test notification email when AD puts doc in appr-reqnopub-pend state"""
        self.approval_pend_notice_test_helper('appr-reqnopub', 'ad')
        self.assertEqual(len(outbox), 1)
        self.assertIn('NOT be published', get_payload_text(outbox[0]))

    def test_no_approval_pend_notice_secr_reqnopub(self):
        """Test notification email when secretariat puts doc in appr-reqnopub-pend state"""
        self.approval_pend_notice_test_helper('appr-reqnopub', 'secretariat')
        self.assertEqual(len(outbox), 0)  # no notification should be sent

    def test_approval_pend_notice_ad_noprob(self):
        """Test notification email when AD puts doc in appr-noprob-pend state"""
        self.approval_pend_notice_test_helper('appr-noprob', 'ad')
        self.assertEqual(len(outbox), 1)
        self.assertIn('IESG has no problem', get_payload_text(outbox[0]))

    def test_no_approval_pend_notice_secr_noprob(self):
        """Test notification email when secretariat puts doc in appr-noprob-pend state"""
        self.approval_pend_notice_test_helper('appr-noprob', 'secretariat')
        self.assertEqual(len(outbox), 0)

    def setUp(self):
        super().setUp()
        IndividualDraftFactory(name='draft-imaginary-independent-submission')
        ConflictReviewFactory(name='conflict-review-imaginary-irtf-submission',review_of=IndividualDraftFactory(name='draft-imaginary-irtf-submission',stream_id='irtf'),notify='notifyme@example.net')


class ConflictReviewSubmitTests(TestCase):
    settings_temp_path_overrides = TestCase.settings_temp_path_overrides + ['CONFLICT_REVIEW_PATH','FTP_PATH']
    def test_initial_submission(self):
        doc = Document.objects.get(name='conflict-review-imaginary-irtf-submission')
        url = urlreverse('ietf.doc.views_conflict_review.submit',kwargs=dict(name=doc.name))
        login_testing_unauthorized(self, "ad", url)

        # normal get
        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        q = PyQuery(r.content)
        self.assertTrue(q('textarea[name="content"]')[0].text.strip().startswith("[Edit this page"))
        
        # Faulty posts using textbox
        # Right now, nothing to test - we let people put whatever the web browser will let them put into that textbox

        # sane post using textbox
        basename = f"{doc.name}-{doc.rev}.txt"
        path = Path(settings.CONFLICT_REVIEW_PATH) / basename
        ftp_dir = Path(settings.FTP_DIR) / "conflict-reviews"
        if not ftp_dir.exists():
            ftp_dir.mkdir()
        ftp_path = ftp_dir / basename
        self.assertEqual(doc.rev,'00')
        self.assertFalse(path.exists())
        self.assertFalse(ftp_path.exists())
        r = self.client.post(url,dict(content="Some initial review text\n",submit_response="1"))
        self.assertEqual(r.status_code,302)
        doc = Document.objects.get(name='conflict-review-imaginary-irtf-submission')
        self.assertEqual(doc.rev,'00')
        with io.open(path) as f:
            self.assertEqual(f.read(),"Some initial review text\n")
            f.close()
        self.assertTrue(ftp_path.exists())
        self.assertTrue( "submission-00" in doc.latest_event(NewRevisionDocEvent).desc)
        self.assertEqual(retrieve_str("conflrev",basename), "Some initial review text\n")

    def test_subsequent_submission(self):
        doc = Document.objects.get(name='conflict-review-imaginary-irtf-submission')
        url = urlreverse('ietf.doc.views_conflict_review.submit',kwargs=dict(name=doc.name))
        login_testing_unauthorized(self, "ad", url)

        # A little additional setup 
        # doc.rev is u'00' per the test setup - double-checking that here - if it fails, the breakage is in setUp
        self.assertEqual(doc.rev,'00')
        path = os.path.join(settings.CONFLICT_REVIEW_PATH, '%s-%s.txt' % (doc.name, doc.rev))
        with io.open(path,'w') as f:
            f.write('This is the old proposal.')
            f.close()

        # normal get
        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        q = PyQuery(r.content)
        self.assertTrue(q('textarea')[0].text.strip().startswith("This is the old proposal."))

        # faulty posts trying to use file upload
        # Copied from wgtracker tests - is this really testing the server code, or is it testing
        #  how client.post populates Content-Type?
        test_file = io.StringIO("\x10\x11\x12") # post binary file
        test_file.name = "unnamed"
        r = self.client.post(url, dict(txt=test_file,submit_response="1"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "does not appear to be a text file")

        # sane post uploading a file
        test_file = io.StringIO("This is a new proposal.")
        test_file.name = "unnamed"
        r = self.client.post(url,dict(txt=test_file,submit_response="1"))
        self.assertEqual(r.status_code, 302)
        doc = Document.objects.get(name='conflict-review-imaginary-irtf-submission')
        self.assertEqual(doc.rev,'01')
        path = os.path.join(settings.CONFLICT_REVIEW_PATH, '%s-%s.txt' % (doc.name, doc.rev))
        with io.open(path) as f:
            self.assertEqual(f.read(),"This is a new proposal.")
            f.close()
        self.assertTrue( "submission-01" in doc.latest_event(NewRevisionDocEvent).desc)

        # verify reset text button works
        r = self.client.post(url,dict(reset_text="1"))
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(q('textarea')[0].text.strip().startswith("[Edit this page"))
        
    def setUp(self):
        super().setUp()
        ConflictReviewFactory(name='conflict-review-imaginary-irtf-submission',review_of=IndividualDraftFactory(name='draft-imaginary-irtf-submission',stream_id='irtf'),notify='notifyme@example.net')

class ConflictReviewStreamStateTests(TestCase):

    def start_review(self, stream, role, kwargs=None):
        doc = RgDraftFactory() if stream=='irtf' else IndividualDraftFactory(stream=StreamName.objects.get(slug='ise'))
        url = urlreverse('ietf.doc.views_conflict_review.start_review', kwargs=dict(name=doc.name))
        login_testing_unauthorized(self, role, url)
        r = self.client.post(url, kwargs)
        self.assertEqual(r.status_code, 302)
        self.assertEqual(doc.get_state('draft-stream-'+stream).slug, 'iesg-rev')

    def test_start_irtf_review_as_secretary(self):
        ad_strpk = str(Person.objects.get(name='Areað Irector').pk)
        state_strpk = str(State.objects.get(used=True, slug='needshep', type__slug='conflrev').pk)
        self.start_review('irtf', 'secretary', kwargs=dict(ad=ad_strpk, create_in_state=state_strpk))

    def test_start_ise_review_as_secretary(self):
        ad_strpk = str(Person.objects.get(name='Areað Irector').pk)
        state_strpk = str(State.objects.get(used=True, slug='needshep', type__slug='conflrev').pk)
        self.start_review('ise', 'secretary', kwargs=dict(ad=ad_strpk, create_in_state=state_strpk))

    def test_start_irtf_review_as_stream_owner(self):
        self.start_review('irtf', 'irtf-chair')

    def test_start_ise_review_as_stream_owner(self):
        self.start_review('ise', 'ise-chair')

    def close_review(self, close_type, stream, role):
        doc = RgDraftFactory() if stream=='irtf' else IndividualDraftFactory(stream=StreamName.objects.get(slug='ise'))
        review = ConflictReviewFactory(review_of=doc)
        url = urlreverse('ietf.doc.views_conflict_review.change_state', kwargs=dict(name=review.name))
        login_testing_unauthorized(self, role, url)
        strpk = str(State.objects.get(used=True, slug=close_type, type__slug='conflrev').pk)
        r = self.client.post(url, dict(review_state=strpk))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(doc.get_state('draft-stream-'+stream).slug, 'chair-w' if stream=='irtf' else 'ise-rev')
        self.assertIn(DocTagName.objects.get(pk='iesg-com'), doc.tags.all())

    def test_close_irtf_review_reqnopub_as_secretary(self):
        self.close_review('appr-reqnopub-sent', 'irtf', 'secretary')

    def test_close_ise_review_reqnopub_as_secretary(self):
        self.close_review('appr-reqnopub-sent', 'ise', 'secretary')

    def test_close_irtf_review_noprob_as_secretary(self):
        self.close_review('appr-noprob-sent', 'irtf', 'secretary')

    def test_close_ise_review_noprob_as_secretary(self):
        self.close_review('appr-noprob-sent', 'ise', 'secretary')

    def test_close_irtf_review_withdraw_as_secretary(self):
        self.close_review('withdraw', 'irtf', 'secretary')

    def test_close_ise_review_withdraw_as_secretary(self):
        self.close_review('withdraw', 'ise', 'secretary')

    def test_close_irtf_review_dead_as_secretary(self):
        self.close_review('dead', 'irtf', 'secretary')

    def test_close_ise_review_dead_as_secretary(self):
        self.close_review('dead', 'ise', 'secretary')

    def test_close_irtf_review_withdraw_as_ad(self):
        self.close_review('withdraw', 'irtf', 'ad')

    def test_close_ise_review_withdraw_as_ad(self):
        self.close_review('withdraw', 'ise', 'ad')

    def test_close_irtf_review_dead_as_ad(self):
        self.close_review('dead', 'irtf', 'ad')

    def test_close_ise_review_dead_as_ad(self):
        self.close_review('dead', 'ise', 'ad')

    def test_approve_review(self):
        doc = RgDraftFactory()
        review = ConflictReviewFactory(review_of=doc)
        review.set_state(State.objects.get(used=True, slug='appr-noprob-pend', type='conflrev'))

        url = urlreverse('ietf.doc.views_conflict_review.approve_conflict_review', kwargs=dict(name=review.name))
        login_testing_unauthorized(self, 'secretary', url)

        r = self.client.post(url, dict(announcement_text=default_approval_text(review)))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(doc.get_state('draft-stream-irtf').slug, 'chair-w')
        self.assertIn(DocTagName.objects.get(pk='iesg-com'), doc.tags.all())
