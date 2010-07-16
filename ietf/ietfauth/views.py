# Portions Copyright (C) 2009 Nokia Corporation and/or its subsidiary(-ies).
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

# Copyright The IETF Trust 2007, All Rights Reserved

from django.template import RequestContext
from django.shortcuts import render_to_response
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect, HttpResponse
from django.contrib.auth import REDIRECT_FIELD_NAME, authenticate, login
from django.contrib.auth.models import User
from django.conf import settings
from django.utils.http import urlquote

def url_login(request, user, passwd):
    user = authenticate(username=user, password=passwd)
    redirect_to = request.REQUEST.get(REDIRECT_FIELD_NAME, '')
    if user is not None:
        if user.is_active:
            login(request, user)
            return HttpResponseRedirect('/accounts/loggedin/?%s=%s' % (REDIRECT_FIELD_NAME, urlquote(redirect_to)))
    return HttpResponse("Not authenticated?", status=500)        

def ietf_login(request):
    if not request.user.is_authenticated():
        # This probably means an exception occured inside IetfUserBackend
        return HttpResponse("Not authenticated?", status=500)
    redirect_to = request.REQUEST.get(REDIRECT_FIELD_NAME, '')
    request.session.set_test_cookie()
    return HttpResponseRedirect('/accounts/loggedin/?%s=%s' % (REDIRECT_FIELD_NAME, urlquote(redirect_to)))

def ietf_loggedin(request):
    if not request.session.test_cookie_worked():
        return HttpResponse("You need to enable cookies")
    request.session.delete_test_cookie()
    redirect_to = request.REQUEST.get(REDIRECT_FIELD_NAME, '')
    if not redirect_to or '//' in redirect_to or ' ' in redirect_to:
        redirect_to = settings.LOGIN_REDIRECT_URL
    return HttpResponseRedirect(redirect_to)
    
@login_required
def profile(request):
    return render_to_response('registration/profile.html', context_instance=RequestContext(request))
