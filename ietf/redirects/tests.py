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

from django.test.client import Client
import unittest
from ietf.utils.test_utils import SimpleUrlTestCase, RealDatabaseTest, split_url

REDIRECT_TESTS = {

    # announcements

    '/public/show_nomcom_message.cgi?id=1799':
        '/ann/nomcom/1799/',

    # idindex/idtracker
    
    '/':
        '/idtracker/',
    '/public/pidtracker.cgi?command=view_id&dTag=11171&rfc_flag=0':
        '/idtracker/11171/',
    '/public/idindex.cgi?command=do_search_id&filename=draft-mills-sntp-v4-00.txt':
        '/drafts/?filename=draft-mills-sntp-v4-00.txt',
    '/public/idindex.cgi?command=do_search_id&filename=draft-ietf-isis-interoperable&search_button=SEARCH':
        '/drafts/?search_button=SEARCH&filename=draft-ietf-isis-interoperable',
    '/public/idindex.cgi?command=do_search_id&filename=rfc0038.txt':
        '/drafts/?filename=rfc0038.txt',
    '/public/idindex.cgi?command=id_detail&id=7096':
        '/drafts/7096/',
    '/public/idindex.cgi?command=view_related_docs&id=10845':
        '/drafts/10845/related/',
    '/public/idindex.cgi?command=id_detail&filename=draft-l3vpn-as4octet-ext-community':
        '/drafts/draft-l3vpn-as4octet-ext-community/',

    # ipr

    '/public/ipr_disclosure.cgi':
        '/ipr/about/',
    '/public/ipr_detail_show.cgi?ipr_id=693':
        '/ipr/693/',
    
    # liaisons

    '/public/liaison_detail.cgi?detail_id=340':
        '/liaison/340/',

    # meeting

    '/public/meeting_agenda_html.cgi?meeting_num=72':
        '/meeting/72/agenda.html',
    '/public/meeting_materials.cgi?meeting_num=76':
        '/meeting/76/materials.html',

    }

class RedirectsTestCase(unittest.TestCase, RealDatabaseTest):
    def setUp(self):
        self.setUpRealDatabase()
    def tearDown(self):
        self.tearDownRealDatabase()

    def testRedirects(self):
        print "Testing redirects"

        c = Client()
        for src, dst in REDIRECT_TESTS.items():
            baseurl, args = split_url(src)
            try:
                response = c.get(baseurl, args)
                self.assert_(str(response.status_code).startswith("3"))
                location = response['Location']
                if location.startswith("http://testserver/"):
                    location = location[17:]
                self.assertEqual(location, dst)
                print "OK   "+src
            except:
                print "Fail "+src
                raise
