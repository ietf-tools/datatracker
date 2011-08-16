class RuleManager(object):

    codename = ''
    description = ''

    def __init__(self, value):
        self.value = self.get_value(value)

    def get_value(self, value):
        return value

    def get_documents(self):
        return []


class WgAsociatedRule(RuleManager):
    codename = 'wg_asociated'
    description = 'All I-Ds associated with an particular WG'


class AreaAsociatedRule(RuleManager):
    codename = 'area_asociated'
    description = 'All I-Ds associated with all WGs in an particular Area'


class AdResponsibleRule(RuleManager):
    codename = 'ad_responsible'
    description = 'All I-Ds with a particular responsible AD'


class AuthorRule(RuleManager):
    codename = 'author'
    description = 'All I-Ds with a particular author'


class ShepherdRule(RuleManager):
    codename = 'shepherd'
    description = 'All I-Ds with a particular document shepherd'


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


TYPES_OF_RULES = [(i.codename, i.description) for i in RuleManager.__subclasses__()]
