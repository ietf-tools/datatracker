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


import re
import os
import sys
import time
import json
import pytz
import importlib
import socket
import warnings
import datetime
import codecs
import gzip

from coverage.report import Reporter
from coverage.results import Numbers
from coverage.misc import NotPython
from optparse import make_option

from django.conf import settings
from django.template import TemplateDoesNotExist
from django.test import TestCase
from django.test.runner import DiscoverRunner
from django.core.management import call_command
from django.core.urlresolvers import RegexURLResolver

import debug                            # pyflakes:ignore

import ietf
import ietf.utils.mail
from ietf.utils.test_smtpserver import SMTPTestServerDriver

loaded_templates = set()
visited_urls = set()
test_database_name = None
old_destroy = None
old_create = None

def safe_create_1(self, verbosity, *args, **kwargs):
    global test_database_name, old_create
    print "     Creating test database..."
    if settings.DATABASES["default"]["ENGINE"] == 'django.db.backends.mysql':
        settings.DATABASES["default"]["OPTIONS"] = settings.DATABASE_TEST_OPTIONS
        print "     Using OPTIONS: %s" % settings.DATABASES["default"]["OPTIONS"]
    test_database_name = old_create(self, 0, *args, **kwargs)
    if settings.GLOBAL_TEST_FIXTURES:
        print "     Loading global test fixtures: %s" % ", ".join(settings.GLOBAL_TEST_FIXTURES)
        loadable = [f for f in settings.GLOBAL_TEST_FIXTURES if "." not in f]
        call_command('loaddata', *loadable, verbosity=0, commit=False, database="default")

        for f in settings.GLOBAL_TEST_FIXTURES:
            if f not in loadable:
                # try to execute the fixture
                components = f.split(".")
                module = importlib.import_module(".".join(components[:-1]))
                fn = getattr(module, components[-1])
                fn()
    if verbosity < 2:
        warnings.simplefilter("ignore", DeprecationWarning)

    return test_database_name

def safe_destroy_0_1(*args, **kwargs):
    global test_database_name, old_destroy
    print "     Checking that it's safe to destroy test database..."
    if settings.DATABASES["default"]["NAME"] != test_database_name:
        print '     NOT SAFE; Changing settings.DATABASES["default"]["NAME"] from %s to %s' % (settings.DATABASES["default"]["NAME"], test_database_name)
        settings.DATABASES["default"]["NAME"] = test_database_name
    return old_destroy(*args, **kwargs)

def template_coverage_loader(template_name, dirs):
    loaded_templates.add(str(template_name))
    raise TemplateDoesNotExist
template_coverage_loader.is_usable = True

class RecordUrlsMiddleware(object):
    def process_request(self, request):
        visited_urls.add(request.path)

def get_url_patterns(module, apps=None):
    def include(name):
        if not apps:
            return True
        for app in apps:
            if name.startswith(app+'.'):
                return True
        return False
    def exclude(name):
        for pat in settings.TEST_URL_COVERAGE_EXCLUDE:
            if re.search(pat, name):
                return True
        return False
    if not hasattr(module, 'urlpatterns'):
        return []
    res = []
    for item in module.urlpatterns:
        if isinstance(item, RegexURLResolver) and not type(item.urlconf_module) is list:
            if include(item.urlconf_module.__name__) and not exclude(item.regex.pattern):
                subpatterns = get_url_patterns(item.urlconf_module)
                for sub, subitem in subpatterns:
                    if sub.startswith("^"):
                        res.append((item.regex.pattern + sub[1:], subitem))
                    else:
                        res.append((item.regex.pattern + ".*" + sub, subitem))
        else:
            res.append((item.regex.pattern, item))
    return res

def get_templates(apps=None):
    templates = set()
    templatepaths = settings.TEMPLATE_DIRS
    for templatepath in templatepaths:
        for dirpath, dirs, files in os.walk(templatepath):
            if ".svn" in dirs:
                dirs.remove(".svn")
            relative_path = dirpath[len(templatepath)+1:]
            for file in files:
                if file.endswith("~") or file.startswith("#"):
                    continue
                if relative_path != "":
                    file = os.path.join(relative_path, file)
                templates.add(file)
    if apps:
        templates = [ t for t in templates if t.split(os.path.sep)[0] in apps ]
    return templates

def save_test_results(failures, test_labels):
    # Record the test result in a file, in order to be able to check the
    # results and avoid re-running tests if we've alread run them with OK
    # result after the latest code changes:
    topdir = os.path.dirname(os.path.dirname(settings.BASE_DIR))
    tfile = codecs.open(os.path.join(topdir,"testresult"), "a", encoding='utf-8')
    timestr = time.strftime("%Y-%m-%d %H:%M:%S")
    if failures:
        tfile.write("%s FAILED (failures=%s)\n" % (timestr, failures))
    else:
        if test_labels:
            tfile.write("%s SUCCESS (tests=%s)\n" % (timestr, test_labels))
        else:
            tfile.write("%s OK\n" % (timestr, ))
    tfile.close()


