# Copyright The IETF Trust 2011-2023, All Rights Reserved
# -*- coding: utf-8 -*-


import datetime
import email
import io
import mock
import os
import re
import sys

from io import StringIO
from pyquery import PyQuery
from typing import Tuple

from pathlib import Path

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.forms import ValidationError
from django.test import override_settings
from django.test.client import RequestFactory
from django.urls import reverse as urlreverse
from django.utils import timezone
from django.utils.encoding import force_str
import debug                            # pyflakes:ignore

from ietf.doc.factories import (DocumentFactory, WgDraftFactory, IndividualDraftFactory,
                                ReviewFactory, WgRfcFactory)
from ietf.doc.models import ( Document, DocEvent, State,
    BallotPositionDocEvent, DocumentAuthor, SubmissionDocEvent )
from ietf.doc.utils import create_ballot_if_not_open, can_edit_docextresources, update_action_holders
from ietf.group.factories import GroupFactory, RoleFactory
from ietf.group.models import Group
from ietf.group.utils import setup_default_community_list_for_group
from ietf.meeting.models import Meeting
from ietf.meeting.factories import MeetingFactory
from ietf.name.models import DraftSubmissionStateName, FormalLanguageName
from ietf.person.models import Person
from ietf.person.factories import UserFactory, PersonFactory
from ietf.submit.factories import SubmissionFactory, SubmissionExtResourceFactory
from ietf.submit.forms import SubmissionBaseUploadForm, SubmissionAutoUploadForm
from ietf.submit.models import Submission, Preapproval, SubmissionExtResource
from ietf.submit.tasks import cancel_stale_submissions, process_and_accept_uploaded_submission_task
from ietf.submit.utils import (expirable_submissions, expire_submission, find_submission_filenames,
                               post_submission, validate_submission_name, validate_submission_rev,
                               process_and_accept_uploaded_submission, SubmissionError, process_submission_text,
                               process_submission_xml, process_uploaded_submission, 
                               process_and_validate_submission, apply_yang_checker_to_draft, 
                               run_all_yang_model_checks)
from ietf.utils import tool_version
from ietf.utils.accesstoken import generate_access_token
from ietf.utils.mail import outbox, get_payload_text
from ietf.utils.test_utils import login_testing_unauthorized, TestCase
from ietf.utils.timezone import date_today
from ietf.utils.draft import PlaintextDraft


class BaseSubmitTestCase(TestCase):
    settings_temp_path_overrides = TestCase.settings_temp_path_overrides + [
        'IDSUBMIT_STAGING_PATH',
        'SUBMIT_YANG_RFC_MODEL_DIR',
        'SUBMIT_YANG_DRAFT_MODEL_DIR',
        'SUBMIT_YANG_IANA_MODEL_DIR',
        'SUBMIT_YANG_CATALOG_DIR',
        'BIBXML_BASE_PATH',
    ]

    def setUp(self):
        super().setUp()

        # The system apparently relies on these paths being equal. If they are not,
        # old drafts may not be moved out of the way properly.
        self.saved_repository_path = settings.IDSUBMIT_REPOSITORY_PATH
        settings.IDSUBMIT_REPOSITORY_PATH = settings.INTERNET_DRAFT_PATH
        os.mkdir(os.path.join(settings.BIBXML_BASE_PATH,'bibxml-ids'))

    def tearDown(self):
        settings.IDSUBMIT_REPOSITORY_PATH = self.saved_repository_path
        super().tearDown()

    @property
    def staging_dir(self):
        return settings.IDSUBMIT_STAGING_PATH

    @property
    def repository_dir(self):
        return settings.IDSUBMIT_REPOSITORY_PATH

    @property
    def archive_dir(self):
        return settings.INTERNET_DRAFT_ARCHIVE_DIR

    def post_to_upload_submission(self, *args, **kwargs):
        """POST to the upload_submission endpoint
        
        Use this instead of directly POSTing to be sure that the appropriate celery
        tasks would be queued (but are not actually queued during testing)
        """
        # Mock task so we can check that it's called without actually submitting a celery task.
        # Also mock on_commit() because otherwise the test transaction prevents the call from
        # ever being made.
        with mock.patch("ietf.submit.views.process_uploaded_submission_task") as mocked_task:
            with mock.patch("ietf.submit.views.transaction.on_commit", side_effect=lambda x: x()):
                response = self.client.post(*args, **kwargs)
        if response.status_code == 302:
            # A 302 indicates we're being redirected to the status page, meaning the upload
            # was accepted. Check that the task would have been queued.
            self.assertTrue(mocked_task.delay.called)
        else:
            self.assertFalse(mocked_task.delay.called)
        return response


def submission_file_contents(name_in_doc, group, templatename, author=None, email=None, title=None, year=None, ascii=True):
    _today = date_today()
    # construct appropriate text draft
    f = io.open(os.path.join(settings.BASE_DIR, "submit", templatename))
    template = f.read()
    f.close()

    if author is None:
        author = PersonFactory()
    if email is None:
        email = author.email().address.lower() if author.email() else None
    if title is None:
        title = "Test Document"
    if year is None:
        year = _today.strftime("%Y")

    # extract_authors() cuts the author line off at the first space past 80 characters
    # very long factory-generated names can hence be truncated, causing a failure
    # ietf/submit/test_submission.txt was changed so that 37-character names and shorter will work
    # this may need further adjustment if longer names still cause failures
    submission_text = template % dict(
            date=_today.strftime("%d %B %Y"),
            expiration=(_today + datetime.timedelta(days=100)).strftime("%d %B, %Y"),
            year=year,
            month=_today.strftime("%B"),
            day=_today.strftime("%d"),
            name=name_in_doc,
            group=group or "",
            author=author.ascii if ascii else author.name,
            asciiAuthor=author.ascii,
            initials=author.initials(),
            surname=author.ascii_parts()[3] if ascii else author.name_parts()[3],
            firstpagename=f"{author.initials()} {author.ascii_parts()[3] if ascii else author.name_parts()[3]}",
            asciiSurname=author.ascii_parts()[3],
            email=email,
            title=title,
    )
    return submission_text, author


def submission_file(name_in_doc, name_in_post, group, templatename, author=None, email=None, title=None, year=None, ascii=True):
    submission_text, author = submission_file_contents(
        name_in_doc, group, templatename, author, email, title, year, ascii
    )
    file = StringIO(submission_text)
    file.name = name_in_post
    return file, author


def create_draft_submission_with_rev_mismatch(rev='01'):
    """Create a draft and submission with mismatched version

    Creates a rev '00' draft and Submission / SubmissionDocEvent in the 'posted'
    state with the requested rev.
    """
    draft_name = 'draft-authorname-testing-tests'
    author = PersonFactory()

    # draft with rev 00
    draft = IndividualDraftFactory(
        name=draft_name,
        authors=[author],
        rev='00',
    )

    # submission with rev mismatched to the draft
    sub = Submission.objects.create(
        name=draft_name,
        group=None,
        submission_date=date_today() - datetime.timedelta(days=1),
        rev=rev,
        state_id='posted',
    )
    SubmissionDocEvent.objects.create(
        doc=draft,
        submission=sub,
        by=author,
        desc='Existing SubmissionDocEvent with mismatched revision',
        rev=sub.rev,
    )
    return draft, sub


class ManualSubmissionTests(TestCase):
    def test_manualpost_view(self):
        submission = SubmissionFactory(state_id="manual")
        url = urlreverse("ietf.submit.views.manualpost")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertIn(
            urlreverse(
                "ietf.submit.views.submission_status", 
                kwargs=dict(submission_id=submission.pk)
            ),
            q("#manual.submissions td a").attr("href")
        )
        self.assertIn(
            submission.name,
            q("#manual.submissions td a").text()
        )

    def test_manualpost_cancel(self):
        pass

