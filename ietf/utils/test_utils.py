# Copyright The IETF Trust 2007, All Rights Reserved

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

import html5lib
import urllib2
from unittest.util import strclass

import django.test
from django.conf import settings

import debug                            # pyflakes:ignore

real_database_name = settings.DATABASES["default"]["NAME"]

def split_url(url):
    if "?" in url:
        url, args = url.split("?", 1)
        args = dict([ map(urllib2.unquote,arg.split("=", 1)) for arg in args.split("&") if "=" in arg ])
    else:
        args = {}
    return url, args

def login_testing_unauthorized(test_case, username, url, password=None):
    r = test_case.client.get(url)
    test_case.assertIn(r.status_code, (302, 403))
    if r.status_code == 302:
        test_case.assertTrue("/accounts/login" in r['Location'])
    if not password:
        password = username + "+password"
    return test_case.client.login(username=username, password=password)

def unicontent(r):
    "Return a HttpResponse object's content as unicode"
    return r.content.decode(r.charset)

def reload_db_objects(*objects):
    """Rerequest the given arguments from the database so they're refreshed, to be used like

    foo, bar = reload_objects(foo, bar)"""

    t = tuple(o.__class__.objects.get(pk=o.pk) for o in objects)
    if len(objects) == 1:
        return t[0]
    else:
        return t

class ReverseLazyTest(django.test.TestCase):
    def test_redirect_with_lazy_reverse(self):
        response = self.client.get('/ipr/update/')
        self.assertRedirects(response, "/ipr/", status_code=301)

class TestCase(django.test.TestCase):
    """
    Does basically the same as django.test.TestCase, but adds asserts for html5 validation.
    """

    parser = html5lib.HTMLParser(strict=True)

    def assertValidHTML(self, data):
        try:
            self.parser.parse(data)
        except Exception as e:
            raise self.failureException(str(e))

    def assertValidHTMLResponse(self, resp):
        self.assertHttpOK(resp)
        self.assertTrue(resp['Content-Type'].startswith('text/html'))
        self.assertValidHTML(resp.content)

    def __str__(self):
        return "%s (%s.%s)" % (self._testMethodName, strclass(self.__class__),self._testMethodName)
