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


import tempfile
import re
import email
import html5lib
import requests_mock
import shutil
import sys

from urllib.parse import unquote
from unittest.util import strclass
from bs4 import BeautifulSoup
from contextlib import contextmanager
from pathlib import Path
from tempfile import NamedTemporaryFile

import django.test
from django.conf import settings
from django.utils.text import slugify

import debug                            # pyflakes:ignore

from ietf.utils.mail import get_payload_text

real_database_name = settings.DATABASES["default"]["NAME"]

def split_url(url):
    if "?" in url:
        url, args = url.split("?", 1)
        args = dict([ list(map(unquote,arg.split("=", 1))) for arg in args.split("&") if "=" in arg ])
    else:
        args = {}
    return url, args

def login_testing_unauthorized(test_case, username, url, password=None, method='get', request_kwargs=None):
    """Test that a request is refused or redirected for login, then log in as the named user

    Defaults to making a 'get'. Set method to one of the other django.test.Client request method names
    (e.g., 'post') to change that. If that request needs arguments, pass these in request_kwargs.
    """
    request_method = getattr(test_case.client, method)
    if request_kwargs is None:
        request_kwargs = dict()
    r = request_method(url, **request_kwargs)
    test_case.assertIn(r.status_code, (302, 403))
    if r.status_code == 302:
        test_case.assertTrue("/accounts/login" in r['Location'])
    if not password:
        password = username + "+password"
    return test_case.client.login(username=username, password=password)

def unicontent(r):
    "Return a HttpResponse object's content as unicode"
    return r.content.decode(r.charset)

def textcontent(r):
    text = BeautifulSoup(r.content, 'lxml').get_text()
    text = re.sub(r'(\n\s+){2,}', '\n\n', text)
    return text

def reload_db_objects(*objects):
    """Rerequest the given arguments from the database so they're refreshed, to be used like

    foo, bar = reload_db_objects(foo, bar)"""

    t = tuple(o.__class__.objects.get(pk=o.pk) for o in objects)
    if len(objects) == 1:
        return t[0]
    else:
        return t

@contextmanager
def name_of_file_containing(contents, mode='w'):
    """Get a context with the name of an email file"""
    f = NamedTemporaryFile(mode, delete=False)
    f.write(contents)
    f.close()
    yield f.name  # hand the filename to the context
    Path(f.name).unlink()  # clean up after context exits


def assert_ical_response_is_valid(test_inst, response, expected_event_summaries=None,
                                  expected_event_uids=None, expected_event_count=None):
    """Validate an HTTP response containing iCal data

    Based on RFC5545, but not exhaustive by any means. Assumes a single iCalendar object. Checks that
    expected_event_summaries/_uids are found, but other events are allowed to be present. Specify the
    expected_event_count if you want to reject additional events. If any of these are None,
    the check for that property is skipped.
    """
    test_inst.assertEqual(response.get('Content-Type'), "text/calendar")

    # Validate iCalendar object
    test_inst.assertContains(response, 'BEGIN:VCALENDAR', count=1)
    test_inst.assertContains(response, 'END:VCALENDAR', count=1)
    test_inst.assertContains(response, 'PRODID:', count=1)
    test_inst.assertContains(response, 'VERSION', count=1)

    # Validate event objects
    event_count = 0
    uids_found = set()
    summaries_found = set()
    got_begin = False
    cur_event_props = set()
    for line_num, line in enumerate(response.content.decode().split("\n")):
        line = line.rstrip()
        if line == 'BEGIN:VEVENT':
            test_inst.assertFalse(got_begin, f"Nested BEGIN:VEVENT found on line {line_num + 1}")
            got_begin = True
        elif line == 'END:VEVENT':
            test_inst.assertTrue(got_begin, f"Unexpected END:VEVENT on line {line_num + 1}")
            test_inst.assertIn("uid", cur_event_props, f"Found END:VEVENT without UID on line {line_num + 1}")
            got_begin = False
            cur_event_props.clear()
            event_count += 1
        elif got_begin:
            # properties in an event
            if line.startswith("UID:"):
                # mandatory, not more than once
                test_inst.assertNotIn("uid", cur_event_props, f"Two UID properties in single event on line {line_num + 1}")
                cur_event_props.add("uid")
                uids_found.add(line.split(":", 1)[1])
            elif line.startswith("SUMMARY:"):
                # optional, not more than once
                test_inst.assertNotIn("summary", cur_event_props, f"Two SUMMARY properties in single event on line {line_num + 1}")
                cur_event_props.add("summary")
                summaries_found.add(line.split(":", 1)[1])

    if expected_event_summaries is not None:
        test_inst.assertCountEqual(summaries_found, set(expected_event_summaries))

    if expected_event_uids is not None:
        test_inst.assertCountEqual(uids_found, set(expected_event_uids))

    if expected_event_count is not None:
        test_inst.assertEqual(event_count, expected_event_count)

    # make sure no doubled colons after timestamp properties
    test_inst.assertNotContains(response, 'DTSTART::')
    test_inst.assertNotContains(response, 'DTEND::')
    test_inst.assertNotContains(response, 'DTSTAMP::')


