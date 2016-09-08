import datetime
import hashlib
import os
import re
import tempfile

from email.header import decode_header
from email.iterators import typed_subpart_iterator
from email import message_from_string

from django.conf import settings
from django.contrib.sites.models import Site
from django.core.exceptions import ObjectDoesNotExist
from django.core.urlresolvers import reverse
from django.template.loader import render_to_string
from django.shortcuts import get_object_or_404
from django.utils.encoding import smart_str

from ietf.dbtemplate.models import DBTemplate
from ietf.person.models import Email, Person
from ietf.mailtrigger.utils import gather_address_lists
from ietf.utils.pipe import pipe
from ietf.utils import unaccent
from ietf.utils.mail import send_mail_text, send_mail
from ietf.utils.log import log

import debug                            # pyflakes:ignore

MAIN_NOMCOM_TEMPLATE_PATH = '/nomcom/defaults/'
QUESTIONNAIRE_TEMPLATE = 'position/questionnaire.txt'
HEADER_QUESTIONNAIRE_TEMPLATE = 'position/header_questionnaire.txt'
REQUIREMENTS_TEMPLATE = 'position/requirements'
HOME_TEMPLATE = 'home.rst'
INEXISTENT_PERSON_TEMPLATE = 'email/inexistent_person.txt'
NOMINEE_EMAIL_TEMPLATE = 'email/new_nominee.txt'
NOMINATION_EMAIL_TEMPLATE = 'email/new_nomination.txt'
NOMINEE_ACCEPT_REMINDER_TEMPLATE = 'email/nomination_accept_reminder.txt'
NOMINEE_QUESTIONNAIRE_REMINDER_TEMPLATE = 'email/questionnaire_reminder.txt'
NOMINATION_RECEIPT_TEMPLATE = 'email/nomination_receipt.txt'
FEEDBACK_RECEIPT_TEMPLATE = 'email/feedback_receipt.txt'

DEFAULT_NOMCOM_TEMPLATES = [HOME_TEMPLATE,
                            INEXISTENT_PERSON_TEMPLATE,
                            NOMINEE_EMAIL_TEMPLATE,
                            NOMINATION_EMAIL_TEMPLATE,
                            NOMINEE_ACCEPT_REMINDER_TEMPLATE,
                            NOMINEE_QUESTIONNAIRE_REMINDER_TEMPLATE,
                            NOMINATION_RECEIPT_TEMPLATE,
                            FEEDBACK_RECEIPT_TEMPLATE]


def get_nomcom_by_year(year):
    from ietf.nomcom.models import NomCom
    return get_object_or_404(NomCom,
                             group__acronym__icontains=year,
                             )


def get_year_by_nomcom(nomcom):
    acronym = nomcom.group.acronym
    m = re.search('(?P<year>\d\d\d\d)', acronym)
    return m.group(0)


def get_user_email(user):
    # a user object already has an email field, but we don't want to
    # overwrite anything that might be there, and we don't know that
    # what's there is the right thing, so we cache the lookup results in a
    # separate attribute
    if not hasattr(user, "_email_cache"):
        user._email_cache = None
        if hasattr(user, "person"):
            emails = user.person.email_set.filter(active=True).order_by('-time')
            if emails:
                user._email_cache = emails[0]
                for email in emails:
                    if email.address == user.username:
                        user._email_cache = email
        else:
            try: 
                user._email_cache = Email.objects.get(address=user.username)
            except ObjectDoesNotExist:
                pass
    return user._email_cache

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
        title=template.title + ' [%s]' % position.name,
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
    if code != 0:
        log("openssl error: %s:\n  Error %s: %s" %(command, code, error))        
    return out


def store_nomcom_private_key(request, year, private_key):
    if not private_key:
        request.session['NOMCOM_PRIVATE_KEY_%s' % year] = ''
    else:
        command = "%s bf -e -in /dev/stdin -k \"%s\" -a"
        code, out, error = pipe(command % (settings.OPENSSL_COMMAND,
                                           settings.SECRET_KEY), private_key)
        if code != 0:
            log("openssl error: %s:\n  Error %s: %s" %(command, code, error))        
        if error:
            out = ''
        request.session['NOMCOM_PRIVATE_KEY_%s' % year] = out


def validate_private_key(key):
    key_file = tempfile.NamedTemporaryFile(delete=False)
    key_file.write(key)
    key_file.close()

    command = "%s rsa -in %s -check -noout"
    code, out, error = pipe(command % (settings.OPENSSL_COMMAND,
                                       key_file.name))
    if code != 0:
        log("openssl error: %s:\n  Error %s: %s" %(command, code, error))        

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
    if code != 0:
        log("openssl error: %s:\n  Error %s: %s" %(command, code, error))        

    os.unlink(key_file.name)
    return (not error, error)


