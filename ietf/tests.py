# Copyright The IETF Trust 2007, All Rights Reserved

import os
import re
import traceback
import urllib2 as urllib
import httplib
from urlparse import urljoin
from datetime import datetime

from ietf.utils.soup2text import TextSoup
from difflib import unified_diff

import django.test.simple
from django.test import TestCase
from django.test.client import Client
from django.conf import settings
from django.db import connection
from django.core import management
import ietf.urls
from ietf.utils import log

startup_database = settings.DATABASE_NAME  # The startup database name, before changing to test_...

def run_tests(module_list, verbosity=0, extra_tests=[]):
    module_list.append(ietf.urls)
    # If we append 'ietf.tests', we get it twice, first as itself, then
    # during the search for a 'tests' module ...
    return django.test.simple.run_tests(module_list, 0, extra_tests)

def normalize_html(html, fill):
    # Line ending normalization
    html = html.replace("\r\n", "\n").replace("\r", "\n")
    # remove comments
    html = re.sub("(?s)<!--.*?-->", "", html)    
    # attempt to close <li>s (avoid too deep recursion later)
    if html.count("<li>") > 5*html.count("</li>"):
        html = html.replace("<li>", "</li><li>")
    if not fill:
        html = re.sub("<br ?/?>", "<br/><br/>", html)
    html = re.sub(r"(?i)(RFC) (\d+)", r"\1\2", html) # ignore "RFC 1234" vs. "RFC1234" diffs
    html = re.sub(r"\bID\b", r"I-D", html)           # idnore " ID " vs. " I-D " diffs
    # some preprocessing to handle common pathological cases
    html = re.sub("<br */?>[ \t\n]*(<br */?>)+", "<p/>", html)
    html = re.sub("<br */?>([^\n])", r"<br />\n\1", html)
    return html
    
def reduce_text(html, pre=False, fill=True):
    html = normalize_html(html, fill)
    page = TextSoup(html)
    text = page.as_text(encoding='latin-1', pre=pre, fill=fill).strip()
    text = text.replace(" : ", ": ").replace(" :", ": ")
    text = text.replace('."', '".')
    text = text.replace(',"', '",')
    return text, page

def update_reachability(url, code, page):
    if code in ["301", "302", "303", "307"]:
        try:
            file = urllib.urlopen(url)
            html = file.read()
            file.close()
            code = 200
            page = TextSoup(html)
        except urllib.URLError, e:
            note("     Error retrieving %s: %s" % (url, e))
            code = e.code
            page = None
    module.reachability[url] = (code, "Test")
    links = ( [ urljoin(url, a["href"]) for a in page.findAll("a") if a.has_key("href")]
            + [ urljoin(url, img["src"]) for img in page.findAll("img") if a.has_key("src")] )
    for link in links:
        link = link.split("#")[0]   # don't include fragment identifier
        if not link in module.reachability:
            module.reachability[link] = (None, url)

def lines(text, pre=False):
    if pre:
        text = text.split("\n")
    else:
        text = [ line.strip() for line in text.split("\n") if line.strip()]
    return text
    
def sorted(lst):
    lst.sort()
    return lst

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

def get_testurls():
    testtuples = []
    for root, dirs, files in os.walk(settings.BASE_DIR):
        if "testurl.list" in files:
            testtuples += read_testurls(root+"/testurl.list")
        if "testurls.list" in files:
            testtuples += read_testurls(root+"/testurls.list")
    return testtuples

def filetext(filename):
    file = open(filename)
    chunk = file.read()
    file.close()
    return chunk


prev_note_time = datetime.utcnow()
def note(string):
    global prev_note_time
    """Like a print function, but adds a leading timestamp line"""
    now = datetime.utcnow()
    print string
    print now.strftime("         %Y-%m-%d_%H:%M"), "+%3.1f" % (now-prev_note_time).seconds
    prev_note_time = datetime.utcnow()