class SubmitTests(BaseSubmitTestCase):
    def setUp(self):
        super().setUp()
        (Path(settings.FTP_DIR) / "internet-drafts").mkdir()
        # Submit views assume there is a "next" IETF to look for cutoff dates against
        MeetingFactory(type_id='ietf', date=date_today()+datetime.timedelta(days=180))

    def create_and_post_submission(self, name, rev, author, group=None, formats=("txt",), base_filename=None, ascii=True):
        """Helper to create and post a submission

        If base_filename is None, defaults to 'test_submission'.
        """
        url = urlreverse('ietf.submit.views.upload_submission')
        files = dict()

        for format in formats:
            fn = '.'.join((base_filename or 'test_submission', format))
            files[format], __ = submission_file(f'{name}-{rev}', f'{name}-{rev}.{format}', group, fn, author=author, ascii=ascii)

        r = self.post_to_upload_submission(url, files)
        if r.status_code == 302:
            # A redirect means the upload was accepted and queued for processing
            process_submission = True
            last_submission = Submission.objects.order_by("-pk").first()
            self.assertEqual(last_submission.state_id, "validating")
        else:
            process_submission = False
            q = PyQuery(r.content)
            print(q('div.invalid-feedback').text())
        self.assertNoFormPostErrors(r, ".invalid-feedback,.alert-danger")
        
        # Now process the submission like the task would do
        if process_submission:
            process_uploaded_submission(Submission.objects.order_by('-pk').first())
            for format in formats:
                self.assertTrue(os.path.exists(os.path.join(self.staging_dir, "%s-%s.%s" % (name, rev, format))))
                if format == 'xml':
                    self.assertTrue(os.path.exists(os.path.join(self.staging_dir, "%s-%s.%s" % (name, rev, 'html'))))
        return r

    def do_submission(self, name, rev, group=None, formats: Tuple[str, ...]=("txt",), author=None, base_filename=None, ascii=True):
        """Simulate uploading a draft and waiting for validation results
        
        Returns the "full access" status URL and the author associated with the submitted draft.
        """
        # break early in case of missing configuration
        self.assertTrue(os.path.exists(settings.IDSUBMIT_IDNITS_BINARY))

        # get
        url = urlreverse('ietf.submit.views.upload_submission')
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('input[type=file][name=txt]')), 1)
        self.assertEqual(len(q('input[type=file][name=xml]')), 1)

        # submit
        if author is None:
            author = PersonFactory()
        r = self.create_and_post_submission(
            name=name, rev=rev, author=author, group=group, formats=formats, base_filename=base_filename, ascii=ascii
        )
        status_url = r["Location"]

        self.assertEqual(Submission.objects.filter(name=name).count(), 1)
        submission = Submission.objects.get(name=name)
        if len(submission.authors) != 1:
            sys.stderr.write("\nAuthor extraction failure.\n")
            sys.stderr.write(force_str("Author name used in test: %s\n"%author))
            sys.stderr.write("Author ascii name: %s\n" % author.ascii)
            sys.stderr.write("Author initials: %s\n" % author.initials())
        self.assertEqual(len(submission.authors), 1)
        a = submission.authors[0]
        if ascii:
            self.assertEqual(a["name"], author.ascii_name())
        if author.email():
            self.assertEqual(a["email"], author.email().address.lower())
        self.assertEqual(a["affiliation"], "Test Centre Inc.")
        self.assertEqual(a["country"], "UK")

        return status_url, author

    def supply_extra_metadata(self, name, status_url, submitter_name, submitter_email, replaces, extresources=None):
        # check the page
        r = self.client.get(status_url)
        q = PyQuery(r.content)
        post_button = q('[type=submit]:contains("Post")')
        self.assertEqual(len(post_button), 1)
        action = post_button.parents("form").find('input[type=hidden][name="action"]').val()

        post_data = {
            "action": action,
            "submitter-name": submitter_name,
            "submitter-email": submitter_email,
            "replaces": replaces,
            'resources': '\n'.join(r.to_form_entry_str() for r in extresources) if extresources else '',
        }

        # post submitter info
        r = self.client.post(status_url, post_data)

        if r.status_code == 302:
            submission = Submission.objects.get(name=name)
            self.assertEqual(submission.submitter, email.utils.formataddr((submitter_name, submitter_email)))
            self.assertEqual([] if submission.replaces == "" else submission.replaces.split(','),
                             [ d.name for d in Document.objects.filter(pk__in=replaces) ])
            self.assertCountEqual(
                [str(r) for r in submission.external_resources.all()],
                [str(r) for r in extresources] if extresources else [],
            )
        return r

    def extract_confirmation_url(self, confirmation_email):
        # dig out confirmation_email link
        msg = get_payload_text(confirmation_email)
        line_start = "http"
        confirmation_url = None
        for line in msg.split("\n"):
            if line.strip().startswith(line_start):
                confirmation_url = line.strip()
        self.assertTrue(confirmation_url)

        return confirmation_url

    def verify_bibxml_ids_creation(self, draft):
        # for name in (draft.name, draft.name[6:]):
        #     ref_file_name = os.path.join(os.path.join(settings.BIBXML_BASE_PATH, 'bibxml-ids'), 'reference.I-D.%s.xml' % (name, ))
        #     self.assertTrue(os.path.exists(ref_file_name))
        #     ref_rev_file_name = os.path.join(os.path.join(settings.BIBXML_BASE_PATH, 'bibxml-ids'), 'reference.I-D.%s-%s.xml' % (name, draft.rev ))
        #     self.assertTrue(os.path.exists(ref_rev_file_name))
        ref_rev_file_name = os.path.join(os.path.join(settings.BIBXML_BASE_PATH, 'bibxml-ids'), 'reference.I-D.%s-%s.xml' % (draft.name, draft.rev ))
        self.assertTrue(os.path.exists(ref_rev_file_name))


    def submit_new_wg(self, formats):
        # submit new -> supply submitter info -> approve
        GroupFactory(type_id='wg',acronym='ames')
        mars = GroupFactory(type_id='wg', acronym='mars')
        RoleFactory(name_id='chair', group=mars, person__user__username='marschairman')
        draft = WgDraftFactory(group=mars)
        setup_default_community_list_for_group(draft.group)

        # prepare draft to suggest replace
        sug_replaced_draft = Document.objects.create(
            name="draft-ietf-ames-sug-replaced",
            time=timezone.now(),
            type_id="draft",
            title="Draft to be suggested to be replaced",
            stream_id="ietf",
            group=Group.objects.get(acronym="ames"),
            abstract="Blahblahblah.",
            rev="01",
            pages=2,
            words=100,
            intended_std_level_id="ps",
            ad=draft.ad,
            expires=timezone.now() + datetime.timedelta(days=settings.INTERNET_DRAFT_DAYS_TO_EXPIRE),
            notify="aliens@example.mars",
        )
        sug_replaced_draft.set_state(State.objects.get(used=True, type="draft", slug="active"))

        name = "draft-ietf-mars-testing-tests"
        rev = "00"
        group = "mars"

        status_url, author = self.do_submission(name, rev, group, formats)

        # supply submitter info, then draft should be in and ready for approval
        mailbox_before = len(outbox)
        r = self.supply_extra_metadata(name, status_url, author.ascii, author.email().address.lower(),
                                       replaces=[str(draft.pk), str(sug_replaced_draft.pk)])

        self.assertEqual(r.status_code, 302)
        status_url = r["Location"]
        self.assertEqual(len(outbox), mailbox_before + 1)
        self.assertTrue("New Internet-Draft waiting for approval" in outbox[-1]["Subject"])
        self.assertTrue(name in outbox[-1]["Subject"])

        # as chair of WG, we should see approval button
        self.client.login(username="marschairman", password="marschairman+password")

        r = self.client.get(status_url)
        self.assertEqual(r.status_code, 200)

        self.assertContains(r, 'xym')
        self.assertContains(r, 'pyang')
        if settings.SUBMIT_YANGLINT_COMMAND and os.path.exists(settings.YANGLINT_BINARY):
            self.assertContains(r, 'yanglint')

        q = PyQuery(r.content)
        approve_button = q('[type=submit]:contains("Approve")')
        self.assertEqual(len(approve_button), 1)

        action = approve_button.parents("form").find('input[type=hidden][name="action"]').val()

        # approve submission
        mailbox_before = len(outbox)
        r = self.client.post(status_url, dict(action=action))
        self.assertEqual(r.status_code, 302)

        draft = Document.objects.get(name=name)
        self.assertEqual(draft.rev, rev)
        new_revision = draft.latest_event(type="new_revision")
        self.assertEqual(draft.group.acronym, "mars")
        self.assertEqual(new_revision.type, "new_revision")
        self.assertEqual(new_revision.by.name, author.name)
        self.assertTrue(draft.latest_event(type="added_suggested_replaces"))
        self.assertTrue(not os.path.exists(os.path.join(self.staging_dir, "%s-%s.txt" % (name, rev))))
        self.assertTrue(os.path.exists(os.path.join(self.repository_dir, "%s-%s.txt" % (name, rev))))
        self.assertEqual(draft.type_id, "draft")
        self.assertEqual(draft.stream_id, "ietf")
        self.assertTrue(draft.expires >= timezone.now() + datetime.timedelta(days=settings.INTERNET_DRAFT_DAYS_TO_EXPIRE - 1))
        self.assertEqual(draft.get_state("draft-stream-%s" % draft.stream_id).slug, "wg-doc")
        authors = draft.documentauthor_set.all()
        self.assertEqual(len(authors), 1)
        self.assertEqual(authors[0].person, author)
        self.assertEqual(set(draft.formal_languages.all()), set(FormalLanguageName.objects.filter(slug="json")))
        self.assertEqual(draft.relations_that_doc("replaces").count(), 1)
        self.assertTrue(draft.relations_that_doc("replaces").first().target, draft)
        self.assertEqual(draft.relations_that_doc("possibly-replaces").count(), 1)
        self.assertTrue(draft.relations_that_doc("possibly-replaces").first().target, sug_replaced_draft)
        self.assertEqual(len(outbox), mailbox_before + 5)
        self.assertIn(("I-D Action: %s" % name), outbox[-4]["Subject"])
        self.assertIn(author.ascii, get_payload_text(outbox[-4]))
        self.assertIn(("I-D Action: %s" % name), outbox[-3]["Subject"])
        self.assertIn(author.ascii, get_payload_text(outbox[-3]))
        self.assertIn("New Version Notification",outbox[-2]["Subject"])
        self.assertIn(name, get_payload_text(outbox[-2]))
        self.assertIn("mars", get_payload_text(outbox[-2]))
        self.assertIn(settings.IETF_ID_ARCHIVE_URL, get_payload_text(outbox[-2]))
        # Check "Review of suggested possible replacements for..." mail
        self.assertIn("review", outbox[-1]["Subject"].lower())
        self.assertIn(name, get_payload_text(outbox[-1]))
        self.assertIn(sug_replaced_draft.name, get_payload_text(outbox[-1]))
        self.assertIn("ames-chairs@", outbox[-1]["To"].lower())
        self.assertIn("mars-chairs@", outbox[-1]["To"].lower())
        # Check submission settings
        self.assertEqual(draft.submission().xml_version, "3" if 'xml' in formats else None)

        # fetch the document page
        url = urlreverse('ietf.doc.views_doc.document_main', kwargs={'name':name})
        r = self.client.get(url)
        self.assertContains(r, name)
        self.assertContains(r, 'Active Internet-Draft')
        self.assertContains(r, 'mars WG')
        self.assertContains(r, 'Yang Validation')
        self.assertContains(r, 'WG Document')

        self.verify_bibxml_ids_creation(draft)

    def test_submit_new_wg_txt(self):
        self.submit_new_wg(["txt"])

    def test_submit_new_wg_xml(self):
        self.submit_new_wg(["xml"])

    def test_submit_new_wg_txt_xml(self):
        self.submit_new_wg(["txt", "xml"])

    def test_submit_new_wg_as_author(self):
        """A new WG submission by a logged-in author needs chair approval"""
        # submit new -> supply submitter info -> approve
        mars = GroupFactory(type_id='wg', acronym='mars')
        draft = WgDraftFactory(group=mars)
        setup_default_community_list_for_group(draft.group)

        name = "draft-ietf-mars-testing-tests"
        rev = "00"
        group = "mars"

        status_url, author = self.do_submission(name, rev, group)
        username = author.user.email

        # supply submitter info, then draft should be in and ready for approval
        mailbox_before = len(outbox)
        self.client.login(username=username, password=username+'+password')  # log in as the author
        r = self.supply_extra_metadata(name, status_url, author.ascii, author.email().address.lower(), replaces=[])
        self.assertEqual(r.status_code, 302)
        status_url = r["Location"]

        # Draft should be in the 'grp-appr' state to await approval by WG chair
        submission = Submission.objects.get(name=name, rev=rev)
        self.assertEqual(submission.state_id, 'grp-appr')

        # Approval request notification should be sent to the WG chair
        self.assertEqual(len(outbox), mailbox_before + 1)
        self.assertTrue("New Internet-Draft waiting for approval" in outbox[-1]["Subject"])
        self.assertTrue(name in outbox[-1]["Subject"])
        self.assertTrue('mars-chairs@ietf.org' in outbox[-1]['To'])

        # Status page should show that group chair approval is needed
        r = self.client.get(status_url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'The submission is pending approval by the group chairs.')

    def test_submit_new_wg_as_author_bad_submitter(self):
        # submit new -> supply submitter info -> approve
        mars = GroupFactory(type_id='wg', acronym='mars')
        draft = WgDraftFactory(group=mars)
        setup_default_community_list_for_group(draft.group)

        name = "draft-ietf-mars-testing-tests"
        rev = "00"
        group = "mars"

        status_url, author = self.do_submission(name, rev, group)
        username = author.user.email

        # supply submitter info with MIME-encoded name
        self.client.login(username=username, password=username+'+password')  # log in as the author
        r = self.supply_extra_metadata(name, status_url, '=?utf-8?q?Peter_Christen_Asbj=C3=B8rnsen?=', author.email().address.lower(), replaces=[])
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'appears to be a MIME-encoded string')

    def submit_new_concluded_wg_as_author(self, group_state_id='conclude'):
        """A new concluded WG submission by a logged-in author needs AD approval"""
        mars = GroupFactory(type_id='wg', acronym='mars', state_id=group_state_id)
        draft = WgDraftFactory(group=mars)
        setup_default_community_list_for_group(draft.group)

        name = "draft-ietf-mars-testing-tests"
        rev = "00"
        group = "mars"

        status_url, author = self.do_submission(name, rev, group)
        username = author.user.email

        # Should receive an error because group is not active
        self.client.login(username=username, password=username+'+password')  # log in as the author
        r = self.client.get(status_url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Group exists but is not an active group')
        q = PyQuery(r.content)
        post_button = q('[type=submit]:contains("Post")')
        self.assertEqual(len(post_button), 0)  # no UI option to post the submission in this state
        
        # Try to post anyway
        r = self.client.post(status_url,
                             {'submitter-name': author.name, 
                              'submitter-email': username, 
                              'action': 'autopost', 
                              'replaces': []})
        # Attempt should fail and draft should remain in the uploaded state
        self.assertEqual(r.status_code, 403)
        submission = Submission.objects.get(name=name, rev=rev)
        self.assertEqual(submission.state_id, 'uploaded')

    def test_submit_new_concluded_wg_as_author(self):
        self.submit_new_concluded_wg_as_author()

    def test_submit_new_bofconc_wg_as_author(self):
        self.submit_new_concluded_wg_as_author('bof-conc')

    def test_submit_new_replaced_wg_as_author(self):
        self.submit_new_concluded_wg_as_author('replaced')

    def test_submit_new_wg_with_extresources(self):
        self.submit_new_draft_with_extresources(group=GroupFactory())

    def submit_existing(self, formats, change_authors=True, group_type='wg', stream_type='ietf'):
        # submit new revision of existing -> supply submitter info -> prev authors confirm

        def _assert_authors_are_action_holders(draft, expect=True):
            for author in draft.authors():
                if expect:
                    self.assertIn(author, draft.action_holders.all())
                else:
                    self.assertNotIn(author, draft.action_holders.all())

        if stream_type == 'ietf':
            ad = Person.objects.get(user__username='ad')
            if group_type == 'area':
                group = GroupFactory(type_id='area', acronym='mars')
                RoleFactory(name_id='ad', group=group, person=ad)
            else:
                area = GroupFactory(type_id='area')
                RoleFactory(name_id='ad',group=area,person=ad)
                group = GroupFactory(type_id=group_type, parent=area, acronym='mars')
            draft = DocumentFactory(type_id='draft', group=group, stream_id=stream_type, ad=ad, authors=PersonFactory.create_batch(1))
            wg_doc_state = State.objects.get(type_id='draft-stream-ietf',slug='wg-doc')
            draft.set_state(wg_doc_state)
            update_action_holders(draft, new_state=wg_doc_state)

            # pretend IANA reviewed it
            not_ok_state = State.objects.get(used=True, type="draft-iana-review", slug="not-ok")
            draft.set_state(not_ok_state)
            update_action_holders(
                draft,
                prev_state=State.objects.get(used=True, type="draft-iana-review", slug="changed"),
                new_state=not_ok_state,
            )

            # pretend it was approved to check that we notify the RFC Editor
            e = DocEvent(type="iesg_approved", doc=draft, rev=draft.rev)
            e.time = draft.time
            e.by = Person.objects.get(name="(System)")
            e.desc = "The IESG approved the document"
            e.save()

            # make a discuss to see if the AD gets an email
            ad = Person.objects.get(user__username="ad")
            ballot = create_ballot_if_not_open(None, draft, ad, 'approve')
            ballot_position = BallotPositionDocEvent()
            ballot_position.ballot = ballot
            ballot_position.pos_id = "discuss"
            ballot_position.type = "changed_ballot_position"
            ballot_position.doc = draft
            ballot_position.rev = draft.rev
            ballot_position.balloter = ballot_position.by = Person.objects.get(user__username="ad2")
            ballot_position.save()

        elif stream_type == 'irtf':
            group = GroupFactory(type_id='rg', parent=Group.objects.get(acronym='irtf'), acronym='mars')
            draft = DocumentFactory(type_id='draft', group=group, stream_id='irtf', authors=PersonFactory.create_batch(1))

        else:
            draft = IndividualDraftFactory(stream_id=stream_type, authors=PersonFactory.create_batch(1))
            
        prev_author = draft.documentauthor_set.all()[0]
        if change_authors:
            # Make it such that one of the previous authors has an invalid email address
            nomail_author = PersonFactory()
            email = nomail_author.email()
            email.address='unknown-email-%s' % nomail_author.plain_ascii().replace(' ', '-')
            email.save()
            DocumentAuthor.objects.create(document=draft, person=nomail_author, email=email, order=draft.documentauthor_set.latest('order').order+1)

        # Set the revision needed tag
        draft.tags.add("need-rev")
        update_action_holders(draft, new_tags=draft.tags.all())

        name = draft.name
        rev = "%02d" % (int(draft.rev) + 1)
        group = draft.group

        # write the old draft in a file so we can check it's moved away
        old_rev = draft.rev
        with io.open(os.path.join(self.repository_dir, "%s-%s.txt" % (name, old_rev)), 'w') as f:
            f.write("a" * 2000)

        old_docevents = list(draft.docevent_set.all())
        _assert_authors_are_action_holders(draft, True)  # authors should be action holders prior to the test

        status_url, author = self.do_submission(name, rev, group, formats, author=prev_author.person)

        _assert_authors_are_action_holders(draft, True)  # still waiting for author confirmation

        # supply submitter info, then previous authors get a confirmation email
        mailbox_before = len(outbox)
        r = self.supply_extra_metadata(name, status_url, "Submitter Name", "submitter@example.com", replaces=[])
        self.assertEqual(r.status_code, 302)
        status_url = r["Location"]
        r = self.client.get(status_url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "The submission is pending approval by the authors")
        _assert_authors_are_action_holders(draft, True)  # still waiting for author confirmation

        self.assertEqual(len(outbox), mailbox_before + 1)
        confirm_email = outbox[-1]
        self.assertTrue("Confirm submission" in confirm_email["Subject"])
        self.assertTrue(name in confirm_email["Subject"])
        self.assertTrue(prev_author.email.address in confirm_email["To"])
        if change_authors:
            self.assertTrue("author@example.com" not in confirm_email["To"])
        self.assertTrue("submitter@example.com" not in confirm_email["To"])
        # Verify that mail wasn't sent to know invalid addresses
        self.assertTrue("unknown-email-" not in confirm_email["To"])
        if change_authors:
            # Since authors changed, ensure chairs are copied (and that the message says why)
            self.assertTrue("chairs have been copied" in str(confirm_email))
            if group_type in ['wg','rg','ag','rag']:
                self.assertTrue("mars-chairs@" in confirm_email["To"].lower())
            elif group_type == 'area':
                self.assertTrue("aread@" in confirm_email["To"].lower())
            else:
                pass
            if stream_type=='ise':
               self.assertTrue("rfc-ise@" in confirm_email["To"].lower())
        else:
            self.assertNotIn("chairs have been copied", str(confirm_email))
            self.assertNotIn("mars-chairs@", confirm_email["To"].lower())

        confirmation_url = self.extract_confirmation_url(confirm_email)

        # go to confirm page
        r = self.client.get(confirmation_url)
        q = PyQuery(r.content)
        self.assertEqual(len(q('[type=submit]:contains("Confirm")')), 1)

        # confirm
        mailbox_before = len(outbox)
        r = self.client.post(confirmation_url, {'action':'confirm'})
        self.assertEqual(r.status_code, 302)

        new_docevents = draft.docevent_set.exclude(pk__in=[event.pk for event in old_docevents])
        _assert_authors_are_action_holders(draft, False)  # confirmed and posted, authors no longer hold action

        # check we have document events 
        doc_events = new_docevents.filter(type__in=["new_submission", "added_comment"])
        edescs = '::'.join([x.desc for x in doc_events])
        self.assertTrue('New version approved' in edescs)
        self.assertTrue('Uploaded new revision' in edescs)

        draft = Document.objects.get(name=name)
        self.assertEqual(draft.rev, rev)
        self.assertEqual(draft.group.acronym, name.split("-")[2])
        #
        docevents = list(new_docevents.order_by("-time", "-id"))
        # Latest events are first (this is the default, but we make it explicit)

        def inspect_docevents(docevents, event_delta, event_type, be_in_desc, by_name):
            self.assertEqual(docevents[event_delta].type, event_type,
                             'Unexpected event type for event_delta={}'.format(event_delta))
            self.assertIn(be_in_desc, docevents[event_delta].desc,
                          'Expected text not found for event_delta={}'.format(event_delta))
            self.assertEqual(docevents[event_delta].by.name, by_name,
                             'Unexpected name for event_delta={}'.format(event_delta))
            if len(docevents) > event_delta + 1:
                self.assertGreater(docevents[event_delta].id, docevents[event_delta+1].id,
                                   'Event out of order for event_delta={}'.format(event_delta))

        # Assert event content in chronological order:
        if draft.stream_id == 'ietf':
            expected_docevents = [
                ("new_submission", "Uploaded new revision", "Submitter Name"),
                ("new_submission", "Request for posting confirmation", "(System)"),
                ("new_submission", "New version approved", "(System)"),
                ("new_revision", "New version available", "Submitter Name"),
                ("changed_state", "IANA Review", "(System)"),
                ("changed_document", "AD Followup", "(System)"),
                ("changed_action_holders", "IESG state changed", "(System)"),
            ]
        elif draft.stream_id in ('ise', 'irtf', 'iab'):
            expected_docevents = [
                ("new_submission", "Uploaded new revision", "Submitter Name"),
                ("new_submission", "Request for posting confirmation", "(System)"),
                ("new_submission", "New version approved", "(System)"),
                ("new_revision", "New version available", "Submitter Name"),
                ("changed_document", "tag cleared", "(System)"),
                ("changed_action_holders", "IESG state changed", "(System)"),
            ]
        else:
            expected_docevents = []  # empty list will skip the docevent test entirely

        # go through event list in reverse so newest gets index 0
        for event_delta, (event_type, be_in_desc, by_name) in enumerate(expected_docevents[::-1]):
            inspect_docevents(docevents, event_delta, event_type, be_in_desc, by_name)

        self.assertTrue(not os.path.exists(os.path.join(self.repository_dir, "%s-%s.txt" % (name, old_rev))))
        self.assertTrue(os.path.exists(os.path.join(self.archive_dir, "%s-%s.txt" % (name, old_rev))))
        self.assertTrue(not os.path.exists(os.path.join(self.staging_dir, "%s-%s.txt" % (name, rev))))
        self.assertTrue(os.path.exists(os.path.join(self.repository_dir, "%s-%s.txt" % (name, rev))))
        self.assertEqual(draft.type_id, "draft")
        if stream_type == 'ietf':
            self.assertEqual(draft.stream_id, "ietf")
            self.assertEqual(draft.get_state_slug("draft-stream-%s" % draft.stream_id), "wg-doc")
            self.assertEqual(draft.get_state_slug("draft-iana-review"), "changed")
        authors = draft.documentauthor_set.all()
        self.assertEqual(len(authors), 1)
        self.assertIn(author, [ a.person for a in authors ])
        self.assertEqual(len(outbox), mailbox_before + 3)
        self.assertTrue(("I-D Action: %s" % name) in outbox[-3]["Subject"])
        self.assertTrue(("I-D Action: %s" % name) in draft.message_set.order_by("-time")[0].subject)
        self.assertTrue(author.ascii in get_payload_text(outbox[-3]))
        self.assertTrue("i-d-announce@" in outbox[-3]['To'])
        self.assertTrue("New Version Notification" in outbox[-2]["Subject"])
        self.assertTrue(name in get_payload_text(outbox[-2]))
        interesting_address = {'ietf':'mars', 'irtf':'irtf-chair', 'iab':'iab-chair', 'ise':'rfc-ise'}[draft.stream_id]
        self.assertTrue(interesting_address in force_str(outbox[-2].as_string()))
        if draft.stream_id == 'ietf':
            self.assertTrue(draft.ad.role_email("ad").address in force_str(outbox[-2].as_string()))
            self.assertTrue(ballot_position.balloter.role_email("ad").address in force_str(outbox[-2].as_string()))
        self.assertTrue("New Version Notification" in outbox[-1]["Subject"])
        self.assertTrue(name in get_payload_text(outbox[-1]))
        r = self.client.get(urlreverse('ietf.doc.views_search.recent_drafts'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, draft.name)
        self.assertContains(r, draft.title)
        # Check submission settings
        self.assertEqual(draft.submission().xml_version, "3" if 'xml' in formats else None)
        self.verify_bibxml_ids_creation(draft)

    def test_submit_existing_txt(self):
        self.submit_existing(["txt"])

    def test_submit_existing_xml(self):
        self.submit_existing(["xml"])

    def test_submit_existing_txt_xml(self):
        self.submit_existing(["txt", "xml"])

    def test_submit_existing_txt_preserve_authors(self):
        self.submit_existing(["txt"], change_authors=False)

    def test_submit_existing_wg_with_extresources(self):
        self.submit_existing_with_extresources(group_type='wg')

    def test_submit_existing_rg(self):
        self.submit_existing(["txt"],group_type='rg', stream_type='irtf')

    def test_submit_existing_rg_with_extresources(self):
        self.submit_existing_with_extresources(group_type='rg', stream_type='irtf')

    def test_submit_existing_ag(self):
        self.submit_existing(["txt"],group_type='ag')

    def test_submit_existing_ag_with_extresources(self):
        self.submit_existing_with_extresources(group_type='ag')

    def test_submit_existing_area(self):
        self.submit_existing(["txt"],group_type='area')

    def test_submit_existing_area_with_extresources(self):
        self.submit_existing_with_extresources(group_type='area')

    def test_submit_existing_ise(self):
        self.submit_existing(["txt"],stream_type='ise', group_type='individ')

    def test_submit_existing_ise_with_extresources(self):
        self.submit_existing_with_extresources(stream_type='ise', group_type='individ')

    def test_submit_existing_iab(self):
        self.submit_existing(["txt"],stream_type='iab', group_type='individ')

    def do_submit_existing_concluded_wg_test(self, group_state_id='conclude', submit_as_author=False):
        """A revision to an existing WG draft should go to AD for approval if WG is not active"""
        ad = Person.objects.get(user__username='ad')
        area = GroupFactory(type_id='area')
        RoleFactory(name_id='ad', group=area, person=ad)
        group = GroupFactory(type_id='wg', state_id=group_state_id, parent=area, acronym='mars')
        author = PersonFactory()
        draft = WgDraftFactory(group=group, authors=[author])
        draft.set_state(State.objects.get(type_id='draft-stream-ietf', slug='wg-doc'))

        name = draft.name
        rev = "%02d" % (int(draft.rev) + 1)

        if submit_as_author:
            username = author.user.email
            self.client.login(username=username, password=username + '+password')
        status_url, author = self.do_submission(name, rev, group, author=author)
        mailbox_before = len(outbox)

        # Try to post anyway
        r = self.client.post(status_url,
                             {'submitter-name': author.name,
                              'submitter-email': 'submitter@example.com',
                              'action': 'autopost',
                              'replaces': []})
        self.assertEqual(r.status_code, 302)
        status_url = r["Location"]

        # Draft should be in the 'ad-appr' state to await approval
        submission = Submission.objects.get(name=name, rev=rev)
        self.assertEqual(submission.state_id, 'ad-appr')

        # Approval request notification should be sent to the AD for the group
        self.assertEqual(len(outbox), mailbox_before + 1)
        self.assertTrue("New Internet-Draft waiting for approval" in outbox[-1]["Subject"])
        self.assertTrue(name in outbox[-1]["Subject"])
        self.assertTrue(ad.user.email in outbox[-1]['To'])

        # Status page should show that AD approval is needed
        r = self.client.get(status_url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'The submission is pending approval by the area director.')

    def test_submit_existing_concluded_wg(self):
        self.do_submit_existing_concluded_wg_test()

    def test_submit_existing_concluded_wg_as_author(self):
        self.do_submit_existing_concluded_wg_test(submit_as_author=True)

    def test_submit_existing_bofconc_wg(self):
        self.do_submit_existing_concluded_wg_test(group_state_id='bof-conc')

    def test_submit_existing_bofconc_wg_as_author(self):
        self.do_submit_existing_concluded_wg_test(group_state_id='bof-conc', submit_as_author=True)

    def test_submit_existing_replaced_wg(self):
        self.do_submit_existing_concluded_wg_test(group_state_id='replaced')

    def test_submit_existing_replaced_wg_as_author(self):
        self.do_submit_existing_concluded_wg_test(group_state_id='replaced', submit_as_author=True)

    def test_submit_existing_iab_with_extresources(self):
        self.submit_existing_with_extresources(stream_type='iab', group_type='individ')

    def submit_new_individual(self, formats):
        # submit new -> supply submitter info -> confirm

        name = "draft-authorname-testing-tests"
        rev = "00"
        group = None

        status_url, author = self.do_submission(name, rev, group, formats)

        # supply submitter info, then draft should be be ready for email auth
        mailbox_before = len(outbox)
        r = self.supply_extra_metadata(name, status_url, "Submitter Name", "submitter@example.com", replaces=[])

        self.assertEqual(r.status_code, 302)
        status_url = r["Location"]
        r = self.client.get(status_url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "The submission is pending email authentication")
        self._assert_extresources_in_table(r, [])
        self._assert_extresources_form_not_present(r)

        self.assertEqual(len(outbox), mailbox_before + 1)
        confirm_email = outbox[-1]
        self.assertTrue("Confirm submission" in confirm_email["Subject"])
        self.assertTrue(name in confirm_email["Subject"])
        # both submitter and author get email
        self.assertTrue(author.email().address.lower() in confirm_email["To"])
        self.assertTrue("submitter@example.com" in confirm_email["To"])
        self.assertFalse("chairs have been copied" in str(confirm_email))

        confirmation_url = self.extract_confirmation_url(outbox[-1])

        # go to confirm page
        r = self.client.get(confirmation_url)
        q = PyQuery(r.content)
        self.assertEqual(len(q('[type=submit]:contains("Confirm")')), 1)

        # confirm
        mailbox_before = len(outbox)
        r = self.client.post(confirmation_url, {'action':'confirm'})
        self.assertEqual(r.status_code, 302)

        draft = Document.objects.get(name=name)
        self.assertEqual(draft.rev, rev)
        new_revision = draft.latest_event()
        self.assertEqual(new_revision.type, "new_revision")
        self.assertEqual(new_revision.by.name, "Submitter Name")
        self.verify_bibxml_ids_creation(draft)

        repository_path = Path(draft.get_file_name())
        self.assertTrue(repository_path.exists()) # Note that this doesn't check that it has the right _content_
        ftp_path = Path(settings.FTP_DIR) / "internet-drafts" / repository_path.name
        self.assertTrue(repository_path.samefile(ftp_path))
        all_archive_path = Path(settings.INTERNET_ALL_DRAFTS_ARCHIVE_DIR) / repository_path.name
        self.assertTrue(repository_path.samefile(all_archive_path))
        for ext in settings.IDSUBMIT_FILE_TYPES:
            if ext == "txt":
                continue
            variant_path = repository_path.parent / f"{repository_path.stem}.{ext}"
            if variant_path.exists():
                variant_ftp_path = Path(settings.FTP_DIR) / "internet-drafts" / variant_path.name
                self.assertTrue(variant_path.samefile(variant_ftp_path))
                variant_all_archive_path = Path(settings.INTERNET_ALL_DRAFTS_ARCHIVE_DIR) / variant_path.name
                self.assertTrue(variant_path.samefile(variant_all_archive_path))



    def test_submit_new_individual_txt(self):
        self.submit_new_individual(["txt"])

    def test_submit_new_individual_xml(self):
        self.submit_new_individual(["xml"])

    def test_submit_new_individual_xml_no_next_meeting(self):
        Meeting.objects.all().delete()
        self.submit_new_individual(["xml"])

    def test_submit_new_individual_txt_xml(self):
        self.submit_new_individual(["txt", "xml"])

    def submit_new_draft_no_org_or_address(self, formats):
        name = 'draft-testing-no-org-or-address'

        author = PersonFactory()
        self.client.login(username='secretary', password='secretary+password')
        r = self.create_and_post_submission(
            name, '00', author, formats=formats, base_filename='test_submission_no_org_or_address'
        )
        status_url = r['Location']
        r = self.supply_extra_metadata(name, status_url, 'Submitter name', 'submitter@example.com', replaces=[])
        self.assertEqual(r.status_code, 302)

        # force post of submission
        r = self.client.get(status_url)
        q = PyQuery(r.content)
        force_post_button = q('[type=submit]:contains("Force post")')
        self.assertEqual(len(force_post_button), 1)
        action = force_post_button.parents("form").find('input[type=hidden][name="action"]').val()
        r = self.client.post(status_url, dict(action=action))

        doc = Document.objects.get(name=name)
        self.assertEqual(doc.documentauthor_set.count(), 1)
        docauth = doc.documentauthor_set.first()
        self.assertEqual(docauth.person, author)
        self.assertEqual(docauth.affiliation, '')
        self.assertEqual(docauth.country, '')
        self.verify_bibxml_ids_creation(doc)

    def test_submit_new_draft_no_org_or_address_txt(self):
        self.submit_new_draft_no_org_or_address(['txt'])

    def test_submit_new_draft_no_org_or_address_xml(self):
        self.submit_new_draft_no_org_or_address(['xml'])

    def test_submit_new_draft_no_org_or_address_txt_xml(self):
        self.submit_new_draft_no_org_or_address(['txt', 'xml'])

    def _assert_extresources_in_table(self, response, extresources, th_label=None):
        """Assert that external resources are properly shown on the submission_status table"""
        q = PyQuery(response.content)
        
        # Find the <th> that labels the resource list
        th = q('th:contains("%s")' % (th_label or 'Submission additional resources'))
        self.assertEqual(len(th), 1)
        
        # Find the <td> element that holds the resource list
        td_siblings = th.siblings('td')
        self.assertEqual(len(td_siblings), 1)
        td = td_siblings.eq(0)
        td_html = td.html()
        
        if extresources:
            for res in extresources:
                # If the value is present, that's good enough. Don't test the detailed format.
                self.assertIn(res.value, td_html, 'Value of resource %s not found' % (res))
        else:
            self.assertIn('None', td_html)

    def _assert_extresources_form(self, response, expected_extresources):
        """Assert that the form for editing external resources is present and has expected contents"""
        q = PyQuery(response.content)
        
        # The external resources form is currently just a text area. Find it by its ID and check
        # that it has the expected contents.
        elems = q('form textarea#id_resources')
        self.assertEqual(len(elems), 1)
        
        text_area = elems.eq(0)
        contents = text_area.text()
        if len(expected_extresources) == 0:
            self.assertEqual(contents.strip(), '')
        else:
            res_strings = [rs for rs in contents.split('\n') if len(rs.strip()) > 0]  # ignore empty lines
            self.assertCountEqual(
                res_strings,
                [r.to_form_entry_str() for r in expected_extresources],
            )

    def _assert_extresources_form_not_present(self, response):
        q=PyQuery(response.content)
        self.assertEqual(len(q('form textarea#id_resources')), 0)
        
    def _assert_extresource_change_event(self, doc, is_present=True):
        """Assert that an external resource change event is (or is not) present for the doc"""
        event = doc.latest_event(type='changed_document', desc__contains='Changed document external resources')
        if is_present:
            self.assertIsNotNone(event, 'External resource change event was not created properly')
        else:
            self.assertIsNone(event, 'External resource change event was unexpectedly created')

    def submit_new_draft_with_extresources(self, group):
        name = 'draft-testing-with-extresources'

        status_url, author = self.do_submission(name, rev='00', group=group)

        # Check that the submission starts with no external resources
        r = self.client.get(status_url)
        self.assertEqual(r.status_code, 200)
        self._assert_extresources_in_table(r, [])
        self._assert_extresources_form(r, [])

        resources = [
            SubmissionExtResource(name_id='faq', value='https://faq.example.com/'),
            SubmissionExtResource(name_id='wiki', value='https://wiki.example.com', display_name='Test Wiki'),
        ]
        r = self.supply_extra_metadata(name, status_url, 'Submitter name', 'submitter@example.com', replaces=[],
                                       extresources=resources)
        self.assertEqual(r.status_code, 302)
        status_url = r['Location']
        
        r = self.client.get(status_url)
        self.assertEqual(r.status_code, 200)
        self._assert_extresources_in_table(r, resources)
        self._assert_extresources_form_not_present(r)

    def test_submit_new_individual_with_extresources(self):
        self.submit_new_draft_with_extresources(group=None)

    def submit_new_individual_logged_in(self, formats):
        # submit new -> supply submitter info -> done

        name = "draft-authorname-testing-logged-in"
        rev = "00"
        group = None

        author = PersonFactory()
        username = author.user.email
        self.client.login(username=username, password=username+"+password")
        
        status_url, author = self.do_submission(name, rev, group, formats, author=author)

        # supply submitter info, then draft should be be ready for email auth
        mailbox_before = len(outbox)
        r = self.supply_extra_metadata(name, status_url, author.name, username, replaces=[])

        self.assertEqual(r.status_code, 302)
        status_url = r["Location"]
        r = self.client.get(status_url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "New version accepted")
        self._assert_extresources_in_table(r, [])
        self._assert_extresources_form_not_present(r)

        self.assertEqual(len(outbox), mailbox_before+2)
        announcement_email = outbox[-2]
        self.assertIn(name, announcement_email["Subject"])
        self.assertIn('I-D Action:', announcement_email["Subject"])
        self.assertIn('i-d-announce', announcement_email["To"])
        notification_email = outbox[-1]
        self.assertIn(name, notification_email["Subject"])
        self.assertIn("New Version Notification", notification_email["Subject"])
        self.assertIn(author.email().address.lower(), notification_email["To"])

        draft = Document.objects.get(name=name)
        self.assertEqual(draft.rev, rev)
        self.assertEqual(draft.docextresource_set.count(), 0)
        new_revision = draft.latest_event()
        self.assertEqual(new_revision.type, "new_revision")
        self.assertEqual(new_revision.by.name, author.name)
        self._assert_extresource_change_event(draft, is_present=False)

        # Check submission settings
        self.assertEqual(draft.submission().xml_version, "3" if 'xml' in formats else None)
        self.verify_bibxml_ids_creation(draft)

    def test_submit_new_logged_in_txt(self):
        self.submit_new_individual_logged_in(["txt"])

    def test_submit_new_logged_in_xml(self):
        self.submit_new_individual_logged_in(["xml"])

    def test_submit_new_logged_in_with_extresources(self):
        """Logged-in author of individual draft can set external resources"""
        name = 'draft-individual-testing-with-extresources'
        author = PersonFactory()
        username = author.user.email
        
        self.client.login(username=username, password=username+'+password')
        status_url, author = self.do_submission(name, rev='00', author=author)

        # Check that the submission starts with no external resources
        r = self.client.get(status_url)
        self.assertEqual(r.status_code, 200)
        self._assert_extresources_in_table(r, [])
        self._assert_extresources_form(r, [])

        resources = [
            SubmissionExtResource(name_id='faq', value='https://faq.example.com/'),
            SubmissionExtResource(name_id='wiki', value='https://wiki.example.com', display_name='Test Wiki'),
        ]
        r = self.supply_extra_metadata(name, status_url, author.name, username, replaces=[],
                                       extresources=resources)
        self.assertEqual(r.status_code, 302)
        status_url = r['Location']

        r = self.client.get(status_url)
        self.assertEqual(r.status_code, 200)
        self._assert_extresources_in_table(r, resources)
        self._assert_extresources_form_not_present(r)

        # Check that the draft itself got the resources        
        draft = Document.objects.get(name=name)
        self.assertCountEqual(
            [str(r) for r in draft.docextresource_set.all()],
            [str(r) for r in resources],
        )
        self._assert_extresource_change_event(draft, is_present=True)
        self.verify_bibxml_ids_creation(draft)

    def test_submit_update_individual(self):
        IndividualDraftFactory(name='draft-ietf-random-thing', states=[('draft','active'),('draft-iesg','approved')], pages=5)
        ad=Person.objects.get(user__username='ad')
        # Group of None here does not reflect real individual submissions
        draft = IndividualDraftFactory(group=None, ad = ad, authors=[ad,], notify='aliens@example.mars', pages=5)
        replaces_count = draft.relateddocument_set.filter(relationship_id='replaces').count()
        name = draft.name
        rev = '%02d'%(int(draft.rev)+1)
        status_url, author = self.do_submission(name,rev)
        mailbox_before = len(outbox)

        r = self.supply_extra_metadata(name, status_url, "Submitter Name", "author@example.com", replaces=[str(draft.pk)])
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'cannot replace itself')
        self._assert_extresources_in_table(r, [])
        self._assert_extresources_form(r, [])

        replaced = Document.objects.get(name='draft-ietf-random-thing')
        r = self.supply_extra_metadata(name, status_url, "Submitter Name", "author@example.com", replaces=[str(replaced.pk)])
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'approved by the IESG and cannot')
        self._assert_extresources_in_table(r, [])
        self._assert_extresources_form(r, [])

        r = self.supply_extra_metadata(name, status_url, "Submitter Name", "author@example.com", replaces=[])
        self.assertEqual(r.status_code, 302)
        status_url = r["Location"]
        r = self.client.get(status_url)
        self._assert_extresources_in_table(r, [])
        self._assert_extresources_form_not_present(r)

        self.assertEqual(len(outbox), mailbox_before + 1)
        confirmation_url = self.extract_confirmation_url(outbox[-1])
        self.assertFalse("chairs have been copied" in str(outbox[-1]))
        mailbox_before = len(outbox)
        r = self.client.post(confirmation_url, {'action':'confirm'})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(len(outbox), mailbox_before+3)
        draft = Document.objects.get(name=name)
        self.assertEqual(draft.rev, rev)
        self.assertEqual(draft.relateddocument_set.filter(relationship_id='replaces').count(), replaces_count)
        self.assertEqual(draft.docextresource_set.count(), 0)
        #
        r = self.client.get(urlreverse('ietf.doc.views_search.recent_drafts'))
        self.assertContains(r, draft.name)
        self.assertContains(r, draft.title)
        self._assert_extresource_change_event(draft, is_present=False)
        self.verify_bibxml_ids_creation(draft)

    def submit_existing_with_extresources(self, group_type, stream_type='ietf'):
        """Submit a draft with external resources
        
        Unlike some other tests in this module, does not confirm draft if this would be required.
        """
        orig_draft: Document = DocumentFactory(  # type: ignore[annotation-unchecked]
            type_id='draft',
            group=GroupFactory(type_id=group_type) if group_type else None,
            stream_id=stream_type,
        )
        name = orig_draft.name
        group = orig_draft.group
        new_rev = '%02d' % (int(orig_draft.rev) + 1)
        author: Person = PersonFactory()  # type: ignore[annotation-unchecked]
        DocumentAuthor.objects.create(person=author, document=orig_draft)
        orig_draft.docextresource_set.create(name_id='faq', value='https://faq.example.com/')
        orig_draft.docextresource_set.create(name_id='wiki', value='https://wiki.example.com', display_name='Test Wiki')
        orig_extresources = list(orig_draft.docextresource_set.all())

        status_url, _ = self.do_submission(name=name, rev=new_rev, author=author, group=group)

        # Make sure the submission status inherits the original draft's external resources
        r = self.client.get(status_url)
        self.assertEqual(r.status_code, 200)
        self._assert_extresources_in_table(r, orig_extresources)
        self._assert_extresources_form(r, orig_extresources)

        # Update with an empty set of resources
        r = self.supply_extra_metadata(orig_draft.name, status_url, author.name, author.user.email,
                                       replaces=[], extresources=[])
        self.assertEqual(r.status_code, 302)
        status_url = r['Location']

        # Should now see the submission's resources and the set currently assigned to the document        
        r = self.client.get(status_url)
        self.assertEqual(r.status_code, 200)
        self._assert_extresources_in_table(r, [])
        self._assert_extresources_in_table(r, orig_extresources, 'Current document additional resources')
        self._assert_extresources_form_not_present(r)

    def test_submit_update_individual_with_extresources(self):
        self.submit_existing_with_extresources(group_type=None, stream_type='ietf')

    def submit_new_individual_replacing_wg(self, logged_in=False, group_state_id='active', notify_ad=False):
        """Chair of an active WG should be notified if individual draft is proposed to replace a WG draft"""
        name = "draft-authorname-testing-tests"
        rev = "00"
        group = None
        status_url, author = self.do_submission(name, rev, group)

        ad = Person.objects.get(user__username='ad')
        replaced_draft = WgDraftFactory(group__state_id=group_state_id)
        RoleFactory(name_id='ad', group=replaced_draft.group.parent, person=ad)
        if logged_in:
            username = author.user.email
            self.client.login(username=username, password=username + '+password')

        mailbox_before = len(outbox)
        self.supply_extra_metadata(
            name,
            status_url,
            "Submitter Name",
            "submitter@example.com",
            replaces=[str(replaced_draft.pk)],
        )
        
        submission = Submission.objects.get(name=name, rev=rev)
        self.assertEqual(submission.state_id, 'ad-appr' if notify_ad else 'grp-appr')
        self.assertEqual(len(outbox), mailbox_before + 1)
        notice = outbox[-1]
        self.assertIn(
            ad.user.email if notify_ad else '%s-chairs@ietf.org' % replaced_draft.group.acronym,
            notice['To']
        )
        self.assertIn('New Internet-Draft waiting for approval', notice['Subject'])

    def test_submit_new_individual_replacing_wg(self):
        self.submit_new_individual_replacing_wg()

    def test_submit_new_individual_replacing_wg_logged_in(self):
        self.submit_new_individual_replacing_wg(logged_in=True)

    def test_submit_new_individual_replacing_concluded_wg(self):
        self.submit_new_individual_replacing_wg(group_state_id='conclude', notify_ad=True)

    def test_submit_new_individual_replacing_concluded_wg_logged_in(self):
        self.submit_new_individual_replacing_wg(group_state_id='conclude', notify_ad=True, logged_in=True)

    def test_submit_cancel_confirmation(self):
        ad=Person.objects.get(user__username='ad')
        # Group of None here does not reflect real individual submissions
        draft = IndividualDraftFactory(group=None, ad = ad, authors=[ad,], notify='aliens@example.mars', pages=5)
        name = draft.name
        old_rev = draft.rev
        rev = '%02d'%(int(draft.rev)+1)
        status_url, author = self.do_submission(name, rev)
        mailbox_before = len(outbox)
        r = self.supply_extra_metadata(name, status_url, "Submitter Name", "author@example.com", replaces=[])
        self.assertEqual(r.status_code, 302)
        status_url = r["Location"]
        r = self.client.get(status_url)
        self.assertEqual(len(outbox), mailbox_before + 1)
        confirmation_url = self.extract_confirmation_url(outbox[-1])
        mailbox_before = len(outbox)
        r = self.client.post(confirmation_url, {'action':'cancel'})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(len(outbox), mailbox_before)
        draft = Document.objects.get(name=name)
        self.assertEqual(draft.rev, old_rev)

    def test_submit_new_wg_with_dash(self):
        group = Group.objects.create(acronym="mars-special", name="Mars Special", type_id="wg", state_id="active")
        name = "draft-ietf-%s-testing-tests" % group.acronym
        self.create_and_post_submission(name=name, rev="00", author=PersonFactory())
        self.assertEqual(Submission.objects.get(name=name).group.acronym, group.acronym)

    def test_submit_new_wg_v2_country_only(self):
        """V2 drafts should accept addresses without street/city"""
        # break early in case of missing configuration
        self.assertTrue(os.path.exists(settings.IDSUBMIT_IDNITS_BINARY))

        # submit
        author = PersonFactory()
        group = GroupFactory()
        name = "draft-authorname-testing-tests"
        r = self.create_and_post_submission(
            name=name,
            rev='00',
            author=author,
            group=group.acronym,
            formats=('xml',),
            base_filename='test_submission_v2_country_only'
        )
        self.assertEqual(r.status_code, 302)
        submission = Submission.objects.get(name=name)
        self.assertEqual(submission.xml_version, '2')  # should reflect the submitted version

    def test_submit_new_irtf(self):
        group = Group.objects.create(acronym="saturnrg", name="Saturn", type_id="rg", state_id="active")
        name = "draft-irtf-%s-testing-tests" % group.acronym
        self.create_and_post_submission(name=name, rev="00", author=PersonFactory())
        submission = Submission.objects.get(name=name)
        self.assertEqual(submission.group.acronym, group.acronym)
        self.assertEqual(submission.group.type_id, group.type_id)

    def test_submit_new_iab(self):
        name = "draft-iab-testing-tests"
        self.create_and_post_submission(name=name, rev="00", author=PersonFactory())
        self.assertEqual(Submission.objects.get(name=name).group.acronym, "iab")

    def test_cancel_submission(self):
        # submit -> cancel
        GroupFactory(acronym='mars')

        name = "draft-ietf-mars-testing-tests"
        rev = "00"

        status_url, author = self.do_submission(name, rev)

        # check we got cancel button
        r = self.client.get(status_url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        cancel_button = q('[type=submit]:contains("Cancel")')
        self.assertEqual(len(cancel_button), 1)

        action = cancel_button.parents("form").find('input[type=hidden][name="action"]').val()

        # cancel
        r = self.client.post(status_url, dict(action=action))
        self.assertTrue(not os.path.exists(os.path.join(self.staging_dir, "%s-%s.txt" % (name, rev))))

    def test_edit_submission_and_force_post(self):
        # submit -> edit
        draft = WgDraftFactory(group__acronym='mars')

        name = "draft-ietf-mars-testing-tests"
        rev = "00"

        status_url, author = self.do_submission(name, rev)

        # check we have edit button
        r = self.client.get(status_url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        adjust_button = q('[type=submit]:contains("Adjust")')
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
        # FIXME If this test is started before midnight, and ends after, it will fail
        document_date = date_today() - datetime.timedelta(days=-3)
        r = self.client.post(edit_url, {
            "edit-title": "some title",
            "edit-rev": "00",
            "edit-document_date": document_date.strftime("%Y-%m-%d"),
            "edit-abstract": "some abstract",
            "edit-pages": "123",
            "submitter-name": "Some Random Test Person",
            "submitter-email": "random@example.com",
            "replaces": [str(draft.pk)],
            "authors-0-name": "Person 1",
            "authors-0-email": "person1@example.com",
            "authors-1-name": "Person 2",
            "authors-1-email": "person2@example.com",
            "authors-2-name": "Person 3",
            "authors-2-email": "person3@example.com",
            "authors-prefix": ["authors-", "authors-0", "authors-1", "authors-2"],
        })
        self.assertNoFormPostErrors(r, ".invalid-feedback,.alert-danger")

        submission = Submission.objects.get(name=name)
        self.assertEqual(submission.title, "some title")
        self.assertEqual(submission.document_date, document_date)
        self.assertEqual(submission.abstract, "some abstract")
        self.assertEqual(submission.pages, 123)
        self.assertEqual(submission.submitter, "Some Random Test Person <random@example.com>")
        self.assertEqual(submission.replaces, draft.name)
        self.assertEqual(submission.state_id, "manual")

        authors = submission.authors
        self.assertEqual(len(authors), 3)
        self.assertEqual(authors[0]["name"], "Person 1")
        self.assertEqual(authors[0]["email"], "person1@example.com")
        self.assertEqual(authors[1]["name"], "Person 2")
        self.assertEqual(authors[1]["email"], "person2@example.com")
        self.assertEqual(authors[2]["name"], "Person 3")
        self.assertEqual(authors[2]["email"], "person3@example.com")

        self.assertEqual(len(outbox), mailbox_before + 1)
        self.assertTrue("Manual Post Requested" in outbox[-1]["Subject"])
        self.assertTrue(name in outbox[-1]["Subject"])

        # as Secretariat, we should see the force post button
        self.client.login(username="secretary", password="secretary+password")

        r = self.client.get(status_url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        post_button = q('[type=submit]:contains("Force")')
        self.assertEqual(len(post_button), 1)

        action = post_button.parents("form").find('input[type=hidden][name="action"]').val()

        # force post
        mailbox_before = len(outbox)
        r = self.client.post(status_url, dict(action=action))
        self.assertEqual(r.status_code, 302)

        draft = Document.objects.get(name=name)
        self.assertEqual(draft.rev, rev)
        self.assertEqual(draft.docextresource_set.count(), 0)
        self.verify_bibxml_ids_creation(draft)

    def test_search_for_submission_and_edit_as_secretariat(self):
        # submit -> edit
        GroupFactory(acronym='mars')

        name = "draft-ietf-mars-testing-tests"
        rev = "00"

        self.do_submission(name, rev)

        # search status page
        r = self.client.get(urlreverse("ietf.submit.views.search_submission"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "submission status")

        # search
        r = self.client.post(urlreverse("ietf.submit.views.search_submission"), dict(name=name))
        self.assertEqual(r.status_code, 302)
        unprivileged_status_url = r['Location']

        # search with rev
        r = self.client.post(urlreverse("ietf.submit.views.search_submission"), dict(name=name+'-'+rev))
        self.assertEqual(r.status_code, 302)
        unprivileged_status_url = r['Location']

        # status page as unprivileged => no edit button
        r = self.client.get(unprivileged_status_url)
        self.assertContains(r, "Submission status of %s" % name)
        q = PyQuery(r.content)
        adjust_button = q('[type=submit]:contains("Adjust")')
        self.assertEqual(len(adjust_button), 0)

        # as Secretariat, we should get edit button
        self.client.login(username="secretary", password="secretary+password")
        r = self.client.get(unprivileged_status_url)
        q = PyQuery(r.content)
        adjust_button = q('[type=submit]:contains("Adjust")')
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
        GroupFactory(acronym='mars')

        name = "draft-ietf-mars-testing-tests"
        rev = "00"

        self.do_submission(name, rev)

        submission = Submission.objects.get(name=name)
        url = urlreverse('ietf.submit.views.submission_status', kwargs=dict(submission_id=submission.pk))

        # check we got request full URL button
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        request_button = q('[type=submit]:contains("Request full access")')
        self.assertEqual(len(request_button), 1)

        # request URL to be sent
        mailbox_before = len(outbox)

        action = request_button.parents("form").find('input[type=hidden][name="action"]').val()
        r = self.client.post(url, dict(action=action))
        self.assertEqual(r.status_code, 200)

        self.assertEqual(len(outbox), mailbox_before + 1)
        self.assertTrue("Full URL for managing submission" in outbox[-1]["Subject"])
        self.assertTrue(name in outbox[-1]["Subject"])

        # This could use a test on an 01 from a new author to make sure the logic on
        # who gets the management url behaves as expected

    def test_submit_all_file_types(self):
        GroupFactory(acronym='mars')
        name = "draft-ietf-mars-testing-tests"
        rev = "00"
        group = "mars"

        self.do_submission(name, rev, group, ["txt", "xml"])

        self.assertEqual(Submission.objects.filter(name=name).count(), 1)

        self.assertTrue(os.path.exists(os.path.join(self.staging_dir, "%s-%s.txt" % (name, rev))))
        fd = io.open(os.path.join(self.staging_dir, "%s-%s.txt" % (name, rev)))
        txt_contents = fd.read()
        fd.close()
        self.assertTrue(name in txt_contents)
        self.assertTrue(os.path.exists(os.path.join(self.staging_dir, "%s-%s.xml" % (name, rev))))
        fd = io.open(os.path.join(self.staging_dir, "%s-%s.xml" % (name, rev)))
        xml_contents = fd.read()
        fd.close()
        self.assertTrue(name in xml_contents)
        self.assertTrue('<?xml version="1.0" encoding="UTF-8"?>' in xml_contents)

    def test_expire_submissions(self):
        s = Submission.objects.create(name="draft-ietf-mars-foo",
                                      group=None,
                                      submission_date=date_today() - datetime.timedelta(days=10),
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
        r = self.client.get(urlreverse("ietf.submit.views.tool_instructions"))
        self.assertEqual(r.status_code, 200)
        
    def test_blackout_access(self):
        # get
        url = urlreverse('ietf.submit.views.upload_submission')

        # Put today in the blackout period
        meeting = Meeting.get_current_meeting()
        meeting.importantdate_set.create(name_id='idcutoff',date=date_today()-datetime.timedelta(days=2))
        
        # regular user, no access
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('input[type=file][name=txt]')), 0)
        
        # Secretariat has access
        self.client.login(username="secretary", password="secretary+password")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('input[type=file][name=txt]')), 1)

    def test_no_blackout_at_all(self):
        url = urlreverse('ietf.submit.views.upload_submission')

        meeting = Meeting.get_current_meeting()
        meeting.date = date_today()+datetime.timedelta(days=7)
        meeting.save()
        meeting.importantdate_set.filter(name_id='idcutoff').delete()
        meeting.importantdate_set.create(name_id='idcutoff', date=date_today()+datetime.timedelta(days=7))
        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('input[type=file][name=txt]')), 1)        

        meeting = Meeting.get_current_meeting()
        meeting.date = date_today()
        meeting.save()
        meeting.importantdate_set.filter(name_id='idcutoff').delete()
        meeting.importantdate_set.create(name_id='idcutoff', date=date_today())
        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('input[type=file][name=txt]')), 1)        

        meeting = Meeting.get_current_meeting()
        meeting.date = date_today()-datetime.timedelta(days=1)
        meeting.save()
        meeting.importantdate_set.filter(name_id='idcutoff').delete()
        meeting.importantdate_set.create(name_id='idcutoff', date=date_today()-datetime.timedelta(days=1))
        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('input[type=file][name=txt]')), 1)        

        
    def submit_bad_file(self, name, formats):
        rev = "00"
        group = None

        # break early in case of missing configuration
        self.assertTrue(os.path.exists(settings.IDSUBMIT_IDNITS_BINARY))

        # get
        url = urlreverse('ietf.submit.views.upload_submission')
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)

        # submit
        files = {}
        for format in formats:
            files[format], author = submission_file(f'{name}-{rev}', f'{name}-{rev}.bad', group, "test_submission.bad")

        r = self.post_to_upload_submission(url, files)

        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(len(q("form .invalid-feedback")) > 0)
        m = q('div.invalid-feedback').text()

        return r, q, m
        
    def submit_bad_doc_name_with_ext(self, name_in_doc, name_in_post, formats):
        group = None
        url = urlreverse('ietf.submit.views.upload_submission')

        # submit
        files = {}
        for format in formats:
            files[format], author = submission_file(name_in_doc, name_in_post, group, "test_submission.%s" % format)
            files[format].name = name_in_post

        r = self.post_to_upload_submission(url, files)
        self.assertEqual(r.status_code, 200)
        return r
        
    def test_submit_bad_file_txt(self):
        r, q, m = self.submit_bad_file("some name", ["txt"])
        self.assertIn('Invalid characters were found in the name', m)
        self.assertIn('Expected the TXT file to have extension ".txt"', m)
        self.assertIn('document does not contain a legitimate name', m)

    def test_submit_bad_doc_name(self):
        r = self.submit_bad_doc_name_with_ext(name_in_doc="draft-foo.dot-bar", name_in_post="draft-foo.dot-bar", formats=["txt"])
        self.assertContains(r, "contains a disallowed character with byte code: 46")
        # This actually is allowed by the existing code. A significant rework of the validation mechanics is needed.
        # r, q, m = self.submit_bad_doc_name_with_ext(name_in_doc="draft-foo-bar-00.txt", name_in_post="draft-foo-bar-00.txt", formats=["txt"])
        # self.assertIn('Did you include a filename extension in the name by mistake?', m)
        r = self.submit_bad_doc_name_with_ext(name_in_doc="draft-foo-bar-00.xml", name_in_post="draft-foo-bar-00.xml", formats=["xml"])
        self.assertContains(r, "Could not extract a valid Internet-Draft revision from the XML")
        r = self.submit_bad_doc_name_with_ext(name_in_doc="../malicious-name-in-content-00", name_in_post="../malicious-name-in-post-00.xml", formats=["xml"])
        self.assertContains(r, "Did you include a filename extension in the name by mistake?")

    def test_submit_bad_file_xml(self):
        r, q, m = self.submit_bad_file("some name", ["xml"])
        self.assertIn('Invalid characters were found in the name', m)
        self.assertIn('Expected the XML file to have extension ".xml"', m)

    def test_submit_file_in_archive(self):
        name = "draft-authorname-testing-file-exists"
        rev = '00'
        formats = ['txt', 'xml']
        group = None

        # break early in case of missing configuration
        self.assertTrue(os.path.exists(settings.IDSUBMIT_IDNITS_BINARY))

        # get
        url = urlreverse('ietf.submit.views.upload_submission')
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)

        # submit
        for dir in [self.repository_dir, self.archive_dir, ]:
            files = {}
            for format in formats:
                fn = os.path.join(dir, "%s-%s.%s" % (name, rev, format))
                with io.open(fn, 'w') as f:
                    f.write("a" * 2000)
                files[format], author = submission_file(f'{name}-{rev}', f'{name}-{rev}.{format}', group, "test_submission.%s" % format)
            r = self.post_to_upload_submission(url, files)

            self.assertEqual(r.status_code, 200)
            q = PyQuery(r.content)
            m = q('.text-danger').text()

            self.assertIn('Unexpected files already in the archive', m)

    def test_submit_nonascii_name(self):
        name = "draft-authorname-testing-nonascii"
        rev = "00"

        user = UserFactory(first_name="Jörgen", last_name="Nilsson")
        author = PersonFactory(user=user)

        status_url, _ = self.do_submission(name=name, rev=rev, author=author, base_filename="test_submission.nonascii", ascii=False)
        r = self.client.get(status_url)
        q = PyQuery(r.content)
        m = q('p.alert-warning').text()

        self.assertIn('The idnits check returned 1 warning', m)

    def test_submit_missing_author_email(self):
        name = "draft-authorname-testing-noemail"
        rev = "00"

        author = PersonFactory()
        for e in author.email_set.all():
            e.delete()

        status_url, _ = self.do_submission(name=name, rev=rev, author=author)
        r = self.client.get(status_url)
        q = PyQuery(r.content)
        m = q('p.text-danger').text()

        self.assertIn('Author email error', m)
        self.assertIn('Found no email address.', m)

    def test_submit_bad_author_email(self):
        name = "draft-authorname-testing-bademail"
        rev = "00"

        author = PersonFactory()
        email = author.email_set.first()
        email.address = '@bad.email'
        email.save()

        status_url, _ = self.do_submission(name=name, rev=rev, author=author, formats=('xml',))
        r = self.client.get(status_url)
        q = PyQuery(r.content)
        m = q('p.text-danger').text()

        self.assertIn('Author email error', m)
        self.assertIn('Invalid email address.', m)

    def test_submit_invalid_yang(self):
        name = "draft-yang-testing-invalid"
        rev = "00"

        status_url, _ = self.do_submission(name=name, rev=rev, base_filename="test_submission_invalid_yang")
        r = self.client.get(status_url)
        q = PyQuery(r.content)
        #
        self.assertContains(r, 'The yang validation returned 1 error')
        #
        m = q('#yang-validation-message').text()
        for command in ['xym', 'pyang', 'yanglint']:
            version = tool_version[command]
            if command != 'yanglint' or (settings.SUBMIT_YANGLINT_COMMAND and os.path.exists(settings.YANGLINT_BINARY)):
                self.assertIn(version, m)
        self.assertIn("draft-yang-testing-invalid-00.txt", m)
        self.assertIn("error: syntax error: illegal keyword: ;", m)
        if settings.SUBMIT_YANGLINT_COMMAND and os.path.exists(settings.YANGLINT_BINARY):
            self.assertIn("No validation errors", m)

    def submit_conflicting_submissiondocevent_rev(self, new_rev='01', existing_rev='01'):
        """Test submitting a rev when an equal or later SubmissionDocEvent rev exists

        The situation tested here "should" never come up. However, it may occur due to data
        corruption or other unexpected situations.
        """
        draft, existing_sub = create_draft_submission_with_rev_mismatch(existing_rev)
        mailbox_before = len(outbox)

        # Submit a "real" rev
        self.create_and_post_submission(draft.name, new_rev, PersonFactory())

        # Submission should have gone into the manual state
        self.assertEqual(Submission.objects.filter(name=draft.name).count(), 2)
        sub = Submission.objects.exclude(pk=existing_sub.pk).get(name=draft.name, rev=new_rev)
        self.assertIsNotNone(sub)
        self.assertEqual(sub.state_id, 'manual')

        # Ensure that an email notification was sent
        self.assertEqual(len(outbox), mailbox_before + 1)
        self.assertTrue("Manual Post Requested" in outbox[-1]["Subject"])
        self.assertTrue(draft.name in outbox[-1]["Subject"])
        expected_error = "Rev %s conflicts with existing submission (%s)"%(new_rev, existing_rev)
        self.assertTrue(expected_error in get_payload_text(outbox[-1]))

    def test_submit_update_existing_submissiondocevent_rev(self):
        """An existing SubmissionDocEvent with same rev should trigger manual processing"""
        self.submit_conflicting_submissiondocevent_rev('01', '01')

    def test_submit_update_later_submissiondocevent_rev(self):
        """An existing SubmissionDocEvent with later rev should trigger manual processing"""
        self.submit_conflicting_submissiondocevent_rev('01', '02')

    def do_wg_approval_auth_test(self, state, chair_can_approve=False):
        """Helper to test approval authorization
        
        Assumes approval allowed by AD and secretary and, optionally, chair of WG
        """
        class _SubmissionFactory:
            """Helper class to generate fresh submissions"""
            def __init__(self, author, state):
                self.author = author
                self.state = state
                self.index = 0

            def next(self):
                self.index += 1
                sub = Submission.objects.create(name="draft-ietf-mars-bar-%d" % self.index,
                                                group=Group.objects.get(acronym="mars"),
                                                submission_date=date_today(),
                                                authors=[dict(name=self.author.name,
                                                              email=self.author.user.email,
                                                              affiliation='affiliation',
                                                              country='country')],
                                                rev="00",
                                                state_id=self.state)
                status_url = urlreverse('ietf.submit.views.submission_status',
                                        kwargs=dict(submission_id=sub.pk,
                                                    access_token=sub.access_token()))
                return sub, status_url

        def _assert_approval_refused(username, submission_factory, user_description):
            """Helper to attempt to approve a document and check that it fails"""
            if username:
                self.client.login(username=username, password=username + '+password')
            submission, status_url = submission_factory.next()
            r = self.client.post(status_url, dict(action='approve'))
            self.assertEqual(r.status_code, 403, '%s should not be able to approve' % user_description.capitalize())
            submission = Submission.objects.get(pk=submission.pk)  # refresh from DB
            self.assertEqual(submission.state_id, state,
                             'Submission should still be awaiting approval after %s approval attempt fails' % user_description)

        def _assert_approval_allowed(username, submission_factory, user_description):
            """Helper to attempt to approve a document and check that it succeeds"""
            self.client.login(username=username, password=username + '+password')
            submission, status_url = submission_factory.next()
            r = self.client.post(status_url, dict(action='approve'))
            self.assertEqual(r.status_code, 302, '%s should be able to approve' % user_description.capitalize())
            submission = Submission.objects.get(pk=submission.pk)  # refresh from DB
            self.assertEqual(submission.state_id, 'posted',
                             'Submission should be posted after %s approves' % user_description)

        # create WGs
        area = GroupFactory(type_id='area', acronym='area')
        mars = GroupFactory(type_id='wg', acronym='mars', parent=area)  # WG for submission
        ames = GroupFactory(type_id='wg', acronym='ames', parent=area)  # another WG
        
        # create / get users and roles
        ad = Person.objects.get(user__username='ad')
        RoleFactory(name_id='ad', group=area, person=ad)
        RoleFactory(name_id='chair', group=mars, person__user__username='marschairman')
        RoleFactory(name_id='chair', group=ames, person__user__username='ameschairman')
        author = PersonFactory(user__username='author_user')
        PersonFactory(user__username='ordinary_user')
        
        submission_factory = _SubmissionFactory(author, state)

        # Most users should not be allowed to approve
        _assert_approval_refused(None, submission_factory, 'anonymous user')
        _assert_approval_refused('ordinary_user', submission_factory, 'ordinary user')
        _assert_approval_refused('author_user', submission_factory, 'author')
        _assert_approval_refused('ameschairman', submission_factory, 'wrong WG chair')

        # chair of correct wg should be able to approve if chair_can_approve == True
        if chair_can_approve:
            _assert_approval_allowed('marschairman', submission_factory, 'WG chair')
        else:
            _assert_approval_refused('marschairman', submission_factory, 'WG chair')

        # ADs and secretaries can always approve
        _assert_approval_allowed('ad', submission_factory, 'AD')
        _assert_approval_allowed('secretary', submission_factory, 'secretary')

    def test_submit_wg_group_approval_auth(self):
        """Group chairs should be able to approve submissions in grp-appr state"""
        self.do_wg_approval_auth_test('grp-appr', chair_can_approve=True)

    def test_submit_wg_ad_approval_auth(self):
        """Area directors should be able to approve submissions in ad-appr state"""
        self.do_wg_approval_auth_test('ad-appr', chair_can_approve=False)
    def do_approval_with_extresources_test(self, submission, url, action, permitted):
        """Helper for submission approval external resource testing
        
        Only intended to test the permissions handling for external resources. Assumes
        the permissions defined by can_edit_docextresources() are tested separately.
        
        Checks that the submission's external_resources are added / not added based on
        permitted. Also checks that a suggestion email is not sent / sent.
        """
        mailbox_before = len(outbox)
        with mock.patch('ietf.submit.utils.can_edit_docextresources', return_value=permitted,) as mocked_permission_check:
            r = self.client.post(url, dict(action=action))
        self.assertEqual(r.status_code, 302)
        self.assertTrue(mocked_permission_check.called, 'Permissions were not checked')

        draft = Document.objects.get(name=submission.name)
        self.assertCountEqual(
            [str(r) for r in draft.docextresource_set.all()],
            [str(r) for r in submission.external_resources.all()] if permitted else [],
        )

        expected_other_emails = 1  # confirmation / approval email
        if permitted:
            self._assert_extresource_change_event(draft, is_present=True)
            self.assertEqual(len(outbox), mailbox_before + expected_other_emails)
        else:
            self._assert_extresource_change_event(draft, is_present=False)
            self.assertEqual(len(outbox), mailbox_before + 1 + expected_other_emails)
            new_mail = outbox[mailbox_before:]
            subject = 'External resource change requested for %s' % submission.name
            suggestion_email = [m for m in new_mail 
                                if m['Subject'] == subject]
            self.assertEqual(len(suggestion_email), 1)
            body = str(suggestion_email[0])
            for res in submission.external_resources.all():
                self.assertIn(res.to_form_entry_str(), body)

    def group_approve_with_extresources(self, permitted):
        group = GroupFactory()
        # someone to be notified of resource suggestion when permission not granted
        RoleFactory(group=group, person=PersonFactory(), name_id='chair')
        submission: Submission = SubmissionFactory(state_id='grp-appr', group=group)  # type: ignore[annotation-unchecked]
        SubmissionExtResourceFactory(submission=submission)

        # use secretary user to ensure we have permission to approve
        self.client.login(username='secretary', password='secretary+password')
        url = urlreverse('ietf.submit.views.submission_status',
                         kwargs=dict(submission_id=submission.pk))
        self.do_approval_with_extresources_test(submission, url, 'approve', permitted)        
    
    def test_group_approve_with_extresources(self):
        """Doc external resources should be updated when approved by group"""
        self.group_approve_with_extresources(permitted=True)
        self.group_approve_with_extresources(permitted=False)

    def confirm_with_extresources(self, state, permitted):
        group = GroupFactory()
        # someone to be notified of resource suggestion when permission not granted
        RoleFactory(group=group, person=PersonFactory(), name_id='chair')
        submission: Submission = SubmissionFactory(state_id=state, group=group)  # type: ignore[annotation-unchecked]
        SubmissionExtResourceFactory(submission=submission)

        url = urlreverse(
            'ietf.submit.views.confirm_submission',
            kwargs=dict(submission_id=submission.pk,
                        auth_token=generate_access_token(submission.auth_key))
        )

        self.do_approval_with_extresources_test(submission, url, 'confirm', permitted)

    def test_confirm_with_extresources(self):
        """Doc external resources should be updated when confirmed by author"""
        self.confirm_with_extresources('aut-appr', permitted=True)
        self.confirm_with_extresources('aut-appr', permitted=False)
        self.confirm_with_extresources('auth', permitted=True)
        self.confirm_with_extresources('auth', permitted=False)

    def test_can_edit_docextresources(self):
        """The can_edit_docextresources method should authorize correctly
        
        Tests that is_authorized_in_doc_stream() being True grants access, but does not
        do detailed testing of that method.
        """
        author = PersonFactory()
        plain = PersonFactory()
        secretary = Person.objects.get(user__username='secretary')
        ad = Person.objects.get(user__username='ad')
        wg_chair = PersonFactory()
        wg = GroupFactory()
        RoleFactory(person=wg_chair, group=wg, name_id='chair')

        wg_doc = WgDraftFactory(authors=[author], group=wg)
        self.assertFalse(can_edit_docextresources(author.user, wg_doc))
        self.assertTrue(can_edit_docextresources(secretary.user, wg_doc))
        self.assertTrue(can_edit_docextresources(ad.user, wg_doc))
        self.assertTrue(can_edit_docextresources(wg_chair.user, wg_doc))
        self.assertFalse(can_edit_docextresources(plain.user, wg_doc))
        with mock.patch('ietf.doc.utils.is_authorized_in_doc_stream', return_value=True):
            self.assertTrue(can_edit_docextresources(plain.user, wg_doc))

        individ_doc = IndividualDraftFactory(authors=[author])
        self.assertTrue(can_edit_docextresources(author.user, individ_doc))
        self.assertTrue(can_edit_docextresources(secretary.user, individ_doc))
        self.assertTrue(can_edit_docextresources(ad.user, individ_doc))
        self.assertFalse(can_edit_docextresources(wg_chair.user, individ_doc))
        self.assertFalse(can_edit_docextresources(plain.user, individ_doc))
        with mock.patch('ietf.doc.utils.is_authorized_in_doc_stream', return_value=True):
            self.assertTrue(can_edit_docextresources(plain.user, individ_doc))

    def test_forcepost_with_extresources(self):
        # state needs to be one that has 'posted' as a next state
        submission: Submission = SubmissionFactory(state_id='grp-appr')  # type: ignore[annotation-unchecked]
        SubmissionExtResourceFactory(submission=submission)

        url = urlreverse(
            'ietf.submit.views.submission_status',
            kwargs=dict(submission_id=submission.pk),
        )

        self.client.login(username='secretary', password='secretary+password')
        r = self.client.post(url, dict(action='forcepost'))
        self.assertEqual(r.status_code, 302)
        draft = Document.objects.get(name=submission.name)
        self._assert_extresource_change_event(draft, is_present=True)
        self.assertCountEqual(
            [str(r) for r in draft.docextresource_set.all()],
            [str(r) for r in submission.external_resources.all()],
        )

    def test_submission_status_labels_extresource_changes(self):
        """Added or removed labels should be present for changed external resources"""
        draft = WgDraftFactory(rev='00')
        draft.docextresource_set.create(
            name_id='faq',
            value='https://example.com/faq-removed',
            display_name='Resource to be removed',
        )
        draft.docextresource_set.create(
            name_id='faq',
            value='https://example.com/faq-kept',
            display_name='Resource to be kept',
        )
        
        submission = SubmissionFactory(name=draft.name, rev='01')
        submission.external_resources.create(
            name_id='faq',
            value='https://example.com/faq-kept',
            display_name='Resource to be kept',
        )
        submission.external_resources.create(
            name_id='faq',
            value='https://example.com/faq-added',
            display_name='Resource to be added',
        )
        
        url = urlreverse('ietf.submit.views.submission_status',
                         kwargs=dict(submission_id=submission.pk))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        
        q = PyQuery(r.content)
        # The removed resource should appear once (for the doc current value), tagged as removed
        removed_div = q('td>div:contains("Resource to be removed")')
        self.assertEqual(len(removed_div), 1)
        self.assertEqual(len(removed_div('span.badge:contains("Removed")')), 1)
        self.assertEqual(len(removed_div('span.badge:contains("New")')), 0)

        # The added resource should appear once (for the submission), tagged as new
        added_div = q('td>div:contains("Resource to be added")')
        self.assertEqual(len(added_div), 1)
        self.assertEqual(len(added_div('span.badge:contains("Removed")')), 0)
        self.assertEqual(len(added_div('span.badge:contains("New")')), 1)

        # The kept resource should appear twice (once for the doc, once for the submission), with no tag
        kept_div = q('td>div:contains("Resource to be kept")')
        self.assertEqual(len(kept_div), 2)
        self.assertEqual(len(kept_div('span.badge:contains("Removed")')), 0)
        self.assertEqual(len(kept_div('span.badge:contains("New")')), 0)
        