class ReverseLazyTest(django.test.TestCase):
    def test_redirect_with_lazy_reverse(self):
        response = self.client.get('/ipr/update/')
        self.assertRedirects(response, "/ipr/", status_code=301)


class TestCase(django.test.TestCase):
    """IETF TestCase class

    Based on django.test.TestCase, but adds a few things:
      * asserts for html5 validation.
      * tempdir() convenience method
      * setUp() and tearDown() that override settings paths with temp directories
      * mocking the requests library to prevent dependencies on the outside network

    The setUp() and tearDown() methods create / remove temporary paths and override
    Django's settings with the temp dir names. Subclasses of this class must
    be sure to call the superclass methods if they are overridden. These are created
    anew for each test to avoid risk of cross-talk between test cases. Overriding
    the settings_temp_path_overrides class value will modify which path settings are
    replaced with temp test dirs.

    Uses requests-mock to prevent the requests library from making requests to outside
    resources. The requests-mock library allows nested mocks, so individual tests can
    ignore this. Note that the mock set up by this class will intercept any requests
    not handled by a test's inner mock - even if the latter is created with
    real_http=True.
    """
    # These settings will be overridden with empty temporary directories
    settings_temp_path_overrides = [
        'RFC_PATH',
        'INTERNET_ALL_DRAFTS_ARCHIVE_DIR',
        'INTERNET_DRAFT_ARCHIVE_DIR',
        'INTERNET_DRAFT_PATH',
        'BIBXML_BASE_PATH',
        'FTP_DIR',
    ]

    parser = html5lib.HTMLParser(strict=True)

    def assertValidHTML(self, data):
        try:
            self.parser.parse(data)
        except Exception as e:
            raise self.failureException(str(e))

    def assertValidHTMLResponse(self, resp):
        self.assertHttpOK(resp)
        self.assertTrue(resp['Content-Type'].startswith('text/html'))
        self.assertValidHTML(resp.content)

    def assertSameEmail(self, a, b, msg=None):
        def normalize(x):
            if x:
                if not isinstance(x, list):
                    x = [ x ]
                x = email.utils.getaddresses(x)
                x.sort()
            return x
        return self.assertEqual(normalize(a), normalize(b), msg)

    def tempdir(self, label):
        slug = slugify(self.__class__.__name__.replace('.','-'))
        suffix = "-{label}-{slug}-dir".format(**locals())
        return tempfile.mkdtemp(suffix=suffix)

    def assertNoFormPostErrors(self, response, error_css_selector=".is-invalid"):
        """Try to fish out form errors, if none found at least check the
        status code to be a redirect.

        Assumptions:
         - a POST is followed by a 302 redirect
         - form errors can be found with a simple CSS selector

        """

        if response.status_code == 200:
            from pyquery import PyQuery
            from lxml import html
            self.maxDiff = None

            errors = [html.tostring(n).decode() for n in PyQuery(response.content)(error_css_selector)]
            if errors:
                explanation = "{} != {}\nGot form back with errors:\n----\n".format(response.status_code, 302) + "----\n".join(errors)
                self.assertEqual(response.status_code, 302, explanation)

        self.assertEqual(response.status_code, 302)
        
    def assertMailboxContains(self, mailbox, subject=None, text=None, count=None):
        """
        Asserts that the given mailbox contains *count* mails with the given
        *subject* and body *text* (if not None).  At least one of subject,
        text, and count must be different from None.  If count is None, the
        filtered mailbox must be non-empty.
        """
        if subject is None and text is None and count is None:
            raise self.failureException("No assertion made, both text and count is None")
        mlist = mailbox
        if subject:
            mlist = [ m for m in mlist if subject in m["Subject"] ]
        if text:
            assert isinstance(text, str)
            mlist = [ m for m in mlist if text in get_payload_text(m) ]
        if count and len(mlist) != count:
            sys.stderr.write("Wrong count in assertMailboxContains().  The complete mailbox contains %s messages, only %s of them contain the searched-for text:\n\n" % (len(mailbox), len(mlist)))
            for m in mailbox:
                sys.stderr.write(m.as_string())
                sys.stderr.write('\n\n')
        if count:
            self.assertEqual(len(mlist), count)
        else:
            self.assertGreater(len(mlist), 0)

    def __str__(self):
        return u"%s (%s.%s)" % (self._testMethodName, strclass(self.__class__),self._testMethodName)

    def setUp(self):
        super().setUp()

        # Prevent the requests library from making live requests during tests
        self.requests_mock = requests_mock.Mocker()
        self.requests_mock.start()

        # Replace settings paths with temporary directories.
        self._ietf_temp_dirs = {}  # trashed during tearDown, DO NOT put paths you care about in this
        for setting in set(self.settings_temp_path_overrides):
            self._ietf_temp_dirs[setting] = self.tempdir(slugify(setting))
        self._ietf_saved_context = django.test.utils.override_settings(**self._ietf_temp_dirs)
        self._ietf_saved_context.enable()

    def tearDown(self):
        self._ietf_saved_context.disable()
        for dir in self._ietf_temp_dirs.values():
            shutil.rmtree(dir)
        self.requests_mock.stop()
        super().tearDown()
