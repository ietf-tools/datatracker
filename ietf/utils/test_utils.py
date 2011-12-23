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

import os
import re
import django
from django.db import connection
from django.test import TestCase
from django.test.client import Client
import ietf.settings
from django.conf import settings
from datetime import datetime
import urllib2 as urllib
from difflib import unified_diff

real_database_name = ietf.settings.DATABASES["default"]["NAME"]

import traceback

class RealDatabaseTest:
    def setUpRealDatabase(self):
        self._original_testdb = self._getDatabaseName()
        newdb = real_database_name
        print "     Switching database from "+self._original_testdb+" to "+newdb
        self._setDatabaseName(newdb)

    def tearDownRealDatabase(self):
        curdb = self._getDatabaseName()
        print "     Switching database from "+curdb+" to "+self._original_testdb
        self._setDatabaseName(self._original_testdb)

    def _getDatabaseName(self):
        return connection.settings_dict['NAME'] 

    def _setDatabaseName(self, name):        
        connection.close()
        django.conf.settings.DATABASES["default"]["NAME"] = name
        connection.settings_dict['NAME'] = name
        connection.cursor()

def read_testurls(filename):
    tuples = []
    file = open(filename)
    for line in file:
        line = line.strip()
        if line and not line.startswith('#'):
            line = line.split("#", 1)[0]
            urlspec = line.split()
            if len(urlspec) == 2:
                codes, testurl = urlspec
                goodurl = None
            elif len(urlspec) == 3:
                codes, testurl, goodurl = urlspec
                # strip protocol and host -- we're making that configurable
                goodurl = re.sub("^https?://[a-z0-9.]+", "", goodurl)
                if not goodurl.startswith("/"):
                    goodurl = "/" + goodurl
            else:
                raise ValueError("Expected 'HTTP_CODE TESTURL [GOODURL]' in %s line, found '%s'." % (filename, line))


            codes = dict([ (item, "") for item in codes.split(",") if not":" in item] +
                         [ (item.split(":")[:2]) for item in codes.split(",") if ":" in item] )
            tuples += [ (codes, testurl, goodurl) ]
    file.close()
    return tuples

def split_url(url):
    if "?" in url:
        url, args = url.split("?", 1)
        args = dict([ map(urllib.unquote,arg.split("=", 1)) for arg in args.split("&") if "=" in arg ])
    else:
        args = {}
    return url, args

class SimpleUrlTestCase(TestCase,RealDatabaseTest):

    def setUp(self):
        self.setUpRealDatabase()
        self.client = Client()        
        self.ref_prefix = os.environ.get("IETFDB_REF_PREFIX", "")
        if self.ref_prefix.endswith("/"):
            self.ref_prefix = self.ref_prefix[:-1]
        self.skip_heavy_tests = os.environ.get("IETFDB_SKIP_HEAVY", False)

    def tearDown(self):
        self.tearDownRealDatabase()

    def doTestUrls(self, test_filename):
        if test_filename.endswith(".list"):
            filename = test_filename
        else:
            filename = os.path.dirname(os.path.abspath(test_filename))+"/testurl.list"
        print "     Reading "+filename
        tuples = read_testurls(filename)
        failures = 0
        for tuple in tuples:
            try:
                self.doTestUrl(tuple)
            except:
                failures = failures + 1
        self.assertEqual(failures, 0, "%d URLs failed" % failures)

    def doTestUrl(self, tuple):
        (codes, url, master) = tuple
        baseurl, args = split_url(url)
        failed = False
        #enable this to see query counts
        #settings.DEBUG = True
        try:
            if "heavy" in codes and self.skip_heavy_tests:
                print "     Skipping heavy test %s" % (url,)
                return
            now = datetime.utcnow()
            response = self.client.get(baseurl, args)
            elapsed_dt = datetime.utcnow()-now
            elapsed = elapsed_dt.seconds + elapsed_dt.microseconds/1e6
            code = str(response.status_code)
            queries = len(connection.queries)
            if code in codes:
                print "OK   %s %s" % (code, url)
            else:
                print "Fail %s %s" % (code, url)
                failed = True
            if queries > 0:
                print "    (%.1f s, %d kB, %d queries)" % (elapsed, len(response.content)/1000, queries)
            else:
                print "    (%.1f s, %d kB)" % (elapsed, len(response.content)/1000)
            if code in codes and code == "200":
                self.doDiff(tuple, response)
        except:
            failed = True
            print "Exception for URL '%s'" % url
            traceback.print_exc()
        self.assertEqual(failed, False)
        
    # Override this in subclasses if needed
    def doCanonicalize(self, url, content):
        return content

    def doDiff(self, tuple, response):
        if not self.ref_prefix:
            return
        (codes, url, master) = tuple
        if "skipdiff" in codes:
            return
        refurl = self.ref_prefix+url
        print "    Fetching "+refurl
        refhtml = None
        try:
            mfile = urllib.urlopen(refurl)
            refhtml = mfile.read()
            mfile.close()
        except Exception, e:
            print "    Error retrieving %s: %s" % (refurl, e)
            return
        testhtml = self.doCanonicalize(url, response.content)
        refhtml = self.doCanonicalize(url, refhtml)
        #print "REFERENCE:\n----------------------\n"+refhtml+"\n-------------\n"
        #print "TEST:\n----------------------\n"+testhtml+"\n-------------\n"

        list0 = refhtml.split("\n")
        list1 = testhtml.split("\n")
        diff = "\n".join(unified_diff(list0, list1, refurl, url, "", "", 0, lineterm=""))
        if diff:
            print "    Differences found:"
            print diff
        else:
            print "    No differences found"

def canonicalize_feed(s):
    # Django 0.96 handled time zone different -- ignore it for now
    s = re.sub(r"(<updated>\d\d\d\d-\d\d-\d\dT)\d\d(:\d\d:\d\d)(Z|-08:00)(</updated>)",r"\g<1>00\g<2>Z\g<4>", s)
    # Insert newline before tags to make diff easier to read
    s = re.sub("\n*\s*(<[a-zA-Z])", "\n\g<1>", s)
    return s

def canonicalize_sitemap(s):
    s = re.sub("> <", "><", s)
    # Insert newline before tags to make diff easier to read
    s = re.sub("\n*\s*(<[a-zA-Z])", "\n\g<1>", s)
    return s
        
def login_testing_unauthorized(tc, remote_user, url):
    r = tc.client.get(url)
    tc.assertTrue(r.status_code in (302, 403))
    if r.status_code == 302:
        tc.assertTrue("/accounts/login" in r['Location'])

    tc.client.login(remote_user=remote_user)
    
class ReverseLazyTest(TestCase):
    def test_redirect_with_lazy_reverse(self):
        response = self.client.get('/ipr/update/')
        self.assertRedirects(response, "/ipr/", status_code=301)
