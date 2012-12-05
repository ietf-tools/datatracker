from ietf.dbtemplate.models import DBTemplate

MAIN_NOMCOM_TEMPLATE_PATH = '/nomcom/defaults/'
DEFAULT_NOMCOM_TEMPLATES = 'home.rst', 'email/inexistent_person.txt', 'email/new_nomination.txt', 'email/new_nominee.txt'
DEFAULT_QUESTIONNAIRE_TEMPLATE = 'position/questionnaire.txt'
DEFAULT_REQUIREMENTS_TEMPLATE = 'position/requirements.txt'


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
    questionnaire_path = MAIN_NOMCOM_TEMPLATE_PATH + DEFAULT_QUESTIONNAIRE_TEMPLATE
    template = DBTemplate.objects.get(path=questionnaire_path)
    return DBTemplate.objects.create(
            group=position.nomcom.group,
            title=template.title + '[%s]' % position.name,
            path='/nomcom/' + position.nomcom.group.acronym + '/' + str(position.id) + '/' + DEFAULT_QUESTIONNAIRE_TEMPLATE,
            variables=template.variables,
            type_id=template.type_id,
            content=template.content)


def initialize_requirements_for_position(position):
    requirements_path = MAIN_NOMCOM_TEMPLATE_PATH + DEFAULT_REQUIREMENTS_TEMPLATE
    template = DBTemplate.objects.get(path=requirements_path)
    return DBTemplate.objects.create(
            group=position.nomcom.group,
            title=template.title + '[%s]' % position.name,
            path='/nomcom/' + position.nomcom.group.acronym + '/' + str(position.id) + '/' + DEFAULT_REQUIREMENTS_TEMPLATE,
            variables=template.variables,
            type_id=template.type_id,
            content=template.content)
