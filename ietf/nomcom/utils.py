# Copyright The IETF Trust 2012-2023, All Rights Reserved
# -*- coding: utf-8 -*-


import base64
import datetime
import hashlib
import hmac
import os
import re
import tempfile

from collections import defaultdict
from email import message_from_string, message_from_bytes
from email.errors import HeaderParseError
from email.header import decode_header
from email.iterators import typed_subpart_iterator
from email.utils import parseaddr
from textwrap import dedent

from django.db.models import Q, Count
from django.conf import settings
from django.contrib.sites.models import Site
from django.core.exceptions import ObjectDoesNotExist
from django.urls import reverse
from django.template.loader import render_to_string
from django.shortcuts import get_object_or_404

from ietf.dbtemplate.models import DBTemplate
from ietf.doc.models import DocEvent, NewRevisionDocEvent
from ietf.group.models import Group, Role
from ietf.person.models import Email, Person
from ietf.mailtrigger.utils import gather_address_lists
from ietf.meeting.models import Meeting
from ietf.meeting.utils import participants_for_meeting
from ietf.utils.pipe import pipe
from ietf.utils.mail import send_mail_text, send_mail, get_payload_text
from ietf.utils.log import log
from ietf.person.name import unidecode_name
from ietf.utils.timezone import date_today, datetime_from_date, DEADLINE_TZINFO

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
DESCRIPTION_TEMPLATE = 'topic/description'
IESG_GENERIC_REQUIREMENTS_TEMPLATE = 'iesg_requirements'

DEFAULT_NOMCOM_TEMPLATES = [HOME_TEMPLATE,
                            INEXISTENT_PERSON_TEMPLATE,
                            NOMINEE_EMAIL_TEMPLATE,
                            NOMINATION_EMAIL_TEMPLATE,
                            NOMINEE_ACCEPT_REMINDER_TEMPLATE,
                            NOMINEE_QUESTIONNAIRE_REMINDER_TEMPLATE,
                            NOMINATION_RECEIPT_TEMPLATE,
                            FEEDBACK_RECEIPT_TEMPLATE,
                            IESG_GENERIC_REQUIREMENTS_TEMPLATE,
                        ]

# See RFC8713 section 4.15
# This potentially over-disqualifies past nomcom chairs if some 
# nomcom 2+ nomcoms ago is still in the active state
DISQUALIFYING_ROLE_QUERY_EXPRESSION = (   Q(group__acronym__in=['isocbot', 'ietf-trust', 'llc-board', 'iab'], name_id__in=['member', 'chair'])
                                        | Q(group__type_id='area', group__state='active',name_id='ad')
                                        | Q(group__type_id='nomcom', group__state='active', name_id='chair')
                                      )


def get_nomcom_by_year(year):
    from ietf.nomcom.models import NomCom
    return get_object_or_404(NomCom,
                             group__acronym__icontains=year,
                             )


def get_year_by_nomcom(nomcom):
    acronym = nomcom.group.acronym
    m = re.search(r'(?P<year>\d\d\d\d)', acronym)
    return m.group(0)


def get_person_email(person):
    if not hasattr(person, "_email_cache"):
        person._email_cache = None
        emails = person.email_set.filter(active=True).order_by('-time')
        if emails:
            person._email_cache = emails[0]
            for email in emails:
                if email.address.lower() == person.user.username.lower():
                    person._email_cache = email
        else:
            try: 
                person._email_cache = Email.objects.get(address=person.user.username)
            except ObjectDoesNotExist:
                pass
    return person._email_cache

def get_hash_nominee_position(date, nominee_position_id):
    return hmac.new(settings.NOMCOM_APP_SECRET, f"{date}{nominee_position_id}".encode('utf-8'), hashlib.sha256).hexdigest()

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

def initialize_description_for_topic(topic):
    description_path = MAIN_NOMCOM_TEMPLATE_PATH + DESCRIPTION_TEMPLATE
    template = DBTemplate.objects.get(path=description_path)
    return DBTemplate.objects.create(
            group=topic.nomcom.group,
            title=template.title + ' [%s]' % topic.subject,
            path='/nomcom/' + topic.nomcom.group.acronym + '/topic/' + str(topic.id) + '/' + DESCRIPTION_TEMPLATE,
            variables=template.variables,
            type_id=template.type_id,
            content=template.content)

