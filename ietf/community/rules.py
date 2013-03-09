from django.db.models import Q

from ietf.doc.models import Document
from ietf.group.models import Group
from ietf.person.models import Person
from ietf.doc.models import State


class RuleManager(object):

    codename = ''
    description = ''

    def __init__(self, value):
        self.value = self.get_value(value)

    def get_value(self, value):
        return value

    def get_documents(self):
        return Document.objects.none()

    def options(self):
        return None

    def show_value(self):
        return self.value


class WgAsociatedRule(RuleManager):
    codename = 'wg_asociated'
    description = 'All I-Ds associated with a particular WG'

    def get_documents(self):
        return Document.objects.filter(type='draft', states__slug='active').filter(group__acronym=self.value).distinct()

    def options(self):
        return [(i.acronym, "%s &mdash; %s"%(i.acronym, i.name)) for i in Group.objects.filter(type='wg', state='active').distinct().order_by('acronym')]

    def show_value(self):
        try:
            return Group.objects.get(acronym=self.value).name
        except Group.DoesNotExist:
            return self.value


class AreaAsociatedRule(RuleManager):
    codename = 'area_asociated'
    description = 'All I-Ds associated with all WGs in a particular Area'

    def get_documents(self):
        return Document.objects.filter(type='draft', states__slug='active').filter(group__parent__acronym=self.value, group__parent__type='area').distinct()

    def options(self):
        return [(i.acronym, "%s &mdash; %s"%(i.acronym, i.name)) for i in Group.objects.filter(type='area', state='active').distinct().order_by('name')]

    def show_value(self):
        try:
            return Group.objects.get(acronym=self.value).name
        except Group.DoesNotExist:
            return self.value


class AdResponsibleRule(RuleManager):
    codename = 'ad_responsible'
    description = 'All I-Ds with a particular responsible AD'

    def get_documents(self):
        return Document.objects.filter(type='draft', states__slug='active').filter(ad=self.value).distinct()

    def options(self):
        return [(i.pk, i.name) for i in Person.objects.filter(role__name='ad',group__state='active').distinct().order_by('name')]

    def show_value(self):
        try:
            return Person.objects.get(pk=self.value).name
        except Person.DoesNotExist:
            return self.value


class AuthorRule(RuleManager):
    codename = 'author'
    description = 'All I-Ds with a particular author'

    def get_documents(self):
        return Document.objects.filter(type='draft', states__slug='active').filter(authors__person__name__icontains=self.value).distinct()


class ShepherdRule(RuleManager):
    codename = 'shepherd'
    description = 'All I-Ds with a particular document shepherd'

    def get_documents(self):
        return Document.objects.filter(type='draft', states__slug='active').filter(shepherd__name__icontains=self.value).distinct()


# class ReferenceToRFCRule(RuleManager):
#     codename = 'reference_to_rfc'
#     description = 'All I-Ds that have a reference to a particular RFC'
# 
#     def get_documents(self):
#         return Document.objects.filter(type='draft', states__slug='active').filter(relateddocument__target__document__states__slug='rfc', relateddocument__target__name__icontains=self.value).distinct()
# 
# 
# class ReferenceToIDRule(RuleManager):
#     codename = 'reference_to_id'
#     description = 'All I-Ds that have a reference to a particular I-D'
# 
#     def get_documents(self):
#         return Document.objects.filter(type='draft', states__slug='active').filter(relateddocument__target__document__type='draft', relateddocument__target__name__icontains=self.value).distinct()
# 
# 
# class ReferenceFromRFCRule(RuleManager):
#     codename = 'reference_from_rfc'
#     description = 'All I-Ds that are referenced by a particular RFC'
# 
#     def get_documents(self):
#         return Document.objects.filter(type='draft', states__slug='active').filter(relateddocument__source__states__slug='rfc', relateddocument__source__name__icontains=self.value).distinct()
# 
# 
# 
# class ReferenceFromIDRule(RuleManager):
#     codename = 'reference_from_id'
#     description = 'All I-Ds that are referenced by a particular I-D'
# 
#     def get_documents(self):
#         return Document.objects.filter(type='draft', states__slug='active').filter(relateddocument__source__type='draft', relateddocument__source__name__icontains=self.value).distinct()


class WithTextRule(RuleManager):
    codename = 'with_text'
    description = 'All I-Ds that contain a particular text string in the name'

    def get_documents(self):
        return Document.objects.filter(type='draft', states__slug='active').filter(name__icontains=self.value).distinct()

class IABInState(RuleManager):
    codename = 'in_iab_state'
    description = 'All I-Ds that are in a particular IAB state'

    def get_documents(self):
        return Document.objects.filter(states__type='draft-stream-iab', states__slug=self.value).distinct()

    def options(self):
        return [(i.slug, i.name) for i in State.objects.filter(type='draft-stream-iab').order_by('name')]

    def show_value(self):
        try:
            return State.objects.get(type='draft-stream-iab', slug=self.value).name
        except State.DoesNotExist:
            return self.value

