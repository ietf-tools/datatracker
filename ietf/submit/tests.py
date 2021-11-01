# Copyright The IETF Trust 2011-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import datetime
import email
import io
import os
import re
import shutil
import sys
import mock

from io import StringIO
from pyquery import PyQuery

from django.conf import settings
from django.urls import reverse as urlreverse
from django.utils.encoding import force_str, force_text

import debug                            # pyflakes:ignore

from ietf.submit.utils import expirable_submissions, expire_submission
from ietf.doc.factories import DocumentFactory, WgDraftFactory, IndividualDraftFactory
from ietf.doc.models import ( Document, DocAlias, DocEvent, State,
    BallotPositionDocEvent, DocumentAuthor, SubmissionDocEvent )
from ietf.doc.utils import create_ballot_if_not_open, can_edit_docextresources, update_action_holders
from ietf.group.factories import GroupFactory, RoleFactory
from ietf.group.models import Group
from ietf.group.utils import setup_default_community_list_for_group
from ietf.meeting.models import Meeting
from ietf.meeting.factories import MeetingFactory
from ietf.message.models import Message
from ietf.name.models import FormalLanguageName
from ietf.person.models import Person
from ietf.person.factories import UserFactory, PersonFactory, EmailFactory
from ietf.submit.factories import SubmissionFactory, SubmissionExtResourceFactory
from ietf.submit.models import Submission, Preapproval, SubmissionExtResource
from ietf.submit.mail import add_submission_email, process_response_email
from ietf.utils.accesstoken import generate_access_token
from ietf.utils.mail import outbox, empty_outbox, get_payload_text
from ietf.utils.models import VersionInfo
from ietf.utils.test_utils import login_testing_unauthorized, TestCase
from ietf.utils.draft import Draft

def submission_file(name, rev, group, format, templatename, author=None, email=None, title=None, year=None, ascii=True):
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
        year = datetime.date.today().strftime("%Y")

    submission_text = template % dict(
            date=datetime.date.today().strftime("%d %B %Y"),
            expiration=(datetime.date.today() + datetime.timedelta(days=100)).strftime("%d %B, %Y"),
            year=year,
            month=datetime.date.today().strftime("%B"),
            day=datetime.date.today().strftime("%d"),
            name="%s-%s" % (name, rev),
            group=group or "",
            author=author.ascii if ascii else author.name,
            asciiAuthor=author.ascii,
            initials=author.initials(),
            surname=author.ascii_parts()[3] if ascii else author.name_parts()[3],
            asciiSurname=author.ascii_parts()[3],
            email=email,
            title=title,
    )
    file = StringIO(submission_text)
    file.name = "%s-%s.%s" % (name, rev, format)
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
        submission_date=datetime.date.today() - datetime.timedelta(days=1),
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