class ApprovalsTestCase(BaseSubmitTestCase):
    def test_approvals(self):
        RoleFactory(name_id='chair',
                    group__acronym='mars',
                    person__user__username='marschairman')
        RoleFactory(name_id='chair',
                    group__acronym='ames',
                    person__user__username='ameschairman')
        RoleFactory(name_id='ad',
                    group=Group.objects.get(acronym='mars').parent,
                    person=Person.objects.get(user__username='ad'))
        RoleFactory(name_id='ad',
                    group=Group.objects.get(acronym='ames').parent,
                    person__user__username='other-ad')

        url = urlreverse('ietf.submit.views.approvals')

        Preapproval.objects.create(name="draft-ietf-mars-foo", by=Person.objects.get(user__username="marschairman"))
        Preapproval.objects.create(name="draft-ietf-mars-baz", by=Person.objects.get(user__username="marschairman"))

        Submission.objects.create(name="draft-ietf-mars-foo",
                                  group=Group.objects.get(acronym="mars"),
                                  submission_date=date_today(),
                                  rev="00",
                                  state_id="posted")
        Submission.objects.create(name="draft-ietf-mars-bar",
                                  group=Group.objects.get(acronym="mars"),
                                  submission_date=date_today(),
                                  rev="00",
                                  state_id="grp-appr")
        Submission.objects.create(name="draft-ietf-mars-quux",
                                  group=Group.objects.get(acronym="mars"),
                                  submission_date=date_today(),
                                  rev="00",
                                  state_id="ad-appr")

        # get as wg chair
        self.client.login(username="marschairman", password="marschairman+password")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)

        self.assertEqual(len(q('.approvals a:contains("draft-ietf-mars-foo")')), 0)
        self.assertEqual(len(q('.approvals a:contains("draft-ietf-mars-bar")')), 1)
        self.assertEqual(len(q('.approvals a:contains("draft-ietf-mars-quux")')), 0)  # wg chair does not see ad-appr
        self.assertEqual(len(q('.preapprovals td:contains("draft-ietf-mars-foo")')), 0)
        self.assertEqual(len(q('.preapprovals td:contains("draft-ietf-mars-baz")')), 1)
        self.assertEqual(len(q('.preapprovals td:contains("draft-ietf-mars-bar")')), 0)
        self.assertEqual(len(q('.preapprovals td:contains("draft-ietf-mars-quux")')), 0)
        self.assertEqual(len(q('.recently-approved a:contains("draft-ietf-mars-foo")')), 1)
        self.assertEqual(len(q('.recently-approved a:contains("draft-ietf-mars-baz")')), 0)
        self.assertEqual(len(q('.recently-approved a:contains("draft-ietf-mars-bar")')), 0)
        self.assertEqual(len(q('.recently-approved a:contains("draft-ietf-mars-quux")')), 0)

        # get as AD - sees everything
        self.client.login(username="ad", password="ad+password")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)

        self.assertEqual(len(q('.approvals a:contains("draft-ietf-mars-foo")')), 0)
        self.assertEqual(len(q('.approvals a:contains("draft-ietf-mars-bar")')), 1)  # AD sees grp-appr in their area 
        self.assertEqual(len(q('.approvals a:contains("draft-ietf-mars-quux")')), 1)  # AD does see ad-appr
        self.assertEqual(len(q('.preapprovals td:contains("draft-ietf-mars-foo")')), 0)
        self.assertEqual(len(q('.preapprovals td:contains("draft-ietf-mars-baz")')), 1)
        self.assertEqual(len(q('.preapprovals td:contains("draft-ietf-mars-bar")')), 0)
        self.assertEqual(len(q('.preapprovals td:contains("draft-ietf-mars-quux")')), 0)
        self.assertEqual(len(q('.recently-approved a:contains("draft-ietf-mars-foo")')), 1)
        self.assertEqual(len(q('.recently-approved a:contains("draft-ietf-mars-baz")')), 0)
        self.assertEqual(len(q('.recently-approved a:contains("draft-ietf-mars-bar")')), 0)
        self.assertEqual(len(q('.recently-approved a:contains("draft-ietf-mars-quux")')), 0)

        # get as wg chair for a different group - should see nothing
        self.client.login(username="ameschairman", password="ameschairman+password")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)

        self.assertEqual(len(q('.approvals a:contains("draft-ietf-mars-foo")')), 0)
        self.assertEqual(len(q('.approvals a:contains("draft-ietf-mars-bar")')), 0)
        self.assertEqual(len(q('.approvals a:contains("draft-ietf-mars-quux")')), 0)
        self.assertEqual(len(q('.preapprovals td:contains("draft-ietf-mars-foo")')), 0)
        self.assertEqual(len(q('.preapprovals td:contains("draft-ietf-mars-baz")')), 0)
        self.assertEqual(len(q('.preapprovals td:contains("draft-ietf-mars-bar")')), 0)
        self.assertEqual(len(q('.preapprovals td:contains("draft-ietf-mars-quux")')), 0)
        self.assertEqual(len(q('.recently-approved a:contains("draft-ietf-mars-foo")')), 0)
        self.assertEqual(len(q('.recently-approved a:contains("draft-ietf-mars-baz")')), 0)
        self.assertEqual(len(q('.recently-approved a:contains("draft-ietf-mars-bar")')), 0)
        self.assertEqual(len(q('.recently-approved a:contains("draft-ietf-mars-quux")')), 0)

        # get as AD for a different area - should see nothing
        self.client.login(username="other-ad", password="other-ad+password")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)

        self.assertEqual(len(q('.approvals a:contains("draft-ietf-mars-foo")')), 0)
        self.assertEqual(len(q('.approvals a:contains("draft-ietf-mars-bar")')), 0) 
        self.assertEqual(len(q('.approvals a:contains("draft-ietf-mars-quux")')), 0)
        self.assertEqual(len(q('.preapprovals td:contains("draft-ietf-mars-foo")')), 0)
        self.assertEqual(len(q('.preapprovals td:contains("draft-ietf-mars-baz")')), 0)
        self.assertEqual(len(q('.preapprovals td:contains("draft-ietf-mars-bar")')), 0)
        self.assertEqual(len(q('.preapprovals td:contains("draft-ietf-mars-quux")')), 0)
        self.assertEqual(len(q('.recently-approved a:contains("draft-ietf-mars-foo")')), 0)
        self.assertEqual(len(q('.recently-approved a:contains("draft-ietf-mars-baz")')), 0)
        self.assertEqual(len(q('.recently-approved a:contains("draft-ietf-mars-bar")')), 0)
        self.assertEqual(len(q('.recently-approved a:contains("draft-ietf-mars-quux")')), 0)

        # get as secretary - should see everything
        self.client.login(username="secretary", password="secretary+password")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)

        self.assertEqual(len(q('.approvals a:contains("draft-ietf-mars-foo")')), 0)
        self.assertEqual(len(q('.approvals a:contains("draft-ietf-mars-bar")')), 1)
        self.assertEqual(len(q('.approvals a:contains("draft-ietf-mars-quux")')), 1)
        self.assertEqual(len(q('.preapprovals td:contains("draft-ietf-mars-foo")')), 0)
        self.assertEqual(len(q('.preapprovals td:contains("draft-ietf-mars-baz")')), 1)
        self.assertEqual(len(q('.preapprovals td:contains("draft-ietf-mars-bar")')), 0)
        self.assertEqual(len(q('.preapprovals td:contains("draft-ietf-mars-quux")')), 0)
        self.assertEqual(len(q('.recently-approved a:contains("draft-ietf-mars-foo")')), 1)
        self.assertEqual(len(q('.recently-approved a:contains("draft-ietf-mars-baz")')), 0)
        self.assertEqual(len(q('.recently-approved a:contains("draft-ietf-mars-bar")')), 0)
        self.assertEqual(len(q('.recently-approved a:contains("draft-ietf-mars-quux")')), 0)

    def test_add_preapproval(self):
        RoleFactory(name_id='chair', group__acronym='mars', person__user__username='marschairman')

        url = urlreverse('ietf.submit.views.add_preapproval')
        login_testing_unauthorized(self, "marschairman", url)

        # get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('[type=submit]:contains("Save")')), 1)

        # faulty post
        r = self.client.post(url, dict(name="draft-test-nonexistingwg-something"))
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(len(q("form .invalid-feedback")) > 0)

        # add
        name = "draft-ietf-mars-foo"
        r = self.client.post(url, dict(name=name))
        self.assertEqual(r.status_code, 302)

        self.assertEqual(len(Preapproval.objects.filter(name=name)), 1)

    def test_cancel_preapproval(self):
        RoleFactory(name_id='chair', group__acronym='mars', person__user__username='marschairman')

        preapproval = Preapproval.objects.create(name="draft-ietf-mars-foo", by=Person.objects.get(user__username="marschairman"))

        url = urlreverse('ietf.submit.views.cancel_preapproval', kwargs=dict(preapproval_id=preapproval.pk))
        login_testing_unauthorized(self, "marschairman", url)

        # get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('[type=submit]:contains("Cancel")')), 1)

        # cancel
        r = self.client.post(url, dict(action="cancel"))
        self.assertEqual(r.status_code, 302)

        self.assertEqual(len(Preapproval.objects.filter(name=preapproval.name)), 0)


