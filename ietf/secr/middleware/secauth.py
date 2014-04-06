import re

from django.conf import settings
from django.contrib.auth.decorators import login_required
from ietf.ietfauth.utils import has_role, role_required



class SecAuthMiddleware(object):
    """
    Middleware component that performs custom auth check for secretariat
    apps.  request except those excluded by SECR_AUTH_UNRESTRICTED_URLS.

    To use, add the class to MIDDLEWARE_CLASSES and define
    SECR_AUTH_UNRESTRICTED_URLS in your settings.py.

    The following example allows access to anything under "/interim/"
    to non-secretariat users:

    SECR_AUTH_UNRESTRICTED_URLS = (
        (r'^/interim/'),

    Also sets custom request attributes:
    user_is_secretariat
    """
 
    def __init__(self):
        self.unrestricted = [re.compile(pattern) for pattern in
            settings.SECR_AUTH_UNRESTRICTED_URLS]

    def is_unrestricted_url(self,path):
        for pattern in self.unrestricted:
            if pattern.match(path):
                return True
        return False
        
    def process_view(self, request, view_func, view_args, view_kwargs):
        if request.path.startswith('/secr/'):
            # set custom request attribute
            if has_role(request.user, 'Secretariat'):
                request.user_is_secretariat = True
            else:
                request.user_is_secretariat = False

            if request.path.startswith('/secr/announcement/'):
                return login_required(view_func)(request,*view_args,**view_kwargs)
            elif self.is_unrestricted_url(request.path):
                return role_required('WG Chair','Secretariat')(view_func)(request,*view_args,**view_kwargs)
            else:
                return role_required('Secretariat')(view_func)(request,*view_args,**view_kwargs)
        else:
            return None
        