class CoverageReporter(Reporter):
    def report(self):
        self.find_file_reporters(None)

        total = Numbers()
        result = {"coverage": 0.0, "covered": {}, "format": 2, }
        for fr in self.file_reporters:
            try:
                analysis = self.coverage._analyze(fr)
                nums = analysis.numbers
                result["covered"][fr.relative_filename()] = (nums.n_statements, nums.pc_covered/100.0)
                total += nums
            except KeyboardInterrupt:                   # pragma: not covered
                raise
            except Exception:
                report_it = not self.config.ignore_errors
                if report_it:
                    typ, msg = sys.exc_info()[:2]
                    if typ is NotPython and not fr.should_be_python():
                        report_it = False
                if report_it:
                    raise
        result["coverage"] = total.pc_covered/100.0
        return result


class CoverageTest(TestCase):

    def __init__(self, test_runner=None, **kwargs):
        self.runner = test_runner
        super(CoverageTest, self).__init__(**kwargs)

    def report_test_result(self, test):
            latest_coverage_version = self.runner.coverage_master["version"]

            master_data = self.runner.coverage_master[latest_coverage_version][test]
            master_missing = [ k for k,v in master_data["covered"].items() if not v ]
            master_coverage = master_data["coverage"]

            test_data = self.runner.coverage_data[test]
            test_missing = [ k for k,v in test_data["covered"].items() if not v ]
            test_coverage = test_data["coverage"]

            # Assert coverage failure only if we're running the full test suite -- if we're
            # only running some tests, then of course the coverage is going to be low.
            if self.runner.run_full_test_suite:
                # Permit 0.02% variation in results -- otherwise small code changes become a pain
                fudge_factor = 0.0002   # 0.02% -- a small change in the last digit we show
                self.assertGreaterEqual(test_coverage, master_coverage - fudge_factor,
                    msg = "The %s coverage percentage is now lower (%.2f%%) than for version %s (%.2f%%)" %
                        ( test, test_coverage*100, latest_coverage_version, master_coverage*100, ))
                self.assertLessEqual(len(test_missing), len(master_missing),
                    msg = "New %s without test coverage since %s: %s" % (test, latest_coverage_version, list(set(test_missing) - set(master_missing))))

    def template_coverage_test(self):
        global loaded_templates
        if self.runner.check_coverage:
            apps = [ app.split('.')[-1] for app in self.runner.test_apps ]
            all = get_templates(apps)
            # The calculations here are slightly complicated by the situation
            # that loaded_templates also contain nomcom page templates loaded
            # from the database.  However, those don't appear in all
            covered = [ k for k in all if k in loaded_templates ]
            self.runner.coverage_data["template"] = {
                "coverage": (1.0*len(covered)/len(all)) if len(all)>0 else float('nan'),
                "covered":  dict( (k, k in covered) for k in all ),
                }
            self.report_test_result("template")
        else:
            self.skipTest("Coverage switched off with --skip-coverage")

    def url_coverage_test(self):
        if self.runner.check_coverage:
            import ietf.urls
            url_patterns = get_url_patterns(ietf.urls, self.runner.test_apps)

            # skip some patterns that we don't bother with
            def ignore_pattern(regex, pattern):
                import django.views.static
                return (regex in ("^_test500/$", "^accounts/testemail/$")
                        or regex.startswith("^admin/")
                        or getattr(pattern.callback, "__name__", "") == "RedirectView"
                        or getattr(pattern.callback, "__name__", "") == "TemplateView"
                        or pattern.callback == django.views.static.serve)

            patterns = [(regex, re.compile(regex)) for regex, pattern in url_patterns
                        if not ignore_pattern(regex, pattern)]
            all = [ regex for regex, compiled in patterns ]

            covered = set()
            for url in visited_urls:
                for regex, compiled in patterns:
                    if regex not in covered and compiled.match(url[1:]): # strip leading /
                        covered.add(regex)
                        break

            self.runner.coverage_data["url"] = {
                "coverage": 1.0*len(covered)/len(all),
                "covered": dict( (k, k in covered) for k in all ),
                }

            self.report_test_result("url")
        else:
            self.skipTest("Coverage switched off with --skip-coverage")

    def code_coverage_test(self):
        if self.runner.check_coverage:
            include = [ os.path.join(path, '*') for path in self.runner.test_paths ]
            checker = self.runner.code_coverage_checker
            checker.stop()
            # Save to the .coverage file
            checker.save()
            # Apply the configured and requested omit and include data 
            checker.config.from_args(ignore_errors=None, omit=settings.TEST_CODE_COVERAGE_EXCLUDE,
                include=include, file=None)
            # Maybe output a html report
            if self.runner.run_full_test_suite:
                checker.html_report(directory=settings.TEST_CODE_COVERAGE_REPORT_DIR)
            # In any case, build a dictionary with per-file data for this run
            reporter = CoverageReporter(checker, checker.config)
            self.runner.coverage_data["code"] = reporter.report()
            self.report_test_result("code")
        else:
            self.skipTest("Coverage switched off with --skip-coverage")