# Transaction.on_commit() interacts badly with TestCase's transaction behavior. Replace it
# with a pass-through for testing purposes.
@mock.patch.object(transaction, 'on_commit', lambda x: x())
@override_settings(IDTRACKER_BASE_URL='https://datatracker.example.com')
class ApiSubmissionTests(BaseSubmitTestCase):
    TASK_TO_MOCK = "ietf.submit.views.process_and_accept_uploaded_submission_task"

    def setUp(self):
        super().setUp()
        MeetingFactory(type_id='ietf', date=date_today()+datetime.timedelta(days=60))

    def test_api_submit_tombstone(self):
        """Tombstone for obsolete API endpoint should return 410 Gone"""
        url = urlreverse("ietf.submit.views.api_submit_tombstone")
        self.assertEqual(self.client.get(url).status_code, 410)
        self.assertEqual(self.client.post(url).status_code, 410)

    def test_upload_draft(self):
        """api_submission accepts a submission and queues it for processing"""
        url = urlreverse('ietf.submit.views.api_submission')
        xml, author = submission_file('draft-somebody-test-00', 'draft-somebody-test-00.xml', None, 'test_submission.xml')
        data = {
            'xml': xml,
            'user': author.user.username,
        }
        with mock.patch(self.TASK_TO_MOCK) as mock_task:
            r = self.client.post(url, data)
        self.assertEqual(r.status_code, 200)
        response = r.json()
        self.assertCountEqual(
            response.keys(),
            ['id', 'name', 'rev', 'status_url'],
        )
        submission_id = int(response['id'])
        self.assertEqual(response['name'], 'draft-somebody-test')
        self.assertEqual(response['rev'], '00')
        self.assertEqual(
            response['status_url'],
            'https://datatracker.example.com' + urlreverse(
                'ietf.submit.views.api_submission_status',
                kwargs={'submission_id': submission_id},
            ),
        )
        self.assertEqual(mock_task.delay.call_count, 1)
        self.assertEqual(mock_task.delay.call_args.args, (submission_id,))
        submission = Submission.objects.get(pk=submission_id)
        self.assertEqual(submission.name, 'draft-somebody-test')
        self.assertEqual(submission.rev, '00')
        self.assertEqual(submission.submitter, author.formatted_email())
        self.assertEqual(submission.state_id, 'validating')
        self.assertIn('Uploaded submission through API', submission.submissionevent_set.last().desc)

    def test_upload_draft_with_replaces(self):
        """api_submission accepts a submission and queues it for processing"""
        existing_draft = WgDraftFactory()
        url = urlreverse('ietf.submit.views.api_submission')
        xml, author = submission_file('draft-somebody-test-00', 'draft-somebody-test-00.xml', None, 'test_submission.xml')
        data = {
            'xml': xml,
            'user': author.user.username,
            'replaces': existing_draft.name,
        }
        # mock out the task so we don't call to celery during testing!
        with mock.patch(self.TASK_TO_MOCK):
            r = self.client.post(url, data)
        self.assertEqual(r.status_code, 200)
        submission = Submission.objects.last()
        self.assertEqual(submission.name, 'draft-somebody-test')
        self.assertEqual(submission.replaces, existing_draft.name)

    def test_rejects_broken_upload(self):
        """api_submission immediately rejects a submission with serious problems"""
        orig_submission_count = Submission.objects.count()
        url = urlreverse('ietf.submit.views.api_submission')

        # invalid submitter
        xml, author = submission_file('draft-somebody-test-00', 'draft-somebody-test-00.xml', None, 'test_submission.xml')
        data = {
            'xml': xml,
            'user': 'i.dont.exist@nowhere.example.com',
        }
        with mock.patch(self.TASK_TO_MOCK) as mock_task:
            r = self.client.post(url, data)
        self.assertEqual(r.status_code, 400)
        response = r.json()
        self.assertIn('No such user: ', response['error'])
        self.assertFalse(mock_task.delay.called)
        self.assertEqual(Submission.objects.count(), orig_submission_count)

        # missing name
        xml, _ = submission_file('', 'draft-somebody-test-00.xml', None, 'test_submission.xml', author=author)
        data = {
            'xml': xml,
            'user': author.user.username,
        }
        with mock.patch(self.TASK_TO_MOCK) as mock_task:
            r = self.client.post(url, data)
        self.assertEqual(r.status_code, 400)
        response = r.json()
        self.assertEqual(response['error'], 'Validation Error')
        self.assertFalse(mock_task.delay.called)
        self.assertEqual(Submission.objects.count(), orig_submission_count)

        # missing rev
        xml, _ = submission_file('draft-somebody-test', 'draft-somebody-test-00.xml', None, 'test_submission.xml', author=author)
        data = {
            'xml': xml,
            'user': author.user.username,
        }
        with mock.patch(self.TASK_TO_MOCK) as mock_task:
            r = self.client.post(url, data)
        self.assertEqual(r.status_code, 400)
        response = r.json()
        self.assertEqual(response['error'], 'Validation Error')
        self.assertFalse(mock_task.delay.called)
        self.assertEqual(Submission.objects.count(), orig_submission_count)

        # in-process submission
        SubmissionFactory(name='draft-somebody-test', rev='00')  # create an already-in-progress submission
        orig_submission_count += 1  # keep this up to date
        xml, _ = submission_file('draft-somebody-test-00', 'draft-somebody-test-00.xml', None, 'test_submission.xml', author=author)
        data = {
            'xml': xml,
            'user': author.user.username,
        }
        with mock.patch(self.TASK_TO_MOCK) as mock_task:
            r = self.client.post(url, data)
        self.assertEqual(r.status_code, 400)
        response = r.json()
        self.assertEqual(response['error'], 'Validation Error')
        self.assertFalse(mock_task.delay.called)
        self.assertEqual(Submission.objects.count(), orig_submission_count)

    @override_settings(IDTRACKER_BASE_URL='http://baseurl.example.com')
    def test_get_documentation(self):
        """A GET to the submission endpoint retrieves documentation"""
        r = self.client.get(urlreverse('ietf.submit.views.api_submission'))
        self.assertTemplateUsed(r, 'submit/api_submission_info.html')
        self.assertContains(r, 'http://baseurl.example.com', status_code=200)

    def test_submission_status(self):
        s = SubmissionFactory(state_id='validating')
        url = urlreverse('ietf.submit.views.api_submission_status', kwargs={'submission_id': s.pk})
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(
            r.json(),
            {'id': str(s.pk), 'state': 'validating', 'state_desc': s.state.name},
        )

        s.state_id = 'uploaded'
        s.save()
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(
            r.json(),
            {'id': str(s.pk), 'state': 'uploaded', 'state_desc': s.state.name},
        )

        # try an invalid one
        r = self.client.get(urlreverse('ietf.submit.views.api_submission_status', kwargs={'submission_id': '999999'}))
        self.assertEqual(r.status_code, 404)

    def test_upload_blackout(self):
        """api_submission returns a useful error in the blackout period"""
        # Put today in the blackout period
        meeting = Meeting.get_current_meeting()
        meeting.importantdate_set.create(name_id='idcutoff',date=date_today()-datetime.timedelta(days=2))

        url = urlreverse('ietf.submit.views.api_submission')
        xml, author = submission_file('draft-somebody-test-00', 'draft-somebody-test-00.xml', None, 'test_submission.xml')
        data = {
            'xml': xml,
            'user': author.user.username,
        }

        with mock.patch('ietf.submit.views.process_uploaded_submission_task'):
            r = self.client.post(url, data)
        self.assertContains(r, 'The last submission time for the I-D submission was', status_code=400)

 

