# Copyright The IETF Trust 2013-2019, All Rights Reserved
import os
import tempfile
import re

from django import template
from django.conf import settings
from django.template.defaultfilters import linebreaksbr, force_escape
from django.utils.encoding import force_text, DjangoUnicodeDecodeError
from django.utils.safestring import mark_safe

import debug           # pyflakes:ignore

from ietf.nomcom.utils import get_nomcom_by_year, retrieve_nomcom_private_key
from ietf.person.models import Person
from ietf.utils.log import log
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
    addrmatch = re.search('<([^>]+)>',address)
    if addrmatch:
        addr = addrmatch.group(1)
    else:
        addr = address
    if addr:
        persons = Person.objects.filter(email__address__in=[addr])
        person = persons and persons[0] or None
    if person and person.name:
        return "%s <%s>" % (person.plain_name(), addr) 
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
    try:
        out = force_text(out)
    except DjangoUnicodeDecodeError:
        pass
    if code != 0:
        log("openssl error: %s:\n  Error %s: %s" %(command, code, error))

    os.unlink(encrypted_file.name)

    if error:
        return '-*- Encrypted text [Your private key is invalid] -*-'

    if not plain:
        return force_escape(linebreaksbr(out))
    return mark_safe(force_escape(out))
