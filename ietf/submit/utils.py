# -*- coding: utf-8 -*-
# Copyright The IETF Trust 2011-2020, All Rights Reserved


import datetime
import io
import json
import os
import pathlib
import re
import sys
import time
import traceback
import xml2rfc

from pathlib import Path
from shutil import move
from typing import Optional, Union  # pyflakes:ignore
from unidecode import unidecode
from xml2rfc import RfcWriterError
from xym import xym

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email 
from django.db import transaction
from django.http import HttpRequest     # pyflakes:ignore
from django.utils.module_loading import import_string
from django.contrib.auth.models import AnonymousUser
from django.utils import timezone

import debug                            # pyflakes:ignore

from ietf.doc.models import ( Document, State, DocEvent, SubmissionDocEvent,
    DocumentAuthor, AddedMessageEvent )
from ietf.doc.models import NewRevisionDocEvent
from ietf.doc.models import RelatedDocument, DocRelationshipName, DocExtResource
from ietf.doc.utils import (add_state_change_event, rebuild_reference_relations,
    set_replaces_for_document, prettify_std_name, update_doc_extresources, 
    can_edit_docextresources, update_documentauthors, update_action_holders,
    bibxml_for_draft )
from ietf.doc.mails import send_review_possibly_replaces_request, send_external_resource_change_request
from ietf.group.models import Group
from ietf.ietfauth.utils import has_role
from ietf.name.models import StreamName, FormalLanguageName
from ietf.person.models import Person, Email
from ietf.community.utils import update_name_contains_indexes_with_new_doc
from ietf.submit.mail import ( announce_to_lists, announce_new_version, announce_to_authors,
    send_approval_request, send_submission_confirmation, announce_new_wg_00, send_manual_post_request )
from ietf.submit.checkers import DraftYangChecker
from ietf.submit.models import ( Submission, SubmissionEvent, Preapproval, DraftSubmissionStateName,
    SubmissionCheck, SubmissionExtResource )
from ietf.utils import log
from ietf.utils.accesstoken import generate_random_key
from ietf.utils.draft import PlaintextDraft
from ietf.utils.mail import is_valid_email
from ietf.utils.text import parse_unicode, normalize_text
from ietf.utils.timezone import date_today
from ietf.utils.xmldraft import XMLDraft
from ietf.person.name import unidecode_name


def validate_submission(submission):
    errors = {}

    if submission.state_id not in ("cancel", "posted"):
        for ext in submission.file_types.split(','):
            source = os.path.join(settings.IDSUBMIT_STAGING_PATH, '%s-%s%s' % (submission.name, submission.rev, ext))
            if not os.path.exists(source):
                errors['files'] = '"%s" was not found in the staging area. We recommend you that you cancel this submission and upload your files again.' % os.path.basename(source)
                break

    if not submission.title:
        errors['title'] = 'Title is empty or was not found'

    if submission.group and submission.group.state_id != "active":
        errors['group'] = 'Group exists but is not an active group'

    if not submission.abstract:
        errors['abstract'] = 'Abstract is empty or was not found'

    if not submission.authors:
        errors['authors'] = 'No authors found'

    # revision
    if submission.state_id != "posted":
        error = validate_submission_rev(submission.name, submission.rev)
        if error:
            errors['rev'] = error

    # draft date
    error = validate_submission_document_date(submission.submission_date, submission.document_date)
    if error:
        errors['document_date'] = error

    # author email addresses
    author_error_count = 0
    seen = set()
    for author in submission.authors:
        email = author['email']
        author['errors'] = []
        if not email:
            author['errors'].append("Found no email address.  A valid email address is required.")
            author_error_count += 1
        else:
            try:
                validate_email(email)
            except ValidationError:
                author['errors'].append("Invalid email address. A valid email address is required.")
                author_error_count += 1
        if email in seen:
            author['errors'].append("Duplicate email address.  A unique email address is required.")
            author_error_count += 1
        else:
            seen.add(email)
            
    if author_error_count:
        errors['authors'] = "Author email error (see below)" if author_error_count == 1 else "Author email errors (see below)"

    return errors

def has_been_replaced_by(name):
    docs=Document.objects.filter(name=name)

    if docs:
        doc=docs[0]
        return doc.related_that("replaces")

    return None

def validate_submission_name(name):
    if not re.search(r'^draft-[a-z][-a-z0-9]{0,43}(-\d\d)?$', name):
        if re.search(r'-\d\d$', name):
            name = name[:-3]
        if len(name) > 50:
            return "Expected the Internet-Draft name to be at most 50 ascii characters long; found %d." % len(name)
        else:
            msg = "Expected name 'draft-...' using lowercase ascii letters, digits, and hyphen; found '%s'." % name
            if '.' in name:
                msg += "  Did you include a filename extension in the name by mistake?"
            return msg

    components = name.split('-')
    if '' in components:
        return "Name contains adjacent dashes or the name ends with a dash."
    if len(components) < 3:
        return "Name has less than three dash-delimited components in the name."

    return None

def validate_submission_rev(name, rev):
    if not rev:
        return 'Revision not found'

    if len(rev) != 2:
        return 'Revision must be a exactly two digits'

    try:
        rev = int(rev)
    except ValueError:
        return 'Revision must be a number'
    else:
        if not (0 <= rev <= 99):
            return 'Revision must be between 00 and 99'

        expected = 0
        existing_revs = [int(i.rev) for i in Document.objects.filter(name=name) if i.rev and i.rev.isdigit() ]
        unexpected_revs = [ i.rev for i in Document.objects.filter(name=name) if i.rev and not i.rev.isdigit() ] # pyflakes:ignore
        log.assertion('unexpected_revs', [])
        if existing_revs:
            expected = max(existing_revs) + 1

        if rev != expected:
            return 'Invalid revision (revision %02d is expected)' % expected
        
        # This is not really correct, though the edges that it doesn't cover are not likely.
        # It might be better just to look in the combined archive to make sure we're not colliding with
        # a thing that exists there already because it was included from an approved personal collection.
        for dirname in [settings.INTERNET_DRAFT_PATH, settings.INTERNET_DRAFT_ARCHIVE_DIR, ]:
            dir = pathlib.Path(dirname)
            pattern = '%s-%02d.*' % (name, rev)
            existing = list(dir.glob(pattern))
            if existing:
                plural = '' if len(existing) == 1 else 's'
                files  = ', '.join([ f.name for f in existing ])
                return 'Unexpected file%s already in the archive: %s' % (plural, files)

    replaced_by=has_been_replaced_by(name)
    if replaced_by:
        return 'This document has been replaced by %s' % ",".join(rd.name for rd in replaced_by)

    return None

def validate_submission_document_date(submission_date, document_date):
    if not document_date:
        return 'Document date is empty or not in a proper format'
    elif abs(submission_date - document_date) > datetime.timedelta(days=3):
        return 'Document date must be within 3 days of submission date'

    return None

def check_submission_revision_consistency(submission):
    """Test submission for data consistency

    Returns None if revision is consistent or an error message describing the problem.
    """
    unexpected_submissions = Submission.objects.filter(name=submission.name, rev__gte=submission.rev, state_id='posted').order_by('rev')
    if len(unexpected_submissions) != 0:
        conflicts = [sub.rev for sub in unexpected_submissions]
        return "Rev %s conflicts with existing %s (%s). This indicates a database inconsistency that requires investigation." %(
            submission.rev,
            "submission" if len(conflicts) == 1 else "submissions",
            ", ".join(conflicts)
        )
    return None