class IetfTestRunner(DiscoverRunner):
    option_list = (
        make_option('--skip-coverage',
            action='store_true', dest='skip_coverage', default=False,
            help='Skip test coverage measurements for code, templates, and URLs. '
        ),
        make_option('--save-version-coverage',
            action='store', dest='save_version_coverage', default=False,
            help='Save test coverage data under the given version label'),
    )

    def __init__(self, skip_coverage=False, save_version_coverage=None, **kwargs):
        #
        self.check_coverage = not skip_coverage
        self.save_version_coverage = save_version_coverage
        #
        self.root_dir = os.path.dirname(settings.BASE_DIR)
        self.coverage_file = os.path.join(self.root_dir, settings.TEST_COVERAGE_MASTER_FILE)
        super(IetfTestRunner, self).__init__(**kwargs)

    def setup_test_environment(self, **kwargs):
        ietf.utils.mail.test_mode = True
        ietf.utils.mail.SMTP_ADDR['ip4'] = '127.0.0.1'
        ietf.utils.mail.SMTP_ADDR['port'] = 2025
        #
        if self.check_coverage:
            if self.coverage_file.endswith('.gz'):
                with gzip.open(self.coverage_file, "rb") as file:
                    self.coverage_master = json.load(file)
            else:
                with codecs.open(self.coverage_file, encoding='utf-8') as file:
                    self.coverage_master = json.load(file)
            self.coverage_data = {
                "time": datetime.datetime.now(pytz.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "template": {
                    "coverage": 0.0, 
                    "covered": {},
                    "format": 1,        # default format, coverage data in 'covered' are just fractions
                },
                "url": {
                    "coverage": 0.0, 
                    "covered": {},
                    "format": 1,
                },
                "code": {
                    "coverage": 0.0, 
                    "covered": {},
                    "format": 1,
                },
            }

            settings.TEMPLATE_LOADERS = ('ietf.utils.test_runner.template_coverage_loader',) + settings.TEMPLATE_LOADERS
            settings.MIDDLEWARE_CLASSES = ('ietf.utils.test_runner.RecordUrlsMiddleware',) + settings.MIDDLEWARE_CLASSES

            self.code_coverage_checker = settings.TEST_CODE_COVERAGE_CHECKER
            if not self.code_coverage_checker._started:
                sys.stderr.write(" **  Warning: In %s: Expected the coverage checker to have\n"
                                 "       been started already, but it wasn't. Doing so now.  Coverage numbers\n"
                                 "       will be off, though.\n" % __name__)
                self.code_coverage_checker.start()

        if settings.SITE_ID != 1:
            print "     Changing SITE_ID to '1' during testing."
            settings.SITE_ID = 1

        if settings.TEMPLATE_STRING_IF_INVALID != '':
            print "     Changing TEMPLATE_STRING_IF_INVALID to '' during testing."
            settings.TEMPLATE_STRING_IF_INVALID = ''

        assert not settings.IDTRACKER_BASE_URL.endswith('/')

        # Try to set up an SMTP test server.  In case other test runs are
        # going on at the same time, try a range of ports.
        base = ietf.utils.mail.SMTP_ADDR['port']
        for offset in range(10):
            try:
                # remember the value so ietf.utils.mail.send_smtp() will use the same
                ietf.utils.mail.SMTP_ADDR['port'] = base + offset 
                self.smtpd_driver = SMTPTestServerDriver((ietf.utils.mail.SMTP_ADDR['ip4'],ietf.utils.mail.SMTP_ADDR['port']),None) 
                self.smtpd_driver.start()
                print("     Running an SMTP test server on %(ip4)s:%(port)s to catch outgoing email." % ietf.utils.mail.SMTP_ADDR)
                break
            except socket.error:
                pass


        super(IetfTestRunner, self).setup_test_environment(**kwargs)

    def teardown_test_environment(self, **kwargs):
        self.smtpd_driver.stop()
        if self.check_coverage:
            latest_coverage_file = os.path.join(self.root_dir, settings.TEST_COVERAGE_LATEST_FILE)
            coverage_latest = {}
            coverage_latest["version"] = "latest"
            coverage_latest["latest"] = self.coverage_data
            with codecs.open(latest_coverage_file, "w", encoding='utf-8') as file:
                json.dump(coverage_latest, file, indent=2, sort_keys=True)
            if self.save_version_coverage:
                self.coverage_master["version"] = self.save_version_coverage
                self.coverage_master[self.save_version_coverage] = self.coverage_data
                if self.coverage_file.endswith('.gz'):
                    with gzip.open(self.coverage_file, "wb") as file:
                        json.dump(self.coverage_master, file, sort_keys=True)
                else:
                    with codecs.open(self.coverage_file, "w", encoding="utf-8") as file:
                        json.dump(self.coverage_master, file, indent=2, sort_keys=True)
        super(IetfTestRunner, self).teardown_test_environment(**kwargs)

    def get_test_paths(self, test_labels):
        """Find the apps and paths matching the test labels, so we later can limit
           the coverage data to those apps and paths.
        """
        test_apps = []
        app_roots = set( app.split('.')[0] for app in settings.INSTALLED_APPS )
        for label in test_labels:
            part_list = label.split('.')
            if label in settings.INSTALLED_APPS:
                # The label is simply an app in installed apps
                test_apps.append(label)
            elif not (part_list[0] in app_roots):
                # try to add an app root to get a match with installed apps
                for root in app_roots:
                    for j in range(len(part_list)):
                        maybe_app = ".".join([root] + part_list[:j+1])
                        if maybe_app in settings.INSTALLED_APPS:
                            test_apps.append(maybe_app)
                            break
                    else:
                        continue
                    break
            else:
                # the label is more detailed than a plain app, and the
                # root is in app_roots.
                for j in range(len(part_list)):
                    maybe_app = ".".join(part_list[:j+1])
                    if maybe_app in settings.INSTALLED_APPS:
                        test_apps.append(maybe_app)
                        break
        test_paths = [ os.path.join(*app.split('.')) for app in test_apps ]
        return test_apps, test_paths

    def run_tests(self, test_labels, extra_tests=[], **kwargs):
        # Tests that involve switching back and forth between the real
        # database and the test database are way too dangerous to run
        # against the production database
        if socket.gethostname().split('.')[0] in ['core3', 'ietfa', 'ietfb', 'ietfc', ]:
            raise EnvironmentError("Refusing to run tests on production server")

        global old_destroy, old_create, test_database_name
        from django.db import connection
        old_create = connection.creation.__class__.create_test_db
        connection.creation.__class__.create_test_db = safe_create_1
        old_destroy = connection.creation.__class__.destroy_test_db
        connection.creation.__class__.destroy_test_db = safe_destroy_0_1

        self.run_full_test_suite = not test_labels

        if not test_labels: # we only want to run our own tests
            test_labels = ["ietf"]

        self.test_apps, self.test_paths = self.get_test_paths(test_labels)

        if self.check_coverage:
            extra_tests += [
                CoverageTest(test_runner=self, methodName='url_coverage_test'),
                CoverageTest(test_runner=self, methodName='template_coverage_test'),
                CoverageTest(test_runner=self, methodName='code_coverage_test'),
            ]

            self.reorder_by += (CoverageTest, ) # see to it that the coverage tests come last

        failures = super(IetfTestRunner, self).run_tests(test_labels, extra_tests=extra_tests, **kwargs)

        if self.check_coverage:
            print("")
            if self.run_full_test_suite:
                print("Test coverage data:")
            else:
                print("Test coverage for this test run across the related app%s (%s):" % (("s" if len(self.test_apps)>1 else ""), ", ".join(self.test_apps)))
            for test in ["template", "url", "code"]:
                latest_coverage_version = self.coverage_master["version"]

                master_data = self.coverage_master[latest_coverage_version][test]
                #master_all = master_data["covered"]
                #master_missing = [ k for k,v in master_data["covered"].items() if not v ]
                master_coverage = master_data["coverage"]

                test_data = self.coverage_data[test]
                #test_all = test_data["covered"]
                #test_missing = [ k for k,v in test_data["covered"].items() if not v ]
                test_coverage = test_data["coverage"]

                if self.run_full_test_suite:
                    print("      %8s coverage: %6.2f%%  (%s: %6.2f%%)" %
                        (test.capitalize(), test_coverage*100, latest_coverage_version, master_coverage*100, ))
                else:
                    print("      %8s coverage: %6.2f%%" %
                        (test.capitalize(), test_coverage*100, ))

            print("""
                Per-file code and template coverage and per-url-pattern url coverage data
                for the latest test run has been written to %s.

                Per-statement code coverage data has been written to '.coverage', readable
                by the 'coverage' program.
                """.replace("    ","") % (settings.TEST_COVERAGE_LATEST_FILE))

        save_test_results(failures, test_labels)

        return failures
