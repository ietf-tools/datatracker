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
from ietf.utils.test_utils import RealDatabaseTest
from ietf.utils.test_utils import SimpleUrlTestCase

class MailingListsUrlTestCase(SimpleUrlTestCase):
    def testUrls(self):
        self.doTestUrls(__file__)

class NonWgWizardAddTest(unittest.TestCase):
    def testAddStep1(self):
        print "Testing /list/nonwg/update/ add step 1"
        c = Client()
        response = c.post('/list/nonwg/update/', {'0-add_edit':'add'})
        self.assertEquals(response.status_code, 200)
        self.assert_('input type="hidden" name="hash_0"' in response.content)
        self.assert_("Step 2" in response.content)
        self.assert_("List URL:" in response.content)

class NonWgWizardDeleteTest(unittest.TestCase, RealDatabaseTest):
    def setUp(self):
        self.setUpRealDatabase()
    def tearDown(self):
        self.tearDownRealDatabase()

    def testDeleteStep1(self):
        print "Testing /list/nonwg/update/ delete step 1"

        # First, get one valid list_id
        c = Client()
        response = c.get('/list/nonwg/update/')
        self.assertEquals(response.status_code, 200)
        p = re.compile(r'option value="(.+)">secdir', re.IGNORECASE)
        m = p.search(response.content)
        self.assert_(m != None)
        list_id = m.group(1)
        #print "Using list_id "+list_id

        # Then attempt deleting it
        response = c.post('/list/nonwg/update/', {'0-add_edit':'delete', '0-list_id_delete':list_id})
        self.assertEquals(response.status_code, 200)
        self.assert_('input type="hidden" name="hash_0"' in response.content)
        self.assert_('Message to the Area Director' in response.content)

class ListReqWizardAddTest(unittest.TestCase):
    def testAddStep1(self):
        print "Testing /list/request/ add step 1"
        c = Client()
        response = c.post('/list/request/', {'0-mail_type':'newnon','0-domain_name':'ietf.org'})
        self.assertEquals(response.status_code, 200)
        self.assert_('input type="hidden" name="hash_0"' in response.content)
        self.assert_("Step 2" in response.content)
        self.assert_("Short description" in response.content)
