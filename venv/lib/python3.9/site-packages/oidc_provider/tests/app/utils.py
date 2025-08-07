import random
import string

import django
from django.contrib.auth.backends import ModelBackend

try:
    from urlparse import parse_qs, urlsplit
except ImportError:
    from urllib.parse import parse_qs, urlsplit

from django.utils import timezone
from django.contrib.auth.models import User

from oidc_provider.models import (
    Client,
    Code,
    Token,
    ResponseType)


FAKE_NONCE = 'cb584e44c43ed6bd0bc2d9c7e242837d'
FAKE_RANDOM_STRING = ''.join(
    random.choice(string.ascii_uppercase + string.digits) for _ in range(32))
FAKE_CODE_CHALLENGE = 'YlYXEqXuRm-Xgi2BOUiK50JW1KsGTX6F1TDnZSC8VTg'
FAKE_CODE_VERIFIER = 'SmxGa0XueyNh5bDgTcSrqzAh2_FmXEqU8kDT6CuXicw'


def create_fake_user():
    """
    Create a test user.

    Return a User object.
    """
    user = User()
    user.username = 'johndoe'
    user.email = 'johndoe@example.com'
    user.first_name = 'John'
    user.last_name = 'Doe'
    user.set_password('1234')

    user.save()

    return user


def create_fake_client(response_type, is_public=False, require_consent=True):
    """
    Create a test client, response_type argument MUST be:
    'code', 'id_token' or 'id_token token'.

    Return a Client object.
    """
    client = Client()
    client.name = 'Some Client'
    client.client_id = str(random.randint(1, 999999)).zfill(6)
    if is_public:
        client.client_type = 'public'
        client.client_secret = ''
    else:
        client.client_secret = str(random.randint(1, 999999)).zfill(6)
    client.redirect_uris = ['http://example.com/']
    client.require_consent = require_consent
    client.scope = ['openid', 'email']
    client.save()

    # check if response_type is a string in a python 2 and 3 compatible way
    if isinstance(response_type, ("".__class__, u"".__class__)):
        response_type = (response_type,)
    for value in response_type:
        client.response_types.add(ResponseType.objects.get(value=value))

    return client


def create_fake_token(user, scopes, client):
    expires_at = timezone.now() + timezone.timedelta(seconds=60)
    token = Token(user=user, client=client, expires_at=expires_at)
    token.scope = scopes

    token.save()

    return token


def is_code_valid(url, user, client):
    """
    Check if the code inside the url is valid. Supporting both query string and fragment.
    """
    try:
        parsed = urlsplit(url)
        params = parse_qs(parsed.query or parsed.fragment)
        code = params['code'][0]
        code = Code.objects.get(code=code)
        is_code_ok = (code.client == client) and (code.user == user)
    except Exception:
        is_code_ok = False

    return is_code_ok


def userinfo(claims, user):
    """
    Fake function for setting OIDC_USERINFO.
    """
    claims['given_name'] = 'John'
    claims['family_name'] = 'Doe'
    claims['name'] = '{0} {1}'.format(claims['given_name'], claims['family_name'])
    claims['email'] = user.email
    claims['email_verified'] = True
    claims['address']['country'] = 'Argentina'
    return claims


def fake_sub_generator(user):
    """
    Fake function for setting OIDC_IDTOKEN_SUB_GENERATOR.
    """
    return user.email


def fake_idtoken_processing_hook(id_token, user, **kwargs):
    """
    Fake function for inserting some keys into token. Testing OIDC_IDTOKEN_PROCESSING_HOOK.
    """
    id_token['test_idtoken_processing_hook'] = FAKE_RANDOM_STRING
    id_token['test_idtoken_processing_hook_user_email'] = user.email
    return id_token


def fake_idtoken_processing_hook2(id_token, user, **kwargs):
    """
    Fake function for inserting some keys into token.
    Testing OIDC_IDTOKEN_PROCESSING_HOOK - tuple or list as param
    """
    id_token['test_idtoken_processing_hook2'] = FAKE_RANDOM_STRING
    id_token['test_idtoken_processing_hook_user_email2'] = user.email
    return id_token


def fake_idtoken_processing_hook3(id_token, user, token, **kwargs):
    """
    Fake function for checking scope is passed to processing hook.
    """
    id_token['scope_of_token_passed_to_processing_hook'] = token.scope
    return id_token


def fake_idtoken_processing_hook4(id_token, user, **kwargs):
    """
    Fake function for checking kwargs passed to processing hook.
    """
    id_token['kwargs_passed_to_processing_hook'] = {
        key: repr(value)
        for (key, value) in kwargs.items()
    }
    return id_token


def fake_introspection_processing_hook(response_dict, client, id_token):
    response_dict['test_introspection_processing_hook'] = FAKE_RANDOM_STRING
    return response_dict


class TestAuthBackend:
    def authenticate(self, *args, **kwargs):
        if django.VERSION[0] >= 2 or (django.VERSION[0] == 1 and django.VERSION[1] >= 11):
            assert len(args) > 0 and args[0]
        return ModelBackend().authenticate(*args, **kwargs)
