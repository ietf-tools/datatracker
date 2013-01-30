import os
import tempfile

from django import template
from django.conf import settings

from ietf.ietfauth.decorators import has_role
from ietf.nomcom.utils import get_nomcom_by_year
from ietf.utils.pipe import pipe

register = template.Library()


@register.filter
def is_chair(user, year):
    if not user or not year:
        return False
    nomcom = get_nomcom_by_year(year=year)
    if has_role(user, "Secretariat"):
        return True
    return nomcom.group.is_chair(user)


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