class SubmitTests(TestCase):
    def setUp(self):
        self.saved_idsubmit_staging_path = settings.IDSUBMIT_STAGING_PATH
        self.staging_dir = self.tempdir('submit-staging')
        settings.IDSUBMIT_STAGING_PATH = self.staging_dir

        self.saved_internet_draft_path = settings.INTERNET_DRAFT_PATH
        self.saved_idsubmit_repository_path = settings.IDSUBMIT_REPOSITORY_PATH
        self.repository_dir = self.tempdir('submit-repository')
        settings.INTERNET_DRAFT_PATH = settings.IDSUBMIT_REPOSITORY_PATH = self.repository_dir

        self.saved_archive_dir = settings.INTERNET_DRAFT_ARCHIVE_DIR
        self.archive_dir = self.tempdir('submit-archive')
        settings.INTERNET_DRAFT_ARCHIVE_DIR = self.archive_dir
        
        self.saved_yang_rfc_model_dir = settings.SUBMIT_YANG_RFC_MODEL_DIR
        self.yang_rfc_model_dir = self.tempdir('yang-rfc-model')
        settings.SUBMIT_YANG_RFC_MODEL_DIR = self.yang_rfc_model_dir

        self.saved_yang_draft_model_dir = settings.SUBMIT_YANG_DRAFT_MODEL_DIR
        self.yang_draft_model_dir = self.tempdir('yang-draft-model')
        settings.SUBMIT_YANG_DRAFT_MODEL_DIR = self.yang_draft_model_dir

        self.saved_yang_iana_model_dir = settings.SUBMIT_YANG_IANA_MODEL_DIR
        self.yang_iana_model_dir = self.tempdir('yang-iana-model')
        settings.SUBMIT_YANG_IANA_MODEL_DIR = self.yang_iana_model_dir

        self.saved_yang_catalog_model_dir = settings.SUBMIT_YANG_CATALOG_MODEL_DIR
        self.yang_catalog_model_dir = self.tempdir('yang-catalog-model')
        settings.SUBMIT_YANG_CATALOG_MODEL_DIR = self.yang_catalog_model_dir

        # Submit views assume there is a "next" IETF to look for cutoff dates against
        MeetingFactory(type_id='ietf', date=datetime.date.today()+datetime.timedelta(days=180))

    def tearDown(self):
        shutil.rmtree(self.staging_dir)
        shutil.rmtree(self.repository_dir)
        shutil.rmtree(self.archive_dir)
        shutil.rmtree(self.yang_rfc_model_dir)
        shutil.rmtree(self.yang_draft_model_dir)
        shutil.rmtree(self.yang_iana_model_dir)
        shutil.rmtree(self.yang_catalog_model_dir)
        settings.IDSUBMIT_STAGING_PATH = self.saved_idsubmit_staging_path
        settings.INTERNET_DRAFT_PATH = self.saved_internet_draft_path
        settings.IDSUBMIT_REPOSITORY_PATH = self.saved_idsubmit_repository_path
        settings.INTERNET_DRAFT_ARCHIVE_DIR = self.saved_archive_dir
        settings.SUBMIT_YANG_RFC_MODEL_DIR = self.saved_yang_rfc_model_dir
        settings.SUBMIT_YANG_DRAFT_MODEL_DIR = self.saved_yang_draft_model_dir
        settings.SUBMIT_YANG_IANA_MODEL_DIR = self.saved_yang_iana_model_dir
        settings.SUBMIT_YANG_CATALOG_MODEL_DIR = self.saved_yang_catalog_model_dir


    def create_and_post_submission(self, name, rev, author, group=None, formats=("txt",), base_filename=None):
        """Helper to create and post a submission

        If base_filename is None, defaults to 'test_submission'
        """
        url = urlreverse('ietf.submit.views.upload_submission')
        files = dict()

        for format in formats:
            fn = '.'.join((base_filename or 'test_submission', format))
            files[format], __ = submission_file(name, rev, group, format, fn, author=author)

        r = self.client.post(url, files)
        if r.status_code != 302:
            q = PyQuery(r.content)
            print(q('div.has-error div.alert').text())

        self.assertNoFormPostErrors(r, ".has-error,.alert-danger")

        for format in formats:
            self.assertTrue(os.path.exists(os.path.join(self.staging_dir, "%s-%s.%s" % (name, rev, format))))
            if format == 'xml':
                self.assertTrue(os.path.exists(os.path.join(self.staging_dir, "%s-%s.%s" % (name, rev, 'html'))))
        return r

    def do_submission(self, name, rev, group=None, formats=["txt",], author=None):
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
        r = self.create_and_post_submission(name, rev, author, group, formats)
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
        self.assertEqual(a["name"], author.ascii)
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
            self.assertEqual(submission.replaces, 
                             ",".join(
                                 d.name for d in DocAlias.objects.filter(
                                     pk__in=replaces.split(",") if replaces else []
                                 )
                             ))
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
            time=datetime.datetime.now(),
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
            expires=datetime.datetime.now() + datetime.timedelta(days=settings.INTERNET_DRAFT_DAYS_TO_EXPIRE),
            notify="aliens@example.mars",
            note="",
        )
        sug_replaced_draft.set_state(State.objects.get(used=True, type="draft", slug="active"))
        sug_replaced_alias = DocAlias.objects.create(name=sug_replaced_draft.name)
        sug_replaced_alias.docs.add(sug_replaced_draft)

        name = "draft-ietf-mars-testing-tests"
        rev = "00"
        group = "mars"

        status_url, author = self.do_submission(name, rev, group, formats)

        # supply submitter info, then draft should be in and ready for approval
        mailbox_before = len(outbox)
        replaced_alias = draft.docalias.first()
        r = self.supply_extra_metadata(name, status_url, author.ascii, author.email().address.lower(),
                                       replaces=str(replaced_alias.pk) + "," + str(sug_replaced_alias.pk))

        self.assertEqual(r.status_code, 302)
        status_url = r["Location"]
        self.assertEqual(len(outbox), mailbox_before + 1)
        self.assertTrue("New draft waiting for approval" in outbox[-1]["Subject"])
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

        draft = Document.objects.get(docalias__name=name)
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
        self.assertTrue(draft.expires >= datetime.datetime.now() + datetime.timedelta(days=settings.INTERNET_DRAFT_DAYS_TO_EXPIRE - 1))
        self.assertEqual(draft.get_state("draft-stream-%s" % draft.stream_id).slug, "wg-doc")
        authors = draft.documentauthor_set.all()
        self.assertEqual(len(authors), 1)
        self.assertEqual(authors[0].person, author)
        self.assertEqual(set(draft.formal_languages.all()), set(FormalLanguageName.objects.filter(slug="json")))
        self.assertEqual(draft.relations_that_doc("replaces").count(), 1)
        self.assertTrue(draft.relations_that_doc("replaces").first().target, replaced_alias)
        self.assertEqual(draft.relations_that_doc("possibly-replaces").count(), 1)
        self.assertTrue(draft.relations_that_doc("possibly-replaces").first().target, sug_replaced_alias)
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
        self.assertIn(sug_replaced_alias.name, get_payload_text(outbox[-1]))
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
        r = self.supply_extra_metadata(name, status_url, author.ascii, author.email().address.lower(), replaces='')
        self.assertEqual(r.status_code, 302)
        status_url = r["Location"]

        # Draft should be in the 'grp-appr' state to await approval by WG chair
        submission = Submission.objects.get(name=name, rev=rev)
        self.assertEqual(submission.state_id, 'grp-appr')

        # Approval request notification should be sent to the WG chair
        self.assertEqual(len(outbox), mailbox_before + 1)
        self.assertTrue("New draft waiting for approval" in outbox[-1]["Subject"])
        self.assertTrue(name in outbox[-1]["Subject"])
        self.assertTrue('mars-chairs@ietf.org' in outbox[-1]['To'])

        # Status page should show that group chair approval is needed
        r = self.client.get(status_url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'The submission is pending approval by the group chairs.')

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
                              'replaces': ''})
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
        r = self.supply_extra_metadata(name, status_url, "Submitter Name", "submitter@example.com", replaces="")
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

        draft = Document.objects.get(docalias__name=name)
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
        self.assertTrue(interesting_address in force_text(outbox[-2].as_string()))
        if draft.stream_id == 'ietf':
            self.assertTrue(draft.ad.role_email("ad").address in force_text(outbox[-2].as_string()))
            self.assertTrue(ballot_position.balloter.role_email("ad").address in force_text(outbox[-2].as_string()))
        self.assertTrue("New Version Notification" in outbox[-1]["Subject"])
        self.assertTrue(name in get_payload_text(outbox[-1]))
        r = self.client.get(urlreverse('ietf.doc.views_search.recent_drafts'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, draft.name)
        self.assertContains(r, draft.title)
        # Check submission settings
        self.assertEqual(draft.submission().xml_version, "3" if 'xml' in formats else None)

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
                              'replaces': ''})
        self.assertEqual(r.status_code, 302)
        status_url = r["Location"]

        # Draft should be in the 'ad-appr' state to await approval
        submission = Submission.objects.get(name=name, rev=rev)
        self.assertEqual(submission.state_id, 'ad-appr')

        # Approval request notification should be sent to the AD for the group
        self.assertEqual(len(outbox), mailbox_before + 1)
        self.assertTrue("New draft waiting for approval" in outbox[-1]["Subject"])
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
        r = self.supply_extra_metadata(name, status_url, "Submitter Name", "submitter@example.com", replaces="")

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

        draft = Document.objects.get(docalias__name=name)
        self.assertEqual(draft.rev, rev)
        new_revision = draft.latest_event()
        self.assertEqual(new_revision.type, "new_revision")
        self.assertEqual(new_revision.by.name, "Submitter Name")

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
        r = self.supply_extra_metadata(name, status_url, 'Submitter name', 'submitter@example.com', replaces='')
        self.assertEqual(r.status_code, 302)

        # force post of submission
        r = self.client.get(status_url)
        q = PyQuery(r.content)
        force_post_button = q('[type=submit]:contains("Force post")')
        self.assertEqual(len(force_post_button), 1)
        action = force_post_button.parents("form").find('input[type=hidden][name="action"]').val()
        r = self.client.post(status_url, dict(action=action))

        doc = Document.objects.get(docalias__name=name)
        self.assertEqual(doc.documentauthor_set.count(), 1)
        docauth = doc.documentauthor_set.first()
        self.assertEqual(docauth.person, author)
        self.assertEqual(docauth.affiliation, '')
        self.assertEqual(docauth.country, '')

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
        r = self.supply_extra_metadata(name, status_url, 'Submitter name', 'submitter@example.com', replaces='',
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
        r = self.supply_extra_metadata(name, status_url, author.name, username, replaces="")

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

        draft = Document.objects.get(docalias__name=name)
        self.assertEqual(draft.rev, rev)
        self.assertEqual(draft.docextresource_set.count(), 0)
        new_revision = draft.latest_event()
        self.assertEqual(new_revision.type, "new_revision")
        self.assertEqual(new_revision.by.name, author.name)
        self._assert_extresource_change_event(draft, is_present=False)

        # Check submission settings
        self.assertEqual(draft.submission().xml_version, "3" if 'xml' in formats else None)

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
        r = self.supply_extra_metadata(name, status_url, author.name, username, replaces='',
                                       extresources=resources)
        self.assertEqual(r.status_code, 302)
        status_url = r['Location']

        r = self.client.get(status_url)
        self.assertEqual(r.status_code, 200)
        self._assert_extresources_in_table(r, resources)
        self._assert_extresources_form_not_present(r)

        # Check that the draft itself got the resources        
        draft = Document.objects.get(docalias__name=name)
        self.assertCountEqual(
            [str(r) for r in draft.docextresource_set.all()],
            [str(r) for r in resources],
        )
        self._assert_extresource_change_event(draft, is_present=True)

    def test_submit_update_individual(self):
        IndividualDraftFactory(name='draft-ietf-random-thing', states=[('draft','rfc')], other_aliases=['rfc9999',], pages=5)
        ad=Person.objects.get(user__username='ad')
        # Group of None here does not reflect real individual submissions
        draft = IndividualDraftFactory(group=None, ad = ad, authors=[ad,], notify='aliens@example.mars', pages=5)
        replaces_count = draft.relateddocument_set.filter(relationship_id='replaces').count()
        name = draft.name
        rev = '%02d'%(int(draft.rev)+1)
        status_url, author = self.do_submission(name,rev)
        mailbox_before = len(outbox)

        replaced_alias = draft.docalias.first()
        r = self.supply_extra_metadata(name, status_url, "Submitter Name", "author@example.com", replaces=str(replaced_alias.pk))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'cannot replace itself')
        self._assert_extresources_in_table(r, [])
        self._assert_extresources_form(r, [])

        replaced_alias = DocAlias.objects.get(name='draft-ietf-random-thing')
        r = self.supply_extra_metadata(name, status_url, "Submitter Name", "author@example.com", replaces=str(replaced_alias.pk))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'cannot replace an RFC')
        self._assert_extresources_in_table(r, [])
        self._assert_extresources_form(r, [])

        replaced_alias.document.set_state(State.objects.get(type='draft-iesg',slug='approved'))
        replaced_alias.document.set_state(State.objects.get(type='draft',slug='active'))
        r = self.supply_extra_metadata(name, status_url, "Submitter Name", "author@example.com", replaces=str(replaced_alias.pk))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'approved by the IESG and cannot')
        self._assert_extresources_in_table(r, [])
        self._assert_extresources_form(r, [])

        r = self.supply_extra_metadata(name, status_url, "Submitter Name", "author@example.com", replaces='')
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
        draft = Document.objects.get(docalias__name=name)
        self.assertEqual(draft.rev, rev)
        self.assertEqual(draft.relateddocument_set.filter(relationship_id='replaces').count(), replaces_count)
        self.assertEqual(draft.docextresource_set.count(), 0)
        #
        r = self.client.get(urlreverse('ietf.doc.views_search.recent_drafts'))
        self.assertContains(r, draft.name)
        self.assertContains(r, draft.title)
        self._assert_extresource_change_event(draft, is_present=False)

    def submit_existing_with_extresources(self, group_type, stream_type='ietf'):
        """Submit a draft with external resources
        
        Unlike some other tests in this module, does not confirm draft if this would be required.
        """
        orig_draft = DocumentFactory(
            type_id='draft',
            group=GroupFactory(type_id=group_type) if group_type else None,
            stream_id=stream_type,
        )  # type: Document
        name = orig_draft.name
        group = orig_draft.group
        new_rev = '%02d' % (int(orig_draft.rev) + 1)
        author = PersonFactory()  # type: Person
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
                                       replaces='', extresources=[])
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
            replaces=str(replaced_draft.docalias.first().pk),
        )
        
        submission = Submission.objects.get(name=name, rev=rev)
        self.assertEqual(submission.state_id, 'ad-appr' if notify_ad else 'grp-appr')
        self.assertEqual(len(outbox), mailbox_before + 1)
        notice = outbox[-1]
        self.assertIn(
            ad.user.email if notify_ad else '%s-chairs@ietf.org' % replaced_draft.group.acronym,
            notice['To']
        )
        self.assertIn('New draft waiting for approval', notice['Subject'])

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
        r = self.supply_extra_metadata(name, status_url, "Submitter Name", "author@example.com", replaces='')
        self.assertEqual(r.status_code, 302)
        status_url = r["Location"]
        r = self.client.get(status_url)
        self.assertEqual(len(outbox), mailbox_before + 1)
        confirmation_url = self.extract_confirmation_url(outbox[-1])
        mailbox_before = len(outbox)
        r = self.client.post(confirmation_url, {'action':'cancel'})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(len(outbox), mailbox_before)
        draft = Document.objects.get(docalias__name=name)
        self.assertEqual(draft.rev, old_rev)

    def test_submit_new_wg_with_dash(self):
        group = Group.objects.create(acronym="mars-special", name="Mars Special", type_id="wg", state_id="active")

        name = "draft-ietf-%s-testing-tests" % group.acronym

        self.do_submission(name, "00")

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

        self.do_submission(name, "00")

        self.assertEqual(Submission.objects.get(name=name).group.acronym, group.acronym)
        self.assertEqual(Submission.objects.get(name=name).group.type_id, group.type_id)

    def test_submit_new_iab(self):
        name = "draft-iab-testing-tests"

        self.do_submission(name, "00")

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
        document_date = datetime.date.today() - datetime.timedelta(days=-3)
        r = self.client.post(edit_url, {
            "edit-title": "some title",
            "edit-rev": "00",
            "edit-document_date": document_date.strftime("%Y-%m-%d"),
            "edit-abstract": "some abstract",
            "edit-pages": "123",
            "submitter-name": "Some Random Test Person",
            "submitter-email": "random@example.com",
            "replaces": str(draft.docalias.first().pk),
            "edit-note": "no comments",
            "authors-0-name": "Person 1",
            "authors-0-email": "person1@example.com",
            "authors-1-name": "Person 2",
            "authors-1-email": "person2@example.com",
            "authors-2-name": "Person 3",
            "authors-2-email": "person3@example.com",
            "authors-prefix": ["authors-", "authors-0", "authors-1", "authors-2"],
        })
        self.assertNoFormPostErrors(r, ".has-error,.alert-danger")

        submission = Submission.objects.get(name=name)
        self.assertEqual(submission.title, "some title")
        self.assertEqual(submission.document_date, document_date)
        self.assertEqual(submission.abstract, "some abstract")
        self.assertEqual(submission.pages, 123)
        self.assertEqual(submission.note, "no comments")
        self.assertEqual(submission.submitter, "Some Random Test Person <random@example.com>")
        self.assertEqual(submission.replaces, draft.docalias.first().name)
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

        draft = Document.objects.get(docalias__name=name)
        self.assertEqual(draft.rev, rev)
        self.assertEqual(draft.docextresource_set.count(), 0)

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

        # status page as unpriviliged => no edit button
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

        self.do_submission(name, rev, group, ["txt", "xml", "pdf"])

        self.assertEqual(Submission.objects.filter(name=name).count(), 1)

        self.assertTrue(os.path.exists(os.path.join(self.staging_dir, "%s-%s.txt" % (name, rev))))
        self.assertTrue(name in io.open(os.path.join(self.staging_dir, "%s-%s.txt" % (name, rev))).read())
        self.assertTrue(os.path.exists(os.path.join(self.staging_dir, "%s-%s.xml" % (name, rev))))
        self.assertTrue(name in io.open(os.path.join(self.staging_dir, "%s-%s.xml" % (name, rev))).read())
        self.assertTrue('<?xml version="1.0" encoding="UTF-8"?>' in io.open(os.path.join(self.staging_dir, "%s-%s.xml" % (name, rev))).read())
        self.assertTrue(os.path.exists(os.path.join(self.staging_dir, "%s-%s.pdf" % (name, rev))))
        self.assertTrue('This is PDF' in io.open(os.path.join(self.staging_dir, "%s-%s.pdf" % (name, rev))).read())

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
        r = self.client.get(urlreverse("ietf.submit.views.tool_instructions"))
        self.assertEqual(r.status_code, 200)
        
    def test_blackout_access(self):
        # get
        url = urlreverse('ietf.submit.views.upload_submission')

        # Put today in the blackout period
        meeting = Meeting.get_current_meeting()
        meeting.importantdate_set.create(name_id='idcutoff',date=datetime.date.today()-datetime.timedelta(days=2))
        
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
        meeting.date = datetime.date.today()+datetime.timedelta(days=7)
        meeting.save()
        meeting.importantdate_set.filter(name_id='idcutoff').delete()
        meeting.importantdate_set.create(name_id='idcutoff', date=datetime.date.today()+datetime.timedelta(days=7))
        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('input[type=file][name=txt]')), 1)        

        meeting = Meeting.get_current_meeting()
        meeting.date = datetime.date.today()
        meeting.save()
        meeting.importantdate_set.filter(name_id='idcutoff').delete()
        meeting.importantdate_set.create(name_id='idcutoff', date=datetime.date.today())
        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('input[type=file][name=txt]')), 1)        

        meeting = Meeting.get_current_meeting()
        meeting.date = datetime.date.today()-datetime.timedelta(days=1)
        meeting.save()
        meeting.importantdate_set.filter(name_id='idcutoff').delete()
        meeting.importantdate_set.create(name_id='idcutoff', date=datetime.date.today()-datetime.timedelta(days=1))
        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('input[type=file][name=txt]')), 1)        

        
    def submit_bad_file(self, name, formats):
        rev = ""
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
            files[format], author = submission_file(name, rev, group, "bad", "test_submission.bad")

        r = self.client.post(url, files)

        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(len(q("form .has-error")) > 0)
        m = q('div.has-error div.alert').text()

        return r, q, m
        
    def submit_bad_doc_name_with_ext(self, name, formats):
        group = None
        url = urlreverse('ietf.submit.views.upload_submission')

        # submit
        files = {}
        for format in formats:
            rev = '00.%s' % format
            files[format], author = submission_file(name, rev, group, format, "test_submission.%s" % format)
            files[format].name = "%s-%s.%s" % (name, 00, format)

        r = self.client.post(url, files)

        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(len(q("form .has-error")) > 0)
        m = q('div.has-error div.alert').text()

        return r, q, m
        
    def test_submit_bad_file_txt(self):
        r, q, m = self.submit_bad_file("some name", ["txt"])
        self.assertIn('Invalid characters were found in the name', m)
        self.assertIn('Expected the TXT file to have extension ".txt"', m)
        self.assertIn('Expected an TXT file of type "text/plain"', m)
        self.assertIn('document does not contain a legitimate name', m)

    def test_submit_bad_doc_name_txt(self):
        r, q, m = self.submit_bad_doc_name_with_ext("draft-foo.dot-bar", ["txt"])
        self.assertIn('contains a disallowed character with byte code: 46', m)
        r, q, m = self.submit_bad_doc_name_with_ext("draft-foo-bar", ["xml"])
        self.assertIn('Did you include a filename extension in the name by mistake?', m)

    def test_submit_bad_file_xml(self):
        r, q, m = self.submit_bad_file("some name", ["xml"])
        self.assertIn('Invalid characters were found in the name', m)
        self.assertIn('Expected the XML file to have extension ".xml"', m)
        self.assertIn('Expected an XML file of type "application/xml"', m)

    def test_submit_bad_file_pdf(self):
        r, q, m = self.submit_bad_file("some name", ["pdf"])
        self.assertIn('Invalid characters were found in the name', m)
        self.assertIn('Expected the PDF file to have extension ".pdf"', m)
        self.assertIn('Expected an PDF file of type "application/pdf"', m)

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
                files[format], author = submission_file(name, rev, group, format, "test_submission.%s" % format)

            r = self.client.post(url, files)

            self.assertEqual(r.status_code, 200)
            q = PyQuery(r.content)
            m = q('div.alert-danger').text()

            self.assertIn('Unexpected files already in the archive', m)

    def test_submit_nonascii_name(self):
        name = "draft-authorname-testing-nonascii"
        rev = "00"
        group = None

        # get
        url = urlreverse('ietf.submit.views.upload_submission')
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)

        # submit
        #author = PersonFactory(name=u"Jörgen Nilsson".encode('latin1'))
        user = UserFactory(first_name="Jörgen", last_name="Nilsson")
        author = PersonFactory(user=user)

        file, __ = submission_file(name, rev, group, "txt", "test_submission.nonascii", author=author, ascii=False)
        files = {"txt": file }

        r = self.client.post(url, files)
        self.assertEqual(r.status_code, 302)
        status_url = r["Location"]
        r = self.client.get(status_url)
        q = PyQuery(r.content)
        m = q('p.alert-warning').text()

        self.assertIn('The idnits check returned 1 warning', m)

    def test_submit_missing_author_email(self):
        name = "draft-authorname-testing-noemail"
        rev = "00"
        group = None

        author = PersonFactory()
        for e in author.email_set.all():
            e.delete()

        files = {"txt": submission_file(name, rev, group, "txt", "test_submission.txt", author=author, ascii=True)[0] }

        # submit
        url = urlreverse('ietf.submit.views.upload_submission')
        r = self.client.post(url, files)
        self.assertEqual(r.status_code, 302)
        status_url = r["Location"]
        r = self.client.get(status_url)
        q = PyQuery(r.content)
        m = q('p.text-danger').text()

        self.assertIn('Author email error', m)
        self.assertIn('Found no email address.', m)

    def test_submit_bad_author_email(self):
        name = "draft-authorname-testing-bademail"
        rev = "00"
        group = None

        author = PersonFactory()
        email = author.email_set.first()
        email.address = '@bad.email'
        email.save()

        files = {"xml": submission_file(name, rev, group, "xml", "test_submission.xml", author=author, ascii=False)[0] }

        # submit
        url = urlreverse('ietf.submit.views.upload_submission')
        r = self.client.post(url, files)
        self.assertEqual(r.status_code, 302)
        status_url = r["Location"]
        r = self.client.get(status_url)
        q = PyQuery(r.content)
        m = q('p.text-danger').text()

        self.assertIn('Author email error', m)
        self.assertIn('Invalid email address.', m)

    def test_submit_invalid_yang(self):
        name = "draft-yang-testing-invalid"
        rev = "00"
        group = None

        # submit
        files = {"txt": submission_file(name, rev, group, "txt", "test_submission_invalid_yang.txt")[0] }

        url = urlreverse('ietf.submit.views.upload_submission')
        r = self.client.post(url, files)
        self.assertEqual(r.status_code, 302)
        status_url = r["Location"]
        r = self.client.get(status_url)
        q = PyQuery(r.content)
        #
        self.assertContains(r, 'The yang validation returned 1 error')
        #
        m = q('#yang-validation-message').text()
        for command in ['xym', 'pyang', 'yanglint']:
            version = VersionInfo.objects.get(command=command).version
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
                                                submission_date=datetime.date.today(),
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
        submission = SubmissionFactory(state_id='grp-appr', group=group)  # type: Submission
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
        submission = SubmissionFactory(state_id=state, group=group)  # type: Submission
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
        submission = SubmissionFactory(state_id='grp-appr')  # type: Submission
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
        self.assertEqual(len(removed_div('span.label:contains("Removed")')), 1)
        self.assertEqual(len(removed_div('span.label:contains("New")')), 0)

        # The added resource should appear once (for the submission), tagged as new
        added_div = q('td>div:contains("Resource to be added")')
        self.assertEqual(len(added_div), 1)
        self.assertEqual(len(added_div('span.label:contains("Removed")')), 0)
        self.assertEqual(len(added_div('span.label:contains("New")')), 1)

        # The kept resource should appear twice (once for the doc, once for the submission), with no tag
        kept_div = q('td>div:contains("Resource to be kept")')
        self.assertEqual(len(kept_div), 2)
        self.assertEqual(len(kept_div('span.label:contains("Removed")')), 0)
        self.assertEqual(len(kept_div('span.label:contains("New")')), 0)
        
