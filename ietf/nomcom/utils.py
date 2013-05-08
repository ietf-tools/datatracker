import email
import hashlib
import os
import re
import tempfile

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404

from ietf.dbtemplate.models import DBTemplate
from ietf.person.models import Email
from ietf.utils.pipe import pipe

MAIN_NOMCOM_TEMPLATE_PATH = '/nomcom/defaults/'
QUESTIONNAIRE_TEMPLATE = 'position/questionnaire.txt'
HEADER_QUESTIONNAIRE_TEMPLATE = 'position/header_questionnaire.txt'
REQUIREMENTS_TEMPLATE = 'position/requirements.txt'
HOME_TEMPLATE = 'home.rst'
INEXISTENT_PERSON_TEMPLATE = 'email/inexistent_person.txt'
NOMINEE_EMAIL_TEMPLATE = 'email/new_nominee.txt'
NOMINATION_EMAIL_TEMPLATE = 'email/new_nomination.txt'
NOMINEE_REMINDER_TEMPLATE = 'email/nomination_reminder.txt'
NOMINATION_RECEIPT_TEMPLATE = 'email/nomination_receipt.txt'
FEEDBACK_RECEIPT_TEMPLATE = 'email/feedback_receipt.txt'

DEFAULT_NOMCOM_TEMPLATES = [HOME_TEMPLATE,
                            INEXISTENT_PERSON_TEMPLATE,
                            NOMINEE_EMAIL_TEMPLATE,
                            NOMINATION_EMAIL_TEMPLATE,
                            NOMINEE_REMINDER_TEMPLATE,
                            NOMINATION_RECEIPT_TEMPLATE,
                            FEEDBACK_RECEIPT_TEMPLATE]


def get_nomcom_by_year(year):
    from ietf.nomcom.models import NomCom
    return get_object_or_404(NomCom,
                             group__acronym__icontains=year,
                             group__state__slug='active')


def get_year_by_nomcom(nomcom):
    acronym = nomcom.group.acronym
    m = re.search('(?P<year>\d\d\d\d)', acronym)
    return m.group(0)


def get_user_email(user):
    emails = Email.objects.filter(person__user=user)
    mail = emails and emails[0] or None
    return mail


def is_nomcom_member(user, nomcom):
    is_group_member = nomcom.group.is_member(user)
    if not is_group_member:
        raise PermissionDenied("Must be nomcom member")


def is_nomcom_chair(user, nomcom):
    is_group_chair = nomcom.group.is_chair(user)
    if not is_group_chair:
        raise PermissionDenied("Must be nomcom chair")


def get_hash_nominee_position(date, nominee_position_id):
    return hashlib.md5('%s%s%s' % (settings.SECRET_KEY, date, nominee_position_id)).hexdigest()


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
    header_questionnaire_path = MAIN_NOMCOM_TEMPLATE_PATH + HEADER_QUESTIONNAIRE_TEMPLATE
    template = DBTemplate.objects.get(path=questionnaire_path)
    header_template = DBTemplate.objects.get(path=header_questionnaire_path)
    DBTemplate.objects.create(
        group=position.nomcom.group,
        title=header_template.title + ' [%s]' % position.name,
        path='/nomcom/' + position.nomcom.group.acronym + '/' + str(position.id) + '/' + HEADER_QUESTIONNAIRE_TEMPLATE,
        variables=header_template.variables,
        type_id=header_template.type_id,
        content=header_template.content)
    questionnaire = DBTemplate.objects.create(
        group=position.nomcom.group,
        title=template.title + '[%s]' % position.name,
        path='/nomcom/' + position.nomcom.group.acronym + '/' + str(position.id) + '/' + QUESTIONNAIRE_TEMPLATE,
        variables=template.variables,
        type_id=template.type_id,
        content=template.content)
    return questionnaire


def initialize_requirements_for_position(position):
    requirements_path = MAIN_NOMCOM_TEMPLATE_PATH + REQUIREMENTS_TEMPLATE
    template = DBTemplate.objects.get(path=requirements_path)
    return DBTemplate.objects.create(
            group=position.nomcom.group,
            title=template.title + ' [%s]' % position.name,
            path='/nomcom/' + position.nomcom.group.acronym + '/' + str(position.id) + '/' + REQUIREMENTS_TEMPLATE,
            variables=template.variables,
            type_id=template.type_id,
            content=template.content)


def delete_nomcom_templates(nomcom):
    nomcom_template_path = '/nomcom/' + nomcom.group.acronym
    DBTemplate.objects.filter(path__contains=nomcom_template_path).delete()


def retrieve_nomcom_private_key(request, year):
    private_key = request.session.get('NOMCOM_PRIVATE_KEY_%s' % year, None)

    if not private_key:
        return private_key

    command = "%s bf -d -in /dev/stdin -k \"%s\" -a"
    code, out, error = pipe(command % (settings.OPENSSL_COMMAND,
                                       settings.SECRET_KEY), private_key)
    return out


def store_nomcom_private_key(request, year, private_key):
    if not private_key:
        request.session['NOMCOM_PRIVATE_KEY_%s' % year] = ''
    else:
        command = "%s bf -e -in /dev/stdin -k \"%s\" -a"
        code, out, error = pipe(command % (settings.OPENSSL_COMMAND,
                                           settings.SECRET_KEY), private_key)
        if error:
            out = ''
        request.session['NOMCOM_PRIVATE_KEY_%s' % year] = out


def extract_body(payload):
    if isinstance(payload, str):
        return payload
    else:
        return '\n'.join([extract_body(part.get_payload()) for part in payload])


def parse_email(text):
    msg = email.message_from_string(text.encode("utf-8"))

    # comment
    body = extract_body(msg.get_payload())

    return msg['From'], msg['Subject'], body


def validate_private_key(key):
    key_file = tempfile.NamedTemporaryFile(delete=False)
    key_file.write(key)
    key_file.close()

    command = "%s rsa -in %s -check -noout"
    code, out, error = pipe(command % (settings.OPENSSL_COMMAND,
                                       key_file.name))

    os.unlink(key_file.name)
    return (not error, error)


def validate_public_key(public_key):
    key_file = tempfile.NamedTemporaryFile(delete=False)
    for chunk in public_key.chunks():
        key_file.write(chunk)
    key_file.close()

    command = "%s x509 -in %s -noout"
    code, out, error = pipe(command % (settings.OPENSSL_COMMAND,
                                       key_file.name))

    os.unlink(key_file.name)
    return (not error, error)
