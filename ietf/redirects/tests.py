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

import unittest, os, re
import django
from django.test.client import Client
from django.conf import settings
from ietf.utils.test_utils import SimpleUrlTestCase, RealDatabaseTest, split_url, read_testurls
import ietf.urls
import ietf.utils.test_runner as test_runner

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

    # RedirectTrailingPeriod middleware
    '/sitemap.xml.':
        '/sitemap.xml'

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

def get_patterns(module):
    all = []
    try:
        patterns = module.urlpatterns
    except AttributeError:
        patterns = []
    for item in patterns:
        try:
            subpatterns = get_patterns(item.urlconf_module)
        except:
            subpatterns = [""]
        for sub in subpatterns:
            if not sub:
                all.append(item.regex.pattern)
            elif sub.startswith("^"):
                all.append(item.regex.pattern + sub[1:])
            else:
                all.append(item.regex.pattern + ".*" + sub)
    return all

class UrlCoverageTestCase(unittest.TestCase):
    def testUrlCoverage(self):
        print "Testing testurl.list coverage"
        testtuples = []
        for root, dirs, files in os.walk(settings.BASE_DIR):
            if "testurl.list" in files:
                testtuples += read_testurls(root+"/testurl.list")

        patterns = get_patterns(ietf.urls)
        covered = []
        for codes, testurl, goodurl in testtuples:
            for pattern in patterns:
                if re.match(pattern, testurl[1:]):
                    covered.append(pattern)

        if not set(patterns) == set(covered):
            missing = list(set(patterns) - set(covered))
            print "The following URLs are not tested by any testurl.list"
            for pattern in missing:
                if not pattern[1:].split("/")[0] in [ "admin", "accounts" ]:
                    print "NoTest", pattern
            print ""
        else:
            print "All URLs are included in some testurl.list"

class MainUrlTestCase(SimpleUrlTestCase):
    def testUrls(self):
        self.doTestUrls(__file__)

def get_templates():
    templates = set()
    for root, dirs, files in os.walk(os.path.join(settings.BASE_DIR,"templates")):
        if ".svn" in dirs:
            dirs.remove(".svn")
        last_dir = os.path.split(root)[1]
        for file in files:
            if file.endswith("~") or file.startswith("#"):
                continue
            if last_dir == "templates":
                templates.add(file)
            else:
                templates.add(os.path.join(last_dir, file))
    return templates

class TemplateCoverageTestCase(unittest.TestCase):
    def testTemplateCoverage(self):
        if not test_runner.loaded_templates:
            print "Skipping template coverage test"
            return

        print "Testing template coverage"
        all_templates = get_templates()

        #notexist = list(test_runner.loaded_templates - all_templates)
        #if notexist:
        #    notexist.sort()
        #    print "The following templates do not exist"
        #    for x in notexist:
        #        print "NotExist", x
            
        notloaded = list(all_templates - test_runner.loaded_templates)
        if notloaded:
            notloaded.sort()
            print "The following templates were never loaded during test"
            for x in notloaded:
                print "NotLoaded", x
        else:
            print "All templates were loaded during test"
        
