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

import os
import unittest
from django.test.client import Client
from django.conf import settings
from ietf.utils.test_utils import SimpleUrlTestCase, RealDatabaseTest, canonicalize_feed, canonicalize_sitemap
from ietf.utils.mail import outbox, empty_outbox

class IprUrlTestCase(SimpleUrlTestCase):
    def testUrls(self):
        self.doTestUrls(__file__)
    def doCanonicalize(self, url, content):
        if url.startswith("/feed/"):
            return canonicalize_feed(content)
        elif url == "/sitemap-ipr.xml":
            return canonicalize_sitemap(content)
        else:
            return content

# this test should be ported to run on a test database instead of the
# real database, and possibly expanded
class NewIprTestCase(unittest.TestCase,RealDatabaseTest):
    SPECIFIC_DISCLOSURE = {
        'legal_name':'Testing Only Please Ignore',
        'hold_name':'Test Holder',
        'hold_telephone':'555-555-0100',
        'hold_email':'test.holder@example.com',
        'ietf_name':'Test Participant',
        'ietf_telephone':'555-555-0101',
        'ietf_email':'test.participant@example.com',
        'rfclist':'1149',
        'draftlist':'draft-burdis-http-sasl-00',
        'patents':'none',
        'date_applied':'never',
        'country':'nowhere',
        'licensing_option':'5',
        'subm_name':'Test Submitter',
        'subm_telephone':'555-555-0102',
        'subm_email':'test.submitter@example.com'
        }

    def setUp(self):
        self.setUpRealDatabase()
    def tearDown(self):
        self.tearDownRealDatabase()

    def testNewSpecific(self):
        print "     Testing IPR disclosure submission"
        empty_outbox()
        c = Client()
        response = c.post('/ipr/new-specific/', self.SPECIFIC_DISCLOSURE)
        self.assertEquals(response.status_code, 200)
        self.assert_("Your IPR disclosure has been submitted" in response.content)
        self.assertEquals(len(outbox), 1)
        print "OK   (1 email found in test outbox)"
        
    
class IprFileTestCase(unittest.TestCase):
    def testFileExistence(self):
        print "     Testing if IPR disclosure files exist locally"
        fpath = os.path.join(settings.IPR_DOCUMENT_PATH, "juniper-ipr-RFC-4875.txt")
        if not os.path.exists(fpath):
            print "\nERROR: IPR disclosure files not found in "+settings.IPR_DOCUMENT_PATH
            print "They are needed for testing IPR searching."
            print "Download them to a local directory with:"
            print "wget -nd -nc -np -r ftp://ftp.ietf.org/ietf/IPR/"
            print "And set IPR_DOCUMENT_PATH in settings_local.py\n"
        else:
            print "OK   (they seem to exist)"
    
