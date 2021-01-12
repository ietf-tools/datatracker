# Copyright The IETF Trust 2009-2020, All Rights Reserved
# -*- coding: utf-8 -*-
#
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


import io
import re
import os
import sys
import time
import json
import pytz
import importlib
import socket
import datetime
import gzip
import unittest
import factory.random
from fnmatch import fnmatch

from coverage.report import Reporter
from coverage.results import Numbers
from coverage.misc import NotPython

import django
from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.operations.fields import FieldOperation
from django.db.migrations.operations.models import ModelOperation
from django.db.migrations.operations.base import Operation
from django.template import TemplateDoesNotExist
from django.template.loaders.filesystem import Loader as BaseLoader
from django.test.runner import DiscoverRunner
from django.core.management import call_command
from django.urls import URLResolver # type: ignore

import debug                            # pyflakes:ignore
debug.debug = True

import ietf
import ietf.utils.mail
from ietf.utils.management.commands import pyflakes
from ietf.utils.test_smtpserver import SMTPTestServerDriver
from ietf.utils.test_utils import TestCase


loaded_templates = set()
visited_urls = set()
test_database_name = None
old_destroy = None
old_create = None

template_coverage_collection = None
code_coverage_collection = None
url_coverage_collection = None

def load_and_run_fixtures(verbosity):
    loadable = [f for f in settings.GLOBAL_TEST_FIXTURES if "." not in f]
    call_command('loaddata', *loadable, verbosity=int(verbosity)-1, database="default")

    for f in settings.GLOBAL_TEST_FIXTURES:
        if f not in loadable:
            # try to execute the fixture
            components = f.split(".")
            module_name = ".".join(components[:-1])
            module = importlib.import_module(module_name)
            fn = getattr(module, components[-1])
            fn()

def safe_create_test_db(self, verbosity, *args, **kwargs):
    global test_database_name, old_create
    keepdb = kwargs.get('keepdb', False)
    if not keepdb:
        print("     Creating test database...")
        if settings.DATABASES["default"]["ENGINE"] == 'django.db.backends.mysql':
            settings.DATABASES["default"]["OPTIONS"] = settings.DATABASE_TEST_OPTIONS
            print("     Using OPTIONS: %s" % settings.DATABASES["default"]["OPTIONS"])
    test_database_name = old_create(self, 0, *args, **kwargs)

    if settings.GLOBAL_TEST_FIXTURES:
        print("     Loading global test fixtures: %s" % ", ".join(settings.GLOBAL_TEST_FIXTURES))
        load_and_run_fixtures(verbosity)

    return test_database_name

def safe_destroy_test_db(*args, **kwargs):
    sys.stdout.write('\n')
    global test_database_name, old_destroy
    keepdb = kwargs.get('keepdb', False)
    if not keepdb:
        if settings.DATABASES["default"]["NAME"] != test_database_name:
            print('     NOT SAFE; Changing settings.DATABASES["default"]["NAME"] from %s to %s' % (settings.DATABASES["default"]["NAME"], test_database_name))
            settings.DATABASES["default"]["NAME"] = test_database_name
    return old_destroy(*args, **kwargs)

class PyFlakesTestCase(TestCase):

    def __init__(self, test_runner=None, **kwargs):
        self.runner = test_runner
        super(PyFlakesTestCase, self).__init__(**kwargs)

    def pyflakes_test(self):
        self.maxDiff = None
        path = os.path.join(settings.BASE_DIR)
        warnings = []
        warnings = pyflakes.checkPaths([path], verbosity=0)
        self.assertEqual([], [str(w) for w in warnings])

class MyPyTest(TestCase):

    def __init__(self, test_runner=None, **kwargs):
        self.runner = test_runner
        super(MyPyTest, self).__init__(**kwargs)

    @unittest.skipIf(sys.version_info[0] < 3, "Mypy and django-stubs not available under Py2")
    def mypy_test(self):
        self.maxDiff = None
        from mypy import api
        out, err, code = api.run(['ietf', ])
        out_lines = [ l for l in out.splitlines() if not l.startswith('Success: ') ]
        self.assertEqual([], err.splitlines())
        self.assertEqual([], out_lines)
        self.assertEqual(code, 0)