class ApprovalsTestCase(TestCase):
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
                                  submission_date=datetime.date.today(),
                                  rev="00",
                                  state_id="posted")
        Submission.objects.create(name="draft-ietf-mars-bar",
                                  group=Group.objects.get(acronym="mars"),
                                  submission_date=datetime.date.today(),
                                  rev="00",
                                  state_id="grp-appr")
        Submission.objects.create(name="draft-ietf-mars-quux",
                                  group=Group.objects.get(acronym="mars"),
                                  submission_date=datetime.date.today(),
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
        self.assertTrue(len(q("form .has-error")) > 0)

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

class ManualPostsTestCase(TestCase):
    def test_manual_posts(self):
        GroupFactory(acronym='mars')

        url = urlreverse('ietf.submit.views.manualpost')
        # Secretariat has access
        self.client.login(username="secretary", password="secretary+password")

        Submission.objects.create(name="draft-ietf-mars-foo",
                                  group=Group.objects.get(acronym="mars"),
                                  submission_date=datetime.date.today(),
                                  state_id="manual")
        Submission.objects.create(name="draft-ietf-mars-bar",
                                  group=Group.objects.get(acronym="mars"),
                                  submission_date=datetime.date.today(),
                                  rev="00",
                                  state_id="grp-appr")

        # get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)

        self.assertEqual(len(q('.submissions a:contains("draft-ietf-mars-foo")')), 1)
        self.assertEqual(len(q('.submissions a:contains("draft-ietf-mars-bar")')), 0)

    def test_waiting_for_draft(self):
        message_string = """To: somebody@ietf.org
From: joe@test.com
Date: {}
Subject: test submission via email

Please submit my draft at http://test.com/mydraft.txt

Thank you
""".format(datetime.datetime.now().ctime())
        message = email.message_from_string(force_str(message_string))
        submission, submission_email_event = (
            add_submission_email(request=None,
                                 remote_ip ="192.168.0.1",
                                 name = "draft-my-new-draft",
                                 rev='00',
                                 submission_pk=None,
                                 message = message,
                                 by = Person.objects.get(name="(System)"),
                                 msgtype = "msgin") )

        url = urlreverse('ietf.submit.views.manualpost')
        # Secretariat has access
        self.client.login(username="secretary", password="secretary+password")

        # get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)

        self.assertEqual(len(q('.waiting-for-draft a:contains("draft-my-new-draft")')), 1)

        # Same name should raise an error
        with self.assertRaises(Exception):
            add_submission_email(request=None,
                                 remote_ip ="192.168.0.1",
                                 name = "draft-my-new-draft",
                                 rev='00',
                                 submission_pk=None,
                                 message = message,
                                 by = Person.objects.get(name="(System)"),
                                 msgtype = "msgin")

        # Cancel this one
        r = self.client.post(urlreverse("ietf.submit.views.cancel_waiting_for_draft"), {
            "submission_id": submission.pk,
            "access_token": submission.access_token(),
        })
        self.assertEqual(r.status_code, 302)
        url = r["Location"]
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('.waiting-for-draft a:contains("draft-my-new-draft")')), 0)

        # Should now be able to add it again
        submission, submission_email_event = (
            add_submission_email(request=None,
                                 remote_ip ="192.168.0.1",
                                 name = "draft-my-new-draft",
                                 rev='00',
                                 submission_pk=None,
                                 message = message,
                                 by = Person.objects.get(name="(System)"),
                                 msgtype = "msgin") )


    def test_waiting_for_draft_with_attachment(self):
        frm = "joe@test.com"
        
        message_string = """To: somebody@ietf.org
From: {}
Date: {}
Subject: A very important message with a small attachment
Content-Type: multipart/mixed; boundary="------------090908050800030909090207"

This is a multi-part message in MIME format.
--------------090908050800030909090207
Content-Type: text/plain; charset=utf-8; format=flowed
Content-Transfer-Encoding: 7bit

The message body will probably say something about the attached document

--------------090908050800030909090207
Content-Type: text/plain; charset=UTF-8; name="attach.txt"
Content-Transfer-Encoding: base64
Content-Disposition: attachment; filename="attach.txt"

QW4gZXhhbXBsZSBhdHRhY2htZW50IHd0aG91dCB2ZXJ5IG11Y2ggaW4gaXQuCgpBIGNvdXBs
ZSBvZiBsaW5lcyAtIGJ1dCBpdCBjb3VsZCBiZSBhIGRyYWZ0Cg==
--------------090908050800030909090207--
""".format(frm, datetime.datetime.now().ctime())

        message = email.message_from_string(force_str(message_string))
        submission, submission_email_event = (
            add_submission_email(request=None,
                                 remote_ip ="192.168.0.1",
                                 name = "draft-my-new-draft",
                                 rev='00',
                                 submission_pk=None,
                                 message = message,
                                 by = Person.objects.get(name="(System)"),
                                 msgtype = "msgin") )

        manualpost_page_url = urlreverse('ietf.submit.views.manualpost')
        # Secretariat has access
        self.client.login(username="secretary", password="secretary+password")

        self.check_manualpost_page(submission=submission, 
                                   submission_email_event=submission_email_event,
                                   the_url=manualpost_page_url, 
                                   submission_name_fragment='draft-my-new-draft',
                                   frm=frm,
                                   is_secretariat=True)
 
        # Try the status page with no credentials
        self.client.logout()

        self.check_manualpost_page(submission=submission, 
                                   submission_email_event=submission_email_event,
                                   the_url=manualpost_page_url, 
                                   submission_name_fragment='draft-my-new-draft',
                                   frm=frm,
                                   is_secretariat=False)
        
        # Post another message to this submission using the link
        message_string = """To: somebody@ietf.org
From: joe@test.com
Date: {}
Subject: A new submission message with a small attachment
Content-Type: multipart/mixed; boundary="------------090908050800030909090207"

This is a multi-part message in MIME format.
--------------090908050800030909090207
Content-Type: text/plain; charset=utf-8; format=flowed
Content-Transfer-Encoding: 7bit

The message body will probably say something more about the attached document

--------------090908050800030909090207
Content-Type: text/plain; charset=UTF-8; name="attach.txt"
Content-Transfer-Encoding: base64
Content-Disposition: attachment; filename="attachment.txt"

QW4gZXhhbXBsZSBhdHRhY2htZW50IHd0aG91dCB2ZXJ5IG11Y2ggaW4gaXQuCgpBIGNvdXBs
ZSBvZiBsaW5lcyAtIGJ1dCBpdCBjb3VsZCBiZSBhIGRyYWZ0Cg==
--------------090908050800030909090207--
""".format(datetime.datetime.now().ctime())

        # Back to secretariat
        self.client.login(username="secretary", password="secretary+password")

        r, q = self.request_and_parse(manualpost_page_url)

        url = self.get_href(q, "a#new-submission-email:contains('New submission from email')")

        # Get the form
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        #self.assertEqual(len(q('input[name=edit-title]')), 1)

        # Post the new message
        r = self.client.post(url, {
            "name": "draft-my-next-new-draft-00",
            "direction": "incoming",
            "message": message_string,
        })

        if r.status_code != 302:
            q = PyQuery(r.content)
            print(q)

        self.assertEqual(r.status_code, 302)
        

        #self.check_manualpost_page(submission, submission_email_event,
        #                        url, 'draft-my-next-new-draft'
        #                        'Another very important message',
        #                        true)

    def check_manualpost_page(self, submission, submission_email_event,
                              the_url, submission_name_fragment,
                              frm,
                              is_secretariat):
        # get the page listing manual posts
        r, q = self.request_and_parse(the_url)
        selector = "#waiting-for-draft a#add-submission-email%s:contains('Add email')" % submission.pk

        if is_secretariat:
            # Can add an email to the submission
            add_email_url = self.get_href(q, selector)
        else:
            # No add email button button
            self.assertEqual(len(q(selector)), 0)

        # Find the link for our submission in those awaiting drafts
        submission_url = self.get_href(q, "#waiting-for-draft a#aw{}:contains('{}')".
                                       format(submission.pk, submission_name_fragment))

        # Follow the link to the status page for this submission
        r, q = self.request_and_parse(submission_url)
        
        selector = "#history a#reply%s:contains('Reply')" % submission.pk

        if is_secretariat:
            # check that reply button is visible and get the form
            reply_url = self.get_href(q, selector)

            # Get the form
            r = self.client.get(reply_url)
            self.assertEqual(r.status_code, 200)
            reply_q = PyQuery(r.content)
            self.assertEqual(len(reply_q('input[name=to]')), 1)
        else:
            # No reply button
            self.assertEqual(len(q(selector)), 0)

        if is_secretariat:
            # Now try to send an email using the send email link
    
            selector = "a#send%s:contains('Send Email')" % submission.pk
            send_url = self.get_href(q, selector)

            self.do_submission_email(the_url = send_url,
                                     to = frm,
                                     body = "A new message")

        # print q
        # print submission.pk
        # print submission_email_event.pk
        
        # Find the link for our message in the list
        url = self.get_href(q, "#aw{}-{}:contains('{}')".format(submission.pk, 
                                                                submission_email_event.message.pk,
                                                                "Received message - manual post"))
        
        # Page displaying message details
        r, q = self.request_and_parse(url)
        
        if is_secretariat:
            # check that reply button is visible

            reply_href = self.get_href(q, "#email-details a#reply%s:contains('Reply')" % submission.pk)

        else:
            # No reply button
            self.assertEqual(len(q(selector)), 0)
            reply_href = None

        # check that attachment link is visible

        url = self.get_href(q, "#email-details a#attach{}:contains('attach.txt')".format(submission.pk))

        # Fetch the attachment
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        
        # Attempt a reply if we can
        if reply_href == None:
            return

        self.do_submission_email(the_url = reply_href,
                                 to = frm,
                                 body = "A reply to the message")
        
        # try adding an email to the submission
        # Use the add email link from the manual post listing page

        if is_secretariat:
            # Can add an email to the submission
            # add_email_url set previously
            r = self.client.get(add_email_url)
            self.assertEqual(r.status_code, 200)
            add_email_q = PyQuery(r.content)
            self.assertEqual(len(add_email_q('input[name=submission_pk]')), 1)

            # Add a simple email
            new_message_string = """To: somebody@ietf.org
From: joe@test.com
Date: {}
Subject: Another message

About my submission

Thank you
""".format(datetime.datetime.now().ctime())

            r = self.client.post(add_email_url, {
                "name": "{}-{}".format(submission.name, submission.rev),
                "direction": "incoming",
                "submission_pk": submission.pk,
                "message": new_message_string,
            })

            if r.status_code != 302:
                q = PyQuery(r.content)
                print(q)

            self.assertEqual(r.status_code, 302)

    def request_and_parse(self, url):
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        return r, PyQuery(r.content)

        
    def get_href(self, q, query):
        link = q(query)
        self.assertEqual(len(link), 1)

        return PyQuery(link[0]).attr('href')


    def do_submission_email(self, the_url, to, body):
        # check the page
        r = self.client.get(the_url)
        q = PyQuery(r.content)
        post_button = q('[type=submit]:contains("Send Email")')
        self.assertEqual(len(post_button), 1)
        subject = post_button.parents("form").find('input[name="subject"]').val()
        frm = post_button.parents("form").find('input[name="frm"]').val()
        cc = post_button.parents("form").find('input[name="cc"]').val()
        reply_to = post_button.parents("form").find('input[name="reply_to"]').val()

        empty_outbox()
        
        # post submitter info
        r = self.client.post(the_url, {
            "subject": subject,
            "frm": frm,
            "to": to,
            "cc": cc,
            "reply_to": reply_to,
            "body": body,
        })

        self.assertEqual(r.status_code, 302)

        self.assertEqual(len(outbox), 1)

        outmsg = outbox[0]
        self.assertTrue(to in outmsg['To'])
        
        reply_to = outmsg['Reply-To']
        self.assertIsNotNone(reply_to, "Expected Reply-To")
        
        # Build a reply

        message_string = """To: {}
From: {}
Date: {}
Subject: test
""".format(reply_to, to, datetime.datetime.now().ctime())

        result = process_response_email(message_string)
        self.assertIsInstance(result, Message)

        return r

    def do_submission(self, name, rev, group=None, formats=["txt",]):
        # We're not testing the submission process - just the submission status 

        # get
        url = urlreverse('ietf.submit.views.upload_submission')
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('input[type=file][name=txt]')), 1)
        self.assertEqual(len(q('input[type=file][name=xml]')), 1)

        # submit
        files = {}
        for format in formats:
            files[format], author = submission_file(name, rev, group, format, "test_submission.%s" % format)

        r = self.client.post(url, files)
        if r.status_code != 302:
            q = PyQuery(r.content)
            print(q('div.has-error span.help-block div').text())

        self.assertEqual(r.status_code, 302)

        status_url = r["Location"]
        for format in formats:
            self.assertTrue(os.path.exists(os.path.join(self.staging_dir, "%s-%s.%s" % (name, rev, format))))
        self.assertEqual(Submission.objects.filter(name=name).count(), 1)
        submission = Submission.objects.get(name=name)
        self.assertTrue(all([ c.passed!=False for c in submission.checks.all() ]))
        self.assertEqual(len(submission.authors), 1)
        author = submission.authors[0]
        self.assertEqual(author["name"], "Author Name")
        self.assertEqual(author["email"], "author@example.com")

        return status_url


    def supply_extra_metadata(self, name, status_url, submitter_name, submitter_email):
        # check the page
        r = self.client.get(status_url)
        q = PyQuery(r.content)
        post_button = q('[type=submit]:contains("Post")')
        self.assertEqual(len(post_button), 1)
        action = post_button.parents("form").find('input[type=hidden][name="action"]').val()

        # post submitter info
        r = self.client.post(status_url, {
            "action": action,
            "submitter-name": submitter_name,
            "submitter-email": submitter_email,
            "approvals_received": True,
        })

        if r.status_code == 302:
            submission = Submission.objects.get(name=name)
            self.assertEqual(submission.submitter, email.utils.formataddr((submitter_name, submitter_email)))

        return r

