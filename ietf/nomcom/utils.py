from django.shortcuts import get_object_or_404

from ietf.dbtemplate.models import DBTemplate

MAIN_NOMCOM_TEMPLATE_PATH = '/nomcom/defaults/'
QUESTIONNAIRE_TEMPLATE = 'position/questionnaire.txt'
REQUIREMENTS_TEMPLATE = 'position/requirements.txt'
HOME_TEMPLATE = 'home.rst'
INEXISTENT_PERSON_TEMPLATE = 'email/inexistent_person.txt'
NOMINEE_EMAIL_TEMPLATE = 'email/new_nominee.txt'
NOMINATION_EMAIL_TEMPLATE = 'email/new_nomination.txt'
DEFAULT_NOMCOM_TEMPLATES = [HOME_TEMPLATE, INEXISTENT_PERSON_TEMPLATE, NOMINATION_EMAIL_TEMPLATE, NOMINEE_EMAIL_TEMPLATE]


def initialize_templates_for_group(group):
    for template_name in DEFAULT_NOMCOM_TEMPLATES:
        template_path = MAIN_NOMCOM_TEMPLATE_PATH + template_name
        template = DBTemplate.objects.get(path=template_path)
        DBTemplate.objects.create(
            group=group.group,
            title=template.title,
            path='/nomcom/' + group.group.acronym + '/' + template_name,
            variables=template.variables,
            type_id=template.type_id,
            content=template.content)


def initialize_questionnaire_for_position(position):
    questionnaire_path = MAIN_NOMCOM_TEMPLATE_PATH + QUESTIONNAIRE_TEMPLATE
    template = DBTemplate.objects.get(path=questionnaire_path)
    return DBTemplate.objects.create(
            group=position.nomcom.group,
            title=template.title + '[%s]' % position.name,
            path='/nomcom/' + position.nomcom.group.acronym + '/' + str(position.id) + '/' + QUESTIONNAIRE_TEMPLATE,
            variables=template.variables,
            type_id=template.type_id,
            content=template.content)


def initialize_requirements_for_position(position):
    requirements_path = MAIN_NOMCOM_TEMPLATE_PATH + REQUIREMENTS_TEMPLATE
    template = DBTemplate.objects.get(path=requirements_path)
    return DBTemplate.objects.create(
            group=position.nomcom.group,
            title=template.title + '[%s]' % position.name,
            path='/nomcom/' + position.nomcom.group.acronym + '/' + str(position.id) + '/' + REQUIREMENTS_TEMPLATE,
            variables=template.variables,
            type_id=template.type_id,
            content=template.content)


def get_nomcom_by_year(year):
    from ietf.nomcom.models import NomCom
    return get_object_or_404(NomCom,
                             group__acronym__icontains=year,
                             group__state__slug='active')
