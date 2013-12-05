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

import unittest
from urlparse import urlsplit

from django.contrib.auth.models import User
from django.test.client import Client

from ietf.utils.test_utils import SimpleUrlTestCase, RealDatabaseTest

class IetfAuthUrlTestCase(SimpleUrlTestCase):
    def testUrls(self):
        self.doTestUrls(__file__)

# this test case should really work on a test database instead of the
# real one
class IetfAuthTestCase(unittest.TestCase,RealDatabaseTest):
    def setUp(self):
        self.setUpRealDatabase()
    def tearDown(self):
        self.tearDownRealDatabase()

    def _doLogin(self, username):
        c = Client()
        response = c.get('/accounts/login/', {}, False, REMOTE_USER=username)
        self.assertEquals(response.status_code, 302)
        nexturl = urlsplit(response['Location'])
        self.assertEquals(nexturl[2], "/accounts/loggedin/")

        response = c.get(nexturl[2], {}, False, REMOTE_USER=username)
        self.assertEquals(response.status_code, 302)
        nexturl = urlsplit(response['Location'])
        self.assertEquals(nexturl[2], "/accounts/profile/")

        response = c.get(nexturl[2], {}, False, REMOTE_USER=username)
        self.assertEquals(response.status_code, 200)
        self.assert_("User name" in response.content)
        return response
