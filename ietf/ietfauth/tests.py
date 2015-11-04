# Copyright (C) 2009 Nokia Corporation and/or its subsidiary(-ies).
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

from urlparse import urlsplit

from django.core.urlresolvers import reverse as urlreverse

from ietf.utils.test_utils import TestCase, login_testing_unauthorized, unicontent
from ietf.utils.test_data import make_test_data

class IetfAuthTests(TestCase):
    def test_index(self):
        self.assertEqual(self.client.get(urlreverse("ietf.ietfauth.views.index")).status_code, 200)

    def test_login(self):
        make_test_data()

        # try logging in without a next
        r = self.client.get('/accounts/login/')
        self.assertEqual(r.status_code, 200)

        r = self.client.post('/accounts/login/', {"username":"plain", "password":"plain+password"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(urlsplit(r["Location"])[2], "/accounts/profile/")

        # try logging out
        r = self.client.get('/accounts/logout/')        
        self.assertEqual(r.status_code, 200)

        r = self.client.get('/accounts/profile/')
        self.assertEqual(r.status_code, 302)
        self.assertEqual(urlsplit(r["Location"])[2], "/accounts/login/")

        # try logging in with a next
        r = self.client.post('/accounts/login/?next=/foobar', {"username":"plain", "password":"plain+password"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(urlsplit(r["Location"])[2], "/foobar")


    def test_profile(self):
        make_test_data()

        url = urlreverse('ietf.ietfauth.views.profile')
        login_testing_unauthorized(self, "plain", url)
        
        # get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertTrue("plain" in unicontent(r))

        # post
        # ... fill in

    # we're missing tests of the other views