class ApiSubmitTests(TestCase):
    def setUp(self):
        # break early in case of missing configuration
        self.assertTrue(os.path.exists(settings.IDSUBMIT_IDNITS_BINARY))

        self.saved_idsubmit_staging_path = settings.IDSUBMIT_STAGING_PATH
        self.staging_dir = self.tempdir('submit-staging')
        settings.IDSUBMIT_STAGING_PATH = self.staging_dir

        self.saved_internet_draft_path = settings.INTERNET_DRAFT_PATH
        self.saved_idsubmit_repository_path = settings.IDSUBMIT_REPOSITORY_PATH
        self.repository_dir = self.tempdir('submit-repository')
        settings.INTERNET_DRAFT_PATH = settings.IDSUBMIT_REPOSITORY_PATH = self.repository_dir

        self.saved_archive_dir = settings.INTERNET_DRAFT_ARCHIVE_DIR
        self.archive_dir = self.tempdir('submit-archive')
        settings.INTERNET_DRAFT_ARCHIVE_DIR = self.archive_dir

        self.saved_yang_rfc_model_dir = settings.SUBMIT_YANG_RFC_MODEL_DIR
        self.rfc_model_dir = self.tempdir('yang-rfcmod')
        settings.SUBMIT_YANG_RFC_MODEL_DIR = self.rfc_model_dir

        self.saved_yang_draft_model_dir = settings.SUBMIT_YANG_DRAFT_MODEL_DIR
        self.draft_model_dir = self.tempdir('yang-draftmod')
        settings.SUBMIT_YANG_DRAFT_MODEL_DIR = self.draft_model_dir

        self.saved_yang_iana_model_dir = settings.SUBMIT_YANG_IANA_MODEL_DIR
        self.iana_model_dir = self.tempdir('yang-ianamod')
        settings.SUBMIT_YANG_IANA_MODEL_DIR = self.iana_model_dir

        self.saved_yang_catalog_model_dir = settings.SUBMIT_YANG_CATALOG_MODEL_DIR
        self.catalog_model_dir = self.tempdir('yang-catalogmod')
        settings.SUBMIT_YANG_CATALOG_MODEL_DIR = self.catalog_model_dir

        MeetingFactory(type_id='ietf', date=datetime.date.today()+datetime.timedelta(days=60))

    def tearDown(self):
        shutil.rmtree(self.staging_dir)
        shutil.rmtree(self.repository_dir)
        shutil.rmtree(self.archive_dir)
        shutil.rmtree(self.rfc_model_dir)
        shutil.rmtree(self.draft_model_dir)
        shutil.rmtree(self.iana_model_dir)
        shutil.rmtree(self.catalog_model_dir)

        settings.IDSUBMIT_STAGING_PATH = self.saved_idsubmit_staging_path
        settings.INTERNET_DRAFT_PATH = self.saved_internet_draft_path
        settings.IDSUBMIT_REPOSITORY_PATH = self.saved_idsubmit_repository_path
        settings.INTERNET_DRAFT_ARCHIVE_DIR = self.saved_archive_dir
        settings.SUBMIT_YANG_RFC_MODEL_DIR = self.saved_yang_rfc_model_dir
        settings.SUBMIT_YANG_DRAFT_MODEL_DIR = self.saved_yang_draft_model_dir
        settings.SUBMIT_YANG_IANA_MODEL_DIR = self.saved_yang_iana_model_dir
        settings.SUBMIT_YANG_CATALOG_MODEL_DIR = self.saved_yang_catalog_model_dir

    def do_post_submission(self, rev, author=None, name=None, group=None, email=None, title=None, year=None):
        url = urlreverse('ietf.submit.views.api_submit')
        if author is None:
            author = PersonFactory()
        if name is None:
            slug = re.sub('[^a-z0-9-]+', '', author.ascii_parts()[3].lower())
            name = 'draft-%s-foo' % slug
        if email is None:
            email = author.user.username
        # submit
        data = {}
        data['xml'], author = submission_file(name, rev, group, 'xml', "test_submission.xml", author=author, email=email, title=title, year=year)
        data['user'] = email
        r = self.client.post(url, data)
        return r, author, name

    def test_api_submit_info(self):
        url = urlreverse('ietf.submit.views.api_submit')
        r = self.client.get(url)
        expected = "A simplified draft submission interface, intended for automation"
        self.assertContains(r, expected, status_code=200)

    def test_api_submit_bad_method(self):
        url = urlreverse('ietf.submit.views.api_submit')
        r = self.client.put(url)
        self.assertEqual(r.status_code, 405)

    def test_api_submit_ok(self):
        r, author, name = self.do_post_submission('00')
        expected = "Upload of %s OK, confirmation requests sent to:\n  %s" % (name, author.formatted_email().replace('\n',''))
        self.assertContains(r, expected, status_code=200)

    def test_api_submit_secondary_email_active(self):
        person = PersonFactory()
        email = EmailFactory(person=person)
        r, author, name = self.do_post_submission('00', author=person, email=email.address)
        for expected in [
                "Upload of %s OK, confirmation requests sent to:" % (name, ),
                author.formatted_email().replace('\n',''),
            ]:
            self.assertContains(r, expected, status_code=200)

    def test_api_submit_secondary_email_inactive(self):
        person = PersonFactory()
        prim = person.email()
        prim.primary = True
        prim.save()
        email = EmailFactory(person=person, active=False)
        r, author, name = self.do_post_submission('00', author=person, email=email.address)
        expected = "No such user: %s" % email.address
        self.assertContains(r, expected, status_code=400)

    def test_api_submit_no_user(self):
        email='nonexistant.user@example.org'
        r, author, name = self.do_post_submission('00', email=email)
        expected = "No such user: %s" % email
        self.assertContains(r, expected, status_code=400)

    def test_api_submit_no_person(self):
        user = UserFactory()
        email = user.username
        r, author, name = self.do_post_submission('00', email=email)
        expected = "No person with username %s" % email
        self.assertContains(r, expected, status_code=400)

    def test_api_submit_wrong_revision(self):
        r, author, name = self.do_post_submission('01')
        expected = "Invalid revision (revision 00 is expected)"
        self.assertContains(r, expected, status_code=400)

    def test_api_submit_update_existing_submissiondocevent_rev(self):
        draft, _ = create_draft_submission_with_rev_mismatch(rev='01')
        r, _, __ = self.do_post_submission(rev='01', name=draft.name)
        expected = "Submission failed"
        self.assertContains(r, expected, status_code=409)

    def test_api_submit_update_later_submissiondocevent_rev(self):
        draft, _ = create_draft_submission_with_rev_mismatch(rev='02')
        r, _, __ = self.do_post_submission(rev='01', name=draft.name)
        expected = "Submission failed"
        self.assertContains(r, expected, status_code=409)

    def test_api_submit_pending_submission(self):
        r, author, name = self.do_post_submission('00')
        expected = "Upload of"
        self.assertContains(r, expected, status_code=200)
        r, author, name = self.do_post_submission('00', author=author, name=name)
        expected = "A submission with same name and revision is currently being processed"
        self.assertContains(r, expected, status_code=400)

    def test_api_submit_no_title(self):
        r, author, name = self.do_post_submission('00', title=" ")
        expected = "Could not extract a valid title from the upload"
        self.assertContains(r, expected, status_code=400)

    def test_api_submit_failed_idnits(self):
        r, author, name = self.do_post_submission('00', year="2010")
        expected = "Document date must be within 3 days of submission date"
        self.assertContains(r, expected, status_code=400)

    def test_api_submit_keeps_extresources(self):
        """API submit should not disturb doc external resources
        
        Tests that the submission inherits the existing doc's docextresource_set.
        Relies on separate testing that Submission external_resources will be
        handled appropriately.
        """
        draft = WgDraftFactory()

        # add an external resource
        self.assertEqual(draft.docextresource_set.count(), 0)
        extres = draft.docextresource_set.create(
            name_id='faq',
            display_name='this is a display name',
            value='https://example.com/faq-for-test.html',
        )
        
        r, _, __ = self.do_post_submission('01', name=draft.name)
        self.assertEqual(r.status_code, 200)
        # draft = Document.objects.get(pk=draft.pk)  # update the draft
        sub = Submission.objects.get(name=draft.name)
        self.assertEqual(
            [str(r) for r in sub.external_resources.all()],
            [str(extres)],
        )

        
class RefsTests(TestCase):

    def test_draft_refs_identification(self):

        group = None
        file, __ = submission_file('draft-some-subject', '00', group, 'txt', "test_submission.txt", )
        draft = Draft(file.read(), file.name)
        refs = draft.get_refs()
        self.assertEqual(refs['rfc2119'], 'norm')
        self.assertEqual(refs['rfc8174'], 'norm')
        self.assertEqual(refs['rfc8126'], 'info')
        self.assertEqual(refs['rfc8175'], 'info')
        