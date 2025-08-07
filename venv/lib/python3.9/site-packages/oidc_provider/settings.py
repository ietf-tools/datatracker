import importlib
import random
import string

from django.conf import settings


class DefaultSettings(object):
    required_attrs = ()

    def __init__(self):
        self._unauthenticated_session_management_key = None

    @property
    def OIDC_LOGIN_URL(self):
        """
        OPTIONAL. Used to log the user in. By default Django's LOGIN_URL will be used.
        """
        return settings.LOGIN_URL

    @property
    def SITE_URL(self):
        """
        OPTIONAL. The OP server url.
        """
        return None

    @property
    def OIDC_AFTER_USERLOGIN_HOOK(self):
        """
        OPTIONAL.  Provide a way to plug into the process after
        the user has logged in, typically to perform some business logic.
        """
        return 'oidc_provider.lib.utils.common.default_after_userlogin_hook'

    @property
    def OIDC_AFTER_END_SESSION_HOOK(self):
        """
        OPTIONAL.  Provide a way to plug into the end session process just before calling
         Django's logout function, typically to perform some business logic.
        """
        return 'oidc_provider.lib.utils.common.default_after_end_session_hook'

    @property
    def OIDC_CODE_EXPIRE(self):
        """
        OPTIONAL. Code expiration time expressed in seconds.
        """
        return 60*10

    @property
    def OIDC_DISCOVERY_CACHE_ENABLE(self):
        """
        OPTIONAL. Enable caching the response on the discovery endpoint.
        """
        return False

    @property
    def OIDC_DISCOVERY_CACHE_EXPIRE(self):
        """
        OPTIONAL. Discovery endpoint cache expiration time expressed in seconds.
        """
        return 60*60*24

    @property
    def OIDC_EXTRA_SCOPE_CLAIMS(self):
        """
        OPTIONAL. A string with the location of your class.
        Used to add extra scopes specific for your app.
        """
        return None

    @property
    def OIDC_IDTOKEN_EXPIRE(self):
        """
        OPTIONAL. Id token expiration time expressed in seconds.
        """
        return 60*10

    @property
    def OIDC_IDTOKEN_SUB_GENERATOR(self):
        """
        OPTIONAL. Subject Identifier. A locally unique and never
        reassigned identifier within the Issuer for the End-User,
        which is intended to be consumed by the Client.
        """
        return 'oidc_provider.lib.utils.common.default_sub_generator'

    @property
    def OIDC_IDTOKEN_INCLUDE_CLAIMS(self):
        """
        OPTIONAL. If enabled, id_token will include standard claims of the user.
        """
        return False

    @property
    def OIDC_SESSION_MANAGEMENT_ENABLE(self):
        """
        OPTIONAL. If enabled, the Server will support Session Management 1.0 specification.
        """
        return False

    @property
    def OIDC_UNAUTHENTICATED_SESSION_MANAGEMENT_KEY(self):
        """
        OPTIONAL. Supply a fixed string to use as browser-state key for unauthenticated clients.
        """

        # Memoize generated value
        if not self._unauthenticated_session_management_key:
            self._unauthenticated_session_management_key = ''.join(
                random.choice(string.ascii_uppercase + string.digits) for _ in range(100))
        return self._unauthenticated_session_management_key

    @property
    def OIDC_SKIP_CONSENT_EXPIRE(self):
        """
        OPTIONAL. User consent expiration after been granted.
        """
        return 30*3

    @property
    def OIDC_TOKEN_EXPIRE(self):
        """
        OPTIONAL. Token object expiration after been created.
        Expressed in seconds.
        """
        return 60*60

    @property
    def OIDC_USERINFO(self):
        """
        OPTIONAL. A string with the location of your function.
        Used to populate standard claims with your user information.
        """
        return 'oidc_provider.lib.utils.common.default_userinfo'

    @property
    def OIDC_IDTOKEN_PROCESSING_HOOK(self):
        """
        OPTIONAL. A string with the location of your hook.
        Used to add extra dictionary values specific for your app into id_token.
        """
        return 'oidc_provider.lib.utils.common.default_idtoken_processing_hook'

    @property
    def OIDC_INTROSPECTION_PROCESSING_HOOK(self):
        """
        OPTIONAL. A string with the location of your function.
        Used to update the response for a valid introspection token request.
        """
        return 'oidc_provider.lib.utils.common.default_introspection_processing_hook'

    @property
    def OIDC_INTROSPECTION_VALIDATE_AUDIENCE_SCOPE(self):
        """
        OPTIONAL: A boolean to specify whether or not to verify that the introspection
        resource has the requesting client id as one of its scopes.
        """
        return True

    @property
    def OIDC_GRANT_TYPE_PASSWORD_ENABLE(self):
        """
        OPTIONAL. A boolean to set whether to allow the Resource Owner Password
        Credentials Grant. https://tools.ietf.org/html/rfc6749#section-4.3

        From the specification:
            Since this access token request utilizes the resource owner's
            password, the authorization server MUST protect the endpoint
            against brute force attacks (e.g., using rate-limitation or
            generating alerts).

        How you do this, is up to you.
        """
        return False

    @property
    def OIDC_TEMPLATES(self):
        return {
            'authorize': 'oidc_provider/authorize.html',
            'error': 'oidc_provider/error.html'
        }

    @property
    def OIDC_INTROSPECTION_RESPONSE_SCOPE_ENABLE(self):
        """
        OPTIONAL: A boolean to specify whether or not to include scope in introspection response.
        """
        return False


default_settings = DefaultSettings()


def import_from_str(value):
    """
    Attempt to import a class from a string representation.
    """
    try:
        parts = value.split('.')
        module_path, class_name = '.'.join(parts[:-1]), parts[-1]
        module = importlib.import_module(module_path)
        return getattr(module, class_name)
    except ImportError as e:
        msg = 'Could not import %s for settings. %s: %s.' % (value, e.__class__.__name__, e)
        raise ImportError(msg)


def get(name, import_str=False):
    """
    Helper function to use inside the package.
    """
    value = None
    default_value = getattr(default_settings, name)

    try:
        value = getattr(settings, name)
    except AttributeError:
        if name in default_settings.required_attrs:
            raise Exception('You must set ' + name + ' in your settings.')

    if isinstance(default_value, dict) and value:
        default_value.update(value)
        value = default_value
    else:
        if value is None:
            value = default_value
        value = import_from_str(value) if import_str else value

    return value
