import os
import re
import traceback

import django.test.simple
from django.test import TestCase
from django.conf import settings
from django.db import connection
import ietf.settings
import ietf.urls


startup_database = settings.DATABASE_NAME  # The startup database name, before changing to test_...

def run_tests(module_list, verbosity=1, extra_tests=[]):
    module_list.append(ietf.urls)
    # If we append 'ietf.tests', we get it twice, first as itself, then
    # during the search for a 'tests' module ...
    return django.test.simple.run_tests(module_list, verbosity, extra_tests)

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

class UrlTestCase(TestCase):
    def setUp(self):
        from django.test.client import Client
        self.client = Client()

        # find test urls
        self.testtuples = []
        self.testurls = []
        for root, dirs, files in os.walk(ietf.settings.BASE_DIR):
            if "testurl.list" in files:
                filename = root+"/testurl.list" # yes, this is non-portable
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
                        self.testtuples += [ (codes, testurl, goodurl) ]
                        self.testurls += [ testurl ]
                    #print "(%s, %s, %s)" % (code, testurl, goodurl)
        # Use the default database for the url tests, instead of the test database
        self.testdb = settings.DATABASE_NAME
        connection.close()
        settings.DATABASE_NAME = startup_database
        connection.cursor()
        
    def tearDown(self):
        # Revert to using the test database
        connection.close()
        settings.DATABASE_NAME = self.testdb
        connection.cursor()
        
    def testCoverage(self):
        covered = []
        patterns = get_patterns(ietf.urls)
        for codes, testurl, goodurl in self.testtuples:
            for pattern in patterns:
                if re.match(pattern, testurl[1:]):
                    covered.append(pattern)
        # We should have at least one test case for each url pattern declared
        # in our Django application:
        #self.assertEqual(set(patterns), set(covered), "Not all the
        #application URLs has test cases.  The missing are: %s" % (list(set(patterns) - set(covered))))        
        if not set(patterns) == set(covered):
            #print "Not all the application URLs has test cases.  The missing are: \n   %s" % ("\n   ".join(list(set(patterns) - set(covered))))
            print "Not all the application URLs has test cases."

    def doUrlsTest(self, lst):
        response_count = {}
        for codes, url, master in lst:
            if "skip" in codes or "Skip" in codes:
                print "Skipping %s" % (url)
            elif url:
                #print "Trying codes, url: (%s, '%s')" % (codes, url)
                try:
                    response = self.client.get(url)
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
                if not res in response_count:
                    response_count[res] = 0
                response_count[res] += 1
            else:
                pass
        if response_count:
            print "Response count:"
        for res in response_count:
            ind, code = res
            print "%-4s %s: %s " % (ind, code, response_count[res])
        for res in response_count:
            ind, code = res
            self.assertEqual(ind, "OK", "Found %s cases of result code: %s" % (response_count[res], code))

    def testUrlsList(self):
        print "\nTesting specified URLs:"
        self.doUrlsTest(self.testtuples)

    def testUrlsFallback(self):
        patterns = get_patterns(ietf.urls)
        lst = []
        for pattern in patterns:
            if pattern.startswith("^") and pattern.endswith("$"):
                url = "/"+pattern[1:-1]
                # if there is no variable parts in the url, test it
                if re.search("^[-a-z0-9./_]*$", url) and not url in self.testurls and not url.startswith("/admin/"):
                    lst.append((["200"], url, None))
                else:
                    lst.append((["skip"], url, None))
            else:
                lst.append((["Skip"], url, None))
            
        print "\nTesting non-listed URLs:"
        self.doUrlsTest(lst)
