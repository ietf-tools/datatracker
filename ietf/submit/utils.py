# Copyright The IETF Trust 2011-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import datetime
import io
import os
import pathlib
import re

from typing import Callable, Optional # pyflakes:ignore

from django.conf import settings
from django.core.validators import validate_email, ValidationError
from django.db import transaction
from django.http import HttpRequest     # pyflakes:ignore
from django.utils.module_loading import import_string

import debug                            # pyflakes:ignore

from ietf.doc.models import ( Document, State, DocAlias, DocEvent, SubmissionDocEvent,
    DocumentAuthor, AddedMessageEvent )
from ietf.doc.models import NewRevisionDocEvent
from ietf.doc.models import RelatedDocument, DocRelationshipName
from ietf.doc.utils import add_state_change_event, rebuild_reference_relations
from ietf.doc.utils import set_replaces_for_document
from ietf.doc.mails import send_review_possibly_replaces_request
from ietf.group.models import Group
from ietf.ietfauth.utils import has_role
from ietf.name.models import StreamName, FormalLanguageName
from ietf.person.models import Person, Email
from ietf.community.utils import update_name_contains_indexes_with_new_doc
from ietf.submit.mail import ( announce_to_lists, announce_new_version, announce_to_authors,
    send_approval_request_to_group, send_submission_confirmation, announce_new_wg_00 )
from ietf.submit.models import Submission, SubmissionEvent, Preapproval, DraftSubmissionStateName, SubmissionCheck
from ietf.utils import log
from ietf.utils.accesstoken import generate_random_key
from ietf.utils.draft import Draft
from ietf.utils.mail import is_valid_email
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
            return "Expected the draft name to be at most 50 ascii characters long; found %d." % len(name)
        else:
            msg = "Expected name 'draft-...' using lowercase ascii letters, digits, and hyphen; found '%s'." % name
            if '.' in name:
                msg += "  Did you include a filename extension in the name by mistake?"
            return msg

def validate_submission_rev(name, rev):
    if not rev:
        return 'Revision not found'

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

def create_submission_event(request, submission, desc):
    by = None
    if request and request.user.is_authenticated:
        try:
            by = request.user.person
        except Person.DoesNotExist:
            pass

    SubmissionEvent.objects.create(submission=submission, by=by, desc=desc)

def docevent_from_submission(request, submission, desc, who=None):
    # type: (HttpRequest, Submission, str, Optional[Person]) -> Optional[DocEvent]
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