def create_submission_event(request: Optional[HttpRequest], submission, desc):
    by = None
    if request and request.user.is_authenticated:
        try:
            by = request.user.person
        except Person.DoesNotExist:
            pass

    SubmissionEvent.objects.create(submission=submission, by=by, desc=desc)

def docevent_from_submission(submission, desc, who=None):
    # type: (Submission, str, Optional[Person]) -> Optional[DocEvent]
    log.assertion('who is None or isinstance(who, Person)')

    try:
        draft = Document.objects.get(name=submission.name)
    except Document.DoesNotExist:
        # Assume this is revision 00 - we'll do this later
        return None

    if who:
        by = who
    else:
        submitter_parsed = submission.submitter_parsed()
        if submitter_parsed["name"] and submitter_parsed["email"]:
            by, _ = ensure_person_email_info_exists(submitter_parsed["name"], submitter_parsed["email"], submission.name)
        else:
            by = Person.objects.get(name="(System)")

    e = SubmissionDocEvent.objects.create(
            doc=draft,
            by = by,
            type = "new_submission",
            desc = desc,
            submission = submission,
            rev = submission.rev,
        )
    return e

def post_rev00_submission_events(draft, submission, submitter):
    # Add previous submission events as docevents
    # For now we'll filter based on the description
    events = []
    for subevent in submission.submissionevent_set.all().order_by('id'):
        desc = subevent.desc
        if desc.startswith("Uploaded submission"):
            desc = "Uploaded new revision"
            e = SubmissionDocEvent(type="new_submission", doc=draft, submission=submission, rev=submission.rev )
        elif desc.startswith("Submission created"):
            e = SubmissionDocEvent(type="new_submission", doc=draft, submission=submission, rev=submission.rev)
        elif desc.startswith("Set submitter to"):
            pos = subevent.desc.find("sent confirmation email")
            e = SubmissionDocEvent(type="new_submission", doc=draft, submission=submission, rev=submission.rev)
            if pos > 0:
                desc = "Request for posting confirmation emailed %s" % (subevent.desc[pos + 23:])
            else:
                pos = subevent.desc.find("sent appproval email")
                if pos > 0:
                    desc = "Request for posting approval emailed %s" % (subevent.desc[pos + 19:])
        elif desc.startswith("Received message") or desc.startswith("Sent message"):
            e = AddedMessageEvent(type="added_message", doc=draft)
            e.message = subevent.submissionemailevent.message
            e.msgtype = subevent.submissionemailevent.msgtype
            e.in_reply_to = subevent.submissionemailevent.in_reply_to
        else:
            continue

        e.time = subevent.time #submission.submission_date
        e.by = submitter
        e.desc = desc
        e.save()
        events.append(e)
    return events


def find_submission_filenames(draft):
    """Find uploaded files corresponding to the draft

    Returns a dict mapping file extension to the corresponding filename (including the full path).
    """
    path = pathlib.Path(settings.IDSUBMIT_STAGING_PATH)
    stem = f'{draft.name}-{draft.rev}'
    allowed_types = settings.IDSUBMIT_FILE_TYPES
    candidates = {ext: path / f'{stem}.{ext}' for ext in allowed_types}
    return {ext: str(filename) for ext, filename in candidates.items() if filename.exists()}


