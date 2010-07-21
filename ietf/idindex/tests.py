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
import re
from django.test.client import Client
from ietf.utils.test_utils import SimpleUrlTestCase, RealDatabaseTest

class IdIndexUrlTestCase(SimpleUrlTestCase):
    def testUrls(self):
        self.doTestUrls(__file__)

class IndexTestCase(unittest.TestCase, RealDatabaseTest):
    def setUp(self):
        self.setUpRealDatabase()
    def tearDown(self):
        self.tearDownRealDatabase()

    def testAllId(self):
        print "     Testing all_id.txt generation"
        c = Client()
        response = c.get('/drafts/_test/all_id.txt')
        self.assertEquals(response.status_code, 200)
        content = response.content
        # Test that correct version number is shown for couple of old drafts
        self.assert_(content.find("draft-ietf-tls-psk-09") >= 0)
        self.assert_(content.find("draft-eronen-eap-sim-aka-80211-00") >= 0)
        # Since all_id.txt contains all old drafts, it should never shrink
        lines = content.split("\n")
        self.assert_(len(lines) > 18000)
        # Test that the lines look OK and have correct number of tabs
        r = re.compile(r'^(draft-\S*-\d\d)\t(\d\d\d\d-\d\d-\d\d)\t([^\t]+)\t([^\t]*)$')
        for line in lines:
            if ((line == "") or 
                (line == "Internet-Drafts Status Summary") or
                (line == "Web version is available at") or 
                (line == "https://datatracker.ietf.org/public/idindex.cgi")):
                pass
            elif r.match(line):
                pass
            else:
                self.fail("Unexpected line \""+line+"\"")
        print "OK   (all_id.txt)"
