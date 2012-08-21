import os
import shutil

from pyquery import PyQuery
from StringIO import StringIO
from textwrap import wrap


import django.test
from django.conf import settings
from django.core.urlresolvers import reverse as urlreverse

from ietf.utils.test_utils import login_testing_unauthorized
from ietf.utils.test_data  import make_test_data
from ietf.utils.mail import outbox
from ietf.doc.utils import create_ballot_if_not_open
from ietf.doc.views_conflict_review import default_approval_text

from ietf.doc.models import Document,DocEvent,NewRevisionDocEvent,BallotPositionDocEvent,TelechatDocEvent,DocAlias,State
from ietf.name.models import StreamName
from ietf.group.models import Person
from ietf.iesg.models import TelechatDate


class ConflictReviewTestCase(django.test.TestCase):

    fixtures = ['names']

    def test_start_review(self):

        doc = Document.objects.get(name='draft-imaginary-independent-submission')
        url = urlreverse('conflict_review_start',kwargs=dict(name=doc.name))

        login_testing_unauthorized(self, "secretary", url)
        
        # can't start conflict reviews on documents not in the ise or irtf streams 
        r = self.client.get(url)
        self.assertEquals(r.status_code, 404)

        doc.stream=StreamName.objects.get(slug='ise')
        doc.save()

        # normal get should succeed and get a reasonable form
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEquals(len(q('form select[name=create_in_state]')),1)

        # faulty posts
        r = self.client.post(url,dict(create_in_state=""))
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(len(q('form ul.errorlist')) > 0)
        self.assertEquals(Document.objects.filter(name='conflict-review-imaginary-independent-submission').count() , 0)

        r = self.client.post(url,dict(ad=""))
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(len(q('form ul.errorlist')) > 0)
        self.assertEquals(Document.objects.filter(name='conflict-review-imaginary-independent-submission').count() , 0)
      
        # successful review start
        ad_strpk = str(Person.objects.get(name='Aread Irector').pk)
        state_strpk = str(State.objects.get(slug='needshep',type__slug='conflrev').pk)        
        r = self.client.post(url,dict(ad=ad_strpk,create_in_state=state_strpk,notify='ipu@ietf.org'))
        self.assertEquals(r.status_code, 302)
        review_doc = Document.objects.get(name='conflict-review-imaginary-independent-submission')
        self.assertEquals(review_doc.get_state('conflrev').slug,'needshep')
        self.assertEquals(review_doc.rev,u'00')
        self.assertEquals(review_doc.ad.name,u'Aread Irector')
        self.assertEquals(review_doc.notify,u'ipu@ietf.org')
        doc = Document.objects.get(name='draft-imaginary-independent-submission')
        self.assertTrue(doc in [x.target.document for x in review_doc.relateddocument_set.filter(relationship__slug='conflrev')])

        self.assertTrue(review_doc.latest_event(DocEvent,type="added_comment").desc.startswith("IETF conflict review requested"))
        self.assertTrue(doc.latest_event(DocEvent,type="added_comment").desc.startswith("IETF conflict review initiated"))
        
        # verify you can't start a review when a review is already in progress
        r = self.client.post(url,dict(ad="Aread Irector",create_in_state="Needs Shepherd",notify='ipu@ietf.org'))
        self.assertEquals(r.status_code, 404)

    def test_change_state(self):

        doc = Document.objects.get(name='conflict-review-imaginary-irtf-submission')
        url = urlreverse('conflict_review_change_state',kwargs=dict(name=doc.name))

        login_testing_unauthorized(self, "ad", url)

        # normal get 
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEquals(len(q('form select[name=review_state]')),1)
        
        # faulty post
        r = self.client.post(url,dict(review_state=""))
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(len(q('form ul.errorlist')) > 0)

        # successful change to AD Review
        adrev_pk = str(State.objects.get(slug='adrev',type__slug='conflrev').pk)
        r = self.client.post(url,dict(review_state=adrev_pk,comment='RDNK84ZD'))
        self.assertEquals(r.status_code, 302)
        review_doc = Document.objects.get(name='conflict-review-imaginary-irtf-submission')
        self.assertEquals(review_doc.get_state('conflrev').slug,'adrev')
        self.assertTrue(review_doc.latest_event(DocEvent,type="added_comment").desc.startswith('RDNK84ZD'))
        self.assertFalse(review_doc.active_ballot())

        # successful change to IESG Evaluation 
        iesgeval_pk = str(State.objects.get(slug='iesgeval',type__slug='conflrev').pk)
        r = self.client.post(url,dict(review_state=iesgeval_pk,comment='TGmZtEjt'))
        self.assertEquals(r.status_code, 302)
        review_doc = Document.objects.get(name='conflict-review-imaginary-irtf-submission')
        self.assertEquals(review_doc.get_state('conflrev').slug,'iesgeval')
        self.assertTrue(review_doc.latest_event(DocEvent,type="added_comment").desc.startswith('TGmZtEjt'))
        self.assertTrue(review_doc.active_ballot())
        self.assertEquals(review_doc.latest_event(BallotPositionDocEvent, type="changed_ballot_position").pos_id,'yes')


    def test_edit_notices(self):
        doc = Document.objects.get(name='conflict-review-imaginary-irtf-submission')
        url = urlreverse('conflict_review_notices',kwargs=dict(name=doc.name))

        login_testing_unauthorized(self, "ad", url)

        # normal get 
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEquals(len(q('form input[name=notify]')),1)
        self.assertEquals(doc.notify,q('form input[name=notify]')[0].value)

        # change notice list
        newlist = '"Foo Bar" <foo@bar.baz.com>'
        r = self.client.post(url,dict(notify=newlist))
        self.assertEquals(r.status_code,302)
        doc = Document.objects.get(name='conflict-review-imaginary-irtf-submission')
        self.assertEquals(doc.notify,newlist)
        self.assertTrue(doc.latest_event(DocEvent,type="added_comment").desc.startswith('Notification list changed'))       


    def test_edit_ad(self):
        doc = Document.objects.get(name='conflict-review-imaginary-irtf-submission')
        url = urlreverse('conflict_review_ad',kwargs=dict(name=doc.name))

        login_testing_unauthorized(self, "ad", url)

        # normal get 
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEquals(len(q('select[name=ad]')),1)

        # change ads
        ad2 = Person.objects.get(name='Ad No2')
        r = self.client.post(url,dict(ad=str(ad2.pk)))
        self.assertEquals(r.status_code,302)
        doc = Document.objects.get(name='conflict-review-imaginary-irtf-submission')
        self.assertEquals(doc.ad,ad2)
        self.assertTrue(doc.latest_event(DocEvent,type="added_comment").desc.startswith('Shepherding AD changed'))       


    def test_edit_telechat_date(self):
        doc = Document.objects.get(name='conflict-review-imaginary-irtf-submission')
        url = urlreverse('conflict_review_telechat_date',kwargs=dict(name=doc.name))

        login_testing_unauthorized(self, "ad", url)

        # normal get 
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEquals(len(q('select[name=telechat_date]')),1)

        # set a date
        self.assertFalse(doc.latest_event(TelechatDocEvent, "scheduled_for_telechat"))
        telechat_date = TelechatDate.objects.active().order_by('date')[0].date
        r = self.client.post(url,dict(telechat_date=telechat_date.isoformat()))
        self.assertEquals(r.status_code,302)
        doc = Document.objects.get(name='conflict-review-imaginary-irtf-submission')
        self.assertEquals(doc.latest_event(TelechatDocEvent, "scheduled_for_telechat").telechat_date,telechat_date)

        # move it forward a telechat (this should set the returning item bit)
        telechat_date = TelechatDate.objects.active().order_by('date')[1].date
        r = self.client.post(url,dict(telechat_date=telechat_date.isoformat()))
        self.assertEquals(r.status_code,302)
        doc = Document.objects.get(name='conflict-review-imaginary-irtf-submission')
        self.assertTrue(doc.returning_item())

        # clear the returning item bit
        r = self.client.post(url,dict(telechat_date=telechat_date.isoformat()))
        self.assertEquals(r.status_code,302)
        doc = Document.objects.get(name='conflict-review-imaginary-irtf-submission')
        self.assertFalse(doc.returning_item())

        # set the returning item bit without changing the date
        r = self.client.post(url,dict(telechat_date=telechat_date.isoformat(),returning_item="on"))
        self.assertEquals(r.status_code,302)
        doc = Document.objects.get(name='conflict-review-imaginary-irtf-submission')
        self.assertTrue(doc.returning_item())

        # Take the doc back off any telechat
        r = self.client.post(url,dict(telechat_date=""))
        self.assertEquals(r.status_code, 302)
        self.assertEquals(doc.latest_event(TelechatDocEvent, "scheduled_for_telechat").telechat_date,None)

    def approve_test_helper(self,approve_type):

        doc = Document.objects.get(name='conflict-review-imaginary-irtf-submission')
        url = urlreverse('conflict_review_approve',kwargs=dict(name=doc.name))

        login_testing_unauthorized(self, "secretary", url)
        
        # Some additional setup
        create_ballot_if_not_open(doc,Person.objects.get(name="Sec Retary"),"conflrev")
        doc.set_state(State.objects.get(slug=approve_type+'-pend',type='conflrev'))
        doc.save()

        # get
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEquals(len(q('form.approve')),1)
        if approve_type == 'appr-noprob':
            self.assertTrue( 'IESG has no problem' in ''.join(wrap(r.content,2**16)))
        else:
            self.assertTrue( 'NOT be published' in ''.join(wrap(r.content,2**16)))
        
        # submit
        messages_before = len(outbox)
        r = self.client.post(url,dict(announcement_text=default_approval_text(doc)))
        self.assertEquals(r.status_code, 302)

        doc = Document.objects.get(name='conflict-review-imaginary-irtf-submission')
        self.assertEquals(doc.get_state_slug(),approve_type+'-sent')
        self.assertFalse(doc.ballot_open("conflrev"))
        
        self.assertEquals(len(outbox), messages_before + 1)
        self.assertTrue('Results of IETF-conflict review' in outbox[-1]['Subject'])
        if approve_type == 'appr-noprob':
            self.assertTrue( 'IESG has no problem' in ''.join(wrap(unicode(outbox[-1]),2**16)))
        else:
            self.assertTrue( 'NOT be published' in ''.join(wrap(unicode(outbox[-1]),2**16)))
        
       
    def test_approve_reqnopub(self):
        self.approve_test_helper('appr-reqnopub')

    def test_approve_noprob(self):
        self.approve_test_helper('appr-noprob')

    def setUp(self):
        make_test_data()


