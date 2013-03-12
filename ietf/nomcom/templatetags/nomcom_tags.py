import os
import tempfile

from django import template
from django.conf import settings

from ietf.utils.pipe import pipe
from ietf.ietfauth.decorators import has_role

from ietf.nomcom.models import Feedback
from ietf.nomcom.utils import get_nomcom_by_year, get_user_email


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
    count = Feedback.objects.filter(position=position,
                                    nominee=nominee,
                                    author=author,
                                    type='comment').count()
    if count:
        mark = """<span style="white-space: pre; color: red;">*</span>"""
    else:
        mark = """<span style="white-space: pre;"> </span> """

    return '<span title="%d earlier comments from you on %s as %s">%s</span>&nbsp;' % (count, nominee, position, mark)


@register.filter
def decrypt(string, key=None):
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

    return out
