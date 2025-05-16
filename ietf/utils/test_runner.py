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
import importlib
import socket
import gzip
import unittest
import pathlib
import subprocess
import tempfile
import copy
import boto3
import botocore.config
import factory.random
import urllib3
import warnings

from fnmatch import fnmatch
from typing import Callable, Optional
from urllib.parse import urlencode

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
from django.template.backends.django import DjangoTemplates
from django.template.backends.django import Template  # type: ignore[attr-defined]
from django.utils import timezone
from django.views.generic import RedirectView, TemplateView

import debug                            # pyflakes:ignore
debug.debug = True

import ietf
import ietf.utils.mail
from ietf.utils.management.commands import pyflakes
from ietf.utils.test_smtpserver import SMTPTestServerDriver
from ietf.utils.test_utils import TestCase

from mypy_boto3_s3.service_resource import Bucket


loaded_templates: set[str] = set()
visited_urls: set[str] = set()
test_database_name: Optional[str] = None
old_destroy: Optional[Callable] = None
old_create: Optional[Callable] = None

template_coverage_collection = None
code_coverage_collection = None
url_coverage_collection = None
validation_settings = {"validate_html": None, "validate_html_harder": None, "show_logging": False}

def start_vnu_server(port=8888):
    "Start a vnu validation server on the indicated port"
    vnu = subprocess.Popen(
        [
            "java",
            "-Dnu.validator.servlet.bind-address=127.0.0.1",
            "-Dnu.validator.servlet.max-file-size=16777216",
            "-cp",
            "bin/vnu.jar",
            "nu.validator.servlet.Main",
            f"{port}",
        ],
        stdout=subprocess.DEVNULL,
    )

    print("     Waiting for vnu server to start up...", end="")
    while vnu_validate(b"", content_type="", port=port) is None:
        print(".", end="")
        time.sleep(1)
    print()
    return vnu


http = urllib3.PoolManager(retries=urllib3.Retry(99, redirect=False))


def vnu_validate(html, content_type="text/html", port=8888):
    "Pass the HTML to the vnu server running on the indicated port"
    if "** No value found for " in html.decode():
        return json.dumps(
            {"messages": [{"message": '"** No value found for" in source'}]}
        )

    gzippeddata = gzip.compress(html)
    try:
        req = http.request(
            "POST",
            f"http://127.0.0.1:{port}/?"
            + urlencode({"out": "json", "asciiquotes": "yes"}),
            headers={
                "Content-Type": content_type,
                "Accept-Encoding": "gzip",
                "Content-Encoding": "gzip",
                "Content-Length": str(len(gzippeddata)),
            },
            body=gzippeddata,
        )
    except (
        urllib3.exceptions.NewConnectionError,
        urllib3.exceptions.MaxRetryError,
        ConnectionRefusedError,
    ):
        return None

    assert req.status == 200
    return req.data.decode("utf-8")


def vnu_fmt_message(file, msg, content):
    "Convert a vnu JSON message into a printable string"
    ret = f"\n{file}:\n"
    if "extract" in msg:
        ret += msg["extract"].replace("\n", " ") + "\n"
        ret += " " * msg["hiliteStart"]
        ret += "^" * msg["hiliteLength"] + "\n"
        ret += " " * msg["hiliteStart"]
    ret += f"{msg['type']}: {msg['message']}\n"
    if "firstLine" in msg and "lastLine" in msg:
        ret += f'Source snippet, lines {msg["firstLine"]-5} to {msg["lastLine"]+4}:\n'
        lines = content.splitlines()
        for line in range(msg["firstLine"] - 5, msg["lastLine"] + 5):
            ret += f"{line}: {lines[line]}\n"
    return ret


