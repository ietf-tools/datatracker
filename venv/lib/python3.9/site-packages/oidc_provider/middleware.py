try:
    # https://docs.djangoproject.com/en/1.10/topics/http/middleware/#upgrading-pre-django-1-10-style-middleware
    from django.utils.deprecation import MiddlewareMixin
except ImportError:
    MiddlewareMixin = object

from oidc_provider import settings
from oidc_provider.lib.utils.common import get_browser_state_or_default


class SessionManagementMiddleware(MiddlewareMixin):
    """
    Maintain a `op_browser_state` cookie along with the `sessionid` cookie that
    represents the End-User's login state at the OP. If the user is not logged
    in then use the value of settings.OIDC_UNAUTHENTICATED_SESSION_MANAGEMENT_KEY.
    """

    def process_response(self, request, response):
        if settings.get('OIDC_SESSION_MANAGEMENT_ENABLE'):
            response.set_cookie('op_browser_state', get_browser_state_or_default(request))
        return response
