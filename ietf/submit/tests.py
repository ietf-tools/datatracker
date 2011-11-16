import datetime, os, shutil

from django.conf import settings
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse as urlreverse
import django.test
from StringIO import StringIO
from pyquery import PyQuery

from ietf.utils.test_utils import login_testing_unauthorized
from ietf.utils.test_data import make_test_data
from ietf.utils.mail import outbox

from redesign.person.models import Person, Email
from redesign.group.models import Group, Role
from redesign.doc.models import Document, BallotPositionDocEvent
from ietf.submit.models import IdSubmissionDetail

class SubmitTestCase(django.test.TestCase):
    fixtures = ['names', 'idsubmissionstatus']

    def setUp(self):
        self.staging_dir = os.path.abspath("tmp-submit-staging-dir")
        os.mkdir(self.staging_dir)
        settings.IDSUBMIT_STAGING_PATH = self.staging_dir

        self.repository_dir = os.path.abspath("tmp-submit-repository-dir")
        os.mkdir(self.repository_dir)
        settings.IDSUBMIT_REPOSITORY_PATH = self.repository_dir

    def tearDown(self):
        shutil.rmtree(self.staging_dir)
        shutil.rmtree(self.repository_dir)

    def do_submission(self, name, rev):
        # break early in case of missing configuration
        self.assertTrue(os.path.exists(settings.IDSUBMIT_IDNITS_BINARY))

        # get
        url = urlreverse('submit_index')
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEquals(len(q('input[type=file][name=txt]')), 1)

        # construct appropriate text draft
        f = open(os.path.join(settings.BASE_DIR, "submit", "test_submission.txt"))
        template = f.read()
        f.close()

        submission_text = template % dict(
            date=datetime.date.today().strftime("%d %B %Y"),
            expire=(datetime.date.today() + datetime.timedelta(days=100)).strftime("%Y-%m-%d"),
            year=datetime.date.today().strftime("%Y"),
            month_year=datetime.date.today().strftime("%B, %Y"),
            filename="%s-%s" % (name, rev),
            )

        test_file = StringIO(str(submission_text))
        test_file.name = "somename.txt"

        # submit
        r = self.client.post(url,
                             dict(txt=test_file))
        self.assertEquals(r.status_code, 302)
        supply_submitter_url = r["Location"]
        self.assertTrue(os.path.exists(os.path.join(self.staging_dir, u"%s-%s.txt" % (name, rev))))
        self.assertEquals(IdSubmissionDetail.objects.filter(filename=name).count(), 1)
        submission = IdSubmissionDetail.objects.get(filename=name)
        self.assertEquals(submission.group_acronym.acronym, "mars")
        self.assertEquals(submission.tempidauthors_set.count(), 1)
        author = submission.tempidauthors_set.all()[0]
        self.assertEquals(author.first_name, "Test Name")

        return supply_submitter_url

    def supply_submitter(self, name, supply_submitter_url):
        # check the page
        r = self.client.get(supply_submitter_url)
        q = PyQuery(r.content)
        self.assertEquals(len(q('input[type=submit][name=autopost]')), 1)

        # post submitter info
        r = self.client.post(supply_submitter_url,
                             dict(autopost="1",
                                  name="Test Name",
                                  email="testname@example.com",
                                  ))
        # submitter is saved as author order 0
        submission = IdSubmissionDetail.objects.get(filename=name)
        self.assertEquals(submission.tempidauthors_set.count(), 2)
        self.assertEquals(submission.tempidauthors_set.get(author_order=0).first_name, "Test Name")

        return r

    def test_submit_new(self):
        # submit new -> supply submitter info -> approve
        draft = make_test_data()

        name = "draft-ietf-mars-testing-tests"
        rev = "00"

        supply_submitter_url = self.do_submission(name, rev)

        # supply submitter info, then draft should be in and ready for approval
        mailbox_before = len(outbox)
        r = self.supply_submitter(name, supply_submitter_url)

        self.assertEquals(r.status_code, 302)
        status_url = r["Location"]
        self.assertEquals(len(outbox), mailbox_before + 1)
        self.assertTrue("New draft waiting for approval" in outbox[-1]["Subject"])
        self.assertTrue(name in outbox[-1]["Subject"])

        # as chair of WG, we should see approval button
        self.client.login(remote_user="marschairman")

        r = self.client.get(status_url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        approve_submit = q('input[type=submit][value*="Approve"]')
        self.assertEquals(len(approve_submit), 1)

        # approve submission
        mailbox_before = len(outbox)
        approve_url = approve_submit.parents("form").attr("action")
        r = self.client.post(approve_url, dict())
        self.assertEquals(r.status_code, 302)

        draft = Document.objects.get(docalias__name=name)
        self.assertEquals(draft.rev, rev)
        new_revision = draft.latest_event()
        self.assertEquals(new_revision.type, "new_revision")
        self.assertEquals(new_revision.by.name, "Test Name")
        self.assertTrue(not os.path.exists(os.path.join(self.staging_dir, u"%s-%s.txt" % (name, rev))))
        self.assertTrue(os.path.exists(os.path.join(self.repository_dir, u"%s-%s.txt" % (name, rev))))
        self.assertEquals(draft.type_id, "draft")
        self.assertEquals(draft.stream_id, "ietf")
        self.assertEquals(draft.get_state("draft-stream-%s" % draft.stream_id).slug, "wg-doc")
        self.assertEquals(draft.authors.count(), 1)
        self.assertEquals(draft.authors.all()[0].get_name(), "Test Name")
        self.assertEquals(draft.authors.all()[0].address, "testname@example.com")
        self.assertEquals(len(outbox), mailbox_before + 2)
        self.assertTrue((u"I-D Action: %s" % name) in outbox[-2]["Subject"])
        self.assertTrue("Test Name" in unicode(outbox[-2]))
        self.assertTrue("New Version Notification" in outbox[-1]["Subject"])
        self.assertTrue(name in unicode(outbox[-1]))
        self.assertTrue("mars" in unicode(outbox[-1]))

    def test_submit_existing(self):
        # submit new revision of existing -> supply submitter info -> confirm
        draft = make_test_data()

        # make a discuss to see if the AD gets an email
        ballot_position = BallotPositionDocEvent()
        ballot_position.pos_id = "discuss"
        ballot_position.type = "changed_ballot_position"
        ballot_position.doc = draft
        ballot_position.ad = ballot_position.by = Person.objects.get(user__username="ad2")
        ballot_position.save()

        name = draft.name
        rev = "%02d" % (int(draft.rev) + 1)

        supply_submitter_url = self.do_submission(name, rev)

        # supply submitter info, then we get a confirmation email
        mailbox_before = len(outbox)
        r = self.supply_submitter(name, supply_submitter_url)

        self.assertEquals(r.status_code, 200)
        self.assertTrue("Your submission is pending email authentication" in r.content)

        self.assertEquals(len(outbox), mailbox_before + 1)
        confirmation = outbox[-1]
        self.assertTrue("Confirmation for" in confirmation["Subject"])
        self.assertTrue(name in confirmation["Subject"])

        # dig out confirmation link
        msg = confirmation.get_payload(decode=True)
        line_start = "I-D Submission Tool URL:"
        self.assertTrue(line_start in msg)
        confirm_url = None
        for line in msg.split("\n"):
            if line.startswith(line_start):
                confirm_url = line[len(line_start):].strip()

        # go to confirm page
        r = self.client.get(confirm_url)
        q = PyQuery(r.content)
        self.assertEquals(len(q('input[type=submit][value=Auto-Post]')), 1)

        # confirm
        mailbox_before = len(outbox)
        r = self.client.post(confirm_url)
        self.assertEquals(r.status_code, 200)
        self.assertTrue('Authorization key accepted' in r.content)

        draft = Document.objects.get(docalias__name=name)
        self.assertEquals(draft.rev, rev)
        new_revision = draft.latest_event()
        self.assertEquals(new_revision.type, "new_revision")
        self.assertEquals(new_revision.by.name, "Test Name")
        self.assertTrue(not os.path.exists(os.path.join(self.staging_dir, u"%s-%s.txt" % (name, rev))))
        self.assertTrue(os.path.exists(os.path.join(self.repository_dir, u"%s-%s.txt" % (name, rev))))
        self.assertEquals(draft.type_id, "draft")
        self.assertEquals(draft.stream_id, "ietf")
        self.assertEquals(draft.get_state("draft-stream-%s" % draft.stream_id).slug, "wg-doc")
        self.assertEquals(draft.authors.count(), 1)
        self.assertEquals(draft.authors.all()[0].get_name(), "Test Name")
        self.assertEquals(draft.authors.all()[0].address, "testname@example.com")
        self.assertEquals(len(outbox), mailbox_before + 3)
        self.assertTrue((u"I-D Action: %s" % name) in outbox[-3]["Subject"])
        self.assertTrue("Test Name" in unicode(outbox[-3]))
        self.assertTrue("New Version Notification" in outbox[-2]["Subject"])
        self.assertTrue(name in unicode(outbox[-2]))
        self.assertTrue("mars" in unicode(outbox[-2]))
        self.assertTrue(draft.ad.email_address().address in unicode(outbox[-2]))
        self.assertTrue(ballot_position.ad.email_address().address in unicode(outbox[-2]))
        self.assertTrue("New Version Notification" in outbox[-1]["Subject"])
        self.assertTrue(name in unicode(outbox[-1]))
        self.assertTrue("mars" in unicode(outbox[-1]))

    def test_cancel_submission(self):
        # submit -> cancel
        draft = make_test_data()

        name = "draft-ietf-mars-testing-tests"
        rev = "00"

        supply_submitter_url = self.do_submission(name, rev)

        # check we got cancel button
        r = self.client.get(supply_submitter_url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        cancel_submission = q('input[type=submit][value*="Cancel"]')
        self.assertEquals(len(cancel_submission), 1)

        cancel_url = cancel_submission.parents("form").attr("action")

        # cancel
        r = self.client.post(cancel_url)
        self.assertTrue(not os.path.exists(os.path.join(self.staging_dir, u"%s-%s.txt" % (name, rev))))

    def test_edit_submission(self):
        # submit -> edit
        draft = make_test_data()

        name = "draft-ietf-mars-testing-tests"
        rev = "00"

        supply_submitter_url = self.do_submission(name, rev)

        # check we got edit button
        r = self.client.get(supply_submitter_url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEquals(len(q('input[type=submit][value*="Adjust"]')), 1)

        # go to edit, we do this by posting, slightly weird
        r = self.client.post(supply_submitter_url)
        self.assertEquals(r.status_code, 302)
        edit_url = r['Location']

        # check page
        r = self.client.get(edit_url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEquals(len(q('input[name=title]')), 1)

        # edit
        mailbox_before = len(outbox)
        creation_date = datetime.date.today() - datetime.timedelta(days=-3)
        r = self.client.post(edit_url,
                             dict(title="some title",
                                  version="00",
                                  creation_date=creation_date.strftime("%Y-%m-%d"),
                                  abstract="some abstract",
                                  pages="123",
                                  name="Some Random Test Person",
                                  email="random@example.com",
                                  comments="no comments",
                                  name_0="Person 1",
                                  email_0="person1@example.com",
                                  name_1="Person 2",
                                  email_1="person2@example.com",
                                  ))
        self.assertEquals(r.status_code, 302)

        submission = IdSubmissionDetail.objects.get(filename=name)
        self.assertEquals(submission.id_document_name, "some title")
        self.assertEquals(submission.creation_date, creation_date)
        self.assertEquals(submission.abstract, "some abstract")
        self.assertEquals(submission.txt_page_count, 123)
        self.assertEquals(submission.comment_to_sec, "no comments")

        authors = submission.tempidauthors_set
        self.assertEquals(authors.count(), 3)
        # first one is submitter
        self.assertEquals(authors.get(author_order=0).first_name, "Some Random Test Person")
        self.assertEquals(authors.get(author_order=0).email_address, "random@example.com")
        self.assertEquals(authors.get(author_order=1).first_name, "Person 1")
        self.assertEquals(authors.get(author_order=1).email_address, "person1@example.com")
        self.assertEquals(authors.get(author_order=2).first_name, "Person 2")
        self.assertEquals(authors.get(author_order=2).email_address, "person2@example.com")

        self.assertEquals(len(outbox), mailbox_before + 1)
        self.assertTrue("Manual Post Requested" in outbox[-1]["Subject"])
        self.assertTrue(name in outbox[-1]["Subject"])

    def test_request_full_url(self):
        # submit -> request full URL to be sent
        draft = make_test_data()

        name = "draft-ietf-mars-testing-tests"
        rev = "00"

        self.do_submission(name, rev)

        submission = IdSubmissionDetail.objects.get(filename=name)
        url = urlreverse('draft_status', kwargs=dict(submission_id=submission.submission_id))

        # check we got request full URL button
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        request_button = q('input[type=submit][value*="Request full access"]')
        self.assertEquals(len(request_button), 1)

        request_url = request_button.parents("form").attr("action")

        # request URL to be sent
        mailbox_before = len(outbox)
        r = self.client.post(request_url)
        self.assertEquals(r.status_code, 200)

        self.assertEquals(len(outbox), mailbox_before + 1)
        self.assertTrue("Full URL for managing submission" in outbox[-1]["Subject"])
        self.assertTrue(name in outbox[-1]["Subject"])


if not settings.USE_DB_REDESIGN_PROXY_CLASSES:
    # the above tests only work with the new schema
    del SubmitTestCase 