def vnu_filter_message(msg, filter_db_issues, filter_test_issues):
    "True if the vnu message is a known false positive"
    if re.search(
        r"""^Document\ uses\ the\ Unicode\ Private\ Use\ Area|
            ^Trailing\ slash\ on\ void\ elements\ has\ no\ effect|
            ^Element\ 'h.'\ not\ allowed\ as\ child\ of\ element\ 'pre'""",
        msg["message"],
        flags=re.VERBOSE,
    ) or (
        filter_db_issues
        and re.search(
            r"""^Forbidden\ code\ point\ U\+|
                 Illegal\ character\ in\ query:\ '\['|
                 'href'\ on\ element\ 'a':\ Percentage\ \("%"\)\ is\ not|
                ^Saw\ U\+\d+\ in\ stream""",
            msg["message"],
            flags=re.VERBOSE,
        )
    ):
        return True

    if filter_test_issues and re.search(
        r"""Ceci\ n'est\ pas\ une\ URL|
            ^The\ '\w+'\ attribute\ on\ the\ '\w+'\ element\ is\ obsolete|
            ^Section\ lacks\ heading""",
        msg["message"],
        flags=re.VERBOSE,
    ):
        return True

    return re.search(
        r"""document\ is\ not\ mappable\ to\ XML\ 1|
            ^Attribute\ 'required'\ not\ allowed\ on\ element\ 'div'|
            ^The\ 'type'\ attribute\ is\ unnecessary\ for\ JavaScript|
            is\ not\ in\ Unicode\ Normalization\ Form\ C""",
        msg["message"],
        flags=re.VERBOSE,
    )


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
    if old_create is None:
        raise RuntimeError("old_create has not been set, cannot proceed")
    keepdb = kwargs.get('keepdb', False)
    if not keepdb:
        print("     Creating test database...")
    global test_database_name
    test_database_name = old_create(self, 0, *args, **kwargs)

    if settings.GLOBAL_TEST_FIXTURES:
        print("     Loading global test fixtures: %s" % ", ".join(settings.GLOBAL_TEST_FIXTURES))
        load_and_run_fixtures(verbosity)

    return test_database_name

def safe_destroy_test_db(*args, **kwargs):
    if old_destroy is None:
        raise RuntimeError("old_destroy has not been set, cannot proceed")
    sys.stdout.write('\n')
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

        # Filter out warnings about unused global variables
        filtered_warnings = [
            w for w in warnings
            if not re.search(r"`global \w+` is unused: name is never assigned in scope", str(w))
        ]

        self.assertEqual([], [str(w) for w in filtered_warnings])

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


class ValidatingTemplates(DjangoTemplates):
    def __init__(self, params):
        super().__init__(params)

        if not validation_settings["validate_html"]:
            return
        self.validation_cache = set()
        self.cwd = str(pathlib.Path.cwd())

    def get_template(self, template_name):
        return ValidatingTemplate(self.engine.get_template(template_name), self)


class ValidatingTemplate(Template):
    def __init__(self, template, backend):
        super().__init__(template, backend)

    def render(self, context=None, request=None):
        content = super().render(context, request)

        if not validation_settings["validate_html"]:
            return content

        if not self.origin.name.endswith("html"):
            # not HTML, skip it
            return content

        if not self.origin.name.startswith(self.backend.cwd):
            # only validate fragments in our source tree
            return content

        fingerprint = hash(content) + sys.maxsize + 1  # make hash positive
        if not validation_settings["validate_html_harder"] and fingerprint in self.backend.validation_cache:
            # already validated this HTML fragment, skip it
            # as an optimization, make page a bit smaller by not returning HTML for the menus
            # FIXME: figure out why this still includes base/menu.html
            return "" if "templates/base/menu" in self.origin.name else content

        self.backend.validation_cache.add(fingerprint)
        kind = (
            "doc"
            if re.search(r"^\s*<!doctype", content, flags=re.IGNORECASE)
            else "frag"
        )

        # don't validate each template by itself, causes too much overhead
        # instead, save a batch of them and then validate them all in one go
        # this delays error detection a bit, but is MUCH faster
        validation_settings["validate_html"].batches[kind].append(
            (self.origin.name, content, fingerprint)
        )
        return content