def module_setup(module):
    # get selected prefixes, if any
    module.prefixes = os.environ.get("URLPREFIX", "").split()

    # find test urls
    module.testtuples = []
    module.testurls = []
    module.diffchunks = {}
    module.ignores = {}
    module.testtuples = get_testurls()
    module.testurls = [ tuple[1] for tuple in module.testtuples ]
    module.reachability = {}

    # find diff chunks
    testdir = os.path.abspath(settings.BASE_DIR+"/../test/diff/")
    for item in os.listdir(testdir):
        path = testdir + "/" + item
        if item.startswith("generic-") and os.path.isfile(path):
            chunk = filetext(path).rstrip()
            chunk = re.sub(r"([\[\]().|+*?])", r"\\\1", chunk)
            # @@ -27,0 \+23,1 @@
            chunk = re.sub(r"(?m)^@@ -\d+,(\d+) \\\+\d+,(\d+) @@$", r"@@ -\d+,\1 \+\d+,\2 @@", chunk)
            module.diffchunks[item] = chunk

    # find ignore chunks
    for root, dirs, files in os.walk(settings.BASE_DIR+"/../test/ignore/"):
        # This only expects one directory level below test/ignore/:
        for file in files:
            path = root + "/" + file
            dir = root.split("/")[-1]
            chunk = filetext(path).strip()
            if not dir in module.ignores:
                module.ignores[dir] = []
            module.ignores[dir].append(chunk)

    # extract application urls:
    module.patterns = get_patterns(ietf.urls)

    # apply prefix filters
    if module.prefixes:
        module.patterns = [ pattern for pattern in module.patterns for prefix in module.prefixes if re.match(prefix, pattern) ]
        module.testtuples = [ tuple for tuple in module.testtuples for prefix in module.prefixes if re.match(prefix, tuple[1][1:]) ]


    # Use the default database for the url tests, instead of the test database
    module.testdb = settings.DATABASE_NAME
    connection.close()
    settings.DATABASE_NAME = startup_database
    # Install updated fixtures:
    # Also has the side effect of creating the database connection.
    management.syncdb(verbosity=1, interactive=False)
    connection.close()
    settings.DATABASE_NAME = module.testdb
    connection.cursor()

class UrlTestCase(TestCase):

    def __init__(self, *args, **kwargs):
        TestCase.__init__(self, *args, **kwargs)

# ------------------------------------------------------------------------------
# Setup and tear-down

    def setUp(self):
        self.client = Client()

        self.testdb = settings.DATABASE_NAME
        connection.close()
        settings.DATABASE_NAME = startup_database
        connection.cursor()
        
    def tearDown(self):
        # Revert to using the test database
        connection.close()
        settings.DATABASE_NAME = self.testdb
        connection.cursor()
        