def delete_nomcom_templates(nomcom):
    nomcom_template_path = '/nomcom/' + nomcom.group.acronym
    DBTemplate.objects.filter(path__contains=nomcom_template_path).delete()

def command_line_safe_secret(secret):
    return base64.encodebytes(secret).decode('utf-8').rstrip()

def retrieve_nomcom_private_key(request, year):
    """Retrieve decrypted nomcom private key from the session store

    Retrieves encrypted, ascii-armored private key from the session store, encodes 
    as utf8 bytes, then decrypts. Raises UnicodeError if the value in the session
    store cannot be encoded as utf8.
    """
    private_key = request.session.get('NOMCOM_PRIVATE_KEY_%s' % year, None)

    if not private_key:
        return private_key

    command = "%s aes-128-ecb -d -in /dev/stdin -k \"%s\" -a -iter 1000"
    code, out, error = pipe(
        command % (
            settings.OPENSSL_COMMAND,
            command_line_safe_secret(settings.NOMCOM_APP_SECRET)
        ),
        # The openssl command expects ascii-armored input, so utf8 encoding should be valid
        private_key.encode("utf8")
    )
    if code != 0:
        log("openssl error: %s:\n  Error %s: %s" %(command, code, error))        
    return out


def store_nomcom_private_key(request, year, private_key):
    """Put encrypted nomcom private key in the session store
    
    Encrypts the private key using openssl, then decodes the ascii-armored output
    as utf8 and adds to the session store. Raises UnicodeError if the openssl's
    output cannot be decoded as utf8.
    """
    if not private_key:
        request.session['NOMCOM_PRIVATE_KEY_%s' % year] = ''
    else:
        command = "%s aes-128-ecb -e -in /dev/stdin -k \"%s\" -a -iter 1000"
        code, out, error = pipe(
            command % (
                settings.OPENSSL_COMMAND,
                command_line_safe_secret(settings.NOMCOM_APP_SECRET)
            ),
            private_key
        )
        if code != 0:
            log("openssl error: %s:\n  Error %s: %s" %(command, code, error))        
        if error and error!=b"*** WARNING : deprecated key derivation used.\nUsing -iter or -pbkdf2 would be better.\n":
            out = b''
        # The openssl command output in 'out' is an ascii-armored value, so should be utf8-decodable
        request.session['NOMCOM_PRIVATE_KEY_%s' % year] = out.decode("utf8")


def validate_private_key(key):
    key_file = tempfile.NamedTemporaryFile(delete=False)
    key_file.write(key.encode('utf-8'))
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
    today = date_today().strftime('%Y%m%d')
    subject = 'Reminder: please accept (or decline) your nomination.'
    domain = Site.objects.get_current().domain
    position = nominee_position.position
    nomcom = position.nomcom
    from_email = settings.NOMCOM_FROM_EMAIL.format(year=nomcom.year())
    nomcom_template_path = '/nomcom/%s/' % nomcom.group.acronym
    mail_path = nomcom_template_path + NOMINEE_ACCEPT_REMINDER_TEMPLATE
    nominee = nominee_position.nominee
    (to_email, cc) = gather_address_lists('nomination_accept_reminder',nominee=nominee.email.address)

    hash = get_hash_nominee_position(today, nominee_position.id)
    accept_url = reverse('ietf.nomcom.views.process_nomination_status',
                          None,
                          args=(get_year_by_nomcom(nomcom),
                          nominee_position.id,
                          'accepted',
                          today,
                          hash))
    decline_url = reverse('ietf.nomcom.views.process_nomination_status',
                          None,
                          args=(get_year_by_nomcom(nomcom),
                          nominee_position.id,
                          'declined',
                          today,
                          hash))

    context = {'nominee': nominee.person.name,
               'position': position,
               'domain': domain,
               'accept_url': accept_url,
               'decline_url': decline_url,
               'year': nomcom.year(),
           }
    body = render_to_string(mail_path, context)
    path = '%s%d/%s' % (nomcom_template_path, position.id, QUESTIONNAIRE_TEMPLATE)
    body += '\n\n%s' % render_to_string(path, context)
    send_mail_text(None, to_email, from_email, subject, body, cc=cc)

