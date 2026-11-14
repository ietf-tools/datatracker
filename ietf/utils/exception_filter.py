# Copyright The IETF Trust 2026, All Rights Reserved
"""Exception report filtering"""

import re

from django.views.debug import SafeExceptionReporterFilter


class AuthorizationAwareReporterFilter(SafeExceptionReporterFilter):
    """SafeExceptionReporterFilter, extended to redact the Authorization header

    Django's own pattern catches HTTP_X_API_KEY through "KEY" but matches nothing in
    HTTP_AUTHORIZATION, so the OIDC provider's client credentials and bearer access
    tokens survive into the traceback that ERROR mails to ADMINS with include_html.
    """

    hidden_settings = re.compile(
        "API|TOKEN|KEY|SECRET|PASS|SIGNATURE|HTTP_COOKIE|AUTHORIZATION", flags=re.IGNORECASE
    )
