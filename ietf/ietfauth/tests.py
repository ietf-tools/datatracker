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
from django.conf import settings
from django.contrib.auth.models import User
from django.test.client import Client
from ietf.utils.test_utils import SimpleUrlTestCase, RealDatabaseTest
from ietf.idtracker.models import Role
from urlparse import urlsplit

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

    def testLogin(self):
        TEST_USERNAME = '__testuser'
        print "     Testing login with "+TEST_USERNAME

        # Delete test user (if it exists)
        try:
            testuser = User.objects.get(username=TEST_USERNAME)
            testuser.delete()
        except User.DoesNotExist:
            pass

        self._doLogin(TEST_USERNAME)
        
        # Delete test user after test
        testuser = User.objects.get(username=TEST_USERNAME)
        testuser.delete()
        print "OK"

    def testGroups(self):
        print "     Testing group assignment"
        username = Role.objects.get(id=Role.IETF_CHAIR).person.iesglogin_set.all()[0].login_name
        print "     (with username "+str(username)+")"
        
        self._doLogin(username)
        
        user = User.objects.get(username=username)
        groups = [x.name for x in user.groups.all()]
        self.assert_("Area_Director" in groups)
        self.assert_("IETF_Chair" in groups)

        print "OK"

if settings.USE_DB_REDESIGN_PROXY_CLASSES:
    del IetfAuthTestCase.testLogin
    # this test doesn't make any sense anymore
    del IetfAuthTestCase.testGroups
