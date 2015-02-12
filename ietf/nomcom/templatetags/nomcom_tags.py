import os
import tempfile

from django import template
from django.conf import settings
from django.template.defaultfilters import linebreaksbr, force_escape

from ietf.utils.pipe import pipe
from ietf.utils.log import log
from ietf.ietfauth.utils import has_role
from ietf.doc.templatetags.ietf_filters import wrap_text

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
    return nomcom.group.has_role(user, "chair")


@register.filter
def has_publickey(nomcom):
    return nomcom and nomcom.public_key and True or False


@register.simple_tag
def add_num_nominations(user, position, nominee):
    author = get_user_email(user)

    count = Feedback.objects.filter(positions__in=[position],
                                    nominees__in=[nominee],
                                    author=author,
                                    type='comment').count()

    return '<span class="badge" title="%d earlier comments from you on %s as %s">%s</span>&nbsp;' % (count, nominee.email.address, position, count)


@register.filter
def formatted_email(address):
    person = None
    if address:
        persons = Person.objects.filter(email__address__in=[address])
        person = persons and persons[0] or None
    if person and person.name:
        return u'"%s" <%s>' % (person.plain_name(), address)
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
    return wrap_text(force_escape(out))