class SubmissionUploadFormTests(BaseSubmitTestCase):
    def test_check_submission_thresholds(self):
        today = date_today()
        yesterday = today - datetime.timedelta(days=1)
        (this_group, that_group) = GroupFactory.create_batch(2, type_id='wg')
        this_ip = '10.0.0.1'
        that_ip = '192.168.42.42'
        one_mb = 1024 * 1024
        this_draft = 'draft-this-draft'
        that_draft = 'draft-different-draft'
        SubmissionFactory(group=this_group, name=this_draft, rev='00', submission_date=yesterday, remote_ip=this_ip, file_size=one_mb)
        SubmissionFactory(group=this_group, name=that_draft, rev='00', submission_date=yesterday, remote_ip=this_ip, file_size=one_mb)
        SubmissionFactory(group=this_group, name=this_draft, rev='00', submission_date=today, remote_ip=this_ip, file_size=one_mb)
        SubmissionFactory(group=this_group, name=that_draft, rev='00', submission_date=today, remote_ip=this_ip, file_size=one_mb)
        SubmissionFactory(group=that_group, name=this_draft, rev='00', submission_date=yesterday, remote_ip=that_ip, file_size=one_mb)
        SubmissionFactory(group=that_group, name=that_draft, rev='00', submission_date=yesterday, remote_ip=that_ip, file_size=one_mb)
        SubmissionFactory(group=that_group, name=this_draft, rev='00', submission_date=today, remote_ip=that_ip, file_size=one_mb)
        SubmissionFactory(group=that_group, name=that_draft, rev='00', submission_date=today, remote_ip=that_ip, file_size=one_mb)
        SubmissionFactory(group=that_group, name=that_draft, rev='01', submission_date=today, remote_ip=that_ip, file_size=one_mb)

        # Tests aim to cover the permutations of DB filters that are used by the clean() method
        #   - all IP addresses, today
        SubmissionBaseUploadForm.check_submissions_thresholds(
            'valid today, all submitters',
            dict(submission_date=today),
            max_amount=5,
            max_size=5,  # megabytes
        )
        with self.assertRaisesMessage(ValidationError, 'Max submissions'):
            SubmissionBaseUploadForm.check_submissions_thresholds(
                'too many today, all submitters',
                dict(submission_date=today),
                max_amount=4,
                max_size=5,  # megabytes
            )
        with self.assertRaisesMessage(ValidationError, 'Max uploaded amount'):
            SubmissionBaseUploadForm.check_submissions_thresholds(
                'too much today, all submitters',
                dict(submission_date=today),
                max_amount=5,
                max_size=4,  # megabytes
            )

        #   - one IP address, today
        SubmissionBaseUploadForm.check_submissions_thresholds(
            'valid today, one submitter',
            dict(remote_ip=this_ip, submission_date=today),
            max_amount=2,
            max_size=2,  # megabytes
        )
        with self.assertRaisesMessage(ValidationError, 'Max submissions'):
            SubmissionBaseUploadForm.check_submissions_thresholds(
                'too many today, one submitter',
                dict(remote_ip=this_ip, submission_date=today),
                max_amount=1,
                max_size=2,  # megabytes
            )
        with self.assertRaisesMessage(ValidationError, 'Max uploaded amount'):
            SubmissionBaseUploadForm.check_submissions_thresholds(
                'too much today, one submitter',
                dict(remote_ip=this_ip, submission_date=today),
                max_amount=2,
                max_size=1,  # megabytes
            )

        #   - single draft/rev, today
        SubmissionBaseUploadForm.check_submissions_thresholds(
            'valid today, one draft',
            dict(name=this_draft, rev='00', submission_date=today),
            max_amount=2,
            max_size=2,  # megabytes
        )
        with self.assertRaisesMessage(ValidationError, 'Max submissions'):
            SubmissionBaseUploadForm.check_submissions_thresholds(
                'too many today, one draft',
                dict(name=this_draft, rev='00', submission_date=today),
                max_amount=1,
                max_size=2,  # megabytes
            )
        with self.assertRaisesMessage(ValidationError, 'Max uploaded amount'):
            SubmissionBaseUploadForm.check_submissions_thresholds(
                'too much today, one draft',
                dict(name=this_draft, rev='00', submission_date=today),
                max_amount=2,
                max_size=1,  # megabytes
            )

        #   - one group, today
        SubmissionBaseUploadForm.check_submissions_thresholds(
            'valid today, one group',
            dict(group=this_group, submission_date=today),
            max_amount=2,
            max_size=2,  # megabytes
        )
        with self.assertRaisesMessage(ValidationError, 'Max submissions'):
            SubmissionBaseUploadForm.check_submissions_thresholds(
                'too many today, one group',
                dict(group=this_group, submission_date=today),
                max_amount=1,
                max_size=2,  # megabytes
            )
        with self.assertRaisesMessage(ValidationError, 'Max uploaded amount'):
            SubmissionBaseUploadForm.check_submissions_thresholds(
                'too much today, one group',
                dict(group=this_group, submission_date=today),
                max_amount=2,
                max_size=1,  # megabytes
            )

    def test_replaces_field(self):
        """test SubmissionAutoUploadForm replaces field"""
        request_factory = RequestFactory()
        WgDraftFactory(name='draft-somebody-test')
        existing_drafts = WgDraftFactory.create_batch(2)
        xml, auth = submission_file('draft-somebody-test-01', 'draft-somebody-test-01.xml', None, 'test_submission.xml')
        files_dict = {
                         'xml': SimpleUploadedFile('draft-somebody-test-01.xml', xml.read().encode('utf8'),
                                                   content_type='application/xml'),
        }

        # no replaces
        form = SubmissionAutoUploadForm(
            request_factory.get('/some/url'),
            data={'user': auth.user.username, 'replaces': ''},
            files=files_dict,
        )
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['replaces'], '')

        # whitespace
        form = SubmissionAutoUploadForm(
            request_factory.get('/some/url'),
            data={'user': auth.user.username, 'replaces': '   '},
            files=files_dict,
        )
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['replaces'], '')

        # one replaces
        form = SubmissionAutoUploadForm(
            request_factory.get('/some/url'),
            data={'user': auth.user.username, 'replaces': existing_drafts[0].name},
            files=files_dict,
        )
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['replaces'], existing_drafts[0].name)

        # two replaces
        form = SubmissionAutoUploadForm(
            request_factory.get('/some/url'),
            data={'user': auth.user.username, 'replaces': f'{existing_drafts[0].name},{existing_drafts[1].name}'},
            files=files_dict,
        )
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['replaces'], f'{existing_drafts[0].name},{existing_drafts[1].name}')

        # two replaces, extra whitespace
        form = SubmissionAutoUploadForm(
            request_factory.get('/some/url'),
            data={'user': auth.user.username, 'replaces': f'   {existing_drafts[0].name} ,  {existing_drafts[1].name}'},
            files=files_dict,
        )
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['replaces'], f'{existing_drafts[0].name},{existing_drafts[1].name}')

        # can't replace self
        form = SubmissionAutoUploadForm(
            request_factory.get('/some/url'),
            data={'user': auth.user.username, 'replaces': 'draft-somebody-test'},
            files=files_dict,
        )
        self.assertFalse(form.is_valid())
        self.assertIn('An Internet-Draft cannot replace itself', form.errors['replaces'])

        # can't replace non-draft
        review = ReviewFactory()
        form = SubmissionAutoUploadForm(
            request_factory.get('/some/url'),
            data={'user': auth.user.username, 'replaces': review.name},
            files=files_dict,
        )
        self.assertFalse(form.is_valid())
        self.assertIn('An Internet-Draft can only replace another Internet-Draft', form.errors['replaces'])

        # can't replace RFC
        rfc = WgRfcFactory()
        draft = WgDraftFactory(states=[("draft", "rfc")])
        draft.relateddocument_set.create(relationship_id="became_rfc", target=rfc)
        form = SubmissionAutoUploadForm(
            request_factory.get('/some/url'),
            data={'user': auth.user.username, 'replaces': draft.name},
            files=files_dict,
        )
        self.assertFalse(form.is_valid())
        self.assertIn('An Internet-Draft cannot replace another Internet-Draft that has become an RFC', form.errors['replaces'])

        # can't replace draft approved by iesg
        existing_drafts[0].set_state(State.objects.get(type='draft-iesg', slug='approved'))
        form = SubmissionAutoUploadForm(
            request_factory.get('/some/url'),
            data={'user': auth.user.username, 'replaces': existing_drafts[0].name},
            files=files_dict,
        )
        self.assertFalse(form.is_valid())
        self.assertIn(f'{existing_drafts[0].name} is approved by the IESG and cannot be replaced',
                      form.errors['replaces'])

        # unknown draft
        form = SubmissionAutoUploadForm(
            request_factory.get('/some/url'),
            data={'user': auth.user.username, 'replaces': 'fake-name'},
            files=files_dict,
        )
        self.assertFalse(form.is_valid())

    def test_invalid_xml(self):
        """Test error message for invalid XML"""
        not_xml = SimpleUploadedFile(
            name="not-xml.xml",
            content=b"this is not xml at all",
            content_type="application/xml",
        )
        form = SubmissionBaseUploadForm(RequestFactory().post('/some/url'), files={"xml": not_xml})
        self.assertFalse(form.is_valid())
        self.assertFormError(
            form,
            "xml",
            "The uploaded file is not valid XML. Please make sure you are uploading the correct file.",
        )

