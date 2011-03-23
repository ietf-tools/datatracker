import os
import re
import datetime

from django.conf import settings
from django.contrib.sites.models import Site

from ietf.idtracker.models import (InternetDraft, PersonOrOrgInfo, IETFWG,
                                   IDAuthor, EmailAddress)
from ietf.utils.mail import send_mail


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


def request_full_url(request, submission):
    subject = 'Full url for managing submission of draft %s' % submission.filename
    from_email = settings.IDST_FROM_EMAIL
    to_email = ['%s <%s>' % i.email() for i in submission.tempidauthors_set.all()]
    send_mail(request, to_email, from_email, subject, 'submit/request_full_url.txt',
        {'submission': submission,
         'domain': Site.objects.get_current().domain})


def perform_post(submission):
    group_id = submission.group_acronym and submission.group_acronym.pk or NONE_WG
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
    update_authors(draft, submission)
    move_docs(submission)
    submission.status_id = POSTED
    submission.save()


def find_person(first_name, last_name, middle_initial, name_suffix, email):
    person_list = None
    if email:
        person_list = PersonOrOrgInfo.objects.filter(emailaddress__address=email).distinct()
        if person_list and len(person_list) == 1:
            return person_list[0]
    if not person_list:
        person_list = PersonOrOrgInfo.objects.all()
    person_list = person_list.filter(first_name=first_name,
                                     last_name=last_name)
    if middle_initial:
        person_list = person_list.filter(middle_initial=middle_initial)
    if name_suffix:
        person_list = person_list.filter(name_suffix=name_suffix)
    if person_list:
        return person_list[0]
    return None


def update_authors(draft, submission):
    # TempAuthor of order 0 is submitter
    new_authors = list(submission.tempidauthors_set.filter(author_order__gt=0))
    person_pks = []
    for author in new_authors:
        person = find_person(author.first_name, author.last_name,
                             author.middle_initial, author.name_suffix,
                             author.email_address)
        if not person:
            person = PersonOrOrgInfo(
                first_name=author.first_name,
                last_name=author.last_name,
                middle_initial=author.middle_initial or '',
                name_suffix=author.name_suffix or '',
                )
            person.save()
            if author.email:
                EmailAddress.objects.create(
                    address=author.email,
                    priority=1,
                    type='INET',
                    person_or_org=person,
                    )
        person_pks.append(person.pk)
        try:
            idauthor = IDAuthor.objects.get(
                document=draft,
                person=person,
                )
            idauthor.author_order = author.author_order
        except IDAuthor.DoesNotExist:
            idauthor = IDAuthor(
                document=draft,
                person=person,
                author_order=author.author_order,
                )
        idauthor.save()
    draft.authors.exclude(person__pk__in=person_pks).delete()


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
        self.validate_wg()

    def validate_wg(self):
        if self.wg and not self.wg.status.pk == IETFWG.ACTIVE:
            self.add_warning('group', 'Working Group exists but is not an active WG')

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
        try:
            if int(revision) != expected:
                self.add_warning('revision', 'Invalid Version Number (Version %02d is expected)' % expected)
        except ValueError:
            self.add_warning('revision', 'Revision not found')

    def validate_authors(self):
        if not self.authors:
            self.add_warning('authors', 'No authors found')
            return

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