# ------------------------------------------------------------------------------
# Test methods.
#
# These are listed in alphabetic order, which is the order in which they will
# be executed.
#

    def testCoverage(self):
        covered = []
        for codes, testurl, goodurl in module.testtuples:
            for pattern in module.patterns:
                if re.match(pattern, testurl[1:]):
                    covered.append(pattern)
        # We should have at least one test case for each url pattern declared
        # in our Django application:
        #self.assertEqual(set(patterns), set(covered), "Not all the
        #application URLs has test cases.  The missing are: %s" % (list(set(patterns) - set(covered))))        
        if not set(module.patterns) == set(covered):
            missing = list(set(module.patterns) - set(covered))
            print "Not all the application URLs has test cases, there are %d missing." % (len(missing))
            print "The ones missing are: "
            for pattern in missing:
                if not pattern[1:].split("/")[0] in [ "admin", "accounts" ]:
                    print "NoTest", pattern
            print ""
        else:
            print "All the application URL patterns seem to have test cases."
            #print "Not all the application URLs has test cases."

    def testRedirectsList(self):
	note("\nTesting specified Redirects:")
	self.doRedirectsTest(module.testtuples)

    def testUrlsFallback(self):
        note("\nFallback: Test access to URLs which don't have an explicit test entry:")
        lst = []
        for pattern in module.patterns:
            if pattern.startswith("^") and pattern.endswith("$"):
                url = "/"+pattern[1:-1]
                # if there is no variable parts in the url, test it
                if re.search("^[-a-z0-9./_]*$", url) and not url in module.testurls and not url.startswith("/admin/"):
                    lst.append((["200"], url, None))
                else:
                    #print "No fallback test for %s" % (url)
                    pass
            else:
                lst.append((["Skip"], pattern, None))
        self.doUrlsTest(lst)

    def testUrlsList(self):
        note("\nTesting specified URLs:")
        self.doUrlsTest(module.testtuples)

    # Disable this test by not having it start with "test"
    def xTestUrlsReachability(self):
        # This test should be sorted after the other tests which retrieve URLs
        note("\nTesting URL reachability of %s URLs:" % len(module.reachability) )
        for url in module.reachability:
            if url:
                code, source = module.reachability[url]
                if not code:
                    print "         %s" % ( url.strip() )
                    if url.startswith("/"):
                        baseurl, args = split_url(url)
                        try:
                            code = str(self.client.get(baseurl, args).status_code)
                        except AssertionError:
                            note("Exception for URL '%s'" % url)
                            traceback.print_exc()
                            self.client = Client()
                            code = "Exc"
                    elif url.startswith("mailto:"):
                        continue
                    else:
                        try:
                            file = urllib.urlopen(url)
                            file.close()
                            code = "200"
                        except urllib.HTTPError, e:
                            code = str(e.code)
                        except urllib.URLError, e:
                            note("Exception for URL '%s'" % url)
                            traceback.print_exc()
                            self.client = Client()
                            code = "Exc"
                        except httplib.InvalidURL, e:
                            note("Exception for URL '%s'" % url)
                            traceback.print_exc()
                            self.client = Client()
                            code = "Exc"
            else:
                code = "000"
            if not code in ["200"]:
                note("Reach %3s <%s> (from %s)\n" % (code, url, source))


