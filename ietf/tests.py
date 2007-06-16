import os
import re
import traceback
import urllib2 as urllib

from ietf.utils import soup2text as html2text
from difflib import unified_diff

import django.test.simple
from django.test import TestCase
from django.conf import settings
from django.db import connection
from django.core import management
import ietf.urls


startup_database = settings.DATABASE_NAME  # The startup database name, before changing to test_...

def run_tests(module_list, verbosity=1, extra_tests=[]):
    module_list.append(ietf.urls)
    # If we append 'ietf.tests', we get it twice, first as itself, then
    # during the search for a 'tests' module ...
    return django.test.simple.run_tests(module_list, verbosity, extra_tests)

def reduce(html, pre=False, fill=True):
    if html.count("<li>") > 5*html.count("</li>"):
        html = html.replace("<li>", "</li><li>")
    html = re.sub(r"(?i)(RFC) (\d+)", r"\1\2", html) # ignore "RFC 1234" vs. "RFC1234" diffs
    html = re.sub(r"\bID\b", r"I-D", html)           # idnore " ID " vs. " I-D " diffs
    text = html2text(html, pre=pre, fill=fill).strip()
    text = text.replace(" : ", ": ").replace(" :", ": ")
    text = text.replace('."', '".')
    text = text.replace(',"', '",')
    if pre:
        text = text.split("\n")
    else:
        text = [ line.strip() for line in text.split("\n") if line.strip()]
    return text

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

def split_url(url):
    if "?" in url:
        url, args = url.split("?", 1)
        args = dict([ arg.split("=", 1) for arg in args.split("&") if "=" in arg ])
    else:
        args = {}
    return url, args

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
            else:
                raise ValueError("Expected 'HTTP_CODE TESTURL [GOODURL]' in %s line, found '%s'." % (filename, line))
            codes = codes.split(",")
            tuples += [ (codes, testurl, goodurl) ]
    file.close()
    return tuples

def filetext(filename):
    file = open(filename)
    chunk = file.read()
    file.close()
    return chunk