class IANAInState(RuleManager):
    codename = 'in_iana_state'
    description = 'All I-Ds that are in a particular IANA state'

    def get_documents(self):
        return Document.objects.filter(states__type='draft-iana-review', states__slug=self.value).distinct()

    def options(self):
        return [(i.slug, i.name) for i in State.objects.filter(type='draft-iana-review').order_by('name')]

    def show_value(self):
        try:
            return State.objects.get(type='draft-iana-review', slug=self.value).name
        except State.DoesNotExist:
            return self.value

class IESGInState(RuleManager):
    codename = 'in_iesg_state'
    description = 'All I-Ds that are in a particular IESG state'

    def get_documents(self):
        return Document.objects.filter(states__type='draft-iesg', states__slug=self.value).distinct()

    def options(self):
        return [(i.slug, i.name) for i in State.objects.filter(type='draft-iesg').order_by('name')]

    def show_value(self):
        try:
            return State.objects.get(type='draft-iesg', slug=self.value).name
        except State.DoesNotExist:
            return self.value

class IRTFInState(RuleManager):
    codename = 'in_irtf_state'
    description = 'All I-Ds that are in a particular IRTF state'

    def get_documents(self):
        return Document.objects.filter(states__type='draft-stream-irtf', states__slug=self.value).distinct()

    def options(self):
        return [(i.slug, i.name) for i in State.objects.filter(type='draft-stream-irtf').order_by('name')]

    def show_value(self):
        try:
            return State.objects.get(type='draft-stream-irtf', slug=self.value).name
        except State.DoesNotExist:
            return self.value

class ISEInState(RuleManager):
    codename = 'in_ise_state'
    description = 'All I-Ds that are in a particular ISE state'

    def get_documents(self):
        return Document.objects.filter(states__type='draft-stream-ise', states__slug=self.value).distinct()

    def options(self):
        return [(i.slug, i.name) for i in State.objects.filter(type='draft-stream-ise').order_by('name')]

    def show_value(self):
        try:
            return State.objects.get(type='draft-stream-ise', slug=self.value).name
        except State.DoesNotExist:
            return self.value

class RfcEditorInState(RuleManager):
    codename = 'in_rfcEdit_state'
    description = 'All I-Ds that are in a particular RFC Editor state'

    def get_documents(self):
        return Document.objects.filter(states__type='draft-rfceditor', states__slug=self.value).distinct()

    def options(self):
        return [(i.slug, i.type_id + ": " + i.name) for i in State.objects.filter(type='draft-rfceditor').order_by('name')]

    def show_value(self):
        try:
            return State.objects.get(type='draft-rfceditor', slug=self.value).name
        except State.DoesNotExist:
            return self.value

class WGInState(RuleManager):
    codename = 'in_wg_state'
    description = 'All I-Ds that are in a particular Working Group state'

    def get_documents(self):
        return Document.objects.filter(states__type='draft-stream-ietf', states__slug=self.value).distinct()

    def options(self):
        return [(i.slug, i.type_id + ": " + i.name) for i in State.objects.filter(type='draft-stream-ietf').order_by('name')]

    def show_value(self):
        try:
            return State.objects.get(type='draft-stream-ietf', slug=self.value).name
        except State.DoesNotExist:
            return self.value

class RfcWgAsociatedRule(RuleManager):
    codename = 'wg_asociated_rfc'
    description = 'All RFCs associated with a particular WG'

    def get_documents(self):
        return Document.objects.filter(type='draft', states__slug='rfc').filter(group__acronym=self.value).distinct()

    def options(self):
        return [(i.acronym, "%s &mdash; %s"%(i.acronym, i.name)) for i in Group.objects.filter(type='wg').distinct().order_by('acronym')]

    def show_value(self):
        try:
            return Group.objects.get(type='draft', acronym=self.value).name
        except Group.DoesNotExist:
            return self.value


class RfcAreaAsociatedRule(RuleManager):
    codename = 'area_asociated_rfc'
    description = 'All RFCs associated with all WGs in a particular Area'

    def get_documents(self):
        return Document.objects.filter(type='draft', states__slug='rfc').filter(group__parent__acronym=self.value, group__parent__type='area').distinct()

    def options(self):
        return [(i.acronym, "%s &mdash; %s"%(i.acronym, i.name)) for i in Group.objects.filter(type='area').distinct().order_by('name')]

    def show_value(self):
        try:
            return Group.objects.get(type='draft', acronym=self.value).name
        except Group.DoesNotExist:
            return self.value


class RfcAuthorRule(RuleManager):
    codename = 'author_rfc'
    description = 'All RFCs with a particular author'

    def get_documents(self):
        return Document.objects.filter(type='draft', states__slug='rfc').filter(authors__person__name__icontains=self.value).distinct()



TYPES_OF_RULES = [(i.codename, i.description) for i in RuleManager.__subclasses__()]