@transaction.atomic
def post_submission(request, submission, approved_doc_desc, approved_subm_desc):
    # This is very chatty into the logs, but these could still be useful for quick diagnostics
    log.log(f"{submission.name}: start")
    system = Person.objects.get(name="(System)")
    submitter_parsed = submission.submitter_parsed()
    if submitter_parsed["name"] and submitter_parsed["email"]:
        submitter, _ = ensure_person_email_info_exists(submitter_parsed["name"], submitter_parsed["email"], submission.name)
        submitter_info = '%s <%s>' % (submitter_parsed["name"], submitter_parsed["email"])
    else:
        submitter = system
        submitter_info = system.name
    log.log(f"{submission.name}: got submitter: {submitter.name}")

    # update draft attributes
    try:
        draft = Document.objects.get(name=submission.name)
        log.log(f"{submission.name}: retrieved Internet-Draft: {draft}")
    except Document.DoesNotExist:
        draft = Document.objects.create(name=submission.name, type_id="draft")
        log.log(f"{submission.name}: created Internet-Draft: {draft}")

    prev_rev = draft.rev

    draft.type_id = "draft"
    draft.title = submission.title
    group = submission.group or Group.objects.get(type="individ")
    if not (group.type_id == "individ" and draft.group and draft.group.type_id == "area"):
        # don't overwrite an assigned area if it's still an individual
        # submission
        draft.group = group
    draft.rev = submission.rev
    draft.pages = submission.pages
    draft.abstract = submission.abstract
    was_rfc = draft.get_state_slug() == "rfc"

    if not draft.stream:
        stream_slug = None
        if draft.name.startswith("draft-iab-"):
            stream_slug = "iab"
        elif draft.name.startswith("draft-irtf-"):
            stream_slug = "irtf"
        elif draft.name.startswith("draft-ietf-") and (draft.group.type_id != "individ" or was_rfc):
            stream_slug = "ietf"

        if stream_slug:
            draft.stream = StreamName.objects.get(slug=stream_slug)

    draft.expires = timezone.now() + datetime.timedelta(settings.INTERNET_DRAFT_DAYS_TO_EXPIRE)
    log.log(f"{submission.name}: got Internet-Draft details")

    events = []

    if draft.rev == '00':
        # Add all the previous submission events as docevents
        events += post_rev00_submission_events(draft, submission, submitter)

    if isinstance(request.user, AnonymousUser):
        doer=system
    else:
        doer=request.user.person
    # Add an approval docevent
    e = SubmissionDocEvent.objects.create(
        type="new_submission",
        doc=draft,
        by=doer,
        desc=approved_doc_desc,
        submission=submission,
        rev=submission.rev,
    )
    events.append(e)

    # new revision event
    e = NewRevisionDocEvent.objects.create(
        type="new_revision",
        doc=draft,
        rev=draft.rev,
        by=submitter,
        desc="New version available: <b>%s-%s.txt</b>" % (draft.name, draft.rev),
    )
    events.append(e)
    log.log(f"{submission.name}: created doc events")

    draft.set_state(State.objects.get(used=True, type="draft", slug="active"))

    update_authors(draft, submission)

    draft.formal_languages.set(submission.formal_languages.all())

    log.log(f"{submission.name}: updated state and info")

    trouble = rebuild_reference_relations(draft, find_submission_filenames(draft))
    if trouble:
        log.log('Rebuild_reference_relations trouble: %s'%trouble)
    log.log(f"{submission.name}: rebuilt reference relations")
    
    if draft.stream_id == "ietf" and draft.group.type_id == "wg" and draft.rev == "00":
        # automatically set state "WG Document"
        draft.set_state(State.objects.get(used=True, type="draft-stream-%s" % draft.stream_id, slug="wg-doc"))

    # automatic state changes for IANA review
    if (draft.get_state_slug("draft-iana-review") in ("ok-act", "ok-noact", "not-ok")
        and not draft.get_state_slug("draft-iesg") in ("approved", "ann", "rfcqueue", "pub", "nopubadw", "nopubanw", "dead") ):
        prev_state = draft.get_state("draft-iana-review")
        next_state = State.objects.get(used=True, type="draft-iana-review", slug="changed")
        draft.set_state(next_state)
        e = add_state_change_event(draft, system, prev_state, next_state)
        if e:
            events.append(e)

    state_change_msg = ""

    if not was_rfc and draft.tags.filter(slug="need-rev"):
        tags_before = list(draft.tags.all())

        draft.tags.remove("need-rev")
        if draft.stream_id == 'ietf':
            draft.tags.add("ad-f-up")

        e = DocEvent(type="changed_document", doc=draft, rev=draft.rev)
        if draft.stream_id == 'ietf':
            e.desc = "Sub state has been changed to <b>AD Followup</b> from <b>Revised I-D Needed</b>"
        else:
            e.desc = "<b>Revised I-D Needed</b> tag cleared"
        e.by = system
        e.save()
        events.append(e)
        state_change_msg = e.desc

        # Changed tags - update action holders if necessary
        e = update_action_holders(draft, prev_tags=tags_before, new_tags=draft.tags.all())
        if e is not None:
            events.append(e)

    if draft.stream_id == "ietf" and draft.group.type_id == "wg" and draft.rev == "00":
        # automatically set state "WG Document"
        draft.set_state(State.objects.get(used=True, type="draft-stream-%s" % draft.stream_id, slug="wg-doc"))

    log.log(f"{submission.name}: handled state changes")

    if not draft.get_state('draft-iesg'):
        draft.states.add(State.objects.get(type_id='draft-iesg', slug='idexists'))

    # save history now that we're done with changes to the draft itself
    draft.save_with_history(events)
    log.log(f"{submission.name}: saved history")

    # clean up old files
    if prev_rev != draft.rev:
        from ietf.doc.expire import move_draft_files_to_archive
        move_draft_files_to_archive(draft, prev_rev)

    move_files_to_repository(submission)
    submission.state = DraftSubmissionStateName.objects.get(slug="posted")
    log.log(f"{submission.name}: moved files")

    new_replaces, new_possibly_replaces = update_replaces_from_submission(request, submission, draft)
    update_name_contains_indexes_with_new_doc(draft)
    log.log(f"{submission.name}: updated replaces and indexes")

    # See whether a change to external resources is requested. Test for equality of sets is ugly,
    # but works.
    draft_resources = '\n'.join(sorted(str(r) for r in draft.docextresource_set.all()))
    submission_resources = '\n'.join(sorted(str(r) for r in submission.external_resources.all()))
    if draft_resources != submission_resources:
        if can_edit_docextresources(request.user, draft):
            update_docextresources_from_submission(request, submission, draft)
            log.log(f"{submission.name}: updated external resources")
        else:
            send_external_resource_change_request(request,
                                                  draft,
                                                  submitter_info,
                                                  submission.external_resources.all())
            log.log(f"{submission.name}: sent email suggesting external resources")

    announce_to_lists(request, submission)
    if submission.group and submission.group.type_id == 'wg' and draft.rev == '00':
        announce_new_wg_00(request, submission)
    announce_new_version(request, submission, draft, state_change_msg)
    announce_to_authors(request, submission)
    log.log(f"{submission.name}: sent announcements")

    if new_possibly_replaces:
        send_review_possibly_replaces_request(request, draft, submitter_info)

    submission.draft = draft
    submission.save()

    create_submission_event(request, submission, approved_subm_desc)

    # Create bibxml-ids entry
    ref_text = bibxml_for_draft(draft, draft.rev)
    ref_rev_file_name = os.path.join(os.path.join(settings.BIBXML_BASE_PATH, 'bibxml-ids'), 'reference.I-D.%s-%s.xml' % (draft.name, draft.rev ))
    with io.open(ref_rev_file_name, "w", encoding='utf-8') as f:
        f.write(ref_text)

    log.log(f"{submission.name}: done")
    

def update_replaces_from_submission(request, submission, draft):
    if not submission.replaces:
        return [], []

    is_secretariat = has_role(request.user, "Secretariat")
    is_chair_of = []
    if request.user.is_authenticated:
        is_chair_of = list(Group.objects.filter(role__person__user=request.user, role__name="chair"))

    replaces = Document.objects.filter(name__in=submission.replaces.split(",")).prefetch_related("group")
    existing_replaces = list(draft.related_that_doc("replaces"))
    existing_suggested = set(draft.related_that_doc("possibly-replaces"))

    submitter_email = submission.submitter_parsed()["email"]

    approved = []
    suggested = []
    for r in replaces:
        if r in existing_replaces:
            continue

        if r == draft:
            continue

        if (is_secretariat
            or (draft.group in is_chair_of and (r.group.type_id == "individ" or r.group in is_chair_of))
            or (submitter_email and r.documentauthor_set.filter(email__address__iexact=submitter_email).exists())):
            approved.append(r)
        else:
            if r not in existing_suggested:
                suggested.append(r)


    try:
        by = request.user.person if request.user.is_authenticated else Person.objects.get(name="(System)")
    except Person.DoesNotExist:
        by = Person.objects.get(name="(System)")
    set_replaces_for_document(request, draft, existing_replaces + approved, by,
                              email_subject="%s replacement status set during submit by %s" % (draft.name, submission.submitter_parsed()["name"]))


    if suggested:
        possibly_replaces = DocRelationshipName.objects.get(slug="possibly-replaces")
        for r in suggested:
            RelatedDocument.objects.create(source=draft, target=r, relationship=possibly_replaces)

        DocEvent.objects.create(doc=draft, rev=draft.rev, by=by, type="added_suggested_replaces",
                                desc="Added suggested replacement relationships: %s" % ", ".join(d.name for d in suggested))

    return approved, suggested

def update_docextresources_from_submission(request, submission, draft):
    doc_resources = [DocExtResource.from_sibling_class(res)
                     for res in submission.external_resources.all()]
    by = request.user.person if request.user.is_authenticated else Person.objects.get(name='(System)')
    update_doc_extresources(draft, doc_resources, by)

def get_person_from_name_email(name, email):
    # try email
    if email and (email.startswith('unknown-email-') or is_valid_email(email)):
        persons = Person.objects.filter(email__address__iexact=email).distinct()
        if len(persons) == 1:
            return persons[0]
    else:
        persons = Person.objects.none()

    if not persons.exists():
        persons = Person.objects.all()

    # try full name
    p = persons.filter(alias__name=name).distinct()
    if p.exists():
        return p.first()

    return None

def ensure_person_email_info_exists(name, email, docname):
    addr = email
    email = None
    person = get_person_from_name_email(name, addr)

    # make sure we have a person
    if not person:
        person = Person()
        person.name = name
        person.name_from_draft = name
        log.assertion('isinstance(person.name, str)')
        person.ascii = unidecode_name(person.name)
        person.save()
    else:
        person.name_from_draft = name


    active = True
    addr = addr.lower()


    try:
        email = person.email_set.get(address=addr)
        email.origin = "author: %s" % docname          # overwrite earlier origin
        email.save()
    except Email.DoesNotExist:
        try:
            # An Email object pointing to some other person will not exist
            # at this point, because get_person_from_name_email would have
            # returned that person, but it's possible that an Email record
            # not associated with any Person exists
            email = Email.objects.get(address=addr,person__isnull=True)
        except Email.DoesNotExist:
            # most likely we just need to create it
            email = Email(address=addr)
            email.active = active
        email.person = person
        if email.time is None:
            email.time = timezone.now()
        email.origin = "author: %s" % docname
        email.save()

    return person, email