def send_accept_reminder_to_nominee(nominee_position):
    today = datetime.date.today().strftime('%Y%m%d')
    subject = 'Reminder: please accept (or decline) your nomination.'
    from_email = settings.NOMCOM_FROM_EMAIL
    domain = Site.objects.get_current().domain
    position = nominee_position.position
    nomcom = position.nomcom
    nomcom_template_path = '/nomcom/%s/' % nomcom.group.acronym
    mail_path = nomcom_template_path + NOMINEE_ACCEPT_REMINDER_TEMPLATE
    nominee = nominee_position.nominee
    (to_email, cc) = gather_address_lists('nomination_accept_reminder',nominee=nominee.email.address)

    hash = get_hash_nominee_position(today, nominee_position.id)
    accept_url = reverse('nomcom_process_nomination_status',
                          None,
                          args=(get_year_by_nomcom(nomcom),
                          nominee_position.id,
                          'accepted',
                          today,
                          hash))
    decline_url = reverse('nomcom_process_nomination_status',
                          None,
                          args=(get_year_by_nomcom(nomcom),
                          nominee_position.id,
                          'declined',
                          today,
                          hash))

    context = {'nominee': nominee,
               'position': position,
               'domain': domain,
               'accept_url': accept_url,
               'decline_url': decline_url}
    body = render_to_string(mail_path, context)
    path = '%s%d/%s' % (nomcom_template_path, position.id, QUESTIONNAIRE_TEMPLATE)
    body += '\n\n%s' % render_to_string(path, context)
    send_mail_text(None, to_email, from_email, subject, body, cc=cc)

def send_questionnaire_reminder_to_nominee(nominee_position):
    subject = 'Reminder: please complete the Nomcom questionnaires for your nomination.'
    from_email = settings.NOMCOM_FROM_EMAIL
    domain = Site.objects.get_current().domain
    position = nominee_position.position
    nomcom = position.nomcom
    nomcom_template_path = '/nomcom/%s/' % nomcom.group.acronym
    mail_path = nomcom_template_path + NOMINEE_QUESTIONNAIRE_REMINDER_TEMPLATE
    nominee = nominee_position.nominee
    (to_email,cc) = gather_address_lists('nomcom_questionnaire_reminder',nominee=nominee.email.address)

    context = {'nominee': nominee,
               'position': position,
               'domain': domain,
               }
    body = render_to_string(mail_path, context)
    path = '%s%d/%s' % (nomcom_template_path, position.id, QUESTIONNAIRE_TEMPLATE)
    body += '\n\n%s' % render_to_string(path, context)
    send_mail_text(None, to_email, from_email, subject, body, cc=cc)

def send_reminder_to_nominees(nominees,type):
    addrs = []
    if type=='accept':
        for nominee in nominees:
            for nominee_position in nominee.nomineeposition_set.pending():
                send_accept_reminder_to_nominee(nominee_position)
                addrs.append(nominee_position.nominee.email.address)
    elif type=='questionnaire':
        for nominee in nominees:
            for nominee_position in nominee.nomineeposition_set.accepted().without_questionnaire_response():
                send_questionnaire_reminder_to_nominee(nominee_position)
                addrs.append(nominee_position.nominee.email.address)
    return addrs


