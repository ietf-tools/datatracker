import os
import tempfile

from django import template
from django.conf import settings
from django.template.defaultfilters import linebreaksbr

from ietf.utils.pipe import pipe
from ietf.ietfauth.decorators import has_role

from ietf.person.models import Person
from ietf.nomcom.models import Feedback
from ietf.nomcom.utils import get_nomcom_by_year, get_user_email, retrieve_nomcom_private_key


register = template.Library()


@register.filter
def is_chair(user, year):
    if not user or not year:
        return False
    nomcom = get_nomcom_by_year(year=year)
    if has_role(user, "Secretariat"):
        return True
    return nomcom.group.is_chair(user)


@register.simple_tag
def add_num_nominations(user, position, nominee):
    author = get_user_email(user)

    count = Feedback.objects.filter(positions__in=[position],
                                    nominees__in=[nominee],
                                    author=author,
                                    type='comment').count()
    if count:
        mark = """<span style="white-space: pre; color: red;">*</span>"""
    else:
        mark = """<span style="white-space: pre;"> </span> """

    return '<span title="%d earlier comments from you on %s as %s">%s</span>&nbsp;' % (count, nominee, position, mark)


@register.filter
def get_person(email):
    person = email
    if email:
        persons = Person.objects.filter(email__address__in=[email])
        person = persons and persons[0].name or person
    return person


@register.simple_tag
def decrypt(string, request, year):
    key = retrieve_nomcom_private_key(request, year)

    if not key:
        return '<-Encripted text [No private key provided]->'

    encrypted_file = tempfile.NamedTemporaryFile(delete=False)
    encrypted_file.write(string)
    encrypted_file.close()

    command = "%s smime -decrypt -in %s -inkey /dev/stdin"
    code, out, error = pipe(command % (settings.OPENSSL_COMMAND,
                            encrypted_file.name), key)

    os.unlink(encrypted_file.name)

    if error:
        return '<-Encripted text [Your private key is invalid]->'

    return linebreaksbr(out)
