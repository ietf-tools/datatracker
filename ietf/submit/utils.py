import re

from ietf.idtracker.models import InternetDraft, EmailAddress


class DraftValidation(object):

    def __init__(self, draft):
        self.draft = draft
        self.warnings = {}
        self.passes_idnits = self.passes_idnits()
        self.wg = self.get_working_group()
        self.authors = self.get_authors()

    def passes_idnits(self):
        passes_idnits = self.check_idnits_success(self.draft.idnits_message)
        return passes_idnits

    def get_working_group(self):
        filename = self.draft.filename
        existing_draft = InternetDraft.objects.filter(filename=filename)
        if existing_draft:
            return existing_draft[0].group and existing_draft[0].group.ietfwg or None
        else:
            if filename.startswith('draft-ietf-'):
                # Extra check for WG that contains dashes
                for group in IETFWG.objects.filter(group_acronym__acronym__contains='-'):
                    if filename.startswith('draft-ietf-%s-' % group.group_acronym.acronym):
                        return group
                group_acronym = filename.split('-')[2]
                try:
                    return IETFWG.objects.get(group_acronym__acronym=group_acronym)
                except IETFWG.DoesNotExist:
                    self.add_warning('group', 'Invalid WG ID: %s' % group_acronym)
                    return None
            else:
                return None

    def check_idnits_success(self, idnits_message):
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

    def add_warning(self, key, value):
        self.warnings.update({key: value})

    def validate_revision(self):
        revision = self.draft.revision
        existing_revisions = [int(i.revision) for i in InternetDraft.objects.filter(filename=self.draft.filename)]
        expected = 0
        if existing_revisions:
            expected = max(existing_revisions) + 1
        if int(revision) != expected:
            self.add_warning('revision', 'Invalid Version Number (Version %00d is expected)' % expected)

    def validate_authors(self):
        if not self.authors:
            self.add_warning('authors', 'No authors found')

    def get_authors(self):
        tmpauthors = self.draft.tempidauthors_set.all().order_by('author_order')
        authors = []
        for i in tmpauthors:
            person = None
            for existing in EmailAddress.objects.filter(address=i.email_address):
                try:
                    person = existing.person_or_org
                except PersonOrOrgInfo.DoesNotExist:
                    pass
            if not person:
                authors.append(i)
            else:
                authors.append(person)
        return authors
