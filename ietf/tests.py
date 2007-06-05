import os
import re
import traceback

import django.test.simple
from django.test import TestCase
import ietf.settings
import ietf.urls

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
                        urlspec = line.split()
                        if len(urlspec) == 2:
                            code, testurl = urlspec
                            goodurl = None
                        elif len(urlspec) == 3:
                            code, testurl, goodurl = urlspec
                        else:
                            raise ValueError("Expected 'HTTP_CODE TESTURL [GOODURL]' in %s line, found '%s'." % (filename, line))
                        self.testtuples += [ (code, testurl, goodurl) ]
                        self.testurls += [ testurl ]
                    #print "(%s, %s, %s)" % (code, testurl, goodurl)
        #print self.testtuples
        
    def testCoverage(self):
        covered = []
        patterns = get_patterns(ietf.urls)
        for code, testurl, goodurl in self.testtuples:
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

    def testUrls(self):
        for code, testurl, goodurl in self.testtuples:
            if code in ["skip", "Skip"]:
                print "Skipping %s" % (testurl)
            else:
                try:
                    response = self.client.get(testurl)
                    print "Got code %s for %s" % (response.status_code, testurl)
                    #self.assertEqual(response.status_code, code, "Unexpected response code (%s) for URL '%s'" % (response.status_code, testurl))
                    # TODO: Add comparison with goodurl
                except:
                    print "Exception for URL '%s'" % testurl
                    traceback.print_exc()

    def testUrlsFallback(self):
        patterns = get_patterns(ietf.urls)
        response_count = {}
        for pattern in patterns:
            if pattern.startswith("^") and pattern.endswith("$"):
                url = "/"+pattern[1:-1]
                # if there is no variable parts in the url, test it
                if re.search("^[-a-z0-9./_]*$", url) and not url in self.testurls and not url.startswith("/admin/"):
                    try:
                        response = self.client.get(url)
                        if not response.status_code in response_count:
                            response_count[response.status_code] = 0
                        response_count[response.status_code] += 1
                        if response.status_code != 200:
                            print "Bad code %s for %s" % (response.status_code, url)
                    except:
                        if not "Exc" in response_count:
                            response_count["Exc"] = 0
                        response_count["Exc"] += 1
                        print "Exception for URL '%s'" % url
                        traceback.print_exc()
                else:
                    print "Skipping %s" % (url)
        print "testUrlsFallback() response count:\n   code count"
        for code in response_count:
            print "   %s: %s " % (code, response_count[code])
        for code in response_count:
            if str(code) != "200":
                self.assertEqual(response_count[code], 0)