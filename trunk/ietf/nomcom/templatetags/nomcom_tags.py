import os
import tempfile

from django import template
from django.conf import settings
from django.template.defaultfilters import linebreaksbr, force_escape
from django.utils.safestring import mark_safe

import debug           # pyflakes:ignore

from ietf.utils.text import wordwrap
from ietf.nomcom.utils import get_nomcom_by_year, retrieve_nomcom_private_key
from ietf.person.models import Person
from ietf.utils.log import log
from ietf.utils.mail import formataddr
from ietf.utils.pipe import pipe


register = template.Library()


@register.filter
def is_chair_or_advisor(user, year):
    if not user or not year:
        return False
    nomcom = get_nomcom_by_year(year=year)
    return nomcom.group.has_role(user, ["chair","advisor"])


@register.filter
def has_publickey(nomcom):
    return nomcom and nomcom.public_key and True or False

@register.filter
def lookup(container,key):
    return container and container.get(key,None)

@register.filter
def formatted_email(address):
    person = None
    if address:
        persons = Person.objects.filter(email__address__in=[address])
        person = persons and persons[0] or None
    if person and person.name:
        return formataddr((person.plain_name(), address))
    else:
        return address


@register.simple_tag
def decrypt(string, request, year, plain=False):
    key = retrieve_nomcom_private_key(request, year)

    if not key:
        return '-*- Encrypted text [No private key provided] -*-'

    encrypted_file = tempfile.NamedTemporaryFile(delete=False)
    encrypted_file.write(string)
    encrypted_file.close()

    command = "%s smime -decrypt -in %s -inkey /dev/stdin"
    code, out, error = pipe(command % (settings.OPENSSL_COMMAND,
                            encrypted_file.name), key)
    if code != 0:
        log("openssl error: %s:\n  Error %s: %s" %(command, code, error))

    os.unlink(encrypted_file.name)

    if error:
        return '-*- Encrypted text [Your private key is invalid] -*-'

    if not plain:
        return force_escape(linebreaksbr(out))
    return mark_safe(wordwrap(force_escape(out)))