# ------------------------------------------------------------------------------
# Worker methods

    def doRedirectsTest(self, lst):
        response_count = {}
        for codes, url, master in lst:
            if "skipredir" in codes or "Skipredir" in codes or "skipredirect" in codes:
                print "Skipping %s" % (url)
	    elif url and master:
		testurl = master.replace('https://datatracker.ietf.org','')
		baseurl, args = split_url(testurl)
                try:
                    response = self.client.get(baseurl, args)
                    code = str(response.status_code)
                    if code == "301":
			if response['Location'] == url:
			    note("OK   %s %s -> %s" % (code, testurl, url))
			    res = ("OK", code)
			else:
			    print "Miss %3s %s ->" % (code, testurl)
                            print "         %s" % (response['Location']) 
                            note( " (wanted %s)" % (url))
                            print ""
                            res = None
                            #res = ("Fail", "wrong-reponse")
                    else:
                        note("Fail %s %s" % (code, testurl))
                        res = ("Fail", code)
                except:
                    res = ("Fail", "Exc")
                    note("Exception for URL '%s'" % testurl)
                    traceback.print_exc()
                if res:
                    if not res in response_count:
                        response_count[res] = 0
                    response_count[res] += 1
        if response_count:
            print ""
            note("Response count:")
        for res in response_count:
            ind, code = res
            print "  %-4s %s: %s " % (ind, code, response_count[res])
        for res in response_count:
            ind, code = res
            self.assertEqual(ind, "OK", "Found %s cases of result code: %s" % (response_count[res], code))
        if response_count:
            print ""

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
                        note("OK   %s %s" % (code, url))
                        res = ("OK", code)
                    else:
                        note("Fail %s %s" % (code, url))
                        res = ("Fail", code)
                except:
                    res = ("Fail", "Exc")
                    note("Exception for URL '%s'" % url)
                    traceback.print_exc()
                if master and not "skipdiff" in codes:
                    hostprefix = settings.TEST_REFERENCE_URL_PREFIX
                    if hostprefix.endswith("/"):
                        hostprefix = hostprefix[:-1]
                    master = hostprefix + master
                    goodhtml = None
                    try:
                        #print "Fetching", master, "...",
                        mfile = urllib.urlopen(master)
                        goodhtml = mfile.read()
                        mfile.close()
                        note("     200 %s" % (master))
                    except urllib.URLError, e:
                        note("     Error retrieving %s: %s" % (master, e))
                    except urllib.BadStatusLine, e:
                        note("     Error retrieving %s: %s" % (master, e))
                    try:
                        if goodhtml and response.content:
                            testhtml = response.content
                            # Always ignore some stuff
                            for regex in module.ignores["always"]:
                                testhtml = re.sub(regex, "", testhtml)
                                goodhtml = re.sub(regex, "", goodhtml)
                            if "sort" in codes:
                                testtext, testpage = reduce_text(testhtml, fill=False)
                                goodtext, goodpage = reduce_text(goodhtml, fill=False)
                            else:
                                testtext, testpage = reduce_text(response.content)
                                goodtext, goodpage = reduce_text(goodhtml)
                            update_reachability(url, code, testpage)
                            # Always ignore some stuff again
                            for regex in module.ignores["always"]:
                                testtext = re.sub(regex, "", testtext)
                                goodtext = re.sub(regex, "", goodtext)
                            if "ignore" in codes:
                                ignores = codes["ignore"].split("/")
                                for ignore in ignores:
                                    for regex in module.ignores[ignore]:
                                        testtext = re.sub(regex, "", testtext)
                                        goodtext = re.sub(regex, "", goodtext)
                            #log("Checking text: %s" % testtext[:96])
                            testtext = lines(testtext.strip())
                            goodtext = lines(goodtext.strip())
                            if "sort" in codes:
                                testtext = sorted(testtext)
                                while testtext and not testtext[0]:
                                    del testtext[0]
                                while testtext and not testtext[-1]:
                                    del testtext[-1]
                                goodtext = sorted(goodtext)
                                while goodtext and not goodtext[0]:
                                    del goodtext[0]
                                while goodtext and not goodtext[-1]:
                                    del goodtext[-1]
                            if testtext == goodtext:
                                note("OK   cmp %s" % (url))
                            else:
                                contextlines = 0
                                difflist = list(unified_diff(goodtext, testtext, master, url, "", "", contextlines, lineterm=""))
                                diff = "\n".join(difflist[2:])
                                log("Checking diff: %s" % diff[:96])
                                keys = module.diffchunks.keys()
                                keys.sort
                                for key in keys:
                                    chunk = module.diffchunks[key]
                                    if chunk:
                                        if not re.search(chunk, diff):
                                            log("No match: %s" % chunk[:96])
                                        while re.search(chunk, diff):
                                            log("Found chunk: %s" % chunk[:96])
                                            diff = re.sub(chunk, "", diff)
                                if len(diff.strip().splitlines()) == 2:
                                    # only the initial 2 lines of the diff remains --
                                    # discard them too
                                    diff = ""
                                if diff:
                                    dfile = "%s/../test/diff/%s" % (settings.BASE_DIR, re.sub("[/?&=]", "_", url) )
                                    if os.path.exists(dfile):
                                        dfile = open(dfile)
                                        #print "Reading OK diff file:", dfile.name
                                        okdiff = dfile.read()
                                        dfile.close()
                                    else:
                                        okdiff = ""
                                    if diff.strip() == okdiff.strip():
                                        note("OK   cmp %s" % (url))
                                    else:
                                        if okdiff:
                                            note("Failed diff: %s" % (url))
                                        else:
                                            note("Diff:    %s" % (url))
                                        print "\n".join(diff.split("\n")[:100])
                                        if len(diff.split("\n")) > 100:
                                            print "... (skipping %s lines of diff)" % (len(difflist)-100)
                                else:
                                    note("OK   cmp %s" % (url))
                                    
                    except:
                        note("Exception occurred for url %s" % (url))
                        traceback.print_exc()
                        #raise

                if not res in response_count:
                    response_count[res] = 0
                response_count[res] += 1
            else:
                pass
        if response_count:
            print ""
            note("Response count:")
        for res in response_count:
            ind, code = res
            print "  %-4s %s: %s " % (ind, code, response_count[res])
        for res in response_count:
            ind, code = res
            self.assertEqual(ind, "OK", "Found %s cases of result code: %s" % (response_count[res], code))
        if response_count:
            print ""



class Module:
    pass
module = Module()
module_setup(module)