def update_authors(draft, submission):
    docauthors = []
    for author in submission.authors:
        person, email = ensure_person_email_info_exists(author["name"], author.get("email"), submission.name)
        docauthors.append(
            DocumentAuthor(
                # update_documentauthors() will fill in document and order for us
                person=person,
                email=email,
                affiliation=author.get("affiliation", ""),
                country=author.get("country", "")
            )
        )
    # The update_documentauthors() method returns a list of unsaved author edit events for the draft.
    # Discard these because the existing logging is already adequate.
    update_documentauthors(draft, docauthors)

def cancel_submission(submission):
    submission.state = DraftSubmissionStateName.objects.get(slug="cancel")
    submission.save()
    remove_submission_files(submission)


def rename_submission_files(submission, prev_rev, new_rev):
    for ext in settings.IDSUBMIT_FILE_TYPES:
        staging_path = Path(settings.IDSUBMIT_STAGING_PATH) 
        source = staging_path / f"{submission.name}-{prev_rev}.{ext}"
        dest = staging_path / f"{submission.name}-{new_rev}.{ext}"
        if source.exists():
            move(source, dest)


def move_files_to_repository(submission):
    for ext in settings.IDSUBMIT_FILE_TYPES:
        fname = f"{submission.name}-{submission.rev}.{ext}"
        source = Path(settings.IDSUBMIT_STAGING_PATH) / fname
        dest = Path(settings.IDSUBMIT_REPOSITORY_PATH) / fname
        if source.exists():
            move(source, dest)
            all_archive_dest = Path(settings.INTERNET_ALL_DRAFTS_ARCHIVE_DIR) / dest.name
            ftp_dest = Path(settings.FTP_DIR) / "internet-drafts" / dest.name
            os.link(dest, all_archive_dest)
            os.link(dest, ftp_dest)
        elif dest.exists():
            log.log("Intended to move '%s' to '%s', but found source missing while destination exists.")
        elif f".{ext}" in submission.file_types.split(','):
            raise ValueError("Intended to move '%s' to '%s', but found source and destination missing.")


def remove_staging_files(name, rev, exts=None):
    """Remove staging files corresponding to a submission
    
    exts is a list of extensions to be removed. If None, defaults to settings.IDSUBMIT_FILE_TYPES.
    """
    if exts is None:
        exts = [f'.{ext}' for ext in settings.IDSUBMIT_FILE_TYPES]
    basename = pathlib.Path(settings.IDSUBMIT_STAGING_PATH) / f'{name}-{rev}' 
    for ext in exts:
        basename.with_suffix(ext).unlink(missing_ok=True)


def remove_submission_files(submission):
    remove_staging_files(submission.name, submission.rev, submission.file_types.split(','))


def approvable_submissions_for_user(user):
    if not user.is_authenticated:
        return []

    # Submissions that are group / AD approvable by someone
    group_approvable = Submission.objects.filter(state="grp-appr")
    ad_approvable = Submission.objects.filter(state="ad-appr")
    if has_role(user, "Secretariat"):
        return (group_approvable | ad_approvable).order_by('-submission_date')

    # group-approvable that we can reach as chair plus group-approvable that we can reach as AD
    # plus AD-approvable that we can reach as ad
    return (
        group_approvable.filter(group__role__name="chair", group__role__person__user=user)
        | group_approvable.filter(group__parent__role__name="ad", group__parent__role__person__user=user)
        | ad_approvable.filter(group__parent__role__name="ad", group__parent__role__person__user=user)
    ).order_by('-submission_date')

def preapprovals_for_user(user):
    if not user.is_authenticated:
        return []

    posted = Submission.objects.distinct().filter(state="posted").values_list('name', flat=True)
    res = Preapproval.objects.exclude(name__in=posted).order_by("-time").select_related('by')
    if has_role(user, "Secretariat"):
        return res

    accessible_groups = (
        Group.objects.filter(role__person__user=user, type__features__req_subm_approval=True)
        | Group.objects.filter(parent__role__name='ad', parent__role__person__user=user, type__features__req_subm_approval=True)
    )
    acronyms = [g.acronym for g in accessible_groups]

    res = res.filter(name__regex="draft-[^-]+-(%s)-.*" % "|".join(acronyms))

    return res

def recently_approved_by_user(user, since):
    if not user.is_authenticated:
        return []

    res = Submission.objects.distinct().filter(state="posted", submission_date__gte=since, rev="00").order_by('-submission_date')
    if has_role(user, "Secretariat"):
        return res

    # those we can reach as chair or ad
    return (
        res.filter(group__role__name="chair", group__role__person__user=user)
        | res.filter(group__parent__role__name="ad", group__parent__role__person__user=user)
    )

def expirable_submissions(older_than_days):
    cutoff = date_today() - datetime.timedelta(days=older_than_days)
    return Submission.objects.exclude(state__in=("cancel", "posted")).filter(submission_date__lt=cutoff)

def expire_submission(submission, by):
    submission.state_id = "cancel"
    submission.save()

    SubmissionEvent.objects.create(submission=submission, by=by, desc="Cancelled expired submission")


def clear_existing_files(form):
    """Make sure there are no leftover files from a previous submission"""
    remove_staging_files(form.filename, form.revision)


def save_files(form):
    file_name = {}
    for ext in list(form.fields.keys()):
        if not ext in form.formats:
            continue
        f = form.cleaned_data[ext]
        if not f:
            continue

        name = os.path.join(settings.IDSUBMIT_STAGING_PATH, '%s-%s.%s' % (form.filename, form.revision, ext))
        file_name[ext] = name
        with io.open(name, 'wb+') as destination:
            for chunk in f.chunks():
                destination.write(chunk)
        log.log("saved file %s" % name)
    return file_name


def get_submission(form):
    # See if there is a Submission in state waiting-for-draft
    # for this revision.
    # If so - we're going to update it otherwise we create a new object

    submissions = Submission.objects.filter(name=form.filename,
                                            rev=form.revision,
                                            state_id = "waiting-for-draft").distinct()
    if not submissions:
        submission = Submission(name=form.filename, rev=form.revision, group=form.group)
    elif len(submissions) == 1:
        submission = submissions.first()
    else:
        raise Exception("Multiple submissions found waiting for upload")
    return submission


def fill_in_submission(form, submission, authors, abstract, file_size):
    submission.state = DraftSubmissionStateName.objects.get(slug="uploaded")
    submission.remote_ip = form.remote_ip
    submission.title = form.title
    submission.abstract = abstract
    submission.authors = authors
    submission.file_size = file_size
    submission.file_types = ','.join(form.file_types)
    submission.xml_version = form.xml_version
    submission.submission_date = date_today()
    submission.replaces = ""
    if form.parsed_draft is not None:
        submission.pages = form.parsed_draft.get_pagecount()
        submission.words = form.parsed_draft.get_wordcount()
        submission.first_two_pages = ''.join(form.parsed_draft.pages[:2])
        submission.document_date = form.parsed_draft.get_creation_date()
    submission.save()

    if form.parsed_draft is not None:
        submission.formal_languages.set(FormalLanguageName.objects.filter(slug__in=form.parsed_draft.get_formal_languages()))
    set_extresources_from_existing_draft(submission)

