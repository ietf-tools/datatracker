# Copyright The IETF Trust 2009-2020, All Rights Reserved
# -*- coding: utf-8 -*-
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


from ietf.utils.test_utils import split_url, TestCase

import debug                            # pyflakes:ignore

REDIRECT_TESTS = {

    # announcements

    '/public/show_nomcom_message.cgi?id=1799':
        '/ann/nomcom/1799/',

    # idindex/idtracker
    
    '/public/pidtracker.cgi?command=view_id&dTag=11171&rfc_flag=0':
        ('/idtracker/11171/', ),
    '/public/idindex.cgi?command=do_search_id&filename=draft-mills-sntp-v4-00.txt':
        ('/drafts/?filename=draft-mills-sntp-v4-00.txt', ),
    '/public/idindex.cgi?command=do_search_id&filename=draft-ietf-isis-interoperable&search_button=SEARCH':
        ('/drafts/?filename=draft-ietf-isis-interoperable&search_button=SEARCH',
         '/drafts/?search_button=SEARCH&filename=draft-ietf-isis-interoperable'),
    '/public/idindex.cgi?command=do_search_id&filename=rfc0038.txt':
        ('/drafts/?filename=rfc0038.txt', ),
    '/public/idindex.cgi?command=id_detail&id=7096':
        ('/drafts/7096/', ),
    '/public/idindex.cgi?command=view_related_docs&id=10845':
        ('/drafts/10845/related/', ),
    '/public/idindex.cgi?command=id_detail&filename=draft-l3vpn-as4octet-ext-community':
        ('/drafts/draft-l3vpn-as4octet-ext-community/', ),
    # non-ASCII parameter
    '/public/pidtracker.cgi?command=view_id&dTag=11171%D182&rfc_flag=0':
        ('/idtracker/', ),
    '/idtracker/': ('/doc/', ),

    # ipr

    '/public/ipr_disclosure.cgi':
        ('/ipr/about/', ), 
    '/public/ipr_detail_show.cgi?ipr_id=693':
        ('/ipr/693/', ), 
    
    # liaisons

    '/public/liaison_detail.cgi?detail_id=340':
        ('/liaison/340/', ),

    # meeting

    '/public/meeting_agenda_html.cgi?meeting_num=72':
        ('/meeting/72/agenda.html', ),
    '/public/meeting_materials.cgi?meeting_num=76':
        ('/meeting/76/materials.html', ),

    # RedirectTrailingPeriod middleware
    '/sitemap.xml.':
        ('/sitemap.xml', ),

    }

class RedirectsTests(TestCase):
    fixtures = ["initial_data.xml", ]

    def test_redirects(self):
        for src, dst in REDIRECT_TESTS.items():
            baseurl, args = split_url(src)
            response = self.client.get(baseurl, args)
            self.assertTrue(str(response.status_code).startswith("3"))
            location = response['Location']
            if location.startswith("http://testserver/"):
                location = location[17:]
            self.assertIn(location, dst, (src, dst, location))

class MainUrlTests(TestCase):
    def test_urls(self):
        self.assertEqual(self.client.get("/_doesnotexist/").status_code, 404)
        self.assertEqual(self.client.get("/sitemap.xml").status_code, 200)
         # Google webmaster tool verification page
        self.assertEqual(self.client.get("/googlea30ad1dacffb5e5b.html").status_code, 200)