def send_questionnaire_reminder_to_nominee(nominee_position):
    subject = 'Reminder: please complete the Nomcom questionnaires for your nomination.'
    domain = Site.objects.get_current().domain
    position = nominee_position.position
    nomcom = position.nomcom
    from_email = settings.NOMCOM_FROM_EMAIL.format(year=nomcom.year())
    nomcom_template_path = '/nomcom/%s/' % nomcom.group.acronym
    mail_path = nomcom_template_path + NOMINEE_QUESTIONNAIRE_REMINDER_TEMPLATE
    nominee = nominee_position.nominee
    (to_email,cc) = gather_address_lists('nomcom_questionnaire_reminder',nominee=nominee.email.address)

    context = {'nominee': nominee.person.name,
               'position': position,
               'domain': domain,
               'year': nomcom.year(),
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
        from_email = settings.NOMCOM_FROM_EMAIL.format(year=nomcom.year())
        (to_email, cc) = gather_address_lists('nomination_new_nominee',nominee=nominee.email.address)
        domain = Site.objects.get_current().domain
        today = date_today().strftime('%Y%m%d')
        hash = get_hash_nominee_position(today, nominee_position.id)
        accept_url = reverse('ietf.nomcom.views.process_nomination_status',
                              None,
                              args=(nomcom.year(),
                              nominee_position.id,
                              'accepted',
                              today,
                              hash))
        decline_url = reverse('ietf.nomcom.views.process_nomination_status',
                              None,
                              args=(nomcom.year(),
                              nominee_position.id,
                              'declined',
                              today,
                              hash))

        context = {'nominee': nominee.person.name,
                   'position': position.name,
                   'year': nomcom.year(),
                   'domain': domain,
                   'accept_url': accept_url,
                   'decline_url': decline_url,
               }

        path = nomcom_template_path + NOMINEE_EMAIL_TEMPLATE
        send_mail(None, to_email, from_email, subject, path, context, cc=cc)

        # send email to nominee with questionnaire
        if nomcom.send_questionnaire:
            subject = '%s Questionnaire' % position
            from_email = settings.NOMCOM_FROM_EMAIL.format(year=nomcom.year())
            (to_email, cc) = gather_address_lists('nomcom_questionnaire',nominee=nominee.email.address)
            context = {'nominee': nominee.person.name,
                      'position': position.name,
                      'year'    : nomcom.year(),
                  }
            path = '%s%d/%s' % (nomcom_template_path,
                                position.id, HEADER_QUESTIONNAIRE_TEMPLATE)
            body = render_to_string(path, context)
            path = '%s%d/%s' % (nomcom_template_path,
                                position.id, QUESTIONNAIRE_TEMPLATE)
            body += '\n\n%s' % render_to_string(path, context)
            send_mail_text(None, to_email, from_email, subject, body, cc=cc)

    # send emails to nomcom chair
    subject = 'Nomination Information'
    from_email = settings.NOMCOM_FROM_EMAIL.format(year=nomcom.year())
    (to_email, cc) = gather_address_lists('nomination_received',nomcom=nomcom)
    context = {'nominee': nominee.person.name,
               'nominee_email': nominee.email.address,
               'position': position.name,
               'year': nomcom.year(),
           }

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
    email = Email.objects.create(address=candidate_email, origin="nominee: %s" % nomcom.group.acronym)
    person = Person.objects.create(name=candidate_name,
                                   ascii=unidecode_name(candidate_name),
                                   )
    email.person = person
    email.save()

    # send email to secretariat and nomcomchair to warn about the new person
    subject = 'New person is created'
    from_email = settings.NOMCOM_FROM_EMAIL.format(year=nomcom.year())
    (to_email, cc) = gather_address_lists('nomination_created_person',nomcom=nomcom)
    context = {'email': email.address,
               'fullname': email.person.name,
               'person_id': email.person.id,
               'year': nomcom.year(),
           }
    nomcom_template_path = '/nomcom/%s/' % nomcom.group.acronym
    path = nomcom_template_path + INEXISTENT_PERSON_TEMPLATE
    send_mail(None, to_email, from_email, subject, path, context, cc=cc)

    return make_nomineeposition(nomcom, email.person, position, author)

def getheader(header_text, default="utf-8"):
    """Decode the specified header"""

    try:
        tuples = decode_header(header_text)
    except TypeError:
        return ""

    header_sections = [ text.decode(charset or default) if isinstance(text, bytes) else text for text, charset in tuples]
    return "".join(header_sections)


def get_charset(message, default="utf-8"):
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
            charset = get_charset(part)
            body.append(get_payload_text(part, default_charset=charset))

        return "\n".join(body).strip()

    else:  # if it is not multipart, the payload will be a string
           # representing the message body
        body = get_payload_text(message)
        return body.strip()


def parse_email(text):
    if isinstance(text, bytes):
        msg = message_from_bytes(text)
    elif isinstance(text, str):
        msg = message_from_string(text)
    else:
        raise ValueError("Expected email message text to be str or bytes")

    body = get_body(msg)
    subject = getheader(msg['Subject'])
    __, addr = parseaddr(msg['From'])
    if not addr:
        raise HeaderParseError

    return addr.lower(), subject, body


def create_feedback_email(nomcom, msg):
    from ietf.nomcom.models import Feedback
    by, subject, body = parse_email(msg)
    #name, addr = parseaddr(by)

    feedback = Feedback(nomcom=nomcom,
                        author=by,
                        subject=subject or '',
                        comments=nomcom.encrypt(body))
    feedback.save()
    return feedback

class EncryptedException(Exception):
    pass

def remove_disqualified(queryset):
        disqualified_roles = Role.objects.filter(DISQUALIFYING_ROLE_QUERY_EXPRESSION)
        return queryset.exclude(role__in=disqualified_roles)

def is_eligible(person, nomcom=None, date=None):
    return list_eligible(nomcom=nomcom, date=date, base_qs=Person.objects.filter(pk=person.pk)).exists()

def list_eligible(nomcom=None, date=None, base_qs=None):
    if not base_qs:
        base_qs = Person.objects.all()
    eligibility_date = get_eligibility_date(nomcom, date)
    if eligibility_date.year in range(2008,2020):
        return list_eligible_8713(date=eligibility_date, base_qs=base_qs)
    elif eligibility_date.year == 2020:
        return list_eligible_8788(date=eligibility_date, base_qs=base_qs)
    elif eligibility_date.year in (2021,2022):
        return list_eligible_8989(date=eligibility_date, base_qs=base_qs)
    elif eligibility_date.year > 2022:
        return list_eligible_9389(date=eligibility_date, base_qs=base_qs)
    else:
        return Person.objects.none()

def decorate_volunteers_with_qualifications(volunteers, nomcom=None, date=None, base_qs=None):
    if not base_qs:
        base_qs = Person.objects.all()
    eligibility_date = get_eligibility_date(nomcom, date)
    if eligibility_date.year in (2021,2022):
        three_of_five_qs, officer_qs, author_qs = get_8989_eligibility_querysets(eligibility_date, base_qs)
        for v in volunteers:
            qualifications = []
            if v.person in three_of_five_qs:
                qualifications.append('path_1')
            if v.person in officer_qs:
                qualifications.append('path_2')
            if v.person in author_qs:
                qualifications.append('path_3')
            v.qualifications = "+".join(qualifications)
    else:
        for v in volunteers:
            v.qualifications = ''

def list_eligible_8713(date, base_qs=None):
    if not base_qs:
        base_qs = Person.objects.all()
    previous_five = previous_five_meetings(date)
    return remove_disqualified(three_of_five_eligible_8713(previous_five=previous_five, queryset=base_qs))

def list_eligible_8788(date, base_qs=None):
    if not base_qs:
        base_qs = Person.objects.all()
    previous_five = Meeting.objects.filter(number__in=['102','103','104','105','106'])
    return remove_disqualified(three_of_five_eligible_8713(previous_five=previous_five, queryset=base_qs))

def get_8989_eligibility_querysets(date, base_qs):
    return get_threerule_eligibility_querysets(date, base_qs, three_of_five_callable=three_of_five_eligible_8713)

def get_9389_eligibility_querysets(date, base_qs):
    return get_threerule_eligibility_querysets(date, base_qs, three_of_five_callable=three_of_five_eligible_9389)

def get_threerule_eligibility_querysets(date, base_qs, three_of_five_callable):
    if not base_qs:
        base_qs = Person.objects.all()

    previous_five = previous_five_meetings(date)
    date_as_dt = datetime_from_date(date, DEADLINE_TZINFO)
    three_of_five_qs = three_of_five_callable(previous_five=previous_five, queryset=base_qs)

    # If date is Feb 29, neither 3 nor 5 years ago has a Feb 29. Use Feb 28 instead.
    if date.month == 2 and date.day == 29:
        three_years_ago = datetime.datetime(date.year - 3, 2, 28, tzinfo=DEADLINE_TZINFO)
        five_years_ago = datetime.datetime(date.year - 5, 2, 28, tzinfo=DEADLINE_TZINFO)
    else:
        three_years_ago = datetime.datetime(date.year - 3, date.month, date.day, tzinfo=DEADLINE_TZINFO)
        five_years_ago = datetime.datetime(date.year - 5, date.month, date.day, tzinfo=DEADLINE_TZINFO)

    officer_qs = base_qs.filter(
        # is currently an officer
        Q(role__name_id__in=('chair','secr'),
          role__group__state_id='active',
          role__group__type_id='wg',
          role__group__time__lte=date_as_dt, ## TODO - inspect - lots of things affect group__time...
        )
        # was an officer since the given date (I think this is wrong - it looks at when roles _start_, not when roles end)
      | Q(rolehistory__group__time__gte=three_years_ago,
          rolehistory__group__time__lte=date_as_dt,
          rolehistory__name_id__in=('chair','secr'),
          rolehistory__group__state_id='active',
          rolehistory__group__type_id='wg',
         )
    ).distinct()

    rfc_pks = set(DocEvent.objects.filter(type='published_rfc', time__gte=five_years_ago, time__lte=date_as_dt).values_list('doc__pk', flat=True))
    iesgappr_pks = set(DocEvent.objects.filter(type='iesg_approved', time__gte=five_years_ago, time__lte=date_as_dt).values_list('doc__pk',flat=True))
    qualifying_pks = rfc_pks.union(iesgappr_pks.difference(rfc_pks))
    author_qs = base_qs.filter(
            documentauthor__document__pk__in=qualifying_pks
        ).annotate(
            document_author_count = Count('documentauthor')
        ).filter(document_author_count__gte=2)
    return three_of_five_qs, officer_qs, author_qs

def list_eligible_8989(date, base_qs=None):
    if not base_qs:
        base_qs = Person.objects.all()
    three_of_five_qs, officer_qs, author_qs = get_8989_eligibility_querysets(date, base_qs)
    three_of_five_pks = three_of_five_qs.values_list('pk',flat=True)
    officer_pks = officer_qs.values_list('pk',flat=True)
    author_pks = author_qs.values_list('pk',flat=True)
    return remove_disqualified(Person.objects.filter(pk__in=set(three_of_five_pks).union(set(officer_pks)).union(set(author_pks))))

def list_eligible_9389(date, base_qs=None):
    if not base_qs:
        base_qs = Person.objects.all()
    three_of_five_qs, officer_qs, author_qs = get_9389_eligibility_querysets(date, base_qs)
    three_of_five_pks = three_of_five_qs.values_list('pk',flat=True)
    officer_pks = officer_qs.values_list('pk',flat=True)
    author_pks = author_qs.values_list('pk',flat=True)
    return remove_disqualified(Person.objects.filter(pk__in=set(three_of_five_pks).union(set(officer_pks)).union(set(author_pks))))

def get_eligibility_date(nomcom=None, date=None):
    if date:
        return date
    elif nomcom:
        if nomcom.first_call_for_volunteers:
            return nomcom.first_call_for_volunteers
        else:
            return datetime.date(int(nomcom.group.acronym[6:]),5,1)
    else:
        last_seated=Role.objects.filter(group__type_id='nomcom',name_id='member').order_by('-group__acronym').first()
        if last_seated:
            last_nomcom_year = int(last_seated.group.acronym[6:])
            if last_nomcom_year == date_today().year:
                next_nomcom_year = last_nomcom_year
            else:
                next_nomcom_year = int(last_seated.group.acronym[6:])+1
            next_nomcom_group = Group.objects.filter(acronym=f'nomcom{next_nomcom_year}').first()
            if next_nomcom_group and next_nomcom_group.nomcom_set.first().first_call_for_volunteers:
                return next_nomcom_group.nomcom_set.first().first_call_for_volunteers
            else:
                return datetime.date(next_nomcom_year,5,1)
        else:
            return datetime.date(date_today().year,5,1)

def previous_five_meetings(date = None):
    if date is None:
        date = date_today()
    return Meeting.objects.filter(type='ietf',date__lte=date).order_by('-date')[:5]

def three_of_five_eligible_8713(previous_five, queryset=None):
    """ Return a list of Person records who attended at least
        3 of the 5 type_id='ietf' meetings before the given
        date. Does not disqualify anyone based on held roles.
        This variant bases the calculation on MeetingRegistration.attended
    """
    if queryset is None:
        queryset = Person.objects.all()
    return queryset.filter(registration__meeting__in=list(previous_five), registration__attended=True).annotate(mtg_count=Count('registration')).filter(mtg_count__gte=3)

def three_of_five_eligible_9389(previous_five, queryset=None):
    """ Return a list of Person records who attended at least
        3 of the 5 type_id='ietf' meetings before the given
        date. Does not disqualify anyone based on held roles.
        This variant bases the calculation on Meeting.Session and MeetingRegistration.checked_in
    """
    if queryset is None:
        queryset = Person.objects.all()

    counts = defaultdict(lambda: 0)
    for meeting in previous_five:
        checked_in, attended = participants_for_meeting(meeting)
        for id in set(checked_in) | set(attended):
            counts[id] += 1
    return queryset.filter(pk__in=[id for id, count in counts.items() if count >= 3])

def suggest_affiliation(person):
    recent_meeting = person.registration_set.order_by('-meeting__date').first()
    affiliation = recent_meeting.affiliation if recent_meeting else ''
    if not affiliation:
        recent_volunteer = person.volunteer_set.order_by('-nomcom__group__acronym').first()
        if recent_volunteer:
            affiliation = recent_volunteer.affiliation 
    if not affiliation:
        recent_draft_revision =  NewRevisionDocEvent.objects.filter(doc__type_id='draft',doc__documentauthor__person=person).order_by('-time').first()
        if recent_draft_revision:
            affiliation = recent_draft_revision.doc.documentauthor_set.filter(person=person).first().affiliation
    return affiliation

def extract_volunteers(year):
    nomcom = get_nomcom_by_year(year)
    # pull list of volunteers
    # get queryset of all eligible (from utils)
    # decorate members of the list with eligibility
    volunteers = nomcom.volunteer_set.all()
    eligible = list_eligible(nomcom)
    for v in volunteers:
        v.eligible = v.person in eligible
    decorate_volunteers_with_qualifications(volunteers,nomcom=nomcom)
    volunteers = sorted(volunteers,key=lambda v:(not v.eligible,v.person.last_name()))
    return nomcom, volunteers


def ingest_feedback_email(message: bytes, year: int):
    from ietf.api.views import EmailIngestionError  # avoid circular import
    from .models import NomCom
    try:
        nomcom = NomCom.objects.get(group__acronym__icontains=str(year),
                                         group__state__slug='active')
    except NomCom.DoesNotExist:
        raise EmailIngestionError(
            f"Error ingesting nomcom email: nomcom {year} does not exist or is not active",
            email_body=dedent(f"""\
                An email for nomcom {year} was posted to ingest_feedback_email, but no
                active nomcom exists for that year.
                """),
        )

    try:
        feedback = create_feedback_email(nomcom, message)
    except Exception as err:
        raise EmailIngestionError(
            f"Error ingesting nomcom {year} feedback email",
            email_recipients=nomcom.chair_emails(),
            email_body=dedent(f"""\
                An error occurred while ingesting feedback email for nomcom {year}.
                
                {{error_summary}}
                """),
            email_original_message=message,
        ) from err
    log("Received nomcom email from %s" % feedback.author)


def _is_time_to_send_reminder(nomcom, send_date, nomination_date):
    if nomcom.reminder_interval:
        days_passed = (send_date - nomination_date).days
        return days_passed > 0 and days_passed % nomcom.reminder_interval == 0
    else:
        return bool(nomcom.reminderdates_set.filter(date=send_date))


def send_reminders():
    from .models import NomCom, NomineePosition
    for nomcom in NomCom.objects.filter(group__state__slug="active"):
        nps = NomineePosition.objects.filter(
            nominee__nomcom=nomcom, nominee__duplicated__isnull=True
        )
        for nominee_position in nps.pending():
            if _is_time_to_send_reminder(nomcom, date_today(), nominee_position.time.date()):
                send_accept_reminder_to_nominee(nominee_position)
                log(f"Sent accept reminder to {nominee_position.nominee.email.address}")
        for nominee_position in nps.accepted().without_questionnaire_response():
            if _is_time_to_send_reminder(nomcom, date_today(), nominee_position.time.date()):
                send_questionnaire_reminder_to_nominee(nominee_position)
                log(f"Sent questionnaire reminder to {nominee_position.nominee.email.address}")