def apply_checker(checker, submission, file_name):
    def apply_check(submission, checker, method, fn):
        func = getattr(checker, method)
        passed, message, errors, warnings, info = func(fn)
        check = SubmissionCheck(submission=submission, checker=checker.name, passed=passed,
                                message=message, errors=errors, warnings=warnings, items=info,
                                symbol=checker.symbol)
        check.save()
    # ordered list of methods to try
    for method in ("check_fragment_xml", "check_file_xml", "check_fragment_txt", "check_file_txt", ):
        ext = method[-3:]
        if hasattr(checker, method) and ext in file_name:
            apply_check(submission, checker, method, file_name[ext])
            break

def apply_checkers(submission, file_name):
    # run submission checkers
    mark = time.time()
    for checker_path in settings.IDSUBMIT_CHECKER_CLASSES:
        lap = time.time()
        checker_class = import_string(checker_path)
        checker = checker_class()
        apply_checker(checker, submission, file_name)
        tau = time.time() - lap
        log.log(f"ran {checker.__class__.__name__} ({tau:.3}s) for {file_name}")
    tau = time.time() - mark
    log.log(f"ran submission checks ({tau:.3}s) for {file_name}")

def accept_submission_requires_prev_auth_approval(submission):
    """Does acceptance process require approval of previous authors?"""
    return Document.objects.filter(name=submission.name).exists()

def accept_submission_requires_group_approval(submission):
    """Does acceptance process require group approval?

    Depending on the state of the group, this approval may come from group chair or area director.
    """
    return (
        submission.rev == '00'
        and submission.group and submission.group.features.req_subm_approval
        and not Preapproval.objects.filter(name=submission.name).exists()
    )


class SubmissionError(Exception):
    """Exception for errors during submission processing
    
    Sanitizes paths appearing in exception messages.
    """
    def __init__(self, *args):
        if len(args) > 0:
            args = (self.sanitize_message(arg) for arg in args)
        super().__init__(*args)

    @staticmethod
    def sanitize_message(msg):
        # Paths likely to appear in submission-related errors
        paths = [
            p for p in (
                getattr(settings, "ALL_ID_DOWNLOAD_DIR", None),
                getattr(settings, "BIBXML_BASE_PATH", None),
                getattr(settings, "DERIVED_DIR", None),
                getattr(settings, "FTP_DIR", None),
                getattr(settings, "IDSUBMIT_REPOSITORY_PATH", None),
                getattr(settings, "IDSUBMIT_STAGING_PATH", None),
                getattr(settings, "INTERNET_ALL_DRAFTS_ARCHIVE_DIR", None),
                getattr(settings, "INTERNET_DRAFT_PATH", None),
                getattr(settings, "INTERNET_DRAFT_ARCHIVE_DIR", None),
                getattr(settings, "INTERNET_DRAFT_PDF_PATH", None),
                getattr(settings, "RFC_PATH", None),
                getattr(settings, "SUBMIT_YANG_CATALOG_MODEL_DIR", None),
                getattr(settings, "SUBMIT_YANG_DRAFT_MODEL_DIR", None),
                getattr(settings, "SUBMIT_YANG_IANA_MODEL_DIR", None),
                getattr(settings, "SUBMIT_YANG_RFC_MODEL_DIR", None),
                "/tmp/",
            ) if p is not None
        ]
        return re.sub(fr"({'|'.join(paths)})/*", "**/", msg)


class XmlRfcError(SubmissionError):
    """SubmissionError caused by xml2rfc
    
    Includes the output from xml2rfc, if any, in xml2rfc_stdout / xml2rfc_stderr
    """
    def __init__(self, *args, xml2rfc_stdout: str, xml2rfc_stderr: str):
        super().__init__(*args)
        self.xml2rfc_stderr = xml2rfc_stderr
        self.xml2rfc_stdout = xml2rfc_stdout


class InconsistentRevisionError(SubmissionError):
    """SubmissionError caused by an inconsistent revision"""


def staging_path(filename, revision, ext):
    if len(ext) > 0 and ext[0] != '.':
        ext = f'.{ext}'
    return pathlib.Path(settings.IDSUBMIT_STAGING_PATH) / f'{filename}-{revision}{ext}'


def render_missing_formats(submission):
    """Generate txt and html formats from xml draft

    If a txt file already exists, leaves it in place. Overwrites an existing html file
    if there is one.
    """
    # Capture stdio/stdout from xml2rfc
    xml2rfc_stdout = io.StringIO()
    xml2rfc_stderr = io.StringIO()
    xml2rfc.log.write_out = xml2rfc_stdout
    xml2rfc.log.write_err = xml2rfc_stderr
    xml_path = staging_path(submission.name, submission.rev, '.xml')
    parser = xml2rfc.XmlRfcParser(str(xml_path), quiet=True)
    try:
        # --- Parse the xml ---
        xmltree = parser.parse(remove_comments=False)
    except Exception as err:
        raise XmlRfcError(
            "Error parsing XML",
            xml2rfc_stdout=xml2rfc_stdout.getvalue(),
            xml2rfc_stderr=xml2rfc_stderr.getvalue(),
        ) from err
    # If we have v2, run it through v2v3. Keep track of the submitted version, though.
    xmlroot = xmltree.getroot()
    xml_version = xmlroot.get('version', '2')
    if xml_version == '2':
        v2v3 = xml2rfc.V2v3XmlWriter(xmltree)
        try:
            xmltree.tree = v2v3.convert2to3()
        except Exception as err:
            raise XmlRfcError(
                "Error converting v2 XML to v3",
                xml2rfc_stdout=xml2rfc_stdout.getvalue(),
                xml2rfc_stderr=xml2rfc_stderr.getvalue(),
            ) from err

    # --- Prep the xml ---
    today = date_today()
    prep = xml2rfc.PrepToolWriter(xmltree, quiet=True, liberal=True, keep_pis=[xml2rfc.V3_PI_TARGET])
    prep.options.accept_prepped = True
    prep.options.date = today
    try:
        xmltree.tree = prep.prep()
    except RfcWriterError:
        raise XmlRfcError(
            f"Error during xml2rfc prep: {prep.errors}",
            xml2rfc_stdout=xml2rfc_stdout.getvalue(),
            xml2rfc_stderr=xml2rfc_stderr.getvalue(),
        )
    except Exception as err:
        raise XmlRfcError(
            "Unexpected error during xml2rfc prep",
            xml2rfc_stdout=xml2rfc_stdout.getvalue(),
            xml2rfc_stderr=xml2rfc_stderr.getvalue(),
        ) from err

    # --- Convert to txt ---
    txt_path = staging_path(submission.name, submission.rev, '.txt')
    if not txt_path.exists():
        writer = xml2rfc.TextWriter(xmltree, quiet=True)
        writer.options.accept_prepped = True
        writer.options.date = today
        try:
            writer.write(txt_path)
        except Exception as err:
            raise XmlRfcError(
                "Error generating text format from XML",
            xml2rfc_stdout=xml2rfc_stdout.getvalue(),
            xml2rfc_stderr=xml2rfc_stderr.getvalue(),
            ) from err
        log.log(
            'In %s: xml2rfc %s generated %s from %s (version %s)' % (
                str(xml_path.parent),
                xml2rfc.__version__,
                txt_path.name,
                xml_path.name,
                xml_version,
            )
        )

    # --- Convert to html ---
    html_path = staging_path(submission.name, submission.rev, '.html')
    writer = xml2rfc.HtmlWriter(xmltree, quiet=True)
    writer.options.date = today
    try:
        writer.write(str(html_path))
    except Exception as err:
        raise XmlRfcError(
            "Error generating HTML format from XML",
            xml2rfc_stdout=xml2rfc_stdout.getvalue(),
            xml2rfc_stderr=xml2rfc_stderr.getvalue(),
        ) from err
    log.log(
        'In %s: xml2rfc %s generated %s from %s (version %s)' % (
            str(xml_path.parent),
            xml2rfc.__version__,
            html_path.name,
            xml_path.name,
            xml_version,
        )
    )


