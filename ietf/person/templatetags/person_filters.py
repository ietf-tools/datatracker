# Copyright The IETF Trust 2017-2020, All Rights Reserved

import datetime

from django import template

import debug                            # pyflakes:ignore

from ietf.nomcom.utils import is_eligible 
from ietf.person.models import Alias

register = template.Library()

@register.filter
def is_nomcom_eligible(person, date=datetime.date.today()):
    return is_eligible(person=person,date=date)

@register.filter
def person_by_name(name):
    "Look up a person record from name"
    if not isinstance(name, (type(b''), type(u''))):
        return None
    alias = Alias.objects.filter(name=name).first()
    return alias.person if alias else None

# CLEANUP: There are several hundred Person objects with no Alias object,
# violating the expectiations of the code. The check for the existance of an
# alias object below matching the person's name avoids presenting a link that
# we know will 404. When the database is corrected and we can expect that the
# Alias for the person's name to always be there, we can remove this extra
# database query (or leave it as a safeguard until it becomes a performance
# issue.)
 
@register.inclusion_tag('person/person_link.html')
def person_link(person, **kwargs):
    title = kwargs.get('title', '')
    cls = kwargs.get('class', '')
    name = person.name if person.alias_set.filter(name=person.name).exists() else ''
    plain_name = person.plain_name()
    email = person.email_address()
    return {'name': name, 'plain_name': plain_name, 'email': email, 'title': title, 'class': cls}


@register.inclusion_tag('person/person_link.html')
def email_person_link(email, **kwargs):
    title = kwargs.get('title', '')
    cls = kwargs.get('class', '')
    name = email.person.name if email.person.alias_set.filter(name=email.person.name).exists() else ''
    plain_name = email.person.plain_name()
    email = email.address
    return {'name': name, 'plain_name': plain_name, 'email': email, 'title': title, 'class': cls}