class TemplateCoverageLoader(BaseLoader):
    is_usable = True

    def get_template(self, template_name, skip=None):
        global template_coverage_collection, loaded_templates
        if template_coverage_collection == True:
            loaded_templates.add(str(template_name))
        raise TemplateDoesNotExist(template_name)

def record_urls_middleware(get_response):
    def record_urls(request):
        global url_coverage_collection, visited_urls
        if url_coverage_collection == True:
            visited_urls.add(request.path)
        return get_response(request)
    return record_urls

def get_url_patterns(module, apps=None):
    def include(name):
        if not apps:
            return True
        for app in apps:
            if str(name).startswith(app+'.'):
                return True
        return False
    def exclude(name):
        for pat in settings.TEST_URL_COVERAGE_EXCLUDE:
            if re.search(pat, str(name)):
                return True
        return False
    def do_append(res, p0, p1, item):
        p0 = str(p0)
        p1 = str(p1)
        if p1.startswith("^"):
            res.append((p0 + p1[1:], item))
        else:
            res.append((p0 + p1, item))
    if not hasattr(module, 'urlpatterns'):
        return []
    res = []
    for item in module.urlpatterns:
        if isinstance(item, URLResolver):
            if type(item.urlconf_module) is list:
                for subitem in item.urlconf_module:
                    if isinstance(subitem, URLResolver):
                        res += get_url_patterns(subitem.urlconf_module)
                    else:
                        sub = subitem.pattern
                        do_append(res, item.pattern, subitem.pattern, subitem)
            else:
                if include(item.urlconf_module.__name__) and not exclude(item.pattern):
                    subpatterns = get_url_patterns(item.urlconf_module)
                    for sub, subitem in subpatterns:
                        do_append(res, item.pattern, sub, subitem)
        else:
            res.append((str(item.pattern), item))
    return res

_all_templates = None
def get_template_paths(apps=None):
    global _all_templates
    if not _all_templates:
        # TODO: Add app templates to the full list, if we are using
        # django.template.loaders.app_directories.Loader
        templates = set()
        templatepaths = settings.TEMPLATES[0]['DIRS']
        for templatepath in templatepaths:
            for dirpath, dirs, files in os.walk(templatepath):
                if ".svn" in dirs:
                    dirs.remove(".svn")
                relative_path = dirpath[len(templatepath)+1:]
                for file in files:
                    ignore = False
                    for pattern in settings.TEST_TEMPLATE_IGNORE:
                        if fnmatch(file, pattern):
                            ignore = True
                            break
                    if ignore:
                        continue
                    if relative_path != "":
                        file = os.path.join(relative_path, file)
                    templates.add(file)
        if apps:
            templates = [ t for t in templates if t.split(os.path.sep)[0] in apps ]
        _all_templates = templates
    return _all_templates

def save_test_results(failures, test_labels):
    # Record the test result in a file, in order to be able to check the
    # results and avoid re-running tests if we've alread run them with OK
    # result after the latest code changes:
    topdir = os.path.dirname(os.path.dirname(settings.BASE_DIR))
    tfile = io.open(os.path.join(topdir,".testresult"), "a", encoding='utf-8')
    timestr = time.strftime("%Y-%m-%d %H:%M:%S")
    if failures:
        tfile.write("%s FAILED (failures=%s)\n" % (timestr, failures))
    else:
        if test_labels:
            tfile.write("%s SUCCESS (tests=%s)\n" % (timestr, test_labels))
        else:
            tfile.write("%s OK\n" % (timestr, ))
    tfile.close()

def set_coverage_checking(flag=True):
    global template_coverage_collection
    global code_coverage_collection
    global url_coverage_collection
    if settings.SERVER_MODE == 'test':
        if flag:
            settings.TEST_CODE_COVERAGE_CHECKER.collector.resume()
            template_coverage_collection = True
            code_coverage_collection = True
            url_coverage_collection = True
        else:
            settings.TEST_CODE_COVERAGE_CHECKER.collector.pause()
            template_coverage_collection = False
            code_coverage_collection = False
            url_coverage_collection = False

