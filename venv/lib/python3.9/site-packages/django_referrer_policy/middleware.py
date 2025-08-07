from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


class ReferrerPolicyMiddleware(object):
    """
    A middleware implementing the Referrer-Policy header.

    The value of the header will be read from the REFERRER_POLICY
    setting, which must be present and must be set to one of the
    string values contained in the attribute VALID_REFERRER_POLICIES
    on this class.

    """
    VALID_REFERRER_POLICIES = [
        'no-referrer',
        'no-referrer-when-downgrade',
        'origin',
        'origin-when-cross-origin',
        'same-origin',
        'strict-origin',
        'strict-origin-when-cross-origin',
        'unsafe-url',
    ]

    def __init__(self, get_response):
        self.get_response = get_response
        if not hasattr(settings, 'REFERRER_POLICY') or \
           settings.REFERRER_POLICY not in self.VALID_REFERRER_POLICIES:
            raise ImproperlyConfigured(
                "settings.REFERRER_POLICY is not set or has an illegal value."
            )

    def __call__(self, request):
        response = self.get_response(request)
        response['Referrer-Policy'] = settings.REFERRER_POLICY
        return response
