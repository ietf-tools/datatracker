import os
import re
import datetime

from django.conf import settings
from ietf.idtracker.models import InternetDraft, PersonOrOrgInfo


# Some usefull states
UPLOADED = 1
WAITING_AUTHENTICATION = 4
MANUAL_POST_REQUESTED = 5
POSTED = -1
POSTED_BY_SECRETARIAT = -2
CANCELED = -4
INITIAL_VERSION_APPROVAL_REQUESTED = 10


# Not a real WG
NONE_WG = 1027


def perform_post(submission):
    group_id = submission.group_acronym and submission.group_acronym.pk or NONE_WG
    updated = False
    try:
        draft = InternetDraft.objects.get(filename=submission.filename)
        draft.title = submission.id_document_name
        draft.group_id = group_id
        draft.filename = submission.filename
        draft.revision = submission.revision
        draft.revision_date = submission.creation_date
        draft.file_type = submission.file_type
        draft.txt_page_count = submission.txt_page_count
        draft.last_modified_date = datetime.date.today()
        draft.abstract = submission.abstract
        draft.save()
        updated = True
    except InternetDraft.DoesNotExist:
        draft = InternetDraft.objects.create(
            title=submission.id_document_name,
            group_id=group_id,
            filename=submission.filename,
            revision=submission.revision,
            revision_date=submission.creation_date,
            file_type=submission.file_type,
            txt_page_count=submission.txt_page_count,
            start_date=datetime.date.today(),
            last_modified_date=datetime.date.today(),
            abstract=submission.abstract,
            status_id=1,  # Active
            intended_status_id=8,  # None
        )
    move_docs(submission)
    submission.status_id = POSTED
    submission.save()


def get_person_for_user(user):
    try:
        return user.get_profile().person()
    except:
        return None


def is_secretariat(user):
    if not user or not user.is_authenticated():
        return False
    return bool(user.groups.filter(name='Secretariat'))


def move_docs(submission):
    for ext in submission.file_type.split(','):
        source = os.path.join(settings.STAGING_PATH, '%s-%s%s' % (submission.filename, submission.revision, ext))
        dest = os.path.join(settings.INTERNET_DRAFT_PATH, '%s-%s%s' % (submission.filename, submission.revision, ext))
        os.rename(source, dest)


def remove_docs(submission):
    for ext in submission.file_type.split(','):
        source = os.path.join(settings.STAGING_PATH, '%s-%s%s' % (submission.filename, submission.revision, ext))
        if os.path.exists(source):
            os.unlink(source)


class DraftValidation(object):

    def __init__(self, draft):
        self.draft = draft
        self.warnings = {}
        self.passes_idnits = self.passes_idnits()
        self.wg = self.get_working_group()
        self.authors = self.get_authors()
        self.submitter = self.get_submitter()

    def passes_idnits(self):
        passes_idnits = self.check_idnits_success(self.draft.idnits_message)
        return passes_idnits

    def get_working_group(self):
        if self.draft.group_acronym and self.draft.group_acronym.pk == NONE_WG:
            return None
        return self.draft.group_acronym

    def check_idnits_success(self, idnits_message):
        if not idnits_message:
            return False
        success_re = re.compile('\s+Summary:\s+0\s+|No nits found')
        if success_re.search(idnits_message):
            return True
        return False

    def is_valid_attr(self, key):
        if key in self.warnings.keys():
            return False
        return True

    def is_valid(self):
        self.validate_metadata()
        return not bool(self.warnings.keys()) and self.passes_idnits

    def validate_metadata(self):
        self.validate_revision()
        self.validate_authors()
        self.validate_abstract()
        self.validate_creation_date()

    def validate_abstract(self):
        if not self.draft.abstract:
            self.add_warning('abstract', 'Abstract is empty or was not found')

    def add_warning(self, key, value):
        self.warnings.update({key: value})

    def validate_revision(self):
        if self.draft.status_id in [POSTED, POSTED_BY_SECRETARIAT]:
            return
        revision = self.draft.revision
        existing_revisions = [int(i.revision) for i in InternetDraft.objects.filter(filename=self.draft.filename)]
        expected = 0
        if existing_revisions:
            expected = max(existing_revisions) + 1
        if int(revision) != expected:
            self.add_warning('revision', 'Invalid Version Number (Version %02d is expected)' % expected)

    def validate_authors(self):
        if not self.authors:
            self.add_warning('authors', 'No authors found')

    def validate_creation_date(self):
        date = self.draft.creation_date
        if not date:
            self.add_warning('creation_date', 'Creation Date field is empty or the creation date is not in a proper format')
            return
        submit_date = self.draft.submission_date
        if date > submit_date:
            self.add_warning('creation_date', 'Creation Date must not be set after submission date')
        if date + datetime.timedelta(days=3) < submit_date:
            self.add_warning('creation_date', 'Creation Date must be within 3 days of submission date')

    def get_authors(self):
        tmpauthors = self.draft.tempidauthors_set.exclude(author_order=0).order_by('author_order')
        return tmpauthors

    def get_submitter(self):
        submitter = self.draft.tempidauthors_set.filter(author_order=0)
        if submitter:
            return submitter[0]
        elif self.draft.submitter_tag:
            try:
                return PersonOrOrgInfo.objects.get(pk=self.draft.submitter_tag)
            except PersonOrOrgInfo.DoesNotExist:
                return False
        return None