class AsyncSubmissionTests(BaseSubmitTestCase):
    """Tests of async submission-related tasks"""
    def test_process_and_accept_uploaded_submission(self):
        """process_and_accept_uploaded_submission should properly process a submission"""
        _today = date_today()
        xml, author = submission_file('draft-somebody-test-00', 'draft-somebody-test-00.xml', None, 'test_submission.xml')
        xml_data = xml.read()
        xml.close()

        submission = SubmissionFactory(
            name='draft-somebody-test',
            rev='00',
            file_types='.xml',
            submitter=author.formatted_email(),
            state_id='validating',
        )
        xml_path = Path(settings.IDSUBMIT_STAGING_PATH) / 'draft-somebody-test-00.xml'
        with xml_path.open('w') as f:
            f.write(xml_data)
        txt_path = xml_path.with_suffix('.txt')
        self.assertFalse(txt_path.exists())
        html_path = xml_path.with_suffix('.html')
        self.assertFalse(html_path.exists())
        process_and_accept_uploaded_submission(submission)

        submission = Submission.objects.get(pk=submission.pk)  # refresh
        self.assertEqual(submission.state_id, 'auth', 'accepted submission should be in auth state')
        self.assertEqual(submission.title, 'Test Document')
        self.assertEqual(submission.xml_version, '3')
        self.assertEqual(submission.document_date, _today)
        self.assertEqual(submission.abstract.strip(), 'This document describes how to test tests.')
        # don't worry about testing the details of these, just that they're set
        self.assertIsNotNone(submission.pages)
        self.assertIsNotNone(submission.words)
        self.assertNotEqual(submission.first_two_pages.strip(), '')
        # at least test that these were created
        self.assertTrue(txt_path.exists())
        self.assertTrue(html_path.exists())
        self.assertEqual(submission.file_size, os.stat(txt_path).st_size)
        self.assertIn('Completed submission validation checks', submission.submissionevent_set.last().desc)

    def test_process_and_accept_uploaded_submission_invalid(self):
        """process_and_accept_uploaded_submission should properly process an invalid submission"""
        xml, author = submission_file('draft-somebody-test-00', 'draft-somebody-test-00.xml', None, 'test_submission.xml')
        xml_data = xml.read()
        xml.close()
        txt, _ = submission_file('draft-somebody-test-00', 'draft-somebody-test-00.xml', None,
                                 'test_submission.txt', author=author)
        txt_data = txt.read()
        txt.close()

        # submitter is not an author
        submitter = PersonFactory()
        submission = SubmissionFactory(
            name='draft-somebody-test',
            rev='00',
            file_types='.xml',
            submitter=submitter.formatted_email(),
            state_id='validating',
        )
        xml_path = Path(settings.IDSUBMIT_STAGING_PATH) / 'draft-somebody-test-00.xml'
        with xml_path.open('w') as f:
            f.write(xml_data)
        process_and_accept_uploaded_submission(submission)
        submission = Submission.objects.get(pk=submission.pk)  # refresh
        self.assertEqual(submission.state_id, 'cancel')
        self.assertIn('not one of the document authors', submission.submissionevent_set.last().desc)

        # author has no email address in XML
        submission = SubmissionFactory(
            name='draft-somebody-test',
            rev='00',
            file_types='.xml',
            submitter=author.formatted_email(),
            state_id='validating',
        )
        xml_path = Path(settings.IDSUBMIT_STAGING_PATH) / 'draft-somebody-test-00.xml'
        with xml_path.open('w') as f:
            f.write(re.sub(r'<email>.*</email>', '', xml_data))
        process_and_accept_uploaded_submission(submission)
        submission = Submission.objects.get(pk=submission.pk)  # refresh
        self.assertEqual(submission.state_id, 'cancel')
        self.assertIn('Email address not found for all authors', submission.submissionevent_set.last().desc)

        # no title
        submission = SubmissionFactory(
            name='draft-somebody-test',
            rev='00',
            file_types='.xml',
            submitter=author.formatted_email(),
            state_id='validating',
        )
        xml_path = Path(settings.IDSUBMIT_STAGING_PATH) / 'draft-somebody-test-00.xml'
        with xml_path.open('w') as f:
            f.write(re.sub(r'<title>.*</title>', '<title></title>', xml_data))
        process_and_accept_uploaded_submission(submission)
        submission = Submission.objects.get(pk=submission.pk)  # refresh
        self.assertEqual(submission.state_id, 'cancel')
        self.assertIn('Could not extract a valid title', submission.submissionevent_set.last().desc)

        # draft name mismatch
        submission = SubmissionFactory(
            name='draft-different-name',
            rev='00',
            file_types='.xml',
            submitter=author.formatted_email(),
            state_id='validating',
        )
        xml_path = Path(settings.IDSUBMIT_STAGING_PATH) / 'draft-different-name-00.xml'
        with xml_path.open('w') as f:
            f.write(xml_data)
        process_and_accept_uploaded_submission(submission)
        submission = Submission.objects.get(pk=submission.pk)  # refresh
        self.assertEqual(submission.state_id, 'cancel')
        self.assertIn('Submission rejected: XML Internet-Draft filename', submission.submissionevent_set.last().desc)

        # rev mismatch
        submission = SubmissionFactory(
            name='draft-somebody-test',
            rev='01',
            file_types='.xml',
            submitter=author.formatted_email(),
            state_id='validating',
        )
        xml_path = Path(settings.IDSUBMIT_STAGING_PATH) / 'draft-somebody-test-01.xml'
        with xml_path.open('w') as f:
            f.write(xml_data)
        process_and_accept_uploaded_submission(submission)
        submission = Submission.objects.get(pk=submission.pk)  # refresh
        self.assertEqual(submission.state_id, 'cancel')
        self.assertIn('Submission rejected: XML Internet-Draft revision', submission.submissionevent_set.last().desc)

        # not xml
        submission = SubmissionFactory(
            name='draft-somebody-test',
            rev='00',
            file_types='.txt',
            submitter=author.formatted_email(),
            state_id='validating',
        )
        txt_path = Path(settings.IDSUBMIT_STAGING_PATH) / 'draft-somebody-test-00.txt'
        with txt_path.open('w') as f:
            f.write(txt_data)
        process_and_accept_uploaded_submission(submission)
        submission = Submission.objects.get(pk=submission.pk)  # refresh
        self.assertEqual(submission.state_id, 'cancel')
        self.assertIn('Only XML Internet-Draft submissions', submission.submissionevent_set.last().desc)

        # wrong state
        submission = SubmissionFactory(
            name='draft-somebody-test',
            rev='00',
            file_types='.xml',
            submitter=author.formatted_email(),
            state_id='uploaded',
        )
        xml_path = Path(settings.IDSUBMIT_STAGING_PATH) / 'draft-somebody-test-00.xml'
        with xml_path.open('w') as f:
            f.write(xml_data)
        with mock.patch('ietf.submit.utils.process_submission_xml') as mock_proc_xml:
            process_and_accept_uploaded_submission(submission)
        submission = Submission.objects.get(pk=submission.pk)  # refresh
        self.assertFalse(mock_proc_xml.called, 'Should not process submission not in "validating" state')
        self.assertEqual(submission.state_id, 'uploaded', 'State should not be changed')

        # failed checker
        submission = SubmissionFactory(
            name='draft-somebody-test',
            rev='00',
            file_types='.xml',
            submitter=author.formatted_email(),
            state_id='validating',
        )
        xml_path = Path(settings.IDSUBMIT_STAGING_PATH) / 'draft-somebody-test-00.xml'
        with xml_path.open('w') as f:
            f.write(xml_data)
        with mock.patch(
                'ietf.submit.utils.apply_checkers',
                side_effect = lambda _, __: submission.checks.create(
                    checker='faked',
                    passed=False,
                    message='fake failure',
                    errors=1,
                    warnings=0,
                    items={},
                    symbol='x',
                )
        ):
            process_and_accept_uploaded_submission(submission)
        submission = Submission.objects.get(pk=submission.pk)  # refresh
        self.assertEqual(submission.state_id, 'cancel')
        self.assertIn('fake failure', submission.submissionevent_set.last().desc)


    @mock.patch('ietf.submit.tasks.process_and_accept_uploaded_submission')
    def test_process_and_accept_uploaded_submission_task(self, mock_method):
        """process_and_accept_uploaded_submission_task task should properly call its method"""
        s = SubmissionFactory()
        process_and_accept_uploaded_submission_task(s.pk)
        self.assertEqual(mock_method.call_count, 1)
        self.assertEqual(mock_method.call_args.args, (s,))

    @mock.patch('ietf.submit.tasks.process_and_accept_uploaded_submission')
    def test_process_and_accept_uploaded_submission_task_ignores_invalid_id(self, mock_method):
        """process_and_accept_uploaded_submission_task should ignore an invalid submission_id"""
        SubmissionFactory()  # be sure there is a Submission
        bad_pk = 9876
        self.assertEqual(Submission.objects.filter(pk=bad_pk).count(), 0)
        process_and_accept_uploaded_submission_task(bad_pk)
        self.assertEqual(mock_method.call_count, 0)

    def test_process_submission_xml(self):
        xml_path = Path(settings.IDSUBMIT_STAGING_PATH) / "draft-somebody-test-00.xml"
        xml, _ = submission_file(
            "draft-somebody-test-00",
            "draft-somebody-test-00.xml",
            None,
            "test_submission.xml",
            title="Correct Draft Title",
        )
        xml_contents = xml.read()
        xml_path.write_text(xml_contents)
        output = process_submission_xml("draft-somebody-test", "00")
        self.assertEqual(output["filename"], "draft-somebody-test")
        self.assertEqual(output["rev"], "00")
        self.assertEqual(output["title"], "Correct Draft Title")
        self.assertIsNone(output["abstract"])
        self.assertEqual(len(output["authors"]), 1)  # not checking in detail, parsing is unreliable
        self.assertEqual(output["document_date"], date_today())
        self.assertIsNone(output["pages"])
        self.assertIsNone(output["words"])
        self.assertIsNone(output["first_two_pages"])
        self.assertIsNone(output["file_size"])
        self.assertIsNone(output["formal_languages"])
        self.assertEqual(output["xml_version"], "3")

        # Should behave on missing or partial <date> elements
        xml_path.write_text(re.sub(r"<date.+>", "", xml_contents))  # strip <date...> entirely
        output = process_submission_xml("draft-somebody-test", "00")
        self.assertEqual(output["document_date"], None)

        xml_path.write_text(re.sub(r"<date year=.+ month", "<date month", xml_contents))  # remove year
        output = process_submission_xml("draft-somebody-test", "00")
        self.assertEqual(output["document_date"], date_today())

        xml_path.write_text(re.sub(r"(<date.+) month=.+day=(.+>)", r"\1 day=\2", xml_contents))  # remove month
        output = process_submission_xml("draft-somebody-test", "00")
        self.assertEqual(output["document_date"], date_today())

        xml_path.write_text(re.sub(r"<date(.+) day=.+>", r"<date\1>", xml_contents))  # remove day
        output = process_submission_xml("draft-somebody-test", "00")
        self.assertEqual(output["document_date"], date_today())

        # name mismatch
        xml, _ = submission_file(
            "draft-somebody-wrong-name-00",  # name that appears in the file
            "draft-somebody-test-00.xml",
            None,
            "test_submission.xml",
            title="Correct Draft Title",
        )
        xml_path.write_text(xml.read())
        with self.assertRaisesMessage(SubmissionError, "disagrees with submission filename"):
            process_submission_xml("draft-somebody-test", "00")

        # rev mismatch
        xml, _ = submission_file(
            "draft-somebody-test-01",  # name that appears in the file
            "draft-somebody-test-00.xml",
            None,
            "test_submission.xml",
            title="Correct Draft Title",
        )
        xml_path.write_text(xml.read())
        with self.assertRaisesMessage(SubmissionError, "disagrees with submission revision"):
            process_submission_xml("draft-somebody-test", "00")

        # missing title
        xml, _ = submission_file(
            "draft-somebody-test-00",  # name that appears in the file
            "draft-somebody-test-00.xml",
            None,
            "test_submission.xml",
            title="",
        )
        xml_path.write_text(xml.read())
        with self.assertRaisesMessage(SubmissionError, "Could not extract a valid title"):
            process_submission_xml("draft-somebody-test", "00")

    def test_process_submission_text(self):
        txt_path = Path(settings.IDSUBMIT_STAGING_PATH) / "draft-somebody-test-00.txt"
        txt, _ = submission_file(
            "draft-somebody-test-00",
            "draft-somebody-test-00.txt",
            None,
            "test_submission.txt",
            title="Correct Draft Title",
        )
        txt_path.write_text(txt.read())
        output = process_submission_text("draft-somebody-test", "00")
        self.assertEqual(output["filename"], "draft-somebody-test")
        self.assertEqual(output["rev"], "00")
        self.assertEqual(output["title"], "Correct Draft Title")
        self.assertEqual(output["abstract"].strip(), "This document describes how to test tests.")
        self.assertEqual(len(output["authors"]), 1)  # not checking in detail, parsing is unreliable
        self.assertLessEqual(output["document_date"] - date_today(), datetime.timedelta(days=1))
        self.assertEqual(output["pages"], 2)
        self.assertGreater(output["words"], 0)  # make sure it got something
        self.assertGreater(len(output["first_two_pages"]), 0)  # make sure it got something
        self.assertGreater(output["file_size"], 0)  # make sure it got something
        self.assertEqual(output["formal_languages"].count(), 1)
        self.assertIsNone(output["xml_version"])

        # name mismatch
        txt, _ = submission_file(
            "draft-somebody-wrong-name-00",  # name that appears in the file
            "draft-somebody-test-00.txt",
            None,
            "test_submission.txt",
            title="Correct Draft Title",
        )
        with txt_path.open('w') as fd:
            fd.write(txt.read())
        txt.close()
        with self.assertRaisesMessage(SubmissionError, 'disagrees with submission filename'):
            process_submission_text("draft-somebody-test", "00")

        # rev mismatch
        txt, _ = submission_file(
            "draft-somebody-test-01",  # name that appears in the file
            "draft-somebody-test-00.txt",
            None,
            "test_submission.txt",
            title="Correct Draft Title",
        )
        with txt_path.open('w') as fd:
            fd.write(txt.read())
        txt.close()
        with self.assertRaisesMessage(SubmissionError, 'disagrees with submission revision'):
            process_submission_text("draft-somebody-test", "00")

    def test_process_and_validate_submission(self):
        xml_data = {
            "title": "The Title",
            "authors": [{
                "name": "Jane Doe",
                "email": "jdoe@example.com",
                "affiliation": "Test Centre",
                "country": "UK",
            }],
            "xml_version": "3",
        }
        text_data = {
            "title": "The Title",
            "abstract": "This is an abstract.",
            "authors": [{
                "name": "John Doh",
                "email": "ignored@example.com",
                "affiliation": "Ignored",
                "country": "CA",
            }],
            "document_date": date_today(),
            "pages": 25,
            "words": 1234,
            "first_two_pages": "Pages One and Two",
            "file_size": 4321,
            "formal_languages": FormalLanguageName.objects.none(),
        }
        submission = SubmissionFactory(
            state_id="validating",
            file_types=".xml,.txt",
        )
        with mock.patch("ietf.submit.utils.process_submission_xml", return_value=xml_data):
            with mock.patch("ietf.submit.utils.process_submission_text", return_value=text_data):
                with mock.patch("ietf.submit.utils.render_missing_formats") as mock_render:
                    with mock.patch("ietf.submit.utils.apply_checkers") as mock_checkers:
                        process_and_validate_submission(submission)
        self.assertTrue(mock_render.called)
        self.assertTrue(mock_checkers.called)
        submission = Submission.objects.get(pk=submission.pk)
        self.assertEqual(submission.title, text_data["title"])
        self.assertEqual(submission.abstract, text_data["abstract"])
        self.assertEqual(submission.authors, xml_data["authors"])
        self.assertEqual(submission.document_date, text_data["document_date"])
        self.assertEqual(submission.pages, text_data["pages"])
        self.assertEqual(submission.words, text_data["words"])
        self.assertEqual(submission.first_two_pages, text_data["first_two_pages"])
        self.assertEqual(submission.file_size, text_data["file_size"])
        self.assertEqual(submission.xml_version, xml_data["xml_version"])

    def test_status_of_validating_submission(self):
        s = SubmissionFactory(state_id='validating')
        url = urlreverse('ietf.submit.views.submission_status', kwargs={'submission_id': s.pk})
        r = self.client.get(url)
        self.assertContains(r, s.name)
        self.assertContains(r, 'This submission is being processed and validated.', status_code=200)

    @override_settings(
        IDSUBMIT_MAX_VALIDATION_TIME=datetime.timedelta(minutes=30),
        IDSUBMIT_EXPIRATION_AGE=datetime.timedelta(minutes=90),
    )
    def test_cancel_stale_submissions(self):
        # these will be lists of (Submission, "state_id") pairs
        submissions_to_skip = []
        submissions_to_cancel = []

        # submissions in the validating state
        fresh_submission = SubmissionFactory(state_id='validating')
        fresh_submission.submissionevent_set.create(
            desc='fake created event',
            time=timezone.now() - datetime.timedelta(minutes=15),
        )
        submissions_to_skip.append((fresh_submission, "validating"))

        stale_submission = SubmissionFactory(state_id='validating')
        stale_submission.submissionevent_set.create(
            desc='fake created event',
            time=timezone.now() - datetime.timedelta(minutes=30, seconds=1),
        )
        submissions_to_cancel.append((stale_submission, "validating"))
        
        # submissions in other states
        for state in DraftSubmissionStateName.objects.filter(used=True).exclude(slug="validating"):
            to_skip = SubmissionFactory(state_id=state.pk)
            to_skip.submissionevent_set.create(
                desc="fake created event",
                time=timezone.now() - datetime.timedelta(minutes=45),  # would be canceled if it were "validating"
            )
            submissions_to_skip.append((to_skip, state.pk))
            to_expire = SubmissionFactory(state_id=state.pk)
            to_expire.submissionevent_set.create(
                desc="fake created event",
                time=timezone.now() - datetime.timedelta(minutes=90, seconds=1),
            )
            if state.pk in ["posted", "cancel"]:
                submissions_to_skip.append((to_expire, state.pk))  # these ones should not be expired regardless of age
            else:
                submissions_to_cancel.append(((to_expire, state.pk)))

        cancel_stale_submissions()

        for _subm, original_state_id in submissions_to_skip:
            subm = Submission.objects.get(pk=_subm.pk)
            self.assertEqual(subm.state_id, original_state_id)
            self.assertEqual(subm.submissionevent_set.count(), 1)

        for _subm, _ in submissions_to_cancel:
            subm = Submission.objects.get(pk=_subm.pk)
            self.assertEqual(subm.state_id, "cancel")
            self.assertEqual(subm.submissionevent_set.count(), 2)

        