class CoverageReporter(Reporter):
    def report(self):
        self.find_file_reporters(None)

        total = Numbers()
        result = {"coverage": 0.0, "covered": {}, "format": 5, }
        for fr in self.file_reporters:
            try:
                analysis = self.coverage._analyze(fr)
                nums = analysis.numbers
                missing_nums = sorted(analysis.missing)
                with io.open(analysis.filename, encoding='utf-8') as file:
                    lines = file.read().splitlines()
                missing_lines = [ lines[l-1] for l in missing_nums ]
                result["covered"][fr.relative_filename()] = (nums.n_statements, nums.pc_covered/100.0, missing_nums, missing_lines)
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


class CoverageTest(unittest.TestCase):

    def __init__(self, test_runner=None, **kwargs):
        self.runner = test_runner
        super(CoverageTest, self).__init__(**kwargs)

    def report_test_result(self, test):
            latest_coverage_version = self.runner.coverage_master["version"]

            master_data = self.runner.coverage_master[latest_coverage_version][test]
            master_missing = [ k for k,v in list(master_data["covered"].items()) if not v ]
            master_coverage = master_data["coverage"]

            test_data = self.runner.coverage_data[test]
            test_missing = [ k for k,v in list(test_data["covered"].items()) if not v ]
            test_coverage = test_data["coverage"]

            # Assert coverage failure only if we're running the full test suite -- if we're
            # only running some tests, then of course the coverage is going to be low.
            if self.runner.run_full_test_suite:
                # Permit 0.02% variation in results -- otherwise small code changes become a pain
                fudge_factor = 0.0002
                self.assertLessEqual(len(test_missing), len(master_missing),
                    msg = "New %s without test coverage since %s: %s" % (test, latest_coverage_version, list(set(test_missing) - set(master_missing))))
                self.assertGreaterEqual(test_coverage, master_coverage - fudge_factor,
                    msg = "The %s coverage percentage is now lower (%.2f%%) than for version %s (%.2f%%)" %
                        ( test, test_coverage*100, latest_coverage_version, master_coverage*100, ))

    def template_coverage_test(self):
        global loaded_templates
        if self.runner.check_coverage:
            apps = [ app.split('.')[-1] for app in self.runner.test_apps ]
            all = get_template_paths(apps)
            # The calculations here are slightly complicated by the situation
            # that loaded_templates also contain nomcom page templates loaded
            # from the database.  However, those don't appear in all
            covered = [ k for k in all if k in loaded_templates ]
            self.runner.coverage_data["template"] = {
                "coverage": (1.0*len(covered)/len(all)) if len(all)>0 else float('nan'),
                "covered":  dict( (k, k in covered) for k in all ),
                "format": 1,
                }
            self.report_test_result("template")
        else:
            self.skipTest("Coverage switched off with --skip-coverage")

    def url_coverage_test(self):
        if self.runner.check_coverage:
            import ietf.urls
            url_patterns = get_url_patterns(ietf.urls, self.runner.test_apps)
            #debug.pprint('[ r for r,p in url_patterns]')

            # skip some patterns that we don't bother with
            def ignore_pattern(regex, pattern):
                import django.views.static
                return (regex in ("^_test500/$", "^accounts/testemail/$")
                        or regex.startswith("^admin/")
                        or re.search('^api/v1/[^/]+/[^/]+/', regex)
                        or getattr(pattern.callback, "__name__", "") == "RedirectView"
                        or getattr(pattern.callback, "__name__", "") == "TemplateView"
                        or pattern.callback == django.views.static.serve)

            patterns = [(regex, re.compile(regex, re.U), obj) for regex, obj in url_patterns
                        if not ignore_pattern(regex, obj)]

            covered = set()
            for url in visited_urls:
                for regex, compiled, obj in patterns:
                    if regex not in covered and compiled.match(url[1:]): # strip leading /
                        covered.add(regex)
                        break

            self.runner.coverage_data["url"] = {
                "coverage": 1.0*len(covered)/len(patterns),
                "covered": dict( (k, (o.lookup_str, k in covered)) for k,p,o in patterns ),
                "format": 4,
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
            checker.config.from_args(ignore_errors=None, omit=settings.TEST_CODE_COVERAGE_EXCLUDE_FILES,
                include=include, file=None)
            for pattern in settings.TEST_CODE_COVERAGE_EXCLUDE_LINES:
                checker.exclude(pattern)
            # Maybe output an HTML report
            if self.runner.run_full_test_suite and self.runner.html_report:
                checker.html_report(directory=settings.TEST_CODE_COVERAGE_REPORT_DIR)
            # In any case, build a dictionary with per-file data for this run
            reporter = CoverageReporter(checker, checker.config)
            self.runner.coverage_data["code"] = reporter.report()
            self.report_test_result("code")
        else:
            self.skipTest("Coverage switched off with --skip-coverage")

    def interleaved_migrations_test(self):
#        from django.apps import apps
#         unreleased = {}
#         for appconf in apps.get_app_configs():
#             mpath = Path(appconf.path) / 'migrations'
#             for pyfile in mpath.glob('*.py'):
#                 if pyfile.name == '__init__.py':
#                     continue
#                 mmod = import_module('%s.migrations.%s' % (appconf.name, pyfile.stem))
#                 for n,v in mmod.__dict__.items():
#                     if isinstance(v, type) and issubclass(v, migrations.Migration):
#                         migration = v
#                         self.runner.coverage_data['migration']['present'][migration.__module__] = {'operations':[]}
#                         d = self.runner.coverage_data['migration']['present'][migration.__module__]
#                         for n,v in migration.__dict__.items():
#                             if n == 'operations':
#                                 for op in v:
#                                     cl = op.__class__
#                                     if issubclass(cl, ModelOperation) or issubclass(cl, FieldOperation):
#                                         d['operations'].append('schema')
#                                     elif issubclass(cl, Operation):
#                                         d['operations'].append('data')
#                                     else:
#                                         raise RuntimeError("Found unexpected operation type in migration: %s" % (op))

        # Clear this setting, otherwise we won't see any migrations
        settings.MIGRATION_MODULES = {}
        # Save information here, for later write to file
        info = self.runner.coverage_data['migration']['present']
        # Get migrations
        loader = MigrationLoader(None, ignore_no_migrations=True)
        graph = loader.graph
        targets = graph.leaf_nodes()
        seen = set()
        opslist = []
        for target in targets:
            #debug.show('target')
            for migration in graph.forwards_plan(target):
                if migration not in seen:
                    node = graph.node_map[migration]
                    #debug.show('node')
                    seen.add(migration)
                    ops = []
                    # get the actual migration object
                    migration = loader.graph.nodes[migration]
                    for op in migration.operations:
                        cl = op.__class__
                        if issubclass(cl, ModelOperation) or issubclass(cl, FieldOperation):
                            ops.append(('schema', cl.__name__))
                        elif issubclass(cl, Operation):
                            if getattr(op, 'code', None) and getattr(op.code, 'interleavable', None) == True:
                                continue
                            ops.append(('data', cl.__name__))
                        else:
                            raise RuntimeError("Found unexpected operation type in migration: %s" % (op))
                    info[migration.__module__] = {'operations': ops}
                    opslist.append((migration, node, ops))
        # Compare the migrations we found to those present in the latest
        # release, to see if we have any unreleased migrations
        latest_coverage_version = self.runner.coverage_master["version"]
        if 'migration' in self.runner.coverage_master[latest_coverage_version]:
            release_data = self.runner.coverage_master[latest_coverage_version]['migration']['present']
        else:
            release_data = {}
        unreleased = []
        for migration, node, ops in opslist:
            if not migration.__module__ in release_data:
                for op, nm in ops:
                    unreleased.append((node, op, nm))
        # gather the transitions in operation types.  We'll allow 1
        # transition, but not 2 or more.
        s = 0
        for s in range(len(unreleased)):
            # ignore leading data migrations, they run with the production
            # schema so can take any time they like
            if unreleased[s][1] != 'data':
                break
        mixed = [ unreleased[i] for i in range(s+1,len(unreleased)) if unreleased[i][1] != unreleased[i-1][1] ]
        if len(mixed) > 1 and not self.runner.permit_mixed_migrations:
            raise self.failureException('Found interleaved schema and data operations in unreleased migrations;'
                ' please see if they can be re-ordered with all data migrations before the schema migrations:\n'
                +('\n'.join(['    %-6s:  %-12s, %s (%s)'% (op, node.key[0], node.key[1], nm) for (node, op, nm) in unreleased ])))

class InvalidString(str):
    def __mod__(self, other):
        from django.template.base import TemplateSyntaxError
        raise TemplateSyntaxError(
            "Undefined variable or unknown value for: \"%s\"" % other)

class IetfTestRunner(DiscoverRunner):

    @classmethod
    def add_arguments(cls, parser):
        super(IetfTestRunner, cls).add_arguments(parser)
        parser.add_argument('--skip-coverage',
            action='store_true', dest='skip_coverage', default=False,
            help='Skip test coverage measurements for code, templates, and URLs. ' )
        parser.add_argument('--save-version-coverage', metavar='RELEASE_VERSION',
            action='store', dest='save_version_coverage', default=False,
            help='Save test coverage data under the given version label')
        parser.add_argument('--save-testresult',
            action='store_true', dest='save_testresult', default=False,
            help='Save short test result data in %s/.testresult' % os.path.dirname(os.path.dirname(settings.BASE_DIR))),
        parser.add_argument('--html-report',
            action='store_true', default=False,
            help='Generate an HTML code coverage report in %s' % settings.TEST_CODE_COVERAGE_REPORT_DIR)
        parser.add_argument('--permit-mixed-migrations',
            action='store_true', default=False,
            help='Permit interleaved unreleased migrations')
        parser.add_argument('--show-logging',
            action='store_true', default=False,
            help='Show logging output going to LOG_USER in production mode')

    def __init__(self, skip_coverage=False, save_version_coverage=None, html_report=None, permit_mixed_migrations=None, show_logging=None, **kwargs):
        #
        self.check_coverage = not skip_coverage
        self.save_version_coverage = save_version_coverage
        self.html_report = html_report
        self.permit_mixed_migrations = permit_mixed_migrations
        self.show_logging = show_logging
        settings.show_logging = show_logging
        #
        self.root_dir = os.path.dirname(settings.BASE_DIR)
        self.coverage_file = os.path.join(self.root_dir, settings.TEST_COVERAGE_MASTER_FILE)
        super(IetfTestRunner, self).__init__(**kwargs)
        if self.parallel > 1:
            if self.html_report == True:
                sys.stderr.write("The switches --parallel and --html-report cannot be combined, "
                                 "as the collection of test coverage data isn't currently threadsafe.")
                sys.exit(1)
            self.check_coverage = False

    def setup_test_environment(self, **kwargs):
        global template_coverage_collection
        global url_coverage_collection

        ietf.utils.mail.test_mode = True
        ietf.utils.mail.SMTP_ADDR['ip4'] = '127.0.0.1'
        ietf.utils.mail.SMTP_ADDR['port'] = 2025
        # switch to a much faster hasher
        settings.PASSWORD_HASHERS = ( 'django.contrib.auth.hashers.MD5PasswordHasher', )
        settings.SERVER_MODE = 'test'
        #
        print("     Datatracker %s test suite, %s:" % (ietf.__version__, time.strftime("%d %B %Y %H:%M:%S %Z")))
        print("     Python %s." % sys.version.replace('\n', ' '))
        print("     Django %s, settings '%s'" % (django.get_version(), settings.SETTINGS_MODULE))

        if self.check_coverage:
            if self.coverage_file.endswith('.gz'):
                with gzip.open(self.coverage_file, "rb") as file:
                    self.coverage_master = json.load(file)
            else:
                with io.open(self.coverage_file, encoding='utf-8') as file:
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
                    "format": 4,
                },
                "code": {
                    "coverage": 0.0, 
                    "covered": {},
                    "format": 1,
                },
                "migration": {
                    "present": {},
                    "format": 3,
                }
            }

            settings.TEMPLATES[0]['OPTIONS']['loaders'] = ('ietf.utils.test_runner.TemplateCoverageLoader',) + settings.TEMPLATES[0]['OPTIONS']['loaders']

            settings.MIDDLEWARE = ('ietf.utils.test_runner.record_urls_middleware',) + tuple(settings.MIDDLEWARE)

            self.code_coverage_checker = settings.TEST_CODE_COVERAGE_CHECKER
            if not self.code_coverage_checker._started:
                sys.stderr.write(" **  Warning: In %s: Expected the coverage checker to have\n"
                                 "       been started already, but it wasn't. Doing so now.  Coverage numbers\n"
                                 "       will be off, though.\n" % __name__)
                self.code_coverage_checker.start()

        if settings.SITE_ID != 1:
            print("     Changing SITE_ID to '1' during testing.")
            settings.SITE_ID = 1

        if True:
            if settings.TEMPLATES[0]['OPTIONS']['string_if_invalid'] != '':
                print("     Changing TEMPLATES[0]['OPTIONS']['string_if_invalid'] to '' during testing")
                settings.TEMPLATES[0]['OPTIONS']['string_if_invalid'] = ''
        else:
            # Alternative code to trigger test exceptions on failure to
            # resolve variables in templates.
            print("     Changing TEMPLATES[0]['OPTIONS']['string_if_invalid'] during testing")
            settings.TEMPLATES[0]['OPTIONS']['string_if_invalid'] = InvalidString('%s')

        if settings.INTERNAL_IPS:
            print("     Changing INTERNAL_IPS to '[]' during testing.")
            settings.INTERNAL_IPS = []

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
                print(("     Running an SMTP test server on %(ip4)s:%(port)s to catch outgoing email." % ietf.utils.mail.SMTP_ADDR))
                break
            except socket.error:
                pass

        if os.path.exists(settings.UTILS_TEST_RANDOM_STATE_FILE):
            print("     Loading factory-boy random state from %s" % settings.UTILS_TEST_RANDOM_STATE_FILE)
        else:
            print("     Saving factory-boy random state to %s" % settings.UTILS_TEST_RANDOM_STATE_FILE)
            with open(settings.UTILS_TEST_RANDOM_STATE_FILE, 'w') as f:
                s = factory.random.get_random_state()
                json.dump(s, f)
        with open(settings.UTILS_TEST_RANDOM_STATE_FILE) as f:
            s = json.load(f)
            s[1] = tuple(s[1])      # random.setstate() won't accept a list in lieu of a tuple
        factory.random.set_random_state(s)

        super(IetfTestRunner, self).setup_test_environment(**kwargs)

    def teardown_test_environment(self, **kwargs):
        self.smtpd_driver.stop()
        if self.check_coverage:
            latest_coverage_file = os.path.join(self.root_dir, settings.TEST_COVERAGE_LATEST_FILE)
            coverage_latest = {}
            coverage_latest["version"] = "latest"
            coverage_latest["latest"] = self.coverage_data
            with open(latest_coverage_file, "w") as file:
                json.dump(coverage_latest, file, indent=2, sort_keys=True)
            if self.save_version_coverage:
                self.coverage_master["version"] = self.save_version_coverage
                self.coverage_master[self.save_version_coverage] = self.coverage_data
                if self.coverage_file.endswith('.gz'):
                    with gzip.open(self.coverage_file, "w") as file:
                        json_coverage = json.dumps(self.coverage_master, sort_keys=True)
                        file.write(json_coverage.encode())
                else:
                    with open(self.coverage_file, "w") as file:
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
        global old_destroy, old_create, test_database_name, template_coverage_collection, code_coverage_collection, url_coverage_collection
        from django.db import connection
        from ietf.doc.tests import TemplateTagTest

        # Tests that involve switching back and forth between the real
        # database and the test database are way too dangerous to run
        # against the production database
        if socket.gethostname().split('.')[0] in ['core3', 'ietfa', 'ietfb', 'ietfc', ]:
            raise EnvironmentError("Refusing to run tests on production server")

        old_create = connection.creation.__class__.create_test_db
        connection.creation.__class__.create_test_db = safe_create_test_db
        old_destroy = connection.creation.__class__.destroy_test_db
        connection.creation.__class__.destroy_test_db = safe_destroy_test_db

        self.run_full_test_suite = not test_labels

        if not test_labels: # we only want to run our own tests
            test_labels = ["ietf"]

        self.test_apps, self.test_paths = self.get_test_paths(test_labels)

        if self.check_coverage:
            template_coverage_collection = True
            code_coverage_collection = True
            url_coverage_collection = True
            extra_tests += [
                PyFlakesTestCase(test_runner=self, methodName='pyflakes_test'),
                MyPyTest(test_runner=self, methodName='mypy_test'),
                CoverageTest(test_runner=self, methodName='interleaved_migrations_test'),
                CoverageTest(test_runner=self, methodName='url_coverage_test'),
                CoverageTest(test_runner=self, methodName='template_coverage_test'),
                CoverageTest(test_runner=self, methodName='code_coverage_test'),
            ]

            # ensure that the coverage tests come last.  Specifically list
            # TemplateTagTest before CoverageTest.  If this list contains
            # parent classes to later subclasses, the parent classes will
            # determine the ordering, so use the most specific classes
            # necessary to get the right ordering:
            self.reorder_by = (PyFlakesTestCase, MyPyTest, ) + self.reorder_by + (StaticLiveServerTestCase, TemplateTagTest, CoverageTest, )

        failures = super(IetfTestRunner, self).run_tests(test_labels, extra_tests=extra_tests, **kwargs)

        if self.check_coverage:
            print("")
            if self.run_full_test_suite:
                print("Test coverage data:")
            else:
                print(("Test coverage for this test run across the related app%s (%s):" % (("s" if len(self.test_apps)>1 else ""), ", ".join(self.test_apps))))
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
                    print(("      %8s coverage: %6.2f%%  (%s: %6.2f%%)" %
                        (test.capitalize(), test_coverage*100, latest_coverage_version, master_coverage*100, )))
                else:
                    print(("      %8s coverage: %6.2f%%" %
                        (test.capitalize(), test_coverage*100, )))

            print(("""
                Per-file code and template coverage and per-url-pattern url coverage data
                for the latest test run has been written to %s.

                Per-statement code coverage data has been written to '.coverage', readable
                by the 'coverage' program.
                """.replace("    ","") % (settings.TEST_COVERAGE_LATEST_FILE)))

        save_test_results(failures, test_labels)

        if not failures and os.path.exists(settings.UTILS_TEST_RANDOM_STATE_FILE):
            os.unlink(settings.UTILS_TEST_RANDOM_STATE_FILE)

        return failures

class IetfLiveServerTestCase(StaticLiveServerTestCase):
    @classmethod
    def setUpClass(cls):
        set_coverage_checking(False)
        super(IetfLiveServerTestCase, cls).setUpClass()

    def setUp(self):
        super(IetfLiveServerTestCase, self).setUp()
        # LiveServerTestCase uses TransactionTestCase which seems to
        # somehow interfere with the fixture loading process in
        # IetfTestRunner when running multiple tests (the first test
        # is fine, in the next ones the fixtures have been wiped) -
        # this is no doubt solvable somehow, but until then we simply
        # recreate them here
        from ietf.person.models import Person
        if not Person.objects.exists():
            load_and_run_fixtures(verbosity=0)

    @classmethod
    def tearDownClass(cls):
        super(IetfLiveServerTestCase, cls).tearDownClass()
        set_coverage_checking(True)

    