class TemplateValidationTests(unittest.TestCase):
    def __init__(self, test_runner, validate_html, **kwargs):
        self.runner = test_runner
        self.validate_html = validate_html
        super().__init__(**kwargs)

    def run_template_validation(self):
        if self.validate_html:
            self.validate_html.validate(self)


class TemplateCoverageLoader(BaseLoader):
    is_usable = True

    def get_template(self, template_name, skip=None):
        if template_coverage_collection:
            loaded_templates.add(str(template_name))
        raise TemplateDoesNotExist(template_name)

def record_urls_middleware(get_response):
    def record_urls(request):
        if url_coverage_collection:
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
    # results and avoid re-running tests if we've already run them with OK
    # result after the latest code changes:
    tfile = io.open(".testresult", "a", encoding='utf-8')
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
                # Permit a small variation in results -- otherwise small code changes become a pain
                fudge_factor = 0.0004
                self.assertLessEqual(len(test_missing), len(master_missing),
                    msg = "New %s without test coverage since %s: %s" % (test, latest_coverage_version, list(set(test_missing) - set(master_missing))))
                if not self.runner.ignore_lower_coverage:
                    self.assertGreaterEqual(test_coverage, master_coverage - fudge_factor,
                        msg = "The %s coverage percentage is now lower (%.2f%%) than for version %s (%.2f%%)" %
                            ( test, test_coverage*100, latest_coverage_version, master_coverage*100, ))

    def template_coverage_test(self):
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
                        or (
                            hasattr(pattern.callback, "view_class")
                            and issubclass(pattern.callback.view_class, (RedirectView, TemplateView))
                        )
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
            warnings.warn('Found interleaved schema and data operations in unreleased migrations;'
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
        parser.add_argument('--ignore-lower-coverage',
            action= 'store_true', dest='ignore_lower_coverage', default=False,
            help='Do not treat lower coverage as a failure. Useful for building a new coverage file to reset the coverage baseline.')
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
        parser.add_argument('--no-validate-html',
            action='store_false', dest="validate_html", default=True,
            help='Do not validate all generated HTML with html-validate.org')
        parser.add_argument('--validate-html-harder',
            action='store_true', dest="validate_html_harder", default=False,
            help='Validate all generated HTML with additional validators (slow)')
        parser.add_argument('--rerun-until-failure',
            action='store_true', dest='rerun', default=False,
            help='Run the indicated tests in a loop until a failure occurs. ' )
        parser.add_argument('--no-manage-blobstore', action='store_false', dest='manage_blobstore',
                            help='Disable creating/deleting test buckets in the blob store.'
                                 'When this argument is used, a set of buckets with "test-" prefixed to their '
                                 'names must already exist.')

    def __init__(
        self,
        ignore_lower_coverage=False,
        skip_coverage=False,
        save_version_coverage=None,
        html_report=None,
        permit_mixed_migrations=None,
        show_logging=None,
        validate_html=None,
        validate_html_harder=None,
        rerun=None,
        manage_blobstore=True,
        **kwargs
    ):    #
        self.ignore_lower_coverage = ignore_lower_coverage
        self.check_coverage = not skip_coverage
        self.save_version_coverage = save_version_coverage
        self.html_report = html_report
        self.permit_mixed_migrations = permit_mixed_migrations
        self.show_logging = show_logging
        self.rerun = rerun
        self.test_labels = None
        validation_settings["validate_html"] = self if validate_html else None
        validation_settings["validate_html_harder"] = self if validate_html and validate_html_harder else None
        validation_settings["show_logging"] = show_logging
        #
        self.root_dir = os.path.dirname(settings.BASE_DIR)
        self.coverage_file = os.path.join(self.root_dir, settings.TEST_COVERAGE_MAIN_FILE)
        super(IetfTestRunner, self).__init__(**kwargs)
        if self.parallel > 1:
            if self.html_report == True:
                sys.stderr.write("The switches --parallel and --html-report cannot be combined, "
                                 "as the collection of test coverage data isn't currently threadsafe.")
                sys.exit(1)
            self.check_coverage = False
        from ietf.doc.tests import TemplateTagTest  # import here to prevent circular imports
        # Ensure that the coverage tests come last. Specifically list TemplateTagTest before CoverageTest. If this list
        # contains parent classes to later subclasses, the parent classes will determine the ordering, so use the most
        # specific classes necessary to get the right ordering:
        self.reorder_by = (PyFlakesTestCase, MyPyTest,) + self.reorder_by + (StaticLiveServerTestCase, TemplateTagTest, CoverageTest,)
        #self.buckets = set()
        self.blobstoremanager = TestBlobstoreManager() if manage_blobstore else None

    def setup_test_environment(self, **kwargs):
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

        settings.TEMPLATES[0]['BACKEND'] = 'ietf.utils.test_runner.ValidatingTemplates'
        if self.check_coverage:
            if self.coverage_file.endswith('.gz'):
                with gzip.open(self.coverage_file, "rb") as file:
                    self.coverage_master = json.load(file)
            else:
                with io.open(self.coverage_file, encoding='utf-8') as file:
                    self.coverage_master = json.load(file)
            self.coverage_data = {
                "time": timezone.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
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

        if not validation_settings["validate_html"]:
            print("     Not validating any generated HTML; "
                  "please do so at least once before committing changes")
        else:
            print("     Validating all HTML generated during the tests", end="")
            self.batches = {"doc": [], "frag": []}

            # keep the html-validate configs here, so they can be kept in sync easily
            config = {}
            config["frag"] = {
                "extends": ["html-validate:recommended"],
                "rules": {
                    # many trailing whitespaces inserted by Django, ignore:
                    "no-trailing-whitespace": "off",
                    # navbar dropdowns can't use buttons, ignore:
                    "prefer-native-element": [
                        "error",
                        {"exclude": ["button"]},
                    ],
                    # title length mostly only matters for SEO, ignore:
                    "long-title": "off",
                    # the current (older) version of Django seems to add type="text/javascript" for form media, ignore:
                    "script-type": "off",
                    # django-bootstrap5 seems to still generate 'checked="checked"', ignore:
                    "attribute-boolean-style": "off",
                    # self-closing style tags are valid in HTML5. Both self-closing and non-self-closing tags are accepted. (vite generates self-closing link tags)
                    "void-style": "off",
                    # Both attributes without value and empty strings are equal and valid. (vite generates empty value attributes)
                    "attribute-empty-style": "off",
                    # For fragments, don't check that elements are in the proper ancestor element
                    "element-required-ancestor": "off",
                    # This is allowed by the HTML spec
                    "form-dup-name": "off",
                    # Don't trip over unused disable blocks
                    "no-unused-disable": "off",
                    # Ignore focusable elements in aria-hidden elements
                    "hidden-focusable": "off",
                    # Ignore missing unique identifier for page "landmarks"
                    "unique-landmark": "off",
                },
            }

            config["doc"] = copy.deepcopy(config["frag"])
            # enable doc-level rules
            config["doc"]["extends"].append("html-validate:document")
            # FIXME: we should find a way to use SRI, but ignore for now:
            config["doc"]["rules"]["require-sri"] = "off"
            # Turn "element-required-ancestor" back on
            del config["doc"]["rules"]["element-required-ancestor"]
            config["doc"]["rules"]["heading-level"] = [
                "error",
                {
                    # permit discontinuous heading numbering in cards, modals and dialogs:
                    "sectioningRoots": [
                        ".card-body",
                        ".modal-content",
                        '[role="dialog"]',
                    ],
                    # permit multiple H1 elements in a single document
                    "allowMultipleH1": True,
                },
            ]

            self.config_file = {}
            for kind in self.batches:
                self.config_file[kind] = tempfile.NamedTemporaryFile(
                    prefix="html-validate-config-",
                    suffix=".json"
                )
                self.config_file[kind].write(json.dumps(config[kind]).encode())
                self.config_file[kind].flush()
                pathlib.Path(self.config_file[kind].name).chmod(0o644)

            if not validation_settings["validate_html_harder"]:
                print("")
                self.vnu = None
            else:
                print(" (extra pedantically)")
                self.vnu = start_vnu_server()

        if self.blobstoremanager is not None:
            self.blobstoremanager.createTestBlobstores()
        
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

        if validation_settings["validate_html"]:
            for kind in self.batches:
                if len(self.batches[kind]):
                    print(f"     WARNING: not all templates of kind '{kind}' were validated")
                self.config_file[kind].close()
            if self.vnu:
                self.vnu.terminate()

        if self.blobstoremanager is not None:
            self.blobstoremanager.destroyTestBlobstores()

        super(IetfTestRunner, self).teardown_test_environment(**kwargs)

    def validate(self, testcase):
        cwd = pathlib.Path.cwd()
        errors = []
        with tempfile.TemporaryDirectory(prefix="html-validate-") as tmpdir_name:
            tmppath = pathlib.Path(tmpdir_name)
            tmppath.chmod(0o777)
            for kind in self.batches:
                if not self.batches[kind]:
                    return
                for (name, content, fingerprint) in self.batches[kind]:
                    path = tmppath.joinpath(
                        hex(fingerprint)[2:],
                        pathlib.Path(name).relative_to(cwd)
                    )
                    pathlib.Path(path.parent).mkdir(parents=True, exist_ok=True)
                    with path.open(mode="w") as file:
                        file.write(content)
                self.batches[kind] = []

                validation_results = None
                with tempfile.NamedTemporaryFile() as stdout:
                    subprocess.run(
                        [
                            "yarn",
                            "html-validate",
                            "--formatter=json",
                            "--config=" + self.config_file[kind].name,
                            tmpdir_name,
                        ],
                        stdout=stdout,
                        stderr=stdout,
                    )

                    stdout.seek(0)
                    try:
                        validation_results = json.load(stdout)
                    except json.decoder.JSONDecodeError:
                        stdout.seek(0)
                        testcase.fail(stdout.read())

                for result in validation_results:
                    source_lines = result["source"].splitlines(keepends=True)
                    for msg in result["messages"]:
                        line = msg["line"]
                        errors.append(
                            f'\n{result["filePath"]}:\n'
                            + "".join(source_lines[line - 5 : line])
                            + " " * (msg["column"] - 1)
                            + "^" * msg["size"] + "\n"
                            + " " * (msg["column"] - 1)
                            + f'{msg["ruleId"]}: {msg["message"]} '
                            + f'on line {line}:{msg["column"]}\n'
                            + "".join(source_lines[line : line + 5])
                            + "\n"
                        )

                if validation_settings["validate_html_harder"] and kind != "frag":
                    files = [
                        os.path.join(d, f)
                        for d, dirs, files in os.walk(tmppath)
                        for f in files
                    ]
                    for file in files:
                        with open(file, "rb") as f:
                            content = f.read()
                            result = vnu_validate(content)
                            assert result
                            for msg in json.loads(result)["messages"]:
                                if vnu_filter_message(msg, False, True):
                                    continue
                                errors.append(vnu_fmt_message(file, msg, content.decode("utf-8")))
        if errors:
            testcase.fail('\n'.join(errors))

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

    # Django 5 will drop the extra_tests mechanism for the test runner. Work around
    # by adding a special label to the test suite, then injecting our extra tests
    # in load_tests_for_label()
    def build_suite(self, test_labels=None, extra_tests=None, **kwargs):
        if test_labels is None:
            # Base class sets test_labels to ["."] if it was None. The label we're
            # adding will interfere with that, so replicate that behavior here. 
            test_labels = ["."]
        test_labels = ("_ietf_extra_tests",) + tuple(test_labels)
        return super().build_suite(test_labels, extra_tests, **kwargs)

    def load_tests_for_label(self, label, discover_kwargs):
        if label == "_ietf_extra_tests":
            return self._extra_tests() or None
        return super().load_tests_for_label(label, discover_kwargs)

    def _extra_tests(self):
        """Get extra tests that should be added to the test suite"""
        tests = []
        if validation_settings["validate_html"]:
            tests += [
                TemplateValidationTests(
                    test_runner=self,
                    validate_html=self,
                    methodName='run_template_validation',
                ),
            ]
        if self.check_coverage:
            global template_coverage_collection, code_coverage_collection, url_coverage_collection
            template_coverage_collection = True
            code_coverage_collection = True
            url_coverage_collection = True
            tests += [
                PyFlakesTestCase(test_runner=self, methodName='pyflakes_test'),
                MyPyTest(test_runner=self, methodName='mypy_test'),
                #CoverageTest(test_runner=self, methodName='interleaved_migrations_test'),
                CoverageTest(test_runner=self, methodName='url_coverage_test'),
                CoverageTest(test_runner=self, methodName='template_coverage_test'),
                CoverageTest(test_runner=self, methodName='code_coverage_test'),
            ]
        return tests

    def run_suite(self, suite, **kwargs):
        failures = super(IetfTestRunner, self).run_suite(suite, **kwargs)
        while self.rerun and not failures.errors and not failures.failures:
            suite = self.build_suite(self.test_labels)
            failures = super(IetfTestRunner, self).run_suite(suite, **kwargs)
        return failures

    def run_tests(self, test_labels, extra_tests=None, **kwargs):
        # Tests that involve switching back and forth between the real
        # database and the test database are way too dangerous to run
        # against the production database
        if socket.gethostname().split('.')[0] in ['core3', 'ietfa', 'ietfb', 'ietfc', ]:
            raise EnvironmentError("Refusing to run tests on production server")

        from django.db import connection
        global old_destroy, old_create
        old_create = connection.creation.__class__.create_test_db
        connection.creation.__class__.create_test_db = safe_create_test_db
        old_destroy = connection.creation.__class__.destroy_test_db
        connection.creation.__class__.destroy_test_db = safe_destroy_test_db

        self.run_full_test_suite = not test_labels

        if not test_labels: # we only want to run our own tests
            test_labels = ["ietf"]

        self.test_apps, self.test_paths = self.get_test_paths(test_labels)

        self.test_labels = test_labels  # these are used in our run_suite() and not available to it otherwise
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
        self.replaced_settings = dict()
        if hasattr(settings, 'IDTRACKER_BASE_URL'):
            self.replaced_settings['IDTRACKER_BASE_URL'] = settings.IDTRACKER_BASE_URL
            settings.IDTRACKER_BASE_URL = self.live_server_url

    @classmethod
    def tearDownClass(cls):
        super(IetfLiveServerTestCase, cls).tearDownClass()
        set_coverage_checking(True)

    def tearDown(self):
        for k, v in self.replaced_settings.items():
            setattr(settings, k, v)
        super().tearDown()

class TestBlobstoreManager():
    # N.B. buckets and blobstore are intentional Class-level attributes
    buckets: set[Bucket] = set()

    blobstore = boto3.resource("s3",
        endpoint_url="http://blobstore:9000",
        aws_access_key_id="minio_root",
        aws_secret_access_key="minio_pass",
        aws_session_token=None,
        config = botocore.config.Config(signature_version="s3v4"),
        #config=botocore.config.Config(signature_version=botocore.UNSIGNED),
        verify=False
    )

    def createTestBlobstores(self):
        for storagename in settings.ARTIFACT_STORAGE_NAMES:
            bucketname = f"test-{storagename}"
            try:
                bucket = self.blobstore.create_bucket(Bucket=bucketname)
                self.buckets.add(bucket)
            except self.blobstore.meta.client.exceptions.BucketAlreadyOwnedByYou:
                bucket = self.blobstore.Bucket(bucketname)
                self.buckets.add(bucket)

    def destroyTestBlobstores(self):
        self.emptyTestBlobstores(destroy=True)

    def emptyTestBlobstores(self, destroy=False):
        # debug.show('f"Asked to empty test blobstores with destroy={destroy}"')
        for bucket in self.buckets:
            bucket.objects.delete()
            if destroy:
                bucket.delete()
        if destroy:
            self.buckets = set()
