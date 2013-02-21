from django.conf import settings
from django.http import HttpResponseForbidden
from django.shortcuts import render_to_response

from ietf.ietfauth.decorators import has_role
            
import re

class SecAuthMiddleware(object):
    """
    Middleware component that performs custom auth check for every
    request except those excluded by SECR_AUTH_UNRESTRICTED_URLS.

    Since authentication is performed externally at the apache level
    REMOTE_USER should contain the name of the authenticated
    user.  If the user is a secretariat than access is granted.  
    Otherwise return a 401 error page.

    To use, add the class to MIDDLEWARE_CLASSES and define
    SECR_AUTH_UNRESTRICTED_URLS in your settings.py.

    The following example allows access to anything under "/interim/"
    to non-secretariat users:

    SECR_AUTH_UNRESTRICTED_URLS = (
        (r'^/interim/'),

    Also sets custom request attributes:
    user_is_secretariat
    user_is_chair
    user_is_ad
    )

    """
 
    def __init__(self):
        self.unrestricted = [re.compile(pattern) for pattern in
            settings.SECR_AUTH_UNRESTRICTED_URLS]

    def process_view(self, request, view_func, view_args, view_kwargs):
        # need to initialize user, it doesn't get set when running tests for example

        if request.path.startswith('/secr/'):
            user = ''
            request.user_is_secretariat = False
            
            if request.user.is_anonymous(): 
                return render_to_response('401.html', {'user':user})
            
            if 'REMOTE_USER' in request.META:
                # do custom auth
                if has_role(request.user,'Secretariat'):
                    request.user_is_secretariat = True
                    
            return None

        return None
        