def accept_submission(submission: Submission, request: Optional[HttpRequest] = None, autopost=False):
    """Accept a submission and post or put in correct state to await approvals

    If autopost is True, will post draft if submitter is authorized to do so.
    """
    doc = submission.existing_document()
    prev_authors = [] if not doc else [ author.person for author in doc.documentauthor_set.all() ]
    curr_authors = [ get_person_from_name_email(author["name"], author.get("email"))
                     for author in submission.authors ]
    # Is the user authenticated as an author who can approve this submission?
    requester = None
    requester_is_author = False
    if request is not None and request.user.is_authenticated:
        requester = request.user.person
        requester_is_author = requester in (prev_authors if submission.rev != '00' else curr_authors)

    # If "who" is None, docevent_from_submission will pull it out of submission
    docevent_from_submission(submission, desc="Uploaded new revision",
                             who=requester if requester_is_author else None)

    replaces = Document.objects.filter(name__in=submission.replaces_names)
    pretty_replaces = '(none)' if not replaces else (
        ', '.join(prettify_std_name(r.name) for r in replaces)
    )

    active_wg_drafts_replaced = submission.active_wg_drafts_replaced
    closed_wg_drafts_replaced = submission.closed_wg_drafts_replaced

    # Determine which approvals are required
    requires_prev_authors_approval = accept_submission_requires_prev_auth_approval(submission)
    requires_group_approval = accept_submission_requires_group_approval(submission)
    requires_ad_approval = submission.revises_wg_draft and not submission.group.is_active
    if submission.is_individual:
        requires_prev_group_approval = active_wg_drafts_replaced.exists()
        requires_prev_ad_approval = closed_wg_drafts_replaced.exists()
    else:
        requires_prev_group_approval = False
        requires_prev_ad_approval = False

    # Partial message for submission event
    sub_event_desc = 'Set submitter to \"%s\", replaces to %s' % (parse_unicode(submission.submitter), pretty_replaces)
    create_event = True  # Indicates whether still need to create an event
    docevent_desc = None
    address_list = []
    if requires_ad_approval or requires_prev_ad_approval:
        submission.state_id = "ad-appr"
        submission.save()

        if closed_wg_drafts_replaced.exists():
            replaced_document = closed_wg_drafts_replaced.first()
        else:
            replaced_document = None

        address_list = send_approval_request(
            request,
            submission,
            replaced_document,  # may be None
        )
        sent_to = ', '.join(address_list)
        sub_event_desc += ' and sent approval email to AD: %s' % sent_to
        docevent_desc = "Request for posting approval emailed to AD: %s" % sent_to
    elif requires_group_approval or requires_prev_group_approval:
        submission.state = DraftSubmissionStateName.objects.get(slug="grp-appr")
        submission.save()

        if active_wg_drafts_replaced.exists():
            replaced_document = active_wg_drafts_replaced.first()
        else:
            replaced_document = None

        address_list = send_approval_request(
            request,
            submission,
            replaced_document,  # may be None
        )
        sent_to = ', '.join(address_list)
        sub_event_desc += ' and sent approval email to group chairs: %s' % sent_to
        docevent_desc = "Request for posting approval emailed to group chairs: %s" % sent_to
    elif requester_is_author and autopost:
        # go directly to posting submission
        sub_event_desc = f'New version accepted (logged-in submitter: {requester})'
        post_submission(request, submission, sub_event_desc, sub_event_desc)
        create_event = False  # do not create submission event below, post_submission() handled it
    else:
        submission.auth_key = generate_random_key()
        if requires_prev_authors_approval:
            submission.state = DraftSubmissionStateName.objects.get(slug="aut-appr")
        else:
            submission.state = DraftSubmissionStateName.objects.get(slug="auth")
        submission.save()

        group_authors_changed = False
        doc = submission.existing_document()
        if doc and doc.group:
            old_authors = [ author.person for author in doc.documentauthor_set.all() ]
            new_authors = [ get_person_from_name_email(author["name"], author.get("email")) for author in submission.authors ]
            group_authors_changed = set(old_authors)!=set(new_authors)

        address_list = send_submission_confirmation(
            request,
            submission,
            chair_notice=group_authors_changed
        )
        sent_to = ', '.join(address_list)
        if submission.state_id == "aut-appr":
            sub_event_desc += " and sent confirmation email to previous authors: %s" % sent_to
            docevent_desc = "Request for posting confirmation emailed to previous authors: %s" % sent_to
        else:
            sub_event_desc += " and sent confirmation email to submitter and authors: %s" % sent_to
            docevent_desc = "Request for posting confirmation emailed to submitter and authors: %s" % sent_to

    if create_event:
        create_submission_event(request, submission, sub_event_desc)
    if docevent_desc:
        docevent_from_submission(submission, docevent_desc, who=Person.objects.get(name="(System)"))

    return address_list

def set_extresources_from_existing_draft(submission):
    """Replace a submission's external resources with values from previous revision

    If there is no previous revision, clears the external resource list for the submission.
    """
    doc = submission.existing_document()
    if doc:
        update_submission_external_resources(
            submission,
            [SubmissionExtResource.from_sibling_class(res)
             for res in doc.docextresource_set.all()]
        )

def update_submission_external_resources(submission, new_resources):
    submission.external_resources.all().delete()
    for new_res in new_resources:
        new_res.submission = submission
        new_res.save()

def remote_ip(request):
    if 'CF-Connecting-IP' in request.META:
        remote_ip = request.META.get('CF-Connecting-IP')
    elif 'X-Forwarded-For' in request.META:
        remote_ip = request.META.get('X-Forwarded-For').split(',')[0]
    else:
        remote_ip = request.META.get('REMOTE_ADDR', None)
    return remote_ip


def _normalize_title(title):
    if isinstance(title, str):
        title = unidecode(title)  # replace unicode with best-match ascii
    return normalize_text(title)  # normalize whitespace