def make_nomineeposition(nomcom, candidate, position, author):
    from ietf.nomcom.models import Nominee, NomineePosition

    nomcom_template_path = '/nomcom/%s/' % nomcom.group.acronym

    # Add the nomination for a particular position
    nominee, created = Nominee.objects.get_or_create(person=candidate,email=candidate.email(), nomcom=nomcom)
    while nominee.duplicated:
        nominee = nominee.duplicated
    nominee_position, nominee_position_created = NomineePosition.objects.get_or_create(position=position, nominee=nominee)

    if nominee_position_created:
        # send email to nominee
        subject = 'IETF Nomination Information'
        from_email = settings.NOMCOM_FROM_EMAIL
        (to_email, cc) = gather_address_lists('nomination_new_nominee',nominee=nominee.email.address)
        domain = Site.objects.get_current().domain
        today = datetime.date.today().strftime('%Y%m%d')
        hash = get_hash_nominee_position(today, nominee_position.id)
        accept_url = reverse('nomcom_process_nomination_status',
                              None,
                              args=(get_year_by_nomcom(nomcom),
                              nominee_position.id,
                              'accepted',
                              today,
                              hash))
        decline_url = reverse('nomcom_process_nomination_status',
                              None,
                              args=(get_year_by_nomcom(nomcom),
                              nominee_position.id,
                              'declined',
                              today,
                              hash))

        context = {'nominee': nominee.person.name,
                   'position': position.name,
                   'domain': domain,
                   'accept_url': accept_url,
                   'decline_url': decline_url}

        path = nomcom_template_path + NOMINEE_EMAIL_TEMPLATE
        send_mail(None, to_email, from_email, subject, path, context, cc=cc)

        # send email to nominee with questionnaire
        if nomcom.send_questionnaire:
            subject = '%s Questionnaire' % position
            from_email = settings.NOMCOM_FROM_EMAIL
            (to_email, cc) = gather_address_lists('nomcom_questionnaire',nominee=nominee.email.address)
            context = {'nominee': nominee.person.name,
                      'position': position.name}
            path = '%s%d/%s' % (nomcom_template_path,
                                position.id, HEADER_QUESTIONNAIRE_TEMPLATE)
            body = render_to_string(path, context)
            path = '%s%d/%s' % (nomcom_template_path,
                                position.id, QUESTIONNAIRE_TEMPLATE)
            body += '\n\n%s' % render_to_string(path, context)
            send_mail_text(None, to_email, from_email, subject, body, cc=cc)

    # send emails to nomcom chair
    subject = 'Nomination Information'
    from_email = settings.NOMCOM_FROM_EMAIL
    (to_email, cc) = gather_address_lists('nomination_received',nomcom=nomcom)
    context = {'nominee': nominee.person.name,
               'nominee_email': nominee.email.address,
               'position': position.name}

    if author:
        context.update({'nominator': author.person.name,
                        'nominator_email': author.address})
    else:
        context.update({'nominator': 'Anonymous',
                        'nominator_email': ''})

    path = nomcom_template_path + NOMINATION_EMAIL_TEMPLATE
    send_mail(None, to_email, from_email, subject, path, context, cc=cc)

    return nominee

def make_nomineeposition_for_newperson(nomcom, candidate_name, candidate_email, position, author):

    # This is expected to fail if called with an existing email address
    email = Email.objects.create(address=candidate_email)
    person = Person.objects.create(name=candidate_name,
                                   ascii=unaccent.asciify(candidate_name),
                                   address=candidate_email)
    email.person = person
    email.save()

    # send email to secretariat and nomcomchair to warn about the new person
    subject = 'New person is created'
    from_email = settings.NOMCOM_FROM_EMAIL
    (to_email, cc) = gather_address_lists('nomination_created_person',nomcom=nomcom)
    context = {'email': email.address,
               'fullname': email.person.name,
               'person_id': email.person.id}
    nomcom_template_path = '/nomcom/%s/' % nomcom.group.acronym
    path = nomcom_template_path + INEXISTENT_PERSON_TEMPLATE
    send_mail(None, to_email, from_email, subject, path, context, cc=cc)

    return make_nomineeposition(nomcom, email.person, position, author)

def getheader(header_text, default="ascii"):
    """Decode the specified header"""

    headers = decode_header(header_text)
    header_sections = [unicode(text, charset or default)
                       for text, charset in headers]
    return u"".join(header_sections)


def get_charset(message, default="ascii"):
    """Get the message charset"""

    if message.get_content_charset():
        return message.get_content_charset()

    if message.get_charset():
        return message.get_charset()

    return default


def get_body(message):
    """Get the body of the email message"""

    if message.is_multipart():
        # get the plain text version only
        text_parts = [part for part in typed_subpart_iterator(message,
                                                             'text',
                                                             'plain')]
        body = []
        for part in text_parts:
            charset = get_charset(part, get_charset(message))
            body.append(unicode(part.get_payload(decode=True),
                                charset,
                                "replace"))

        return u"\n".join(body).strip()

    else:  # if it is not multipart, the payload will be a string
           # representing the message body
        body = unicode(message.get_payload(decode=True),
                       get_charset(message),
                       "replace")
        return body.strip()


def parse_email(text):
    if isinstance(text, unicode):
        text = smart_str(text)
    msg = message_from_string(text)

    body = get_body(msg)
    subject = getheader(msg['Subject'])
    return msg['From'], subject, body


def create_feedback_email(nomcom, msg):
    from ietf.nomcom.models import Feedback
    by, subject, body = parse_email(msg)
    #name, addr = parseaddr(by)

    feedback = Feedback(nomcom=nomcom,
                        author=by,
                        subject=subject or '',
                        comments=body)
    feedback.save()
    return feedback