class UrlTestCase(TestCase):
    def setUp(self):
        from django.test.client import Client
        self.client = Client()

        # find test urls
        self.testtuples = []
        self.testurls = []
        self.diffchunks = []
        for root, dirs, files in os.walk(settings.BASE_DIR):
            if "testurl.list" in files:
                self.testtuples += read_testurls(root+"/testurl.list")
            if "testurls.list" in files:
                self.testtuples += read_testurls(root+"/testurls.list")
        self.testurls = [ tuple[1] for tuple in self.testtuples ]

        # find diff chunks
        testdir = os.path.abspath(settings.BASE_DIR+"/../test/diff/")
        for item in os.listdir(testdir):
            path = testdir + "/" + item
            if item.startswith("generic-") and os.path.isfile(path):
                chunk = filetext(path).strip()
                chunk = re.sub(r"([\[\]().|+*?])", r"\\\1", chunk)
                # @@ -27,0 \+23,1 @@
                chunk = re.sub(r"(?m)^@@ -\d+,(\d+) \\\+\d+,(\d+) @@$", r"@@ -\d+,\1 \+\d+,\2 @@", chunk)
                #print "*** Installing diff chunk:"
                #print chunk
                self.diffchunks.append(chunk)

        # extract application urls:
        self.patterns = get_patterns(ietf.urls)
        # Use the default database for the url tests, instead of the test database
        self.testdb = settings.DATABASE_NAME
        connection.close()
        settings.DATABASE_NAME = startup_database
        # Install updated fixtures:
        # Also has the side effect of creating the database connection.
        management.syncdb(verbosity=1, interactive=False)
        
    def tearDown(self):
        # Revert to using the test database
        connection.close()
        settings.DATABASE_NAME = self.testdb
        connection.cursor()
        
    def testCoverage(self):
        covered = []
        for codes, testurl, goodurl in self.testtuples:
            for pattern in self.patterns:
                if re.match(pattern, testurl[1:]):
                    covered.append(pattern)
        # We should have at least one test case for each url pattern declared
        # in our Django application:
        #self.assertEqual(set(patterns), set(covered), "Not all the
        #application URLs has test cases.  The missing are: %s" % (list(set(patterns) - set(covered))))        
        if not set(self.patterns) == set(covered):
            missing = list(set(self.patterns) - set(covered))
            print "Not all the application URLs has test cases, there are %d missing." % (len(missing))
            print "The ones missing are: "
            for pattern in missing:
                if not pattern[1:].split("/")[0] in [ "admin", "accounts" ]:
                    print "NoTest", pattern
            print ""
        else:
            print "All the application URL patterns seem to have test cases."
            #print "Not all the application URLs has test cases."

    def doRedirectsTest(self, lst):
        response_count = {}
        for codes, url, master in lst:
            if "skipredir" in codes or "Skipredir" in codes:
                print "Skipping %s" % (url)
	    elif url and master:
		testurl = master.replace('https://datatracker.ietf.org','')
		baseurl, args = split_url(testurl)
                try:
                    response = self.client.get(baseurl, args)
                    code = str(response.status_code)
                    if code == "301":
			if response['Location'] == url:
			    print "OK   %s %s -> %s" % (code, testurl, url)
			    res = ("OK", code)
			else:
			    print "Miss %3s %s ->" % (code, testurl)
                            print "         %s" % (response['Location']) 
                            print " (wanted %s)" % (url)
                            print ""
                            #res = ("Fail", "wrong-reponse")
                    else:
                        print "Fail %s %s" % (code, testurl)
                        res = ("Fail", code)
                except:
                    res = ("Fail", "Exc")
                    print "Exception for URL '%s'" % testurl
                    traceback.print_exc()
                if not res in response_count:
                    response_count[res] = 0
                response_count[res] += 1
        if response_count:
            print "Response count:"
        for res in response_count:
            ind, code = res
            print "  %-4s %s: %s " % (ind, code, response_count[res])
        for res in response_count:
            ind, code = res
            self.assertEqual(ind, "OK", "Found %s cases of result code: %s" % (response_count[res], code))

    def doUrlsTest(self, lst):
        response_count = {}
        for codes, url, master in lst:
            if "skip" in codes or "Skip" in codes:
                print "Skipping %s" % (url)
            elif url:
                baseurl, args = split_url(url)
                #print "Trying codes, url: (%s, '%s')" % (codes, url)
                try:
                    response = self.client.get(baseurl, args)
                    code = str(response.status_code)
                    if code in codes:
                        print "OK   %s %s" % (code, url)
                        res = ("OK", code)
                    else:
                        print "Fail %s %s" % (code, url)
                        res = ("Fail", code)
                except:
                    res = ("Fail", "Exc")
                    print "Exception for URL '%s'" % url
                    traceback.print_exc()
                if master:
                    try:
                        #print "Fetching", master, "...",
                        mfile = urllib.urlopen(master)
                        goodhtml = mfile.read()
                    except urllib.URLError, e:
                        print "Failed retrieving master text for comparison: %s" % e
                    try:
                        mfile.close()
                        if goodhtml and response.content:
                            if "sort" in codes:
                                def sorted(l):
                                    l.sort()
                                    return l
                                testtext = sorted(reduce(response.content, fill=False))
                                while testtext and not testtext[0]:
                                    del testtext[0]
                                goodtext = sorted(reduce(goodhtml, fill=False))
                                while goodtext and not goodtext[0]:
                                    del goodtext[0]
                            else:
                                testtext = reduce(response.content)
                                goodtext = reduce(goodhtml)
                            if testtext == goodtext:
                                print "OK   cmp %s" % (url)
                            else:
                                contextlines = 0
                                difflist = list(unified_diff(goodtext, testtext, master, url, "", "", contextlines, lineterm=""))
                                diff = "\n".join(difflist)
                                for chunk in self.diffchunks:
                                    #print "*** Checking for chunk:", chunk[:24]
                                    while re.search(chunk, diff):
                                        #print "*** Removing chunk of %s lines" % (len(chunk.split("\n")))
                                        diff = re.sub(chunk, "", diff)
                                if len(diff.strip().splitlines()) == 2:
                                    # only the initial 2 lines of the diff remains --
                                    # discard them too
                                    diff = ""
                                if diff:
                                    dfile = "%s/../test/diff/%s" % (settings.BASE_DIR, url.replace("/", "_").replace("?", "_"))
                                    if os.path.exists(dfile):
                                        dfile = open(dfile)
                                        #print "Reading OK diff file:", dfile.name
                                        okdiff = dfile.read()
                                        dfile.close()
                                    else:
                                        okdiff = ""
                                    if diff.strip() == okdiff.strip():
                                        print "OK   cmp %s" % (url)
                                    else:
                                        print "Diff:    %s" % (url)
                                        print "\n".join(difflist[:100])
                                        if len(difflist) > 100:
                                            print "... (skipping %s lines of diff)" % (len(difflist)-100)
                                else:
                                    print "OK   cmp %s" % (url)
                                    
                    except:
                        print "Exception occurred for url %s" % (url)
                        traceback.print_exc()
                        #raise

                if not res in response_count:
                    response_count[res] = 0
                response_count[res] += 1
            else:
                pass
        if response_count:
            print "Response count:"
        for res in response_count:
            ind, code = res
            print "  %-4s %s: %s " % (ind, code, response_count[res])
        for res in response_count:
            ind, code = res
            self.assertEqual(ind, "OK", "Found %s cases of result code: %s" % (response_count[res], code))

    def testUrlsList(self):
        print "\nTesting specified URLs:"
        self.doUrlsTest(self.testtuples)

    def testRedirectsList(self):
	print "\nTesting specified Redirects:"
	self.doRedirectsTest(self.testtuples)

    def testUrlsFallback(self):
        print "\nFallback: Test access to URLs which don't have an explicit test entry:"
        lst = []
        for pattern in self.patterns:
            if pattern.startswith("^") and pattern.endswith("$"):
                url = "/"+pattern[1:-1]
                # if there is no variable parts in the url, test it
                if re.search("^[-a-z0-9./_]*$", url) and not url in self.testurls and not url.startswith("/admin/"):
                    lst.append((["200"], url, None))
                else:
                    #print "No fallback test for %s" % (url)
                    pass
            else:
                lst.append((["Skip"], pattern, None))
            
        self.doUrlsTest(lst)