def process_submission_xml(filename, revision):
    """Validate and extract info from an uploaded submission"""
    xml_path = staging_path(filename, revision, '.xml')
    xml_draft = XMLDraft(xml_path)

    if filename != xml_draft.filename:
        raise SubmissionError(
            f"XML Internet-Draft filename ({xml_draft.filename}) "
            f"disagrees with submission filename ({filename})"
        )
    if revision != xml_draft.revision:
        raise SubmissionError(
            f"XML Internet-Draft revision ({xml_draft.revision}) "
            f"disagrees with submission revision ({revision})"
        )
    title = _normalize_title(xml_draft.get_title())
    if not title:
        raise SubmissionError("Could not extract a valid title from the XML")
    
    return {
        "filename": xml_draft.filename,
        "rev": xml_draft.revision,
        "title": title,
        "authors": [
            {key: auth[key] for key in ('name', 'email', 'affiliation', 'country')}
            for auth in xml_draft.get_author_list()
        ],
        "abstract": None,  # not supported from XML
        "document_date": xml_draft.get_creation_date(),
        "pages": None,  # not supported from XML
        "words": None,  # not supported from XML
        "first_two_pages": None,  # not supported from XML
        "file_size": None,  # not supported from XML
        "formal_languages": None,  # not supported from XML
        "xml_version": xml_draft.xml_version,
    }


def _turn_into_unicode(s: Optional[Union[str, bytes]]):
    """Decode a possibly null string-like item as a string
    
    Would be nice to ditch this.
    """
    if s is None:
        return ""

    if isinstance(s, str):
        return s
    else:
        try:
            return s.decode("utf-8")
        except UnicodeDecodeError:
            try:
                return s.decode("latin-1")
            except UnicodeDecodeError:
                return ""


def _is_valid_email(addr):
    try:
        validate_email(addr)
    except ValidationError:
        return False
    return True


def process_submission_text(filename, revision):
    """Validate/extract data from the text version of a submitted draft"""
    text_path = staging_path(filename, revision, '.txt')
    text_draft = PlaintextDraft.from_file(text_path)

    if filename != text_draft.filename:
        raise SubmissionError(
            f"Text Internet-Draft filename ({text_draft.filename}) "
            f"disagrees with submission filename ({filename})"
        )
    if revision != text_draft.revision:
        raise SubmissionError(
            f"Text Internet-Draft revision ({text_draft.revision}) "
            f"disagrees with submission revision ({revision})"
        )
    title = text_draft.get_title()
    if title:
        title = _normalize_title(title)

    # Translation taable drops \r, \n, <, >.
    trans_table = str.maketrans("", "", "\r\n<>")
    authors = [
        {
            "name": fullname.translate(trans_table).strip(),
            "email": _turn_into_unicode(email if _is_valid_email(email) else ""),
            "affiliation": _turn_into_unicode(company),
            "country": _turn_into_unicode(country),
        }
        for (fullname, _, _, _, _, email, country, company) in text_draft.get_author_list()
    ]
    return {
        "filename": text_draft.filename,
        "rev": text_draft.revision,
        "title": title,
        "authors": authors,
        "abstract": text_draft.get_abstract(),
        "document_date": text_draft.get_creation_date(),
        "pages": text_draft.get_pagecount(),
        "words": text_draft.get_wordcount(),
        "first_two_pages": ''.join(text_draft.pages[:2]),
        "file_size": os.stat(text_path).st_size,
        "formal_languages": FormalLanguageName.objects.filter(
            slug__in=text_draft.get_formal_languages()
        ),
        "xml_version": None,  # not supported from text
    }


def process_and_validate_submission(submission):
    """Process and validate a submission

    Raises SubmissionError or a subclass if an error is encountered.
    """
    if len(set(submission.file_types.split(",")).intersection({".xml", ".txt"})) == 0:
        raise SubmissionError("Require XML and/or text format to process an Internet-Draft submission.")

    try:
        xml_metadata = None
        # Parse XML first, if we have it
        if ".xml" in submission.file_types:
            xml_metadata = process_submission_xml(submission.name, submission.rev)
            try:
                render_missing_formats(submission)  # makes HTML and text, unless text was uploaded
            except XmlRfcError as err:
                # log stdio/stderr
                log.log(
                    f"xml2rfc failure when rendering missing formats for {submission.name}-{submission.rev}:\n"
                    f">> stdout:\n{err.xml2rfc_stdout}\n"
                    f">> stderr:\n{err.xml2rfc_stderr}"
                )
                raise
        # Parse text, whether uploaded or generated from XML
        text_metadata = process_submission_text(submission.name, submission.rev)

        if (
            ".txt" in submission.file_types
            and xml_metadata
            and xml_metadata["title"] != text_metadata["title"]
        ):
            raise SubmissionError(
                f"Text Internet-Draft title ({text_metadata['title']}) "
                f"disagrees with XML Internet-Draft title ({xml_metadata['title']})"
            )

        # Fill in the submission from the parsed XML/text metadata
        if xml_metadata is not None:
            # Items preferred / only available from XML
            submission.xml_version = xml_metadata["xml_version"]
            submission.title = xml_metadata["title"] or ""
            submission.authors = xml_metadata["authors"]
        else:
            # Items to get from text only if XML not available
            submission.title = text_metadata["title"] or ""
            submission.authors = text_metadata["authors"]

        if not submission.title:
            raise SubmissionError("Could not determine the title of the draft")

        # Items to get from text only when not available from XML
        if xml_metadata and xml_metadata.get("document_date", None) is not None:
            submission.document_date = xml_metadata["document_date"]
        else:
            submission.document_date = text_metadata["document_date"]

        # Items always to get from text, even when XML is available
        submission.abstract = text_metadata["abstract"]
        submission.pages = text_metadata["pages"]
        submission.words = text_metadata["words"]
        submission.first_two_pages = text_metadata["first_two_pages"]
        submission.file_size = text_metadata["file_size"]
        submission.save()
        submission.formal_languages.set(text_metadata["formal_languages"])

        consistency_error = check_submission_revision_consistency(submission)
        if consistency_error:
            raise InconsistentRevisionError(consistency_error)
        set_extresources_from_existing_draft(submission)
        apply_checkers(
            submission,
            {
                ext: staging_path(submission.name, submission.rev, ext)
                for ext in ['xml', 'txt', 'html']
            }
        )
        errors = [c.message for c in submission.checks.filter(passed__isnull=False) if not c.passed]
        if len(errors) > 0:
            raise SubmissionError('Checks failed: ' + ' / '.join(errors))
    except SubmissionError:
        raise  # pass SubmissionErrors up the stack
    except Exception as err:
        # convert other exceptions into SubmissionErrors
        log.log(f'Unexpected exception while processing submission {submission.pk}.')
        log.log(traceback.format_exc())
        raise SubmissionError('A system error occurred while processing the submission.') from err


def submitter_is_author(submission):
    submitter = get_person_from_name_email(**submission.submitter_parsed())
    if submitter:
        author_emails = [
            author["email"].strip().lower()
            for author in submission.authors
            if "email" in author
        ]
        return any(
            email.address.lower() in author_emails
            for email in submitter.email_set.filter(active=True)
        )
    return False


def all_authors_have_emails(submission):
    return all(a["email"] for a in submission.authors)