class RefsTests(BaseSubmitTestCase):

    def test_draft_refs_identification(self):

        group = None
        file, __ = submission_file('draft-some-subject-00', 'draft-some-subject-00.txt', group, "test_submission.txt", )
        draft = PlaintextDraft(file.read(), file.name)
        refs = draft.get_refs()
        self.assertEqual(refs['rfc2119'], 'norm')
        self.assertEqual(refs['rfc8174'], 'norm')
        self.assertEqual(refs['rfc8126'], 'info')
        self.assertEqual(refs['rfc8175'], 'info')


class PostSubmissionTests(BaseSubmitTestCase):

    @override_settings(RFC_FILE_TYPES=('txt', 'xml'), IDSUBMIT_FILE_TYPES=('pdf', 'md'))
    def test_find_submission_filenames(self):
        """Posting an I-D submission should use IDSUBMIT_FILE_TYPES"""
        draft = WgDraftFactory()
        path = Path(self.staging_dir)
        for ext in ['txt', 'xml', 'pdf', 'md']:
            (path / f'{draft.name}-{draft.rev}.{ext}').touch()
        files = find_submission_filenames(draft)
        self.assertCountEqual(
            files,
            {
                'pdf': f'{path}/{draft.name}-{draft.rev}.pdf',
                'md': f'{path}/{draft.name}-{draft.rev}.md',
                # should NOT find the txt or xml
            }
        )

    @mock.patch('ietf.submit.utils.rebuild_reference_relations')
    @mock.patch('ietf.submit.utils.find_submission_filenames')
    def test_post_submission_rebuilds_ref_relations(self, mock_find_filenames, mock_rebuild_reference_relations):
        """The post_submission method should rebuild reference relations from correct files

        This tests that the post_submission() utility function gets the list of files to handle from the
        find_submission_filenames() method and passes them along to rebuild_reference_relations().
        """
        submission = SubmissionFactory()
        mock_find_filenames.return_value = {'xml': f'{self.staging_dir}/{submission.name}.xml'}
        request = RequestFactory()
        request.user = PersonFactory().user
        post_submission(request, submission, 'doc_desc', 'subm_desc')
        args, kwargs = mock_rebuild_reference_relations.call_args
        self.assertEqual(args[1], mock_find_filenames.return_value)


