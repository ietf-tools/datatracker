import datetime
import os
import shutil
import re

from django.conf import settings

from django.core.urlresolvers import reverse as urlreverse
from StringIO import StringIO
from pyquery import PyQuery

from ietf.utils.test_utils import login_testing_unauthorized
from ietf.utils.test_data import make_test_data
from ietf.utils.mail import outbox
from ietf.utils.test_utils import TestCase
from ietf.submit.utils import expirable_submissions, expire_submission, ensure_person_email_info_exists
from ietf.person.models import Person
from ietf.group.models import Group
from ietf.doc.models import Document, DocEvent, State, BallotDocEvent, BallotPositionDocEvent, DocumentAuthor
from ietf.submit.models import Submission, Preapproval

class SubmitTests(TestCase):
    def setUp(self):
        self.staging_dir = os.path.abspath("tmp-submit-staging-dir")
        os.mkdir(self.staging_dir)
        settings.IDSUBMIT_STAGING_PATH = self.staging_dir

        self.repository_dir = os.path.abspath("tmp-submit-repository-dir")
        os.mkdir(self.repository_dir)
        settings.INTERNET_DRAFT_PATH = settings.IDSUBMIT_REPOSITORY_PATH = self.repository_dir

        self.archive_dir = os.path.abspath("tmp-submit-archive-dir")
        os.mkdir(self.archive_dir)
        settings.INTERNET_DRAFT_ARCHIVE_DIR = self.archive_dir
        
    def tearDown(self):
        shutil.rmtree(self.staging_dir)
        shutil.rmtree(self.repository_dir)
        shutil.rmtree(self.archive_dir)

    def submission_txt_file(self, name, rev):
        # construct appropriate text draft
        f = open(os.path.join(settings.BASE_DIR, "submit", "test_submission.txt"))
        template = f.read()
        f.close()

        submission_text = template % dict(
            date=datetime.date.today().strftime("%d %B %Y"),
            expire=(datetime.date.today() + datetime.timedelta(days=100)).strftime("%Y-%m-%d"),
            year=datetime.date.today().strftime("%Y"),
            month_year=datetime.date.today().strftime("%B, %Y"),
            name="%s-%s" % (name, rev),
            )

        txt_file = StringIO(str(submission_text))
        txt_file.name = "somename.txt"
        return txt_file

    def do_submission(self, name, rev):
        # break early in case of missing configuration
        self.assertTrue(os.path.exists(settings.IDSUBMIT_IDNITS_BINARY))

        # get
        url = urlreverse('submit_upload_submission')
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('input[type=file][name=txt]')), 1)

        # submit
        txt_file = self.submission_txt_file(name, rev)

        r = self.client.post(url,
                             dict(txt=txt_file))
        self.assertEqual(r.status_code, 302)
        status_url = r["Location"]
        self.assertTrue(os.path.exists(os.path.join(self.staging_dir, u"%s-%s.txt" % (name, rev))))
        self.assertEqual(Submission.objects.filter(name=name).count(), 1)
        submission = Submission.objects.get(name=name)
        self.assertTrue(re.search('\s+Summary:\s+0\s+errors|No nits found', submission.idnits_message))
        self.assertEqual(len(submission.authors_parsed()), 1)
        author = submission.authors_parsed()[0]
        self.assertEqual(author["name"], "Author Name")
        self.assertEqual(author["email"], "author@example.com")

        return status_url

    def supply_submitter(self, name, status_url, submitter_name, submitter_email):
        # check the page
        r = self.client.get(status_url)
        q = PyQuery(r.content)
        post_button = q('input[type=submit][value*="Post"]')
        self.assertEqual(len(post_button), 1)
        action = post_button.parents("form").find('input[type=hidden][name="action"]').val()

        # post submitter info
        r = self.client.post(status_url, {
            "action": action,
            "submitter-name": submitter_name,
            "submitter-email": submitter_email,
        })

        submission = Submission.objects.get(name=name)
        self.assertEqual(submission.submitter, u"%s <%s>" % (submitter_name, submitter_email))

        return r

    def extract_confirm_url(self, confirm_email):
        # dig out confirm_email link
        msg = confirm_email.get_payload(decode=True)
        line_start = "http"
        confirm_url = None
        for line in msg.split("\n"):
            if line.strip().startswith(line_start):
                confirm_url = line.strip()
        self.assertTrue(confirm_url)

        return confirm_url

    def test_submit_new_wg(self):
        # submit new -> supply submitter info -> approve
        draft = make_test_data()

        name = "draft-ietf-mars-testing-tests"
        rev = "00"

        status_url = self.do_submission(name, rev)

        # supply submitter info, then draft should be in and ready for approval
        mailbox_before = len(outbox)
        r = self.supply_submitter(name, status_url, "Author Name", "author@example.com")

        self.assertEqual(r.status_code, 302)
        status_url = r["Location"]
        self.assertEqual(len(outbox), mailbox_before + 1)
        self.assertTrue("New draft waiting for approval" in outbox[-1]["Subject"])
        self.assertTrue(name in outbox[-1]["Subject"])

        # as chair of WG, we should see approval button
        self.client.login(username="marschairman", password="marschairman+password")

        r = self.client.get(status_url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        approve_button = q('input[type=submit][value*="Approve"]')
        self.assertEqual(len(approve_button), 1)

        action = approve_button.parents("form").find('input[type=hidden][name="action"]').val()

        # approve submission
        mailbox_before = len(outbox)
        r = self.client.post(status_url, dict(action=action))
        self.assertEqual(r.status_code, 302)

        draft = Document.objects.get(docalias__name=name)
        self.assertEqual(draft.rev, rev)
        new_revision = draft.latest_event()
        self.assertEqual(draft.group.acronym, "mars")
        self.assertEqual(new_revision.type, "new_revision")
        self.assertEqual(new_revision.by.name, "Author Name")
        self.assertTrue(not os.path.exists(os.path.join(self.staging_dir, u"%s-%s.txt" % (name, rev))))
        self.assertTrue(os.path.exists(os.path.join(self.repository_dir, u"%s-%s.txt" % (name, rev))))
        self.assertEqual(draft.type_id, "draft")
        self.assertEqual(draft.stream_id, "ietf")
        self.assertTrue(draft.expires >= datetime.datetime.now() + datetime.timedelta(days=settings.INTERNET_DRAFT_DAYS_TO_EXPIRE - 1))
        self.assertEqual(draft.get_state("draft-stream-%s" % draft.stream_id).slug, "wg-doc")
        self.assertEqual(draft.authors.count(), 1)
        self.assertEqual(draft.authors.all()[0].get_name(), "Author Name")
        self.assertEqual(draft.authors.all()[0].address, "author@example.com")
        self.assertEqual(len(outbox), mailbox_before + 2)
        self.assertTrue((u"I-D Action: %s" % name) in outbox[-2]["Subject"])
        self.assertTrue("Author Name" in unicode(outbox[-2]))
        self.assertTrue("New Version Notification" in outbox[-1]["Subject"])
        self.assertTrue(name in unicode(outbox[-1]))
        self.assertTrue("mars" in unicode(outbox[-1]))

    def test_submit_existing(self):
        # submit new revision of existing -> supply submitter info -> prev authors confirm
        draft = make_test_data()
        prev_author = draft.documentauthor_set.all()[0]

        # Make it such that one of the previous authors has an invalid email address
        bogus_email = ensure_person_email_info_exists('Bogus Person',None)  
        DocumentAuthor.objects.create(document=draft,author=bogus_email,order=draft.documentauthor_set.latest('order').order+1)

        # pretend IANA reviewed it
        draft.set_state(State.objects.get(used=True, type="draft-iana-review", slug="not-ok"))

        # pretend it was approved to check that we notify the RFC Editor
        e = DocEvent(type="iesg_approved", doc=draft)
        e.time = draft.time
        e.by = Person.objects.get(name="(System)")
        e.desc = "The IESG approved the document"
        e.save()

        # make a discuss to see if the AD gets an email
        ballot_position = BallotPositionDocEvent()
        ballot_position.ballot = draft.latest_event(BallotDocEvent, type="created_ballot")
        ballot_position.pos_id = "discuss"
        ballot_position.type = "changed_ballot_position"
        ballot_position.doc = draft
        ballot_position.ad = ballot_position.by = Person.objects.get(user__username="ad2")
        ballot_position.save()

        name = draft.name
        rev = "%02d" % (int(draft.rev) + 1)

        # write the old draft in a file so we can check it's moved away
        old_rev = draft.rev
        with open(os.path.join(self.repository_dir, "%s-%s.txt" % (name, old_rev)), 'w') as f:
            f.write("a" * 2000)

        status_url = self.do_submission(name, rev)

        # supply submitter info, then previous authors get a confirmation email
        mailbox_before = len(outbox)
        r = self.supply_submitter(name, status_url, "Submitter Name", "submitter@example.com")
        self.assertEqual(r.status_code, 302)
        status_url = r["Location"]
        r = self.client.get(status_url)
        self.assertEqual(r.status_code, 200)
        self.assertTrue("The submission is pending approval by the authors" in r.content)

        self.assertEqual(len(outbox), mailbox_before + 1)
        confirm_email = outbox[-1]
        self.assertTrue("Confirm submission" in confirm_email["Subject"])
        self.assertTrue(name in confirm_email["Subject"])
        self.assertTrue(prev_author.author.address in confirm_email["To"])
        # submitter and new author can't confirm
        self.assertTrue("author@example.com" not in confirm_email["To"])
        self.assertTrue("submitter@example.com" not in confirm_email["To"])
        # Verify that mail wasn't sent to know invalid addresses
        self.assertTrue("unknown-email-" not in confirm_email["To"])

        confirm_url = self.extract_confirm_url(confirm_email)

        # go to confirm page
        r = self.client.get(confirm_url)
        q = PyQuery(r.content)
        self.assertEqual(len(q('input[type=submit][value*="Confirm"]')), 1)

        # confirm
        mailbox_before = len(outbox)
        r = self.client.post(confirm_url)
        self.assertEqual(r.status_code, 302)

        draft = Document.objects.get(docalias__name=name)
        self.assertEqual(draft.rev, rev)
        self.assertEqual(draft.group.acronym, name.split("-")[2])
        self.assertEqual(draft.docevent_set.all()[1].type, "new_revision")
        self.assertEqual(draft.docevent_set.all()[1].by.name, "Submitter Name")
        self.assertTrue(not os.path.exists(os.path.join(self.repository_dir, "%s-%s.txt" % (name, old_rev))))
        self.assertTrue(os.path.exists(os.path.join(self.archive_dir, "%s-%s.txt" % (name, old_rev))))
        self.assertTrue(not os.path.exists(os.path.join(self.staging_dir, u"%s-%s.txt" % (name, rev))))
        self.assertTrue(os.path.exists(os.path.join(self.repository_dir, u"%s-%s.txt" % (name, rev))))
        self.assertEqual(draft.type_id, "draft")
        self.assertEqual(draft.stream_id, "ietf")
        self.assertEqual(draft.get_state_slug("draft-stream-%s" % draft.stream_id), "wg-doc")
        self.assertEqual(draft.get_state_slug("draft-iana-review"), "changed")
        self.assertEqual(draft.authors.count(), 1)
        self.assertEqual(draft.authors.all()[0].get_name(), "Author Name")
        self.assertEqual(draft.authors.all()[0].address, "author@example.com")
        self.assertEqual(len(outbox), mailbox_before + 3)
        self.assertTrue((u"I-D Action: %s" % name) in outbox[-3]["Subject"])
        self.assertTrue((u"I-D Action: %s" % name) in draft.message_set.order_by("-time")[0].subject)
        self.assertTrue("Author Name" in unicode(outbox[-3]))
        self.assertTrue("New Version Notification" in outbox[-2]["Subject"])
        self.assertTrue(name in unicode(outbox[-2]))
        self.assertTrue("mars" in unicode(outbox[-2]))
        self.assertTrue(draft.ad.role_email("ad").address in unicode(outbox[-2]))
        self.assertTrue(ballot_position.ad.role_email("ad").address in unicode(outbox[-2]))
        self.assertTrue("New Version Notification" in outbox[-1]["Subject"])
        self.assertTrue(name in unicode(outbox[-1]))
        self.assertTrue("mars" in unicode(outbox[-1]))

    def test_submit_new_individual(self):
        # submit new -> supply submitter info -> confirm
        draft = make_test_data()

        name = "draft-authorname-testing-tests"
        rev = "00"

        status_url = self.do_submission(name, rev)

        # supply submitter info, then draft should be be ready for email auth
        mailbox_before = len(outbox)
        r = self.supply_submitter(name, status_url, "Submitter Name", "submitter@example.com")

        self.assertEqual(r.status_code, 302)
        status_url = r["Location"]
        r = self.client.get(status_url)
        self.assertEqual(r.status_code, 200)
        self.assertTrue("The submission is pending email authentication" in r.content)

        self.assertEqual(len(outbox), mailbox_before + 1)
        confirm_email = outbox[-1]
        self.assertTrue("Confirm submission" in confirm_email["Subject"])
        self.assertTrue(name in confirm_email["Subject"])
        # both submitter and author get email
        self.assertTrue("author@example.com" in confirm_email["To"])
        self.assertTrue("submitter@example.com" in confirm_email["To"])

        confirm_url = self.extract_confirm_url(outbox[-1])

        # go to confirm page
        r = self.client.get(confirm_url)
        q = PyQuery(r.content)
        self.assertEqual(len(q('input[type=submit][value*="Confirm"]')), 1)

        # confirm
        mailbox_before = len(outbox)
        r = self.client.post(confirm_url)
        self.assertEqual(r.status_code, 302)

        draft = Document.objects.get(docalias__name=name)
        self.assertEqual(draft.rev, rev)
        new_revision = draft.latest_event()
        self.assertEqual(new_revision.type, "new_revision")
        self.assertEqual(new_revision.by.name, "Submitter Name")

    def test_submit_new_wg_with_dash(self):
        make_test_data()

        group = Group.objects.create(acronym="mars-special", name="Mars Special", type_id="wg", state_id="active")

        name = "draft-ietf-%s-testing-tests" % group.acronym

        self.do_submission(name, "00")

        self.assertEqual(Submission.objects.get(name=name).group.acronym, group.acronym)

    def test_submit_new_irtf(self):
        make_test_data()

        group = Group.objects.create(acronym="saturnrg", name="Saturn", type_id="rg", state_id="active")

        name = "draft-irtf-%s-testing-tests" % group.acronym

        self.do_submission(name, "00")

        self.assertEqual(Submission.objects.get(name=name).group.acronym, group.acronym)
        self.assertEqual(Submission.objects.get(name=name).group.type_id, group.type_id)

    def test_submit_new_iab(self):
        make_test_data()

        name = "draft-iab-testing-tests"

        self.do_submission(name, "00")

        self.assertEqual(Submission.objects.get(name=name).group.acronym, "iab")

    def test_cancel_submission(self):
        # submit -> cancel
        make_test_data()

        name = "draft-ietf-mars-testing-tests"
        rev = "00"

        status_url = self.do_submission(name, rev)

        # check we got cancel button
        r = self.client.get(status_url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        cancel_button = q('input[type=submit][value*="Cancel"]')
        self.assertEqual(len(cancel_button), 1)

        action = cancel_button.parents("form").find("input[type=hidden][name=\"action\"]").val()

        # cancel
        r = self.client.post(status_url, dict(action=action))
        self.assertTrue(not os.path.exists(os.path.join(self.staging_dir, u"%s-%s.txt" % (name, rev))))

    def test_edit_submission_and_force_post(self):
        # submit -> edit
        make_test_data()

        name = "draft-ietf-mars-testing-tests"
        rev = "00"

        status_url = self.do_submission(name, rev)

        # check we have edit button
        r = self.client.get(status_url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        adjust_button = q('input[type=submit][value*="Adjust"]')
        self.assertEqual(len(adjust_button), 1)

        action = adjust_button.parents("form").find('input[type=hidden][name="action"]').val()

        # go to edit, we do this by posting, slightly weird
        r = self.client.post(status_url, dict(action=action))
        self.assertEqual(r.status_code, 302)
        edit_url = r['Location']

        # check page
        r = self.client.get(edit_url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('input[name=edit-title]')), 1)

        # edit
        mailbox_before = len(outbox)
        document_date = datetime.date.today() - datetime.timedelta(days=-3)
        r = self.client.post(edit_url, {
            "edit-title": "some title",
            "edit-rev": "00",
            "edit-document_date": document_date.strftime("%Y-%m-%d"),
            "edit-abstract": "some abstract",
            "edit-pages": "123",
            "submitter-name": "Some Random Test Person",
            "submitter-email": "random@example.com",
            "edit-note": "no comments",
            "authors-0-name": "Person 1",
            "authors-0-email": "person1@example.com",
            "authors-1-name": "Person 2",
            "authors-1-email": "person2@example.com",
            "authors-prefix": ["authors-", "authors-0", "authors-1"],
        })
        self.assertEqual(r.status_code, 302)

        submission = Submission.objects.get(name=name)
        self.assertEqual(submission.title, "some title")
        self.assertEqual(submission.document_date, document_date)
        self.assertEqual(submission.abstract, "some abstract")
        self.assertEqual(submission.pages, 123)
        self.assertEqual(submission.note, "no comments")
        self.assertEqual(submission.submitter, "Some Random Test Person <random@example.com>")
        self.assertEqual(submission.state_id, "manual")

        authors = submission.authors_parsed()
        self.assertEqual(len(authors), 2)
        self.assertEqual(authors[0]["name"], "Person 1")
        self.assertEqual(authors[0]["email"], "person1@example.com")
        self.assertEqual(authors[1]["name"], "Person 2")
        self.assertEqual(authors[1]["email"], "person2@example.com")

        self.assertEqual(len(outbox), mailbox_before + 1)
        self.assertTrue("Manual Post Requested" in outbox[-1]["Subject"])
        self.assertTrue(name in outbox[-1]["Subject"])

        # as Secretariat, we should see the force post button
        self.client.login(username="secretary", password="secretary+password")

        r = self.client.get(status_url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        post_button = q('input[type=submit][value*="Force"]')
        self.assertEqual(len(post_button), 1)

        action = post_button.parents("form").find('input[type=hidden][name="action"]').val()

        # force post
        mailbox_before = len(outbox)
        r = self.client.post(status_url, dict(action=action))
        self.assertEqual(r.status_code, 302)

        draft = Document.objects.get(docalias__name=name)
        self.assertEqual(draft.rev, rev)

    def test_search_for_submission_and_edit_as_secretariat(self):
        # submit -> edit
        make_test_data()

        name = "draft-ietf-mars-testing-tests"
        rev = "00"

        self.do_submission(name, rev)

        # search status page
        r = self.client.get(urlreverse("submit_search_submission"))
        self.assertEqual(r.status_code, 200)
        self.assertTrue("submission status" in r.content)

        # search
        r = self.client.post(urlreverse("submit_search_submission"), dict(name=name))
        self.assertEqual(r.status_code, 302)
        unprivileged_status_url = r['Location']

        # status page as unpriviliged => no edit button
        r = self.client.get(unprivileged_status_url)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(("status of submission of %s" % name) in r.content.lower())
        q = PyQuery(r.content)
        adjust_button = q('input[type=submit][value*="Adjust"]')
        self.assertEqual(len(adjust_button), 0)

        # as Secretariat, we should get edit button
        self.client.login(username="secretary", password="secretary+password")
        r = self.client.get(unprivileged_status_url)
        q = PyQuery(r.content)
        adjust_button = q('input[type=submit][value*="Adjust"]')
        self.assertEqual(len(adjust_button), 1)

        action = adjust_button.parents("form").find('input[type=hidden][name="action"]').val()

        # go to edit, we do this by posting, slightly weird
        r = self.client.post(unprivileged_status_url, dict(action=action))
        self.assertEqual(r.status_code, 302)
        edit_url = r['Location']

        # check page
        r = self.client.get(edit_url)
        self.assertEqual(r.status_code, 200)

    def test_request_full_url(self):
        # submit -> request full URL to be sent
        make_test_data()

        name = "draft-ietf-mars-testing-tests"
        rev = "00"

        self.do_submission(name, rev)

        submission = Submission.objects.get(name=name)
        url = urlreverse('submit_submission_status', kwargs=dict(submission_id=submission.pk))

        # check we got request full URL button
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        request_button = q('input[type=submit][value*="Request full access"]')
        self.assertEqual(len(request_button), 1)

        # request URL to be sent
        mailbox_before = len(outbox)

        action = request_button.parents("form").find("input[type=hidden][name=\"action\"]").val()
        r = self.client.post(url, dict(action=action))
        self.assertEqual(r.status_code, 200)

        self.assertEqual(len(outbox), mailbox_before + 1)
        self.assertTrue("Full URL for managing submission" in outbox[-1]["Subject"])
        self.assertTrue(name in outbox[-1]["Subject"])

    def test_submit_all_file_types(self):
        make_test_data()

        name = "draft-ietf-mars-testing-tests"
        rev = "00"

        txt_file = self.submission_txt_file(name, rev)

        # the checks for other file types are currently embarrassingly
        # dumb, so don't bother constructing proper XML/PS/PDF draft
        # files
        xml_file = StringIO('<?xml version="1.0" encoding="utf-8"?>\n<draft>This is XML</draft>')
        xml_file.name = "somename.xml"

        pdf_file = StringIO('%PDF-1.5\nThis is PDF')
        pdf_file.name = "somename.pdf"

        ps_file = StringIO('%!PS-Adobe-2.0\nThis is PostScript')
        ps_file.name = "somename.ps"
        
        r = self.client.post(urlreverse('submit_upload_submission'), dict(
            txt=txt_file,
            xml=xml_file,
            pdf=pdf_file,
            ps=ps_file,
        ))
        self.assertEqual(r.status_code, 302)

        self.assertEqual(Submission.objects.filter(name=name).count(), 1)

        self.assertTrue(os.path.exists(os.path.join(self.staging_dir, u"%s-%s.txt" % (name, rev))))
        self.assertTrue(name in open(os.path.join(self.staging_dir, u"%s-%s.txt" % (name, rev))).read())
        self.assertTrue(os.path.exists(os.path.join(self.staging_dir, u"%s-%s.xml" % (name, rev))))
        self.assertTrue('This is XML' in open(os.path.join(self.staging_dir, u"%s-%s.xml" % (name, rev))).read())
        self.assertTrue(os.path.exists(os.path.join(self.staging_dir, u"%s-%s.pdf" % (name, rev))))
        self.assertTrue('This is PDF' in open(os.path.join(self.staging_dir, u"%s-%s.pdf" % (name, rev))).read())
        self.assertTrue(os.path.exists(os.path.join(self.staging_dir, u"%s-%s.ps" % (name, rev))))
        self.assertTrue('This is PostScript' in open(os.path.join(self.staging_dir, u"%s-%s.ps" % (name, rev))).read())

    def test_expire_submissions(self):
        s = Submission.objects.create(name="draft-ietf-mars-foo",
                                      group=None,
                                      submission_date=datetime.date.today() - datetime.timedelta(days=10),
                                      rev="00",
                                      state_id="uploaded")

        self.assertEqual(len(expirable_submissions(older_than_days=10)), 0)
        self.assertEqual(len(expirable_submissions(older_than_days=9)), 1)

        s.state_id = "cancel"
        s.save()

        self.assertEqual(len(expirable_submissions(older_than_days=9)), 0)

        s.state_id = "posted"
        s.save()

        self.assertEqual(len(expirable_submissions(older_than_days=9)), 0)

        s.state_id = "uploaded"
        s.save()

        expire_submission(s, by=None)

        self.assertEqual(s.state_id, "cancel")

    def test_help_pages(self):
        r = self.client.get(urlreverse("submit_note_well"))
        self.assertEquals(r.status_code, 200)

        r = self.client.get(urlreverse("submit_tool_instructions"))
        self.assertEquals(r.status_code, 200)
        
class ApprovalsTestCase(TestCase):
    def test_approvals(self):
        make_test_data()

        url = urlreverse('submit_approvals')
        self.client.login(username="marschairman", password="marschairman+password")

        Preapproval.objects.create(name="draft-ietf-mars-foo", by=Person.objects.get(user__username="marschairman"))
        Preapproval.objects.create(name="draft-ietf-mars-baz", by=Person.objects.get(user__username="marschairman"))

        Submission.objects.create(name="draft-ietf-mars-foo",
                                  group=Group.objects.get(acronym="mars"),
                                  submission_date=datetime.date.today(),
                                  rev="00",
                                  state_id="posted")
        Submission.objects.create(name="draft-ietf-mars-bar",
                                  group=Group.objects.get(acronym="mars"),
                                  submission_date=datetime.date.today(),
                                  rev="00",
                                  state_id="grp-appr")

        # get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)

        self.assertEqual(len(q('.approvals a:contains("draft-ietf-mars-foo")')), 0)
        self.assertEqual(len(q('.approvals a:contains("draft-ietf-mars-bar")')), 1)
        self.assertEqual(len(q('.preapprovals td:contains("draft-ietf-mars-foo")')), 0)
        self.assertEqual(len(q('.preapprovals td:contains("draft-ietf-mars-baz")')), 1)
        self.assertEqual(len(q('.recently-approved a:contains("draft-ietf-mars-foo")')), 1)

    def test_add_preapproval(self):
        make_test_data()

        url = urlreverse('submit_add_preapproval')
        login_testing_unauthorized(self, "marschairman", url)

        # get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('input[type=submit]')), 1)

        # faulty post
        r = self.client.post(url, dict(name="draft-test-nonexistingwg-something"))
        self.assertEqual(r.status_code, 200)
        self.assertTrue("errorlist" in r.content)

        # add
        name = "draft-ietf-mars-foo"
        r = self.client.post(url, dict(name=name))
        self.assertEqual(r.status_code, 302)

        self.assertEqual(len(Preapproval.objects.filter(name=name)), 1)

    def test_cancel_preapproval(self):
        make_test_data()

        preapproval = Preapproval.objects.create(name="draft-ietf-mars-foo", by=Person.objects.get(user__username="marschairman"))

        url = urlreverse('submit_cancel_preapproval', kwargs=dict(preapproval_id=preapproval.pk))
        login_testing_unauthorized(self, "marschairman", url)

        # get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('input[type=submit]')), 1)

        # cancel
        r = self.client.post(url, dict(action="cancel"))
        self.assertEqual(r.status_code, 302)

        self.assertEqual(len(Preapproval.objects.filter(name=preapproval.name)), 0)