def process_and_accept_uploaded_submission(submission):
    """Process, validate, and, if valid, accept an uploaded submission

    Requires that the submitter already be set and is an author of the submitted draft.
    The submission must be in the "validating" state. On success, it will be in the
    "posted" state. On error, it wil be in the "cancel" state.
    """
    if submission.state_id != "validating":
        log.log(f'Submission {submission.pk} is not in "validating" state, skipping.')
        return  # do nothing

    if submission.file_types != '.xml':
        # permit only XML uploads for automatic acceptance
        cancel_submission(submission)
        create_submission_event(
            None, 
            submission, 
            "Only XML Internet-Draft submissions can be processed.",
        )
        return

    try:
        process_and_validate_submission(submission)
    except SubmissionError as err:
        submission.refresh_from_db()  # guard against incomplete changes in submission validation / processing
        cancel_submission(submission)  # changes Submission.state
        create_submission_event(None, submission, f"Submission rejected: {err}")
        return

    if not all_authors_have_emails(submission):
        cancel_submission(submission)  # changes Submission.state
        create_submission_event(
            None,
            submission,
            "Submission rejected: Email address not found for all authors"
        )
        return
        
    if not submitter_is_author(submission):
        cancel_submission(submission)  # changes Submission.state
        create_submission_event(
            None,
            submission,
            f"Submission rejected: Submitter ({submission.submitter}) is not one of the document authors",
        )
        return

    create_submission_event(None, submission, desc="Completed submission validation checks")
    accept_submission(submission)


def process_uploaded_submission(submission):
    """Process and validate an uploaded submission

    The submission must be in the "validating" state. On success, it will be in the "uploaded"
    state. On error, it will be in the "cancel" state.
    """
    if submission.state_id != "validating":
        log.log(f'Submission {submission.pk} is not in "validating" state, skipping.')
        return  # do nothing

    try:
        process_and_validate_submission(submission)
    except InconsistentRevisionError as consistency_error:
        submission.refresh_from_db()  # guard against incomplete changes in submission validation / processing
        submission.state_id = "manual"
        submission.save()
        create_submission_event(None, submission, desc="Uploaded submission (diverted to manual process)")
        send_manual_post_request(None, submission, errors=dict(consistency=str(consistency_error)))
    except SubmissionError as err:
        # something generic went wrong
        submission.refresh_from_db()  # guard against incomplete changes in submission validation / processing
        cancel_submission(submission)  # changes Submission.state
        create_submission_event(None, submission, f"Submission rejected: {err}")
    else:
        submission.state_id = "uploaded"
        submission.save()
        create_submission_event(None, submission, desc="Completed submission validation checks")


def apply_yang_checker_to_draft(checker, draft):
    submission = Submission.objects.filter(name=draft.name, rev=draft.rev).order_by('-id').first()
    if submission:
        check = submission.checks.filter(checker=checker.name).order_by('-id').first()
        if check:
            result = checker.check_file_txt(draft.get_file_name())
            passed, message, errors, warnings, items = result
            items = json.loads(json.dumps(items))
            new_res = (passed, errors, warnings, message)
            old_res = (check.passed, check.errors, check.warnings, check.message) if check else ()
            if new_res != old_res:
                log.log(f"Saving new yang checker results for {draft.name}-{draft.rev}")
                qs = submission.checks.filter(checker=checker.name).order_by('time')
                submission.checks.filter(checker=checker.name).exclude(pk=qs.first().pk).delete()
                submission.checks.create(submission=submission, checker=checker.name, passed=passed,
                                         message=message, errors=errors, warnings=warnings, items=items,
                                         symbol=checker.symbol)
    else:
        log.log(f"Could not run yang checker for {draft.name}-{draft.rev}: missing submission object")


def run_all_yang_model_checks():
    checker = DraftYangChecker()
    for draft in Document.objects.filter(
        type_id="draft",
        states=State.objects.get(type="draft", slug="active"),
    ):
        apply_yang_checker_to_draft(checker, draft)


def populate_yang_model_dirs():
    """Update the yang model dirs

     * All yang modules from published RFCs should be extracted and be
       available in an rfc-yang repository.

     * All valid yang modules from active, not replaced, Internet-Drafts
       should be extracted and be available in a draft-valid-yang repository.

     * All, valid and invalid, yang modules from active, not replaced,
       Internet-Drafts should be available in a draft-all-yang repository.
       (Actually, given precedence ordering, it would be enough to place
       non-validating modules in a draft-invalid-yang repository instead).

     * In all cases, example modules should be excluded.

     * Precedence is established by the search order of the repository as
       provided to pyang.

     * As drafts expire, models should be removed in order to catch cases
       where a module being worked on depends on one which has slipped out
       of the work queue.

    """
    def extract_from(file, dir, strict=True):
        saved_stdout = sys.stdout
        saved_stderr = sys.stderr
        xymerr = io.StringIO()
        xymout = io.StringIO()
        sys.stderr = xymerr
        sys.stdout = xymout
        model_list = []
        try:
            model_list = xym.xym(str(file), str(file.parent), str(dir), strict=strict, debug_level=-2)
            for name in model_list:
                modfile = moddir / name
                mtime = file.stat().st_mtime
                os.utime(str(modfile), (mtime, mtime))
                if '"' in name:
                    name = name.replace('"', '')
                    modfile.rename(str(moddir / name))
            model_list = [n.replace('"', '') for n in model_list]
        except Exception as e:
            log.log("Error when extracting from %s: %s" % (file, str(e)))
        finally:
            sys.stdout = saved_stdout
            sys.stderr = saved_stderr
        return model_list

    # Extract from new RFCs

    rfcdir = Path(settings.RFC_PATH)

    moddir = Path(settings.SUBMIT_YANG_RFC_MODEL_DIR)
    if not moddir.exists():
        moddir.mkdir(parents=True)

    latest = 0
    for item in moddir.iterdir():
        if item.stat().st_mtime > latest:
            latest = item.stat().st_mtime

    log.log(f"Extracting RFC Yang models to {moddir} ...")
    for item in rfcdir.iterdir():
        if item.is_file() and item.name.startswith('rfc') and item.name.endswith('.txt') and item.name[3:-4].isdigit():
            if item.stat().st_mtime > latest:
                model_list = extract_from(item, moddir)
                for name in model_list:
                    if not (name.startswith('ietf') or name.startswith('iana')):
                        modfile = moddir / name
                        modfile.unlink()

    # Extract valid modules from drafts

    six_months_ago = time.time() - 6 * 31 * 24 * 60 * 60

    def active(dirent):
        return dirent.stat().st_mtime > six_months_ago

    draftdir = Path(settings.INTERNET_DRAFT_PATH)
    moddir = Path(settings.SUBMIT_YANG_DRAFT_MODEL_DIR)
    if not moddir.exists():
        moddir.mkdir(parents=True)
    log.log(f"Emptying {moddir} ...")
    for item in moddir.iterdir():
        item.unlink()

    log.log(f"Extracting draft Yang models to {moddir} ...")
    for item in draftdir.iterdir():
        try:
            if item.is_file() and item.name.startswith('draft') and item.name.endswith('.txt') and active(item):
                model_list = extract_from(item, moddir, strict=False)
                for name in model_list:
                    if name.startswith('example'):
                        modfile = moddir / name
                        modfile.unlink()
        except UnicodeDecodeError as e:
            log.log(f"Error processing {item.name}: {e}")