class ValidateSubmissionFilenameTests(BaseSubmitTestCase):
    def test_validate_submission_name(self):
        # This test does not need BaseSubmitTestCase, it could use TestCase
        good_names = (
            'draft-ietf-mars-foobar',
            'draft-ietf-mars-foobar-01',
            'draft-myname-mydraft')
        bad_names = (
            'draft-includes-filename-extension-01.txt',
            'does-not-start-with-draft',
            'draft-Upper-Case',
            'draft-double--dash',
            'draft-trailing-dash-',
            'draft-tooshort',
            'draft-toolong-this-is-a-very-long-name-for-an-internet-draft',
            u'draft-contains-non-ascii-göran')

        for n in good_names:
            msg = validate_submission_name(n)
            self.assertIsNone(msg)

        for n in bad_names:
            msg = validate_submission_name(n)
            self.assertIsNotNone(msg)

    def test_validate_submission_rev(self):
        # This test needs BaseSubmitTestCase
        ind_doc = IndividualDraftFactory()
        old_wg_doc = WgDraftFactory(relations=[('replaces',ind_doc)])
        new_wg_doc = WgDraftFactory(rev='01', relations=[('replaces',old_wg_doc)])
        path = Path(self.archive_dir) / f'{new_wg_doc.name}-{new_wg_doc.rev}.txt'
        path.touch()

        bad_revs = (None, '', '2', 'aa', '00', '01', '100', '002', u'öö')
        for rev in bad_revs:
            msg = validate_submission_rev(new_wg_doc.name, rev)
            self.assertIsNotNone(msg)

        new_rev = '%02d' % (int(ind_doc.rev)+1)
        msg = validate_submission_rev(ind_doc.name, new_rev)
        self.assertIsNotNone(msg)

        new_rev = '%02d' % (int(old_wg_doc.rev)+1)
        msg = validate_submission_rev(old_wg_doc.name, new_rev)
        self.assertIsNotNone(msg)

        msg = validate_submission_rev(new_wg_doc.name, '02')
        self.assertIsNone(msg)

class TestOldNamesAreProtected(BaseSubmitTestCase):
    
    def test_submit_case_conflited_name_fails(self):
        WgDraftFactory(name="draft-something-HasCapitalLetters")
        with self.assertRaisesMessage(ValidationError, "Case-conflicting draft name found"):
            SubmissionBaseUploadForm.check_for_old_uppercase_collisions("draft-something-hascapitalletters")
        url = urlreverse("ietf.submit.views.upload_submission")
        files = {}
        files["xml"], _ = submission_file("draft-something-hascapitalletters-00", "draft-something-hascapitalletters-00.xml", None, "test_submission.xml")
        r = self.post_to_upload_submission(url, files)
        self.assertContains(r,"Case-conflicting draft name found",status_code=200)


class SubmissionStatusTests(BaseSubmitTestCase):
    """Tests of the submission_status view

    Many tests are interspersed in the monolithic tests above. We can aspire to break these
    out more modularly, though.
    """

    def test_submission_checks(self):
        for state_slug in ("uploaded", "cancel", "posted"):
            submission = SubmissionFactory(state_id=state_slug)
            url = urlreverse(
                "ietf.submit.views.submission_status",
                kwargs={"submission_id": submission.pk},
            )
            # No checks
            r = self.client.get(url)
            self.assertContains(
                r,
                "No submission checks were applied to your Internet-Draft.",
                status_code=200,
            )
            # Inapplicable check
            submission.checks.create(
                checker="yang validation", passed=None, message="Yang message"
            )
            r = self.client.get(url)
            self.assertContains(
                r,
                "No submission checks were applied to your Internet-Draft.",
                status_code=200,
            )
            # Passed check
            submission.checks.create(
                checker="idnits check", passed=True, message="idnits ok"
            )
            r = self.client.get(url)
            self.assertContains(
                r,
                "Your Internet-Draft has been verified to pass the submission checks.",
                status_code=200,
            )
            # Failed check + passed check
            submission.checks.filter(checker="yang validation").update(passed=False)
            r = self.client.get(url)
            self.assertContains(
                r,
                "Your Internet-Draft failed at least one submission check.",
                status_code=200,
            )


class YangCheckerTests(TestCase):
    @mock.patch("ietf.submit.utils.apply_yang_checker_to_draft")
    def test_run_all_yang_model_checks(self, mock_apply):
        active_drafts = WgDraftFactory.create_batch(3)
        WgDraftFactory(states=[("draft", "expired")])
        run_all_yang_model_checks()
        self.assertEqual(mock_apply.call_count, 3)
        self.assertCountEqual(
            [args[0][1] for args in mock_apply.call_args_list],
            active_drafts,
        )

    def test_apply_yang_checker_to_draft(self):
        draft = WgDraftFactory()
        submission = SubmissionFactory(name=draft.name, rev=draft.rev)
        submission.checks.create(checker="my-checker")
        checker = mock.Mock()
        checker.name = "my-checker"
        checker.symbol = "X"
        checker.check_file_txt.return_value = (True, "whee", None, None, {})
        apply_yang_checker_to_draft(checker, draft)
        self.assertEqual(checker.check_file_txt.call_args, mock.call(draft.get_file_name()))


@override_settings(IDSUBMIT_REPOSITORY_PATH="/some/path/", IDSUBMIT_STAGING_PATH="/some/other/path")
class SubmissionErrorTests(TestCase):
    def test_sanitize_message(self):
        sanitized = SubmissionError.sanitize_message(
            "This refers to /some/path/with-a-file\n"
            "and also /some/other/path/with-a-different-file isn't that neat?\n"
            "and has /some/path//////with-slashes"
        )
        self.assertEqual(
            sanitized,
            "This refers to **/with-a-file\n"
            "and also **/with-a-different-file isn't that neat?\n"
            "and has **/with-slashes"
        )
    
    @mock.patch.object(SubmissionError, "sanitize_message")
    def test_submissionerror(self, mock_sanitize_message):
        SubmissionError()
        self.assertFalse(mock_sanitize_message.called)
        SubmissionError("hi", "there")
        self.assertTrue(mock_sanitize_message.called)
        self.assertCountEqual(
            mock_sanitize_message.call_args_list,
            [mock.call("hi"), mock.call("there")],
        )
