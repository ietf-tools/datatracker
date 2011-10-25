from django.db.models import Q

from redesign.doc.models import Document


class RuleManager(object):

    codename = ''
    description = ''

    def __init__(self, value):
        self.value = self.get_value(value)

    def get_value(self, value):
        return value

    def get_documents(self):
        return Document.objects.none()


class WgAsociatedRule(RuleManager):
    codename = 'wg_asociated'
    description = 'All I-Ds associated with a particular WG'

    def get_documents(self):
        return Document.objects.filter(group__acronym=self.value)


class AreaAsociatedRule(RuleManager):
    codename = 'area_asociated'
    description = 'All I-Ds associated with all WGs in a particular Area'

    def get_documents(self):
        return Document.objects.filter(group__parent__acronym=self.value, group__parent__type='area')


class AdResponsibleRule(RuleManager):
    codename = 'ad_responsible'
    description = 'All I-Ds with a particular responsible AD'

    def get_documents(self):
        return Document.objects.filter(ad__name__icontains=self.value)


class AuthorRule(RuleManager):
    codename = 'author'
    description = 'All I-Ds with a particular author'

    def get_documents(self):
        return Document.objects.filter(authors__person__name__icontains=self.value)


class ShepherdRule(RuleManager):
    codename = 'shepherd'
    description = 'All I-Ds with a particular document shepherd'

    def get_documents(self):
        return Document.objects.filter(shepherd__name__icontains=self.value)


class ReferenceToRFCRule(RuleManager):
    codename = 'reference_to_rfc'
    description = 'All I-Ds that have a reference to a particular RFC'


class ReferenceToIDRule(RuleManager):
    codename = 'reference_to_id'
    description = 'All I-Ds that have a reference to a particular I-D'


class ReferenceFromRFCRule(RuleManager):
    codename = 'reference_from_rfc'
    description = 'All I-Ds that are referenced by a particular RFC'


class ReferenceFromIDRule(RuleManager):
    codename = 'reference_from_id'
    description = 'All I-Ds that are referenced by a particular I-D'


class WithTextRule(RuleManager):
    codename = 'with_text'
    description = 'All I-Ds that contain a particular text string'

    def get_documents(self):
        return Document.objects.filter(Q(title__icontains=self.value) | Q(abstract__icontains=self.value))


TYPES_OF_RULES = [(i.codename, i.description) for i in RuleManager.__subclasses__()]