class ConflictReviewSubmitTestCase(django.test.TestCase):

    fixtures = ['names']

    def test_initial_submission(self):
        doc = Document.objects.get(name='conflict-review-imaginary-irtf-submission')
        url = urlreverse('conflict_review_submit',kwargs=dict(name=doc.name))
        login_testing_unauthorized(self, "ad", url)

        # normal get
        r = self.client.get(url)
        self.assertEquals(r.status_code,200)
        q = PyQuery(r.content)
        self.assertTrue(q('textarea')[0].text.startswith("[Edit this page"))
        
        # Faulty posts using textbox
        # Right now, nothing to test - we let people put whatever the web browser will let them put into that textbox

        # sane post using textbox
        path = os.path.join(settings.CONFLICT_REVIEW_PATH, '%s-%s.txt' % (doc.canonical_name(), doc.rev))
        self.assertEquals(doc.rev,u'00')
        self.assertFalse(os.path.exists(path))
        r = self.client.post(url,dict(content="Some initial review text\n",submit_response="1"))
        self.assertEquals(r.status_code,302)
        doc = Document.objects.get(name='conflict-review-imaginary-irtf-submission')
        self.assertEquals(doc.rev,u'00')
        with open(path) as f:
            self.assertEquals(f.read(),"Some initial review text\n")
            f.close()
        self.assertTrue( "submission-00" in doc.latest_event(NewRevisionDocEvent).desc)

    def test_subsequent_submission(self):
        doc = Document.objects.get(name='conflict-review-imaginary-irtf-submission')
        url = urlreverse('conflict_review_submit',kwargs=dict(name=doc.name))
        login_testing_unauthorized(self, "ad", url)

        # A little additional setup 
        # doc.rev is u'00' per the test setup - double-checking that here - if it fails, the breakage is in setUp
        self.assertEquals(doc.rev,u'00')
        path = os.path.join(settings.CONFLICT_REVIEW_PATH, '%s-%s.txt' % (doc.canonical_name(), doc.rev))
        with open(path,'w') as f:
            f.write('This is the old proposal.')
            f.close()

        # normal get
        r = self.client.get(url)
        self.assertEquals(r.status_code,200)
        q = PyQuery(r.content)
        self.assertTrue(q('textarea')[0].text.startswith("This is the old proposal."))

        # faulty posts trying to use file upload
        # Copied from wgtracker tests - is this really testing the server code, or is it testing
        #  how client.post populates Content-Type?
        test_file = StringIO("\x10\x11\x12") # post binary file
        test_file.name = "unnamed"
        r = self.client.post(url, dict(txt=test_file,submit_response="1"))
        self.assertEquals(r.status_code, 200)
        self.assertTrue("does not appear to be a text file" in r.content)

        # sane post uploading a file
        test_file = StringIO("This is a new proposal.")
        test_file.name = "unnamed"
        r = self.client.post(url,dict(txt=test_file,submit_response="1"))
        self.assertEquals(r.status_code, 302)
        doc = Document.objects.get(name='conflict-review-imaginary-irtf-submission')
        self.assertEquals(doc.rev,u'01')
        path = os.path.join(settings.CONFLICT_REVIEW_PATH, '%s-%s.txt' % (doc.canonical_name(), doc.rev))
        with open(path) as f:
            self.assertEquals(f.read(),"This is a new proposal.")
            f.close()
        self.assertTrue( "submission-01" in doc.latest_event(NewRevisionDocEvent).desc)

        # verify reset text button works
        r = self.client.post(url,dict(reset_text="1"))
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(q('textarea')[0].text.startswith("[Edit this page"))
        
    def setUp(self):
        make_test_data()
        self.test_dir = os.path.abspath("tmp-conflict-review-testdir")
        os.mkdir(self.test_dir)
        settings.CONFLICT_REVIEW_PATH = self.test_dir

    def tearDown(self):
        shutil.rmtree(self.test_dir)
