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

import socket, re, os, time, importlib
import warnings
import coverage

from django.conf import settings
from django.template import TemplateDoesNotExist
from django.test.runner import DiscoverRunner
from django.core.management import call_command

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

def get_url_patterns(module):
    res = []
    try:
        patterns = module.urlpatterns
    except AttributeError:
        patterns = []
    for item in patterns:
        try:
            subpatterns = get_url_patterns(item.urlconf_module)
        except:
            subpatterns = [("", None)]
        for sub, subitem in subpatterns:
            if not sub:
                res.append((item.regex.pattern, item))
            elif sub.startswith("^"):
                res.append((item.regex.pattern + sub[1:], subitem))
            else:
                res.append((item.regex.pattern + ".*" + sub, subitem))
    return res

def check_url_coverage(verbosity):
    import ietf.urls

    url_patterns = get_url_patterns(ietf.urls)

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

    covered = set()
    for url in visited_urls:
        for regex, compiled in patterns:
            if regex not in covered and compiled.match(url[1:]): # strip leading /
                covered.add(regex)
                break

    missing = list(set(regex for regex, compiled in patterns) - covered)

    if missing and verbosity > 1:
        print "The following URL patterns were not tested"
        for pattern in sorted(missing):
            print "     Not tested", pattern

def get_templates():
    templates = set()
    # Should we teach this to use TEMPLATE_DIRS?
    templatepath = os.path.join(settings.BASE_DIR, "templates")
    for root, dirs, files in os.walk(templatepath):
        if ".svn" in dirs:
            dirs.remove(".svn")
        relative_path = root[len(templatepath)+1:]
        for file in files:
            if file.endswith("~") or file.startswith("#"):
                continue
            if relative_path == "":
                templates.add(file)
            else:
                templates.add(os.path.join(relative_path, file))
    return templates

def check_template_coverage(verbosity):
    all_templates = get_templates()

    not_loaded = list(all_templates - loaded_templates)
    if not_loaded and verbosity > 1:
        print "The following templates were never loaded during test"
        for t in sorted(not_loaded):
            print "     Not loaded", t

def save_test_results(failures, test_labels):
    # Record the test result in a file, in order to be able to check the
    # results and avoid re-running tests if we've alread run them with OK
    # result after the latest code changes:
    import ietf.settings as config
    topdir = os.path.dirname(os.path.dirname(config.__file__))
    tfile = open(os.path.join(topdir,"testresult"), "a")
    timestr = time.strftime("%Y-%m-%d %H:%M:%S")
    if failures:
        tfile.write("%s FAILED (failures=%s)\n" % (timestr, failures))
    else:
        if test_labels:
            tfile.write("%s SUCCESS (tests=%s)\n" % (timestr, test_labels))
        else:
            tfile.write("%s OK\n" % (timestr, ))
    tfile.close()


class IetfTestRunner(DiscoverRunner):
    def test_code_coverage(self):
        pass

    def run_tests(self, test_labels, extra_tests=None, **kwargs):
        # Tests that involve switching back and forth between the real
        # database and the test database are way too dangerous to run
        # against the production database
        if socket.gethostname().split('.')[0] in ['core3', 'ietfa', 'ietfb', 'ietfc', ]:
            raise EnvironmentError("Refusing to run tests on production server")
        ietf.utils.mail.test_mode = True
        ietf.utils.mail.SMTP_ADDR['ip4'] = '127.0.0.1'
        ietf.utils.mail.SMTP_ADDR['port'] = 2025

        global old_destroy, old_create, test_database_name
        from django.db import connection
        old_create = connection.creation.__class__.create_test_db
        connection.creation.__class__.create_test_db = safe_create_1
        old_destroy = connection.creation.__class__.destroy_test_db
        connection.creation.__class__.destroy_test_db = safe_destroy_0_1

        do_template_coverage = not test_labels
        do_url_coverage = not test_labels
        do_code_coverage = True
        
        if do_template_coverage:
            settings.TEMPLATE_LOADERS = ('ietf.utils.test_runner.template_coverage_loader',) + settings.TEMPLATE_LOADERS
        if do_url_coverage:
            settings.MIDDLEWARE_CLASSES = ('ietf.utils.test_runner.RecordUrlsMiddleware',) + settings.MIDDLEWARE_CLASSES
        if do_code_coverage:
            import ietf.settings as config
            sources = [ os.path.dirname(config.__file__), ]
            code_coverage = coverage.coverage(source=sources, cover_pylib=False,
                omit = ['^0*'])
            code_coverage.start()

        if not test_labels: # we only want to run our own tests
            test_labels = [app for app in settings.INSTALLED_APPS if app.startswith("ietf")]

        if settings.SITE_ID != 1:
            print "     Changing SITE_ID to '1' during testing."
            settings.SITE_ID = 1

        if settings.TEMPLATE_STRING_IF_INVALID != '':
            print "     Changing TEMPLATE_STRING_IF_INVALID to '' during testing."
            settings.TEMPLATE_STRING_IF_INVALID = ''

        assert not settings.IDTRACKER_BASE_URL.endswith('/')

        smtpd_driver = SMTPTestServerDriver((ietf.utils.mail.SMTP_ADDR['ip4'],ietf.utils.mail.SMTP_ADDR['port']),None) 
        smtpd_driver.start()

        try:
            failures = super(IetfTestRunner, self).run_tests(test_labels, extra_tests=extra_tests, **kwargs)
        finally:
            smtpd_driver.stop()

        if do_template_coverage and not failures:
            check_template_coverage(self.verbosity)
        if do_url_coverage and not failures:
            check_url_coverage(self.verbosity)
        if do_code_coverage and not failures:
            code_coverage.stop()
            code_coverage.save()
            code_coverage_pct = code_coverage.report(file="coverage.txt")
            print("Code coverage: %6.3f%%.  Details written to coverage.txt" % code_coverage_pct)
#             with open("sysinfo.txt", "w") as file:
#                 import pprint
#                 pprint.pprint(code_coverage.sysinfo(), file)
#                 print("Sysinfo written to sysinfo.txt")
        if (do_template_coverage or do_url_coverage or do_code_coverage) and not failures:
            print "0 test failures - coverage shown above"

        save_test_results(failures, test_labels)

        return failures
