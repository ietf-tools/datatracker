# -*- coding: utf-8 -*-

import datetime, os, shutil, json
import tarfile, tempfile, mailbox
import email.mime.multipart, email.mime.text, email.utils
from StringIO import StringIO

from django.core.urlresolvers import reverse as urlreverse
from django.conf import settings

from pyquery import PyQuery

import debug                            # pyflakes:ignore

from ietf.review.models import ReviewRequest, ReviewTeamResult, ReviewerSettings
import ietf.review.mailarch
from ietf.person.models import Email, Person
from ietf.name.models import ReviewResultName, ReviewRequestStateName, ReviewTypeName, DocRelationshipName
from ietf.doc.models import DocumentAuthor, Document, DocAlias, RelatedDocument, DocEvent
from ietf.utils.test_utils import TestCase
from ietf.utils.test_data import make_test_data, make_review_data
from ietf.utils.test_utils import login_testing_unauthorized, unicontent, reload_db_objects
from ietf.utils.mail import outbox, empty_outbox

class ReviewTests(TestCase):
    def setUp(self):
        self.review_dir = os.path.abspath("tmp-review-dir")
        if not os.path.exists(self.review_dir):
            os.mkdir(self.review_dir)

        self.old_document_path_pattern = settings.DOCUMENT_PATH_PATTERN
        settings.DOCUMENT_PATH_PATTERN = self.review_dir + "/{doc.type_id}/"

        self.review_subdir = os.path.join(self.review_dir, "review")
        if not os.path.exists(self.review_subdir):
            os.mkdir(self.review_subdir)
        
    def tearDown(self):
        shutil.rmtree(self.review_dir)
        settings.DOCUMENT_PATH_PATTERN = self.old_document_path_pattern

    def test_request_review(self):
        doc = make_test_data()
        review_req = make_review_data(doc)
        review_team = review_req.team

        url = urlreverse('ietf.doc.views_review.request_review', kwargs={ "name": doc.name })
        login_testing_unauthorized(self, "secretary", url)

        # get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        deadline = datetime.date.today() + datetime.timedelta(days=10)

        # post request
        r = self.client.post(url, {
            "type": "early",
            "team": review_team.pk,
            "deadline": deadline.isoformat(),
            "requested_rev": "01",
            "requested_by": Person.objects.get(user__username="plain").pk,
        })
        self.assertEqual(r.status_code, 302)

        req = ReviewRequest.objects.get(doc=doc, state="requested")
        self.assertEqual(req.deadline, deadline)
        self.assertEqual(req.team, review_team)
        self.assertEqual(req.requested_rev, "01")
        self.assertEqual(doc.latest_event().type, "requested_review")

    def test_doc_page(self):
        doc = make_test_data()
        review_req = make_review_data(doc)

        # move the review request to a doubly-replaced document to
        # check we can fish it out
        old_doc = Document.objects.get(name="draft-foo-mars-test")
        older_doc = Document.objects.create(name="draft-older")
        older_docalias = DocAlias.objects.create(name=older_doc.name, document=older_doc)
        RelatedDocument.objects.create(source=old_doc, target=older_docalias, relationship=DocRelationshipName.objects.get(slug='replaces'))
        review_req.doc = older_doc
        review_req.save()

        url = urlreverse('doc_view', kwargs={ "name": doc.name })
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        content = unicontent(r)
        self.assertTrue("{} Review".format(review_req.type.name) in content)

    def test_review_request(self):
        doc = make_test_data()
        review_req = make_review_data(doc)

        url = urlreverse('ietf.doc.views_review.review_request', kwargs={ "name": doc.name, "request_id": review_req.pk })

        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(review_req.team.acronym.upper() in unicontent(r))

    def test_close_request(self):
        doc = make_test_data()
        review_req = make_review_data(doc)
        review_req.state = ReviewRequestStateName.objects.get(slug="accepted")
        review_req.save()

        close_url = urlreverse('ietf.doc.views_review.close_request', kwargs={ "name": doc.name, "request_id": review_req.pk })


        # follow link
        req_url = urlreverse('ietf.doc.views_review.review_request', kwargs={ "name": doc.name, "request_id": review_req.pk })
        self.client.login(username="secretary", password="secretary+password")
        r = self.client.get(req_url)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(close_url in unicontent(r))
        self.client.logout()

        # get close page
        login_testing_unauthorized(self, "secretary", close_url)
        r = self.client.get(close_url)
        self.assertEqual(r.status_code, 200)

        # close
        empty_outbox()
        r = self.client.post(close_url, { "close_reason": "withdrawn" })
        self.assertEqual(r.status_code, 302)

        review_req = reload_db_objects(review_req)
        self.assertEqual(review_req.state_id, "withdrawn")
        e = doc.latest_event()
        self.assertEqual(e.type, "changed_review_request")
        self.assertTrue("closed" in e.desc.lower())
        self.assertEqual(len(outbox), 1)
        self.assertTrue("closed" in unicode(outbox[0]).lower())

    def test_assign_reviewer(self):
        doc = make_test_data()

        # set up some reviewer-suitability factors
        plain_email = Email.objects.filter(person__user__username="plain").first()
        DocumentAuthor.objects.create(
            author=plain_email,
            document=doc,
        )
        doc.rev = "10"
        doc.save_with_history([DocEvent.objects.create(doc=doc, type="changed_document", by=Person.objects.get(user__username="secretary"), desc="Test")])

        # review to assign to
        review_req = make_review_data(doc)
        review_req.state = ReviewRequestStateName.objects.get(slug="requested")
        review_req.reviewer = None
        review_req.save()

        # previous review
        ReviewRequest.objects.create(
            time=datetime.datetime.now() - datetime.timedelta(days=100),
            requested_by=Person.objects.get(name="(System)"),
            doc=doc,
            type=ReviewTypeName.objects.get(slug="early"),
            team=review_req.team,
            state=ReviewRequestStateName.objects.get(slug="completed"),
            reviewed_rev="01",
            deadline=datetime.date.today() - datetime.timedelta(days=80),
            reviewer=plain_email,
        )

        reviewer_settings = ReviewerSettings.objects.get(person__email=plain_email)
        reviewer_settings.filter_re = doc.name
        reviewer_settings.unavailable_until = datetime.datetime.now() + datetime.timedelta(days=10)
        reviewer_settings.save()

        assign_url = urlreverse('ietf.doc.views_review.assign_reviewer', kwargs={ "name": doc.name, "request_id": review_req.pk })


        # follow link
        req_url = urlreverse('ietf.doc.views_review.review_request', kwargs={ "name": doc.name, "request_id": review_req.pk })
        self.client.login(username="secretary", password="secretary+password")
        r = self.client.get(req_url)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(assign_url in unicontent(r))
        self.client.logout()

        # get assign page
        login_testing_unauthorized(self, "secretary", assign_url)
        r = self.client.get(assign_url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        plain_label = q("option[value=\"{}\"]".format(plain_email.address)).text().lower()
        self.assertIn("ready for", plain_label)
        self.assertIn("reviewed document before", plain_label)
        self.assertIn("is author", plain_label)
        self.assertIn("regexp matches", plain_label)
        self.assertIn("unavailable until", plain_label)

        # assign
        empty_outbox()
        reviewer = Email.objects.filter(role__name="reviewer", role__group=review_req.team).first()
        r = self.client.post(assign_url, { "action": "assign", "reviewer": reviewer.pk })
        self.assertEqual(r.status_code, 302)

        review_req = reload_db_objects(review_req)
        self.assertEqual(review_req.state_id, "requested")
        self.assertEqual(review_req.reviewer, reviewer)
        self.assertEqual(len(outbox), 1)
        self.assertTrue("assigned" in unicode(outbox[0]))

        # re-assign
        empty_outbox()
        review_req.state = ReviewRequestStateName.objects.get(slug="accepted")
        review_req.save()
        reviewer = Email.objects.filter(role__name="reviewer", role__group=review_req.team).exclude(pk=reviewer.pk).first()
        r = self.client.post(assign_url, { "action": "assign", "reviewer": reviewer.pk })
        self.assertEqual(r.status_code, 302)

        review_req = reload_db_objects(review_req)
        self.assertEqual(review_req.state_id, "requested") # check that state is reset
        self.assertEqual(review_req.reviewer, reviewer)
        self.assertEqual(len(outbox), 2)
        self.assertTrue("cancelled your assignment" in unicode(outbox[0]))
        self.assertTrue("assigned" in unicode(outbox[1]))

    def test_accept_reviewer_assignment(self):
        doc = make_test_data()
        review_req = make_review_data(doc)
        review_req.state = ReviewRequestStateName.objects.get(slug="requested")
        review_req.save()

        url = urlreverse('ietf.doc.views_review.review_request', kwargs={ "name": doc.name, "request_id": review_req.pk })
        username = review_req.reviewer.person.user.username
        self.client.login(username=username, password=username + "+password")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(q("[name=action][value=accept]"))

        # accept
        r = self.client.post(url, { "action": "accept" })
        self.assertEqual(r.status_code, 302)

        review_req = reload_db_objects(review_req)
        self.assertEqual(review_req.state_id, "accepted")

    def test_reject_reviewer_assignment(self):
        doc = make_test_data()
        review_req = make_review_data(doc)
        review_req.state = ReviewRequestStateName.objects.get(slug="accepted")
        review_req.save()

        reject_url = urlreverse('ietf.doc.views_review.reject_reviewer_assignment', kwargs={ "name": doc.name, "request_id": review_req.pk })


        # follow link
        req_url = urlreverse('ietf.doc.views_review.review_request', kwargs={ "name": doc.name, "request_id": review_req.pk })
        self.client.login(username="secretary", password="secretary+password")
        r = self.client.get(req_url)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(reject_url in unicontent(r))
        self.client.logout()

        # get reject page
        login_testing_unauthorized(self, "secretary", reject_url)
        r = self.client.get(reject_url)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(unicode(review_req.reviewer.person) in unicontent(r))

        # reject
        empty_outbox()
        r = self.client.post(reject_url, { "action": "reject", "message_to_secretary": "Test message" })
        self.assertEqual(r.status_code, 302)

        review_req = reload_db_objects(review_req)
        self.assertEqual(review_req.state_id, "rejected")
        e = doc.latest_event()
        self.assertEqual(e.type, "changed_review_request")
        self.assertTrue("rejected" in e.desc)
        self.assertEqual(ReviewRequest.objects.filter(doc=review_req.doc, team=review_req.team, state="requested").count(), 1)
        self.assertEqual(len(outbox), 1)
        self.assertTrue("Test message" in unicode(outbox[0]))

    def make_test_mbox_tarball(self, review_req):
        mbox_path = os.path.join(self.review_dir, "testmbox.tar.gz")
        with tarfile.open(mbox_path, "w:gz") as tar:
            with tempfile.NamedTemporaryFile(dir=self.review_dir, suffix=".mbox") as tmp:
                mbox = mailbox.mbox(tmp.name)

                # plain text
                msg = email.mime.text.MIMEText("Hello,\n\nI have reviewed the document and did not find any problems.\n\nJohn Doe")
                msg["From"] = "johndoe@example.com"
                msg["To"] = review_req.team.list_email
                msg["Subject"] = "Review of {}-01".format(review_req.doc.name)
                msg["Message-ID"] = email.utils.make_msgid()
                msg["Archived-At"] = "<https://www.example.com/testmessage>"
                msg["Date"] = email.utils.formatdate()

                mbox.add(msg)

                # plain text + HTML
                msg = email.mime.multipart.MIMEMultipart('alternative')
                msg["From"] = "johndoe2@example.com"
                msg["To"] = review_req.team.list_email
                msg["Subject"] = "Review of {}".format(review_req.doc.name)
                msg["Message-ID"] = email.utils.make_msgid()
                msg["Archived-At"] = "<https://www.example.com/testmessage2>"

                msg.attach(email.mime.text.MIMEText("Hi!,\r\nLooks OK!\r\n-John", "plain"))
                msg.attach(email.mime.text.MIMEText("<html><body><p>Hi!,</p><p>Looks OK!</p><p>-John</p></body></html>", "html"))
                mbox.add(msg)

                tmp.flush()

                tar.add(os.path.relpath(tmp.name))

        return mbox_path

    def test_search_mail_archive(self):
        doc = make_test_data()
        review_req = make_review_data(doc)
        review_req.state = ReviewRequestStateName.objects.get(slug="accepted")
        review_req.save()
        review_req.team.save()

        # test URL construction
        query_urls = ietf.review.mailarch.construct_query_urls(review_req)
        self.assertTrue(review_req.doc.name in query_urls["query_data_url"])

        # test parsing
        mbox_path = self.make_test_mbox_tarball(review_req)

        try:
            # mock URL generator and point it to local file - for this
            # to work, the module (and not the function) must be
            # imported in the view
            real_fn = ietf.review.mailarch.construct_query_urls
            ietf.review.mailarch.construct_query_urls = lambda review_req, query=None: { "query_data_url": "file://" + os.path.abspath(mbox_path) }

            url = urlreverse('ietf.doc.views_review.search_mail_archive', kwargs={ "name": doc.name, "request_id": review_req.pk })
            login_testing_unauthorized(self, "secretary", url)

            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)
            messages = json.loads(r.content)["messages"]
            self.assertEqual(len(messages), 2)

            self.assertEqual(messages[0]["url"], "https://www.example.com/testmessage")
            self.assertTrue("John Doe" in messages[0]["content"])
            self.assertEqual(messages[0]["subject"], "Review of {}-01".format(review_req.doc.name))

            self.assertEqual(messages[1]["url"], "https://www.example.com/testmessage2")
            self.assertTrue("Looks OK" in messages[1]["content"])
            self.assertTrue("<html>" not in messages[1]["content"])
            self.assertEqual(messages[1]["subject"], "Review of {}".format(review_req.doc.name))
        finally:
            ietf.review.mailarch.construct_query_urls = real_fn

    def setup_complete_review_test(self):
        doc = make_test_data()
        review_req = make_review_data(doc)
        review_req.state = ReviewRequestStateName.objects.get(slug="accepted")
        review_req.save()
        for r in ReviewResultName.objects.filter(slug__in=("issues", "ready")):
            ReviewTeamResult.objects.get_or_create(team=review_req.team, result=r)
        review_req.team.save()

        url = urlreverse('ietf.doc.views_review.complete_review', kwargs={ "name": doc.name, "request_id": review_req.pk })

        return review_req, url

    def test_complete_review_upload_content(self):
        review_req, url = self.setup_complete_review_test()

        login_testing_unauthorized(self, review_req.reviewer.person.user.username, url)

        # get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        # faulty post
        r = self.client.post(url, data={
            "result": "ready",
            "state": "completed",
            "reviewed_rev": "abc",
            "review_submission": "upload",
            "review_content": "",
            "review_url": "",
            "review_file": "",
        })
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(q("[name=reviewed_rev]").closest(".form-group").filter(".has-error"))
        self.assertTrue(q("[name=review_file]").closest(".form-group").filter(".has-error"))

        # complete by uploading file
        empty_outbox()

        test_file = StringIO("This is a review\nwith two lines")
        test_file.name = "unnamed"

        r = self.client.post(url, data={
            "result": ReviewResultName.objects.get(reviewteamresult__team=review_req.team, slug="ready").pk,
            "state": ReviewRequestStateName.objects.get(slug="completed").pk,
            "reviewed_rev": review_req.doc.rev,
            "review_submission": "upload",
            "review_content": "",
            "review_url": "",
            "review_file": test_file,
        })
        self.assertEqual(r.status_code, 302)

        review_req = reload_db_objects(review_req)
        self.assertEqual(review_req.state_id, "completed")
        self.assertEqual(review_req.result_id, "ready")
        self.assertEqual(review_req.reviewed_rev, review_req.doc.rev)
        self.assertTrue(review_req.team.acronym.lower() in review_req.review.name)
        self.assertTrue(review_req.doc.rev in review_req.review.name)

        with open(os.path.join(self.review_subdir, review_req.review.name + ".txt")) as f:
            self.assertEqual(f.read(), "This is a review\nwith two lines")

        self.assertEqual(len(outbox), 1)
        self.assertTrue(review_req.team.list_email in outbox[0]["To"])
        self.assertTrue("This is a review" in unicode(outbox[0]))

        self.assertTrue(settings.MAILING_LIST_ARCHIVE_URL in review_req.review.external_url)

    def test_complete_review_enter_content(self):
        review_req, url = self.setup_complete_review_test()

        login_testing_unauthorized(self, review_req.reviewer.person.user.username, url)

        # complete by uploading file
        empty_outbox()

        r = self.client.post(url, data={
            "result": ReviewResultName.objects.get(reviewteamresult__team=review_req.team, slug="ready").pk,
            "state": ReviewRequestStateName.objects.get(slug="completed").pk,
            "reviewed_rev": review_req.doc.rev,
            "review_submission": "enter",
            "review_content": "This is a review\nwith two lines",
            "review_url": "",
            "review_file": "",
        })
        self.assertEqual(r.status_code, 302)

        review_req = reload_db_objects(review_req)
        self.assertEqual(review_req.state_id, "completed")

        with open(os.path.join(self.review_subdir, review_req.review.name + ".txt")) as f:
            self.assertEqual(f.read(), "This is a review\nwith two lines")

        self.assertEqual(len(outbox), 1)
        self.assertTrue(review_req.team.list_email in outbox[0]["To"])
        self.assertTrue("This is a review" in unicode(outbox[0]))

        self.assertTrue(settings.MAILING_LIST_ARCHIVE_URL in review_req.review.external_url)

    def test_complete_review_link_to_mailing_list(self):
        review_req, url = self.setup_complete_review_test()

        login_testing_unauthorized(self, review_req.reviewer.person.user.username, url)

        # complete by uploading file
        empty_outbox()

        r = self.client.post(url, data={
            "result": ReviewResultName.objects.get(reviewteamresult__team=review_req.team, slug="ready").pk,
            "state": ReviewRequestStateName.objects.get(slug="completed").pk,
            "reviewed_rev": review_req.doc.rev,
            "review_submission": "link",
            "review_content": "This is a review\nwith two lines",
            "review_url": "http://example.com/testreview/",
            "review_file": "",
        })
        self.assertEqual(r.status_code, 302)

        review_req = reload_db_objects(review_req)
        self.assertEqual(review_req.state_id, "completed")

        with open(os.path.join(self.review_subdir, review_req.review.name + ".txt")) as f:
            self.assertEqual(f.read(), "This is a review\nwith two lines")

        self.assertEqual(len(outbox), 0)
        self.assertTrue("http://example.com" in review_req.review.external_url)

    def test_partially_complete_review(self):
        review_req, url = self.setup_complete_review_test()

        login_testing_unauthorized(self, review_req.reviewer.person.user.username, url)

        # partially complete
        empty_outbox()

        r = self.client.post(url, data={
            "result": ReviewResultName.objects.get(reviewteamresult__team=review_req.team, slug="ready").pk,
            "state": ReviewRequestStateName.objects.get(slug="part-completed").pk,
            "reviewed_rev": review_req.doc.rev,
            "review_submission": "enter",
            "review_content": "This is a review\nwith two lines",
        })
        self.assertEqual(r.status_code, 302)

        review_req = reload_db_objects(review_req)
        self.assertEqual(review_req.state_id, "part-completed")
        self.assertTrue(review_req.doc.rev in review_req.review.name)

        self.assertEqual(len(outbox), 2)
        self.assertTrue("secretary" in outbox[0]["To"])
        self.assertTrue("partially" in outbox[0]["Subject"].lower())
        self.assertTrue("new review request" in unicode(outbox[0]))

        self.assertTrue(review_req.team.list_email in outbox[1]["To"])
        self.assertTrue("partial review" in outbox[1]["Subject"].lower())
        self.assertTrue("This is a review" in unicode(outbox[1]))

        first_review = review_req.review
        first_reviewer = review_req.reviewer


        # complete
        review_req = ReviewRequest.objects.get(state="requested", doc=review_req.doc, team=review_req.team)
        self.assertEqual(review_req.reviewer, None)
        review_req.reviewer = first_reviewer # same reviewer, so we can test uniquification
        review_req.save()

        url = urlreverse('ietf.doc.views_review.complete_review', kwargs={ "name": review_req.doc.name, "request_id": review_req.pk })

        r = self.client.post(url, data={
            "result": ReviewResultName.objects.get(reviewteamresult__team=review_req.team, slug="ready").pk,
            "state": ReviewRequestStateName.objects.get(slug="completed").pk,
            "reviewed_rev": review_req.doc.rev,
            "review_submission": "enter",
            "review_content": "This is another review\nwith\nthree lines",
        })
        self.assertEqual(r.status_code, 302)

        review_req = reload_db_objects(review_req)
        self.assertEqual(review_req.state_id, "completed")
        self.assertTrue(review_req.doc.rev in review_req.review.name)
        second_review = review_req.review
        self.assertTrue(first_review.name != second_review.name)
        self.assertTrue(second_review.name.endswith("-2")) # uniquified
