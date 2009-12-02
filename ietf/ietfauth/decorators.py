# Portion Copyright (C) 2009 Nokia Corporation and/or its subsidiary(-ies).
# All rights reserved. Contact: Pasi Eronen <pasi.eronen@nokia.com>
# 
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions 
# are met:
# 
#  * Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 
#  * Redistributions in binary form must reproduce the above
#    copyright notice, this list of conditions and the following
#    disclaimer in the documentation and/or other materials provided
#    with the distribution.
# 
#  * Neither the name of the Nokia Corporation and/or its
#    subsidiary(-ies) nor the names of its contributors may be used
#    to endorse or promote products derived from this software
#    without specific prior written permission.
# 
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

from django.utils.http import urlquote
from django.contrib.auth.decorators import _CheckLogin
from django.http import HttpResponseRedirect, HttpResponseForbidden

# based on http://www.djangosnippets.org/snippets/254/
class _CheckLogin403(_CheckLogin):
    def __init__(self, view_func, test_func, forbidden_message=None):
        self.forbidden_message = forbidden_message
        super(_CheckLogin403, self).__init__(view_func, test_func)

    def __call__(self, request, *args, **kwargs):
        if not request.user.is_authenticated():
            path = urlquote(request.get_full_path())
            tup = self.login_url, self.redirect_field_name, path
            return HttpResponseRedirect('%s?%s=%s' % tup)
        elif self.test_func(request.user):
            return self.view_func(request, *args, **kwargs)
        else:
            return HttpResponseForbidden(self.forbidden_message)

# based on http://www.djangosnippets.org/snippets/1703/
def group_required(*group_names):
    """
    Decorator for views that checks that the user is logged in,
    and belongs to (at least) one of the listed groups. Users who
    are not logged in are redirected to the login page; users
    who don't belong to any of the groups (but are logged in) 
    get a "403" page.
    """
    def decorate(view_func):
        return _CheckLogin403(view_func, lambda u: bool(u.groups.filter(name__in=group_names)), "Restricted to group(s) "+",".join(group_names))
    return decorate