@transaction.atomic
def post_submission(request, submission, approved_doc_desc, approved_subm_desc):
    system = Person.objects.get(name="(System)")
    submitter_parsed = submission.submitter_parsed()
    if submitter_parsed["name"] and submitter_parsed["email"]:
        submitter, _ = ensure_person_email_info_exists(submitter_parsed["name"], submitter_parsed["email"], submission.name)
        submitter_info = '%s <%s>' % (submitter_parsed["name"], submitter_parsed["email"])
    else:
        submitter = system
        submitter_info = system.name

    # update draft attributes
    try:
        draft = Document.objects.get(name=submission.name)
    except Document.DoesNotExist:
        draft = Document.objects.create(name=submission.name, type_id="draft")

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

    draft.expires = datetime.datetime.now() + datetime.timedelta(settings.INTERNET_DRAFT_DAYS_TO_EXPIRE)

    events = []

    if draft.rev == '00':
        # Add all the previous submission events as docevents
        events += post_rev00_submission_events(draft, submission, submitter)

    # Add an approval docevent
    e = SubmissionDocEvent.objects.create(
        type="new_submission",
        doc=draft,
        by=system,
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

    # update related objects
    alias, __ = DocAlias.objects.get_or_create(name=submission.name)
    alias.docs.add(draft)

    draft.set_state(State.objects.get(used=True, type="draft", slug="active"))

    update_authors(draft, submission)

    draft.formal_languages.set(submission.formal_languages.all())

    trouble = rebuild_reference_relations(draft, filename=os.path.join(settings.IDSUBMIT_STAGING_PATH, '%s-%s.txt' % (submission.name, submission.rev)))
    if trouble:
        log.log('Rebuild_reference_relations trouble: %s'%trouble)
    
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
        draft.tags.remove("need-rev")
        if draft.stream_id == 'ietf':
            draft.tags.add("ad-f-up")

        e = DocEvent(type="changed_document", doc=draft, rev=draft.rev)
        if draft.stream_id == 'ietf':
            e.desc = "Sub state has been changed to <b>AD Followup</b> from <b>Revised ID Needed</b>"
        else:
            e.desc = "<b>Revised ID Needed</b> tag cleared"
        e.by = system
        e.save()
        events.append(e)

        state_change_msg = e.desc

    if draft.stream_id == "ietf" and draft.group.type_id == "wg" and draft.rev == "00":
        # automatically set state "WG Document"
        draft.set_state(State.objects.get(used=True, type="draft-stream-%s" % draft.stream_id, slug="wg-doc"))

    # Update yang urls if applicable
    for check in submission.checks.all():
        # Temporary code -- remove after 6.64.0 release
        if not type(check.items) is dict:
            continue
        if not 'checker' in check.items:
            continue
        log.assertion('type(check.items) is dict')
        check.items['draft'] = draft.name
        check.items['rev'] = draft.rev
        if 'code' in check.items and check.items['code']:
            code = check.items['code']
            if 'yang' in code:
                modules = code['yang']
                # Yang impact analysis URL
                draft.documenturl_set.filter(tag_id='yang-impact-analysis').delete()
                f = settings.SUBMIT_YANG_CATALOG_MODULEARG
                moduleargs = '&'.join([ f.format(module=m) for m in modules])
                url  = settings.SUBMIT_YANG_CATALOG_IMPACT_URL.format(moduleargs=moduleargs, draft=draft.name)
                desc = settings.SUBMIT_YANG_CATALOG_IMPACT_DESC.format(modules=','.join(modules), draft=draft.name)
                draft.documenturl_set.create(url=url, tag_id='yang-impact-analysis', desc=desc)
                # Yang module metadata URLs
                old_urls = draft.documenturl_set.filter(tag_id='yang-module-metadata')
                old_urls.delete()
                for module in modules:
                    url  = settings.SUBMIT_YANG_CATALOG_MODULE_URL.format(module=module)
                    desc = settings.SUBMIT_YANG_CATALOG_MODULE_DESC.format(module=module)
                    draft.documenturl_set.create(url=url, tag_id='yang-module-metadata', desc=desc)

    if not draft.get_state('draft-iesg'):
        draft.states.add(State.objects.get(type_id='draft-iesg', slug='idexists'))

    # save history now that we're done with changes to the draft itself
    draft.save_with_history(events)

    # clean up old files
    if prev_rev != draft.rev:
        from ietf.doc.expire import move_draft_files_to_archive
        move_draft_files_to_archive(draft, prev_rev)

    move_files_to_repository(submission)
    submission.state = DraftSubmissionStateName.objects.get(slug="posted")

    new_replaces, new_possibly_replaces = update_replaces_from_submission(request, submission, draft)

    update_name_contains_indexes_with_new_doc(draft)

    announce_to_lists(request, submission)
    if submission.group and submission.group.type_id == 'wg' and draft.rev == '00':
        announce_new_wg_00(request, submission)
    announce_new_version(request, submission, draft, state_change_msg)
    announce_to_authors(request, submission)

    if new_possibly_replaces:
        send_review_possibly_replaces_request(request, draft, submitter_info)

    submission.draft = draft
    submission.save()

    create_submission_event(request, submission, approved_subm_desc)

def update_replaces_from_submission(request, submission, draft):
    if not submission.replaces:
        return [], []

    is_secretariat = has_role(request.user, "Secretariat")
    is_chair_of = []
    if request.user.is_authenticated:
        is_chair_of = list(Group.objects.filter(role__person__user=request.user, role__name="chair"))

    replaces = DocAlias.objects.filter(name__in=submission.replaces.split(",")).prefetch_related("docs", "docs__group")
    existing_replaces = list(draft.related_that_doc("replaces"))
    existing_suggested = set(draft.related_that_doc("possibly-replaces"))

    submitter_email = submission.submitter_parsed()["email"]

    approved = []
    suggested = []
    for r in replaces:
        if r in existing_replaces:
            continue

        rdoc = r.document

        if rdoc == draft:
            continue

        if (is_secretariat
            or (draft.group in is_chair_of and (rdoc.group.type_id == "individ" or rdoc.group in is_chair_of))
            or (submitter_email and rdoc.documentauthor_set.filter(email__address__iexact=submitter_email).exists())):
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

    # make sure we have an email address
    if addr and (addr.startswith('unknown-email-') or is_valid_email(addr)):
        active = True
        addr = addr.lower()
    else:
        log.unreachable('2019-10-02')
        # we're in trouble, use a fake one
        active = False
        addr = "unknown-email-%s" % person.plain_ascii().replace(" ", "-")

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
            email.time = datetime.datetime.now()
        email.origin = "author: %s" % docname
        email.save()

    return person, email

def update_authors(draft, submission):
    persons = []
    for order, author in enumerate(submission.authors):
        person, email = ensure_person_email_info_exists(author["name"], author.get("email"), submission.name)

        a = DocumentAuthor.objects.filter(document=draft, person=person).first()
        if not a:
            a = DocumentAuthor(document=draft, person=person)

        a.email = email
        a.affiliation = author.get("affiliation") or ""
        a.country = author.get("country") or ""
        a.order = order
        a.save()
        log.assertion('a.email_id != "none"')

        persons.append(person)

    draft.documentauthor_set.exclude(person__in=persons).delete()

def cancel_submission(submission):
    submission.state = DraftSubmissionStateName.objects.get(slug="cancel")
    submission.save()

    remove_submission_files(submission)

def rename_submission_files(submission, prev_rev, new_rev):
    for ext in settings.IDSUBMIT_FILE_TYPES:
        source = os.path.join(settings.IDSUBMIT_STAGING_PATH, '%s-%s.%s' % (submission.name, prev_rev, ext))
        dest = os.path.join(settings.IDSUBMIT_STAGING_PATH, '%s-%s.%s' % (submission.name, new_rev, ext))
        if os.path.exists(source):
            os.rename(source, dest)

def move_files_to_repository(submission):
    for ext in settings.IDSUBMIT_FILE_TYPES:
        source = os.path.join(settings.IDSUBMIT_STAGING_PATH, '%s-%s.%s' % (submission.name, submission.rev, ext))
        dest = os.path.join(settings.IDSUBMIT_REPOSITORY_PATH, '%s-%s.%s' % (submission.name, submission.rev, ext))
        if os.path.exists(source):
            os.rename(source, dest)
        else:
            if os.path.exists(dest):
                log.log("Intended to move '%s' to '%s', but found source missing while destination exists.")
            elif ext in submission.file_types.split(','):
                raise ValueError("Intended to move '%s' to '%s', but found source and destination missing.")

def remove_submission_files(submission):
    for ext in submission.file_types.split(','):
        source = os.path.join(settings.IDSUBMIT_STAGING_PATH, '%s-%s%s' % (submission.name, submission.rev, ext))
        if os.path.exists(source):
            os.unlink(source)

def approvable_submissions_for_user(user):
    if not user.is_authenticated:
        return []

    res = Submission.objects.filter(state="grp-appr").order_by('-submission_date')
    if has_role(user, "Secretariat"):
        return res

    # those we can reach as chair
    return res.filter(group__role__name="chair", group__role__person__user=user)

def preapprovals_for_user(user):
    if not user.is_authenticated:
        return []

    posted = Submission.objects.distinct().filter(state="posted").values_list('name', flat=True)
    res = Preapproval.objects.exclude(name__in=posted).order_by("-time").select_related('by')
    if has_role(user, "Secretariat"):
        return res

    acronyms = [g.acronym for g in Group.objects.filter(role__person__user=user, type__features__req_subm_approval=True)]

    res = res.filter(name__regex="draft-[^-]+-(%s)-.*" % "|".join(acronyms))

    return res

def recently_approved_by_user(user, since):
    if not user.is_authenticated:
        return []

    res = Submission.objects.distinct().filter(state="posted", submission_date__gte=since, rev="00").order_by('-submission_date')
    if has_role(user, "Secretariat"):
        return res

    # those we can reach as chair
    return res.filter(group__role__name="chair", group__role__person__user=user)

def expirable_submissions(older_than_days):
    cutoff = datetime.date.today() - datetime.timedelta(days=older_than_days)
    return Submission.objects.exclude(state__in=("cancel", "posted")).filter(submission_date__lt=cutoff)

def expire_submission(submission, by):
    submission.state_id = "cancel"
    submission.save()

    SubmissionEvent.objects.create(submission=submission, by=by, desc="Cancelled expired submission")

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
    return file_name

def get_draft_meta(form, saved_files):
    authors = []
    file_name = saved_files
    abstract = None
    file_size = None
    if form.cleaned_data['xml']:
        # Some meta-information, such as the page-count, can only
        # be retrieved from the generated text file.  Provide a
        # parsed draft object to get at that kind of information.
        file_name['txt'] = os.path.join(settings.IDSUBMIT_STAGING_PATH, '%s-%s.txt' % (form.filename, form.revision))
        file_size = os.stat(file_name['txt']).st_size
        with io.open(file_name['txt']) as txt_file:
            form.parsed_draft = Draft(txt_file.read(), txt_file.name)
    else:
        file_size = form.cleaned_data['txt'].size

    if form.authors:
        authors = form.authors
    else:
        # If we don't have an xml file, try to extract the
        # relevant information from the text file
        for author in form.parsed_draft.get_author_list():
            full_name, first_name, middle_initial, last_name, name_suffix, email, country, company = author

            name = full_name.replace("\n", "").replace("\r", "").replace("<", "").replace(">", "").strip()

            if email:
                try:
                    validate_email(email)
                except ValidationError:
                    email = ""

            def turn_into_unicode(s):
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

            name = turn_into_unicode(name)
            email = turn_into_unicode(email)
            company = turn_into_unicode(company)

            authors.append({
                "name": name,
                "email": email,
                "affiliation": company,
                "country": country
            })

    if form.abstract:
        abstract = form.abstract
    else:
        abstract = form.parsed_draft.get_abstract()

    return authors, abstract, file_name, file_size


def get_submission(form):
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
    # See if there is a Submission in state waiting-for-draft
    # for this revision.
    # If so - we're going to update it otherwise we create a new object 

    submission.state = DraftSubmissionStateName.objects.get(slug="uploaded")
    submission.remote_ip = form.remote_ip
    submission.title = form.title
    submission.abstract = abstract
    submission.pages = form.parsed_draft.get_pagecount()
    submission.words = form.parsed_draft.get_wordcount()
    submission.authors = authors
    submission.first_two_pages = ''.join(form.parsed_draft.pages[:2])
    submission.file_size = file_size
    submission.file_types = ','.join(form.file_types)
    submission.submission_date = datetime.date.today()
    submission.document_date = form.parsed_draft.get_creation_date()
    submission.replaces = ""

    submission.save()

    submission.formal_languages.set(FormalLanguageName.objects.filter(slug__in=form.parsed_draft.get_formal_languages()))

def apply_checkers(submission, file_name):
    # run submission checkers
    def apply_check(submission, checker, method, fn):
        func = getattr(checker, method)
        passed, message, errors, warnings, info = func(fn)
        check = SubmissionCheck(submission=submission, checker=checker.name, passed=passed,
                                message=message, errors=errors, warnings=warnings, items=info,
                                symbol=checker.symbol)
        check.save()

    for checker_path in settings.IDSUBMIT_CHECKER_CLASSES:
        checker_class = import_string(checker_path)
        checker = checker_class()
        # ordered list of methods to try
        for method in ("check_fragment_xml", "check_file_xml", "check_fragment_txt", "check_file_txt", ):
            ext = method[-3:]
            if hasattr(checker, method) and ext in file_name:
                apply_check(submission, checker, method, file_name[ext])
                break

def send_confirmation_emails(request, submission, requires_group_approval, requires_prev_authors_approval):
    docevent_from_submission(request, submission, desc="Uploaded new revision")

    if requires_group_approval:
        submission.state = DraftSubmissionStateName.objects.get(slug="grp-appr")
        submission.save()

        sent_to = send_approval_request_to_group(request, submission)

        desc = "sent approval email to group chairs: %s" % ", ".join(sent_to)
        docDesc = "Request for posting approval emailed to group chairs: %s" % ", ".join(sent_to)

    else:
        group_authors_changed = False
        doc = submission.existing_document()
        if doc and doc.group:
            old_authors = [ author.person for author in doc.documentauthor_set.all() ]
            new_authors = [ get_person_from_name_email(author["name"], author.get("email")) for author in submission.authors ]
            group_authors_changed = set(old_authors)!=set(new_authors)

        submission.auth_key = generate_random_key()
        if requires_prev_authors_approval:
            submission.state = DraftSubmissionStateName.objects.get(slug="aut-appr")
        else:
            submission.state = DraftSubmissionStateName.objects.get(slug="auth")
        submission.save()

        sent_to = send_submission_confirmation(request, submission, chair_notice=group_authors_changed)

        if submission.state_id == "aut-appr":
            desc = "sent confirmation email to previous authors: %s" % ", ".join(sent_to)
            docDesc = "Request for posting confirmation emailed to previous authors: %s" % ", ".join(sent_to)
        else:
            desc = "sent confirmation email to submitter and authors: %s" % ", ".join(sent_to)
            docDesc = "Request for posting confirmation emailed to submitter and authors: %s" % ", ".join(sent_to)
    return sent_to, desc, docDesc

    
