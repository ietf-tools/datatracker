# Copyright The IETF Trust 2014-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import datetime
import io
import json
import lxml.etree
import os.path
import pytz
import shutil
import types

from mock import call, patch
from pyquery import PyQuery
from typing import Dict, List       # pyflakes:ignore

from email.message import Message
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from fnmatch import fnmatch
from importlib import import_module
from textwrap import dedent
from tempfile import mkdtemp

from django.apps import apps
from django.contrib.auth.models import User
from django.conf import settings
from django.forms import Form
from django.template import Context
from django.template import Template    # pyflakes:ignore
from django.template.defaulttags import URLNode
from django.template.loader import get_template, render_to_string
from django.templatetags.static import StaticNode
from django.test import RequestFactory
from django.urls import reverse as urlreverse

import debug                            # pyflakes:ignore

from ietf.admin.sites import AdminSite
from ietf.person.name import name_parts, unidecode_name
from ietf.submit.tests import submission_file
from ietf.utils.draft import PlaintextDraft, getmeta
from ietf.utils.fields import SearchableField
from ietf.utils.log import unreachable, assertion
from ietf.utils.mail import (
    send_mail_preformatted,
    send_mail_text,
    send_mail_mime,
    outbox,
    get_payload_text,
    decode_header_value,
    show_that_mail_was_sent,
)
from ietf.utils.test_runner import get_template_paths, set_coverage_checking
from ietf.utils.test_utils import TestCase, unicontent
from ietf.utils.text import parse_unicode
from ietf.utils.timezone import timezone_not_near_midnight
from ietf.utils.xmldraft import XMLDraft

class SendingMail(TestCase):

    def test_send_mail_preformatted(self):
        msg = """To: to1@example.com, to2@example.com
From: from1@ietf.org
Cc: cc1@example.com, cc2@example.com
Bcc: bcc1@example.com, bcc2@example.com
Subject: subject

body
"""
        send_mail_preformatted(None, msg, {}, {})
        recv = outbox[-1]
        self.assertSameEmail(recv['To'], '<to1@example.com>, <to2@example.com>')
        self.assertSameEmail(recv['From'], 'from1@ietf.org')
        self.assertSameEmail(recv['Cc'], 'cc1@example.com, cc2@example.com')
        self.assertSameEmail(recv['Bcc'], None)
        self.assertEqual(recv['Subject'], 'subject')
        self.assertEqual(get_payload_text(recv), 'body\n')

        override = {
            'To': 'oto1@example.net, oto2@example.net',
            'From': 'ofrom1@ietf.org',
            'Cc': 'occ1@example.net, occ2@example.net',
            'Subject': 'osubject',
        }
        send_mail_preformatted(request=None, preformatted=msg, extra={}, override=override)
        recv = outbox[-1]
        self.assertSameEmail(recv['To'], '<oto1@example.net>, <oto2@example.net>')
        self.assertSameEmail(recv['From'], 'ofrom1@ietf.org')
        self.assertSameEmail(recv['Cc'], 'occ1@example.net, occ2@example.net')
        self.assertSameEmail(recv['Bcc'], None)
        self.assertEqual(recv['Subject'], 'osubject')
        self.assertEqual(recv.get_payload(), 'body\n')

        override = {
            'To': ['<oto1@example.net>', 'oto2@example.net'],
            'From': ['<ofrom1@ietf.org>'],
            'Cc': ['<occ1@example.net>', 'occ2@example.net'],
            'Subject': 'osubject',
        }
        send_mail_preformatted(request=None, preformatted=msg, extra={}, override=override)
        recv = outbox[-1]
        self.assertSameEmail(recv['To'], '<oto1@example.net>, <oto2@example.net>')
        self.assertSameEmail(recv['From'], '<ofrom1@ietf.org>')
        self.assertSameEmail(recv['Cc'], '<occ1@example.net>, occ2@example.net')
        self.assertSameEmail(recv['Bcc'], None)
        self.assertEqual(recv['Subject'], 'osubject')
        self.assertEqual(get_payload_text(recv), 'body\n')

        extra = {'Fuzz': [ 'bucket' ]}
        send_mail_preformatted(request=None, preformatted=msg, extra=extra, override={})
        recv = outbox[-1]
        self.assertEqual(recv['Fuzz'], 'bucket')

        extra = {'Fuzz': ['bucket','monger']}
        send_mail_preformatted(request=None, preformatted=msg, extra=extra, override={})
        recv = outbox[-1]
        self.assertEqual(recv['Fuzz'], 'bucket, monger')


class MailUtilsTests(TestCase):
    def test_decode_header_value(self):
        self.assertEqual(
            decode_header_value("cake"),
            "cake",
            "decodes simple string value",
        )
        self.assertEqual(
            decode_header_value("=?utf-8?b?8J+Ogg==?="),
            "\U0001f382",
            "decodes single utf-8-encoded part",
        )
        self.assertEqual(
            decode_header_value("=?utf-8?b?8J+Ogg==?= = =?macintosh?b?jYxrjg==?="),
            "\U0001f382 = çåké",
            "decodes a value with non-utf-8 encodings",
        )

    # Patch in a side_effect so we can distinguish values that came from decode_header_value.
    @patch("ietf.utils.mail.decode_header_value", side_effect=lambda s: f"decoded-{s}")
    @patch("ietf.utils.mail.messages")
    def test_show_that_mail_was_sent(self, mock_messages, mock_decode_header_value):
        request = RequestFactory().get("/some/path")
        request.user = object()  # just needs to exist
        msg = Message()
        msg["To"] = "to-value"
        msg["Subject"] = "subject-value"
        msg["Cc"] = "cc-value"
        with patch("ietf.ietfauth.utils.has_role", return_value=True):
            show_that_mail_was_sent(request, "mail was sent", msg, "bcc-value")
        self.assertCountEqual(
            mock_decode_header_value.call_args_list,
            [call("to-value"), call("subject-value"), call("cc-value"), call("bcc-value")],
        )
        self.assertEqual(mock_messages.info.call_args[0][0], request)
        self.assertIn("mail was sent", mock_messages.info.call_args[0][1])
        self.assertIn("decoded-subject-value", mock_messages.info.call_args[0][1])
        self.assertIn("decoded-to-value", mock_messages.info.call_args[0][1])
        self.assertIn("decoded-cc-value", mock_messages.info.call_args[0][1])
        self.assertIn("decoded-bcc-value", mock_messages.info.call_args[0][1])
        mock_messages.reset_mock()
        mock_decode_header_value.reset_mock()

        # no bcc
        with patch("ietf.ietfauth.utils.has_role", return_value=True):
            show_that_mail_was_sent(request, "mail was sent", msg, None)
        self.assertCountEqual(
            mock_decode_header_value.call_args_list,
            [call("to-value"), call("subject-value"), call("cc-value")],
        )
        self.assertEqual(mock_messages.info.call_args[0][0], request)
        self.assertIn("mail was sent", mock_messages.info.call_args[0][1])
        self.assertIn("decoded-subject-value", mock_messages.info.call_args[0][1])
        self.assertIn("decoded-to-value", mock_messages.info.call_args[0][1])
        self.assertIn("decoded-cc-value", mock_messages.info.call_args[0][1])
        # Note: here and below - when using assertNotIn(), leaving off the "decoded-" prefix
        # proves that neither the original value nor the decoded value appear.
        self.assertNotIn("bcc-value", mock_messages.info.call_args[0][1])
        mock_messages.reset_mock()
        mock_decode_header_value.reset_mock()

        # no cc
        del msg["Cc"]
        with patch("ietf.ietfauth.utils.has_role", return_value=True):
            show_that_mail_was_sent(request, "mail was sent", msg, None)
        self.assertCountEqual(
            mock_decode_header_value.call_args_list,
            [call("to-value"), call("subject-value")],
        )
        self.assertEqual(mock_messages.info.call_args[0][0], request)
        self.assertIn("mail was sent", mock_messages.info.call_args[0][1])
        self.assertIn("decoded-subject-value", mock_messages.info.call_args[0][1])
        self.assertIn("decoded-to-value", mock_messages.info.call_args[0][1])
        self.assertNotIn("cc-value", mock_messages.info.call_args[0][1])
        self.assertNotIn("bcc-value", mock_messages.info.call_args[0][1])
        mock_messages.reset_mock()
        mock_decode_header_value.reset_mock()

        # no to
        del msg["To"]
        with patch("ietf.ietfauth.utils.has_role", return_value=True):
            show_that_mail_was_sent(request, "mail was sent", msg, None)
        self.assertCountEqual(
            mock_decode_header_value.call_args_list,
            [call("[no to]"), call("subject-value")],
        )
        self.assertEqual(mock_messages.info.call_args[0][0], request)
        self.assertIn("mail was sent", mock_messages.info.call_args[0][1])
        self.assertIn("decoded-subject-value", mock_messages.info.call_args[0][1])
        self.assertIn("decoded-[no to]", mock_messages.info.call_args[0][1])
        self.assertNotIn("to-value", mock_messages.info.call_args[0][1])
        self.assertNotIn("cc-value", mock_messages.info.call_args[0][1])
        self.assertNotIn("bcc-value", mock_messages.info.call_args[0][1])
        mock_messages.reset_mock()
        mock_decode_header_value.reset_mock()

        # no subject
        del msg["Subject"]
        with patch("ietf.ietfauth.utils.has_role", return_value=True):
            show_that_mail_was_sent(request, "mail was sent", msg, None)
        self.assertCountEqual(
            mock_decode_header_value.call_args_list,
            [call("[no to]"), call("[no subject]")],
        )
        self.assertEqual(mock_messages.info.call_args[0][0], request)
        self.assertIn("mail was sent", mock_messages.info.call_args[0][1])
        self.assertIn("decoded-[no subject]", mock_messages.info.call_args[0][1])
        self.assertNotIn("subject-value", mock_messages.info.call_args[0][1])
        self.assertIn("decoded-[no to]", mock_messages.info.call_args[0][1])
        self.assertNotIn("to-value", mock_messages.info.call_args[0][1])
        self.assertNotIn("cc-value", mock_messages.info.call_args[0][1])
        self.assertNotIn("bcc-value", mock_messages.info.call_args[0][1])
        mock_messages.reset_mock()
        mock_decode_header_value.reset_mock()
        
        # user does not have role
        with patch("ietf.ietfauth.utils.has_role", return_value=False):
            show_that_mail_was_sent(request, "mail was sent", msg, None)
        self.assertFalse(mock_messages.called)
        
        # no user
        request.user = None
        with patch("ietf.ietfauth.utils.has_role", return_value=True) as mock_has_role:
            show_that_mail_was_sent(request, "mail was sent", msg, None)
        self.assertFalse(mock_messages.called)
        self.assertFalse(mock_has_role.called)


class TestSMTPServer(TestCase):

    def test_address_rejected(self):

        def send_simple_mail(to):
            send_mail_text(None, to=to, frm=None, subject="Test for rejection", txt="dummy body")

        len_before = len(outbox)
        send_simple_mail('good@example.com,poison@example.com')
        self.assertEqual(len(outbox),len_before+2)
        self.assertTrue('Some recipients were refused' in outbox[-1]['Subject'])

        len_before = len(outbox)
        send_simple_mail('poison@example.com')
        self.assertEqual(len(outbox),len_before+2)
        self.assertTrue('error while sending email' in outbox[-1]['Subject'])
        
    def test_rejecting_complex_mail(self):

        def send_complex_mail(to):
            msg = MIMEMultipart()
            textpart= MIMEText(dedent("""\
                             Sometimes people send mail with things like “smart quotes” in them.
                             Sometimes they have attachments with pictures.
                              """),_charset='utf-8')
            msg.attach(textpart)
            img = MIMEImage(b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x10\x00\x00\x00\x10\x08\x06\x00\x00\x00\x1f\xf3\xffa\x00\x00\x02\x88IDATx\xda\xa5\x93\xcbO\x13Q\x14\xc6\xbf\xb9\xd32}L\x9fZ\x06\x10Q\x90\x10\x85b\x89\xfe\x01\x06BXK"\xd4hB\xdc\xa0\x06q\xe1c% H1l\xd0\x8dbT6\x1a5\x91\x12#K\x891\xf2\x07\x98\xc8[L\x1ay\xa8@\xdb\xd0\xd2\xe9\x83N;\xbdc\x1f\x11\x03\x04\x17zW\'_\xce\xf9\xdd\xef\x9c\x9c\xc3\xe0?\x1f\xb3S\xf8\xfe\xba\xc2Be\xa9]m\xd6\x9e\xe6x\xde\x9e\xd1\xa4HdF\x0e\xc5G\x89\x8a{X\xec\xfc\x1a\xdc\x1307X\xd4$T\nC\xc6\xfc|\x13\x8d\xa6\x00\xe5O\x16\xd1\xb3\x10}\xbe\x90w\xce\xdbZyeed\x17\xc03(4\x15\x9d(s\x13\xca!\x10\xa6\xb0\x1a\xb6\x9b\x0b\x84\x95\xb4F@\x89\x84\xe5O\x0b\xcdG\xaf\xae\x8dl\x01V\x9f\x1d\xb4q\x16\xde\xa33[\x8d\xe3\x93)\xdc\x7f\x9b\xc4\xf3\x1b\x1c,|\xaex#\n\xb4\x0cH\xb8\xd6\xa8F\xad\x83El# \xc6\x83\xb1\xf2\xa2\x0bK\xfe,`y\xd0\xe6*<V\xda\x99\x92\x15\xb8\xdc\x14\xef>\x03\xaes\x0c\xea\xaas.\xc6g\x14t\xbcR\xd0P\x03t;\tX\x15\x83\xd5\xf9\xc5\xbe\x926_W6\xe3\xe7ca\xc2Z,82\xb1\xeb\r\x8b\xb1)\x82\xde\xa6\x14\xea\xec4\x0b\xf88K\xd0\xe5fQ_M\xd1s&\x95k\xe9\x87w\xf2\xc0eoM\x16\xe0\x1b*\xdc4XM\x9aL\xfca\x8e\xc5\xbd1\x0e//\xc6`\xd5\xe7Z\x08\xa6[8\xffT\x87\xeb\r\x12\xea\xabr\x80p \x14\xcfo]\xd5f\x01k\x8fl\x9bF3\xaf\xf9=\xb0X\x82\x81.O\xd96\xc4\x9d\x9a\xb8\x11\x89\x17\xb4\xf9s\x80\xe5\x01\xc3\xc4\xfe}FG\\\x064\xaa\xbf/\x0eM3\x92i\x13\xe1\x908Yr3\x9ck\xe1[\xbf\xd6%X\xf4\x9d\xef=z$(\xc1\xa9\xc3Q\xf0\x1c\xddV(\xa7\x18Ly9L\xafq8{\\D0\x14\xbd{\xe4V\xac3\x0bX\xe8\xd7\xdb\xb4,\xf5\x18\xb4j\xe3\xf8\xa2\x1e/\xa6\xac`\x18\x06\x02\x9f\x84\x8a\xa4\x07\x16c\xb1\xbe\xc9\xa2\xf6P\x04-\x8e\x00\x12\xc9\x84(&\xd9\xf2\x8a\x8e\x88\x7fk[\xbet\xe75\x0bzf\x98cI\xd6\xe6\xfc\xba\x06\xd3~\x1d\x12\xe9\x9fK\xcd\x12N\x16\xc4\xa0UQH)\x8a\x95\x08\x9c\xf6^\xc9\xbdk\x95\xe7o\xab\x9c&\xb5\xf2\x84W3\xa6\x9dG\x92\x19_$\xa9\x84\xd6%r\xc9\xde\x97\x1c\xde\xf3\x98\x96\xee\xb0\x16\x99\xd2v\x15\x94\xc6<\xc2Te\xb4\x04Ufe\x85\x8c2\x84<(\xeb\x91\xf7>\xa6\x7fy\xbf\x00\x96T\xff\x11\xf7\xd8R\xb9\x00\x00\x00\x00IEND\xaeB`\x82')

            msg.attach(img)
            send_mail_mime(request=None, to=to, frm=settings.DEFAULT_FROM_EMAIL, subject='это сложно', msg=msg, cc=None, extra=None)

        len_before = len(outbox)
        send_complex_mail('good@example.com')
        self.assertEqual(len(outbox),len_before+1)

        len_before = len(outbox)
        send_complex_mail('good@example.com,poison@example.com')
        self.assertEqual(len(outbox),len_before+2)


def get_callbacks(urllist, namespace=None):
    callbacks = set()
    def qualified(name):
        return '%s:%s' % (namespace, name) if namespace else name
    for entry in urllist:
        if hasattr(entry, 'url_patterns'):
            callbacks.update(get_callbacks(entry.url_patterns, entry.namespace))
        else:
            if hasattr(entry, '_callback_str'):
                callbacks.add(qualified(entry._callback_str))
            if (hasattr(entry, 'callback') and entry.callback and
                type(entry.callback) in [types.FunctionType, types.MethodType ]):
                    callbacks.add(qualified("%s.%s" % (entry.callback.__module__, entry.callback.__name__)))
            if hasattr(entry, 'name') and entry.name:
                callbacks.add(qualified(entry.name))
            if hasattr(entry, 'lookup_str') and entry.lookup_str:
                callbacks.add(qualified(entry.lookup_str))
            # There are some entries we don't handle here, mostly classes
            # (such as Feed subclasses)

    return list(callbacks)

class TemplateChecksTestCase(TestCase):

    paths = []                          # type: List[str]
    templates = {}                      # type: Dict[str, Template]

    def setUp(self):
        super().setUp()
        set_coverage_checking(False)
        self.paths = list(get_template_paths())
        self.paths.sort()
        for path in self.paths:
            try:
                self.templates[path] = get_template(path).template
            except Exception:
                pass

    def tearDown(self):
        set_coverage_checking(True)
        super().tearDown()

    def test_parse_templates(self):
        errors = []
        for path in self.paths:
            for pattern in settings.TEST_TEMPLATE_IGNORE:
                if fnmatch(path, pattern):
                    continue
            if not path in self.templates:

                try:
                    get_template(path)
                except Exception as e:
                    errors.append((path, e))
        if errors:
            messages = [ "Parsing template '%s' failed with error: %s" % (path, ex) for (path, ex) in errors ]
            raise self.failureException("Template parsing failed for %s templates:\n  %s" % (len(errors), "\n  ".join(messages)))

    def apply_template_test(self, func, node_type, msg, *args, **kwargs):
        errors = []
        for path, template in self.templates.items():
            origin = str(template.origin).replace(settings.BASE_DIR, '')
            for node in template.nodelist:
                for child in node.get_nodes_by_type(node_type):
                    errors += func(child, origin, *args, **kwargs)
        if errors:
            errors = list(set(errors))
            errors.sort()
            messages = [ msg % (k, v) for (k, v) in errors ]
            raise self.failureException("Found %s errors when trying to %s:\n  %s" %(len(errors), func.__name__.replace('_',' '), "\n  ".join(messages)))

    def test_template_url_lookup(self):
        """
        This test doesn't do full url resolving, using the appropriate contexts, as it
        simply doesn't have any context to use.  It only looks if there exists a URL
        pattern with the appropriate callback, callback string, or name.  If no matching
        urlconf can be found, a full resolution would also fail.
        """
        #
        import ietf.urls

        def check_that_url_tag_callbacks_exists(node, origin, callbacks):
            """
            Check that an URLNode's callback is in callbacks.
            """
            cb = node.view_name.token.strip("\"'")
            if cb in callbacks or cb.startswith("admin:"):
                return []
            else:
                return [ (origin, cb), ]
        #

        callbacks = get_callbacks(ietf.urls.urlpatterns)
        self.apply_template_test(check_that_url_tag_callbacks_exists, URLNode, 'In %s: Could not find urlpattern for "%s"', callbacks)

    def test_template_statics_exists(self):
        """
        This test checks that every static template tag found in the template files found
        by utils.test_runner.get_template_paths() actually resolves to a file that can be
        served.  If collectstatic is correctly set up and used, the results should apply
        to both development and production mode.
        """
        #
        def check_that_static_tags_resolve(node, origin, checked):
            """
            Check that a StaticNode resolves to an url that can be served.
            """
            url = node.render(Context((), {}))
            if url in checked:
                return []
            else:
                r = self.client.get(url)
                if r.status_code == 200:
                    checked[url] = origin
                    return []
                else:
                    return [(origin, url), ]
        #
        checked = {}
        # the test client will only return static files when settings.DEBUG is True:
        saved_debug = settings.DEBUG
        settings.DEBUG = True
        self.apply_template_test(check_that_static_tags_resolve, StaticNode, 'In %s: Could not find static file for "%s"', checked)
        settings.DEBUG = saved_debug

    def test_500_page(self):
        url = urlreverse('django.views.defaults.server_error')
        r = self.client.get(url)        
        self.assertTemplateUsed(r, '500.html')

class BaseTemplateTests(TestCase):
    base_template = 'base.html'

    def test_base_template_includes_ietf_js(self):
        content = render_to_string(self.base_template, {})
        pq = PyQuery(content)
        self.assertTrue(
            pq('head > script[src$="ietf/js/ietf.js"]'),
            'base template should include ietf.js',
        )

    def test_base_template_righthand_nav(self):
        """The base template provides an automatic righthand navigation panel

        This is provided by ietf.js and requires the ietf-auto-nav class and a parent with the row class
        or the nav widget will not render properly.
        """
        content = render_to_string(self.base_template, {})
        pq = PyQuery(content)
        self.assertTrue(
            pq('.row > #content.ietf-auto-nav'),
            'base template should have a #content element with .ietf-auto-nav class and .row parent',
        )

OMITTED_APPS = [
    'ietf.secr.meetings',
    'ietf.secr.proceedings',
    'ietf.redirects',
]

class AdminTestCase(TestCase):
    def __init__(self, *args, **kwargs):
        self.apps = {}
        for app_name in settings.INSTALLED_APPS:
            if app_name.startswith('ietf') and not app_name in OMITTED_APPS:
                app = import_module(app_name)
                name = app_name.split('.',1)[-1]
                models_path = os.path.join(os.path.dirname(app.__file__), "models.py")
                if os.path.exists(models_path):
                    self.apps[name] = app_name
        super(AdminTestCase, self).__init__(*args, **kwargs)

    def test_all_model_admins_exist(self):

        User.objects.create_superuser('admin', 'admin@example.org', 'admin+password')
        self.client.login(username='admin', password='admin+password')
        rtop = self.client.get("/admin/")
        self.assertContains(rtop, AdminSite.site_header())
        for name in self.apps:
            app_name = self.apps[name]
            self.assertContains(rtop, name)
            app = import_module(app_name)
            r = self.client.get('/admin/%s/'%name)
            #
            model_list = apps.get_app_config(name).get_models()
            for model in model_list:
                if model.__name__.startswith('Historical') and hasattr(model, "get_history_type_display"):
                    continue
                else:
                    self.assertContains(r, model._meta.model_name,
                        msg_prefix="There doesn't seem to be any admin API for model %s.models.%s"%(app.__name__,model.__name__,))

class PlaintextDraftTests(TestCase):

    def setUp(self):
        super().setUp()
        file,_ = submission_file(name_in_doc='draft-test-draft-class-00', name_in_post='draft-test-draft-class-00.txt',templatename='test_submission.txt',group=None)
        self.draft = PlaintextDraft(text=file.getvalue(), source='draft-test-draft-class-00.txt', name_from_source=False)

    def test_get_status(self):
        self.assertEqual(self.draft.get_status(),'Informational')
    
    def test_get_authors(self):
        self.assertTrue(all([u'@' in author for author in self.draft.get_authors()]))

    def test_get_authors_with_firm(self):
        self.assertTrue(all([u'@' in author for author in self.draft.get_authors_with_firm()]))
        
    def test_old_get_refs(self):
        self.assertEqual(self.draft.old_get_refs()[1][0],u'rfc2119')

    def test_get_meta(self):
        tempdir = mkdtemp()
        filename = os.path.join(tempdir,self.draft.source)
        with io.open(filename,'w') as file:
            file.write(self.draft.text)
        self.assertEqual(getmeta(filename)['docdeststatus'],'Informational')
        shutil.rmtree(tempdir)


class XMLDraftTests(TestCase):
    def test_get_refs_v3(self):
        draft = XMLDraft('ietf/utils/test_draft_with_references_v3.xml')
        self.assertEqual(
            draft.get_refs(),
            {
                'rfc1': XMLDraft.REF_TYPE_NORMATIVE,
                'rfc2': XMLDraft.REF_TYPE_NORMATIVE,
                'draft-wood-key-consistency-03': XMLDraft.REF_TYPE_INFORMATIVE,
                'rfc255': XMLDraft.REF_TYPE_INFORMATIVE,
                'bcp6': XMLDraft.REF_TYPE_INFORMATIVE,
                'bcp14': XMLDraft.REF_TYPE_INFORMATIVE,
                'rfc1207': XMLDraft.REF_TYPE_UNKNOWN,
                'rfc4086': XMLDraft.REF_TYPE_NORMATIVE,
                'draft-ietf-teas-pcecc-use-cases-00': XMLDraft.REF_TYPE_INFORMATIVE,
                'draft-ietf-teas-pcecc-use-cases': XMLDraft.REF_TYPE_INFORMATIVE,
                'draft-ietf-sipcore-multiple-reasons-00': XMLDraft.REF_TYPE_INFORMATIVE,
                'draft-ietf-sipcore-multiple-reasons': XMLDraft.REF_TYPE_INFORMATIVE,
            }
        )

    def test_get_refs_v2(self):
        draft = XMLDraft('ietf/utils/test_draft_with_references_v2.xml')
        self.assertEqual(
            draft.get_refs(),
            {
                'rfc1': XMLDraft.REF_TYPE_NORMATIVE,
                'rfc255': XMLDraft.REF_TYPE_INFORMATIVE,
                'bcp6': XMLDraft.REF_TYPE_INFORMATIVE,
                'rfc1207': XMLDraft.REF_TYPE_UNKNOWN,
            }
        )

    def test_parse_creation_date(self):
        # override date_today to avoid skew when test runs around midnight
        today = datetime.date.today()
        with patch("ietf.utils.xmldraft.date_today", return_value=today):
            # Note: using a dict as a stand-in for XML elements, which rely on the get() method
            self.assertEqual(
                XMLDraft.parse_creation_date({"year": "2022", "month": "11", "day": "24"}),
                datetime.date(2022, 11, 24),
                "Fully specified date should be parsed",
            )
            self.assertEqual(
                XMLDraft.parse_creation_date(None), None, "return None if input is None"
            )
            # Cases where the date is empty - missing fields or fields filled in with blank strings.
            self.assertEqual(XMLDraft.parse_creation_date({}), today)
            self.assertEqual(XMLDraft.parse_creation_date({"day": ""}), today)
            self.assertEqual(XMLDraft.parse_creation_date({}), today)
            self.assertEqual(XMLDraft.parse_creation_date({"year": ""}), today)
            self.assertEqual(XMLDraft.parse_creation_date({"month": ""}), today)
            self.assertEqual(XMLDraft.parse_creation_date({"day": ""}), today)
            self.assertEqual(XMLDraft.parse_creation_date({"year": "", "month": ""}), today)
            self.assertEqual(XMLDraft.parse_creation_date({"year": "", "day": ""}), today)
            self.assertEqual(XMLDraft.parse_creation_date({"month": "", "day": ""}), today)
            self.assertEqual(
                XMLDraft.parse_creation_date({"year": "", "month": "", "day": ""}), today
            )
            self.assertEqual(
                XMLDraft.parse_creation_date(
                    {"year": str(today.year), "month": str(today.month), "day": ""}
                ),
                today,
            )
            # When year/month do not match, day should be 15th of the month
            self.assertEqual(
                XMLDraft.parse_creation_date(
                    {"year": str(today.year - 1), "month": str(today.month), "day": ""}
                ),
                datetime.date(today.year - 1, today.month, 15),
            )
            self.assertEqual(
                XMLDraft.parse_creation_date(
                    {
                        "year": str(today.year),
                        "month": "1" if today.month != 1 else "2",
                        "day": "",
                    }
                ),
                datetime.date(today.year, 1 if today.month != 1 else 2, 15),
            )

    def test_parse_docname(self):
        with self.assertRaises(ValueError) as cm:
            XMLDraft.parse_docname(lxml.etree.Element("xml"))  # no docName
        self.assertIn("Missing docName attribute", str(cm.exception))

        # There to be more invalid docNames, but we use XMLDraft in places where we don't
        # actually care about the validation, so for now just test what has long been the
        # implementation. 
        with self.assertRaises(ValueError) as cm:
            XMLDraft.parse_docname(lxml.etree.Element("xml", docName=""))  # not a valid docName
        self.assertIn("Unable to parse docName", str(cm.exception))

        self.assertEqual(
            XMLDraft.parse_docname(lxml.etree.Element("xml", docName="draft-foo-bar-baz-01")),
            ("draft-foo-bar-baz", "01"),
        )

        self.assertEqual(
            XMLDraft.parse_docname(lxml.etree.Element("xml", docName="draft-foo-bar-baz")),
            ("draft-foo-bar-baz", None),
        )

        self.assertEqual(
            XMLDraft.parse_docname(lxml.etree.Element("xml", docName="draft-foo-bar-baz-")),
            ("draft-foo-bar-baz-", None),
        )

        # This is awful, but is how we've been running for some time. The missing rev will trigger
        # validation errors for submissions, so we're at least somewhat guarded against this
        # property.
        self.assertEqual(
            XMLDraft.parse_docname(lxml.etree.Element("xml", docName="-01")),
            ("-01", None),
        )

    def test_render_author_name(self):
        self.assertEqual(
            XMLDraft.render_author_name(lxml.etree.Element("author", fullname="Joanna Q. Public")),
            "Joanna Q. Public",
        )
        self.assertEqual(
            XMLDraft.render_author_name(lxml.etree.Element(
                "author",
                fullname="Joanna Q. Public",
                asciiFullname="Not the Same at All",
            )),
            "Joanna Q. Public",
        )
        self.assertEqual(
            XMLDraft.render_author_name(lxml.etree.Element(
                "author",
                fullname="Joanna Q. Public",
                initials="J. Q.",
                surname="Public-Private",
            )),
            "Joanna Q. Public",
        )
        self.assertEqual(
            XMLDraft.render_author_name(lxml.etree.Element(
                "author",
                initials="J. Q.",
                surname="Public",
            )),
            "J. Q. Public",
        )
        self.assertEqual(
            XMLDraft.render_author_name(lxml.etree.Element(
                "author",
                surname="Public",
            )),
            "Public",
        )
        self.assertEqual(
            XMLDraft.render_author_name(lxml.etree.Element(
                "author",
                initials="J. Q.",
            )),
            "J. Q.",
        )


class NameTests(TestCase):

    def test_name_parts(self):
        names = (
            #name,                          (prefix, first, middle, last, suffix)
            ("Mart van Oostendorp",         ('', 'Mart', '', 'van Oostendorp', '')),
            ("Lina Heribert van Laon",      ('', 'Lina', 'Heribert', 'van Laon', '')),
            ("Daniél van Luin",             ('', 'Daniél', '', 'van Luin', '')),
            ("Dylano van 't Riet",          ('', 'Dylano', '', 'van \'t Riet', '')),
            ("Pedro de la Rosa",            ('', 'Pedro', '', 'de la Rosa', '')),
            ("Jim Bruijne van der Veen",    ('', 'Jim', 'Bruijne', 'van der Veen', '')),
            ("Mr. Fix Hollister",           ('Mr.', 'Fix', '', 'Hollister', '')),
            ("Donald E. Eastlake 3rd",      ('', 'Donald', 'E.', 'Eastlake', '3rd')),
            ("Professor André Danthine",    ('Professor', 'André', '', 'Danthine', '')),
            ("DENG Hui",                    ('', 'Hui', '', 'Deng', '')),
            ("ዳዊት በቀለ (Dawit Bekele)",      ('', 'ዳዊት', '', 'በቀለ', '')),
            ("",  ('', '', '', '', '')),
            ("",  ('', '', '', '', '')),
            ("",  ('', '', '', '', '')),
            ("",  ('', '', '', '', '')),
            )

        for name, parts in names:
            if name:
                self.assertEqual(parts, name_parts(name))


    def test_unidecode(self):
        names = (
            ("ዳዊት በቀለ",         ("Daawite Baqala", )),
            ("丽 郜",             ("Li Gao", )),
            ("कम्बोज डार",      ("Kmboj Ddaar", )),
            ("Ηράκλεια Λιόντη", ("Erakleia Lionte", )),
            ("ישראל רוזנפלד",   ("Yshrl Rvznpld", "Yshral Rvznpld", )),
            ("丽华 皇",            ("Li Hua Huang", )),
            ("نرگس پویان",      ("Nrgs Pwyn", )),
            ("موسوی سينا زمانی",("Mwswy Syn Zmny", )),
            ("Iñigo Sanç Ibáñez de la Peña",    ("Inigo Sanc Ibanez de La Pena", )),
            ("",    ("", )),
            )

        for name, ascii in names:
            if name:
                self.assertIn(unidecode_name(name), ascii)
            
class LogUtilTests(TestCase):
    def test_unreachable(self):
        with self.assertRaises(AssertionError):
            unreachable()
        settings.SERVER_MODE = 'development'
        # FIXME-LARS: this fails when the tests are run with --debug-mode, i.e., DEBUG is set:
        if not settings.DEBUG:
            unreachable()
        settings.SERVER_MODE = 'test'

    def test_assertion(self):
        with self.assertRaises(AssertionError):
            assertion('False')
        settings.DEBUG = False
        settings.SERVER_MODE = 'development'
        assertion('False')
        settings.SERVER_MODE = 'test'

class TestRFC2047Strings(TestCase):
    def test_parse_unicode(self):
        names = (
            ('=?utf-8?b?4Yuz4YuK4Ym1IOGJoOGJgOGIiA==?=', 'ዳዊት በቀለ'),
            ('=?utf-8?b?5Li9IOmDnA==?=', '丽 郜'),
            ('=?utf-8?b?4KSV4KSu4KWN4KSs4KWL4KScIOCkoeCkvuCksA==?=', 'कम्बोज डार'),
            ('=?utf-8?b?zpfPgc6szrrOu861zrnOsSDOm865z4zOvc+Ezrc=?=', 'Ηράκλεια Λιόντη'),
            ('=?utf-8?b?15nXqdeo15DXnCDXqNeV15bXoNek15zXkw==?=', 'ישראל רוזנפלד'),
            ('=?utf-8?b?5Li95Y2OIOeahw==?=', '丽华 皇'),
            ('=?utf-8?b?77ul77qu766V77qzIO+tlu+7ru+vvu+6ju+7pw==?=', 'ﻥﺮﮕﺳ ﭖﻮﯾﺎﻧ'),
            ('=?utf-8?b?77uh77uu77qz77uu76++IO+6su+7tO+7p++6jSDvurDvu6Pvuo7vu6jvr74=?=', 'ﻡﻮﺳﻮﯾ ﺲﻴﻧﺍ ﺰﻣﺎﻨﯾ'),
            ('=?utf-8?b?ScOxaWdvIFNhbsOnIEliw6HDsWV6IGRlIGxhIFBlw7Fh?=', 'Iñigo Sanç Ibáñez de la Peña'),
            ('Mart van Oostendorp', 'Mart van Oostendorp'),
            ('', ''),
            )
        for encoded_str, unicode in names: 
            self.assertEqual(unicode, parse_unicode(encoded_str))

class TestAndroidSiteManifest(TestCase):
    def test_manifest(self):
        r = self.client.get(urlreverse('site.webmanifest'))
        self.assertEqual(r.status_code, 200)
        manifest = json.loads(unicontent(r))
        self.assertTrue('name' in manifest)
        self.assertTrue('theme_color' in manifest)


class TimezoneTests(TestCase):
    """Tests of the timezone utilities"""
    @patch(
        'ietf.utils.timezone.timezone.now',
        return_value=pytz.timezone('America/Chicago').localize(datetime.datetime(2022, 7, 1, 23, 15, 0)),  # 23:15:00
    )
    def test_timezone_not_near_midnight(self, mock):
        # give it several choices that should be rejected and one that should be accepted
        with patch(
                'ietf.utils.timezone.available_timezones',
                return_value=set([
                    'America/Chicago',  # time is 23:15, should be rejected
                    'America/Lima',  # time is 23:15, should be rejected
                    'America/New_York',  # time is 00:15, should be rejected
                    'Europe/Riga',  # time is 07:15, acceptable
                ]),
        ):
            # check a few times (will pass by chance < 0.1% of the time)
            self.assertEqual(timezone_not_near_midnight(), 'Europe/Riga')
            self.assertEqual(timezone_not_near_midnight(), 'Europe/Riga')
            self.assertEqual(timezone_not_near_midnight(), 'Europe/Riga')
            self.assertEqual(timezone_not_near_midnight(), 'Europe/Riga')
            self.assertEqual(timezone_not_near_midnight(), 'Europe/Riga')

        # now give it no valid choice
        with patch(
                'ietf.utils.timezone.available_timezones',
                return_value=set([
                    'America/Chicago',  # time is 23:15, should be rejected
                    'America/Lima',  # time is 23:15, should be rejected
                    'America/New_York',  # time is 00:15, should be rejected
                ]),
        ):
            with self.assertRaises(RuntimeError):
                timezone_not_near_midnight()


class SearchableFieldTests(TestCase):
    def test_has_changed_single_value(self):
        """Should work with initial as a single value or list when max_entries == 1"""
        class TestSearchableField(SearchableField):
            model = "fake model"  # needs to be not-None to allow field init

        class TestForm(Form):
            test_field = TestSearchableField(max_entries=1)

        # single value in initial (e.g., when used as a single-valued field in a formset)
        changed_form = TestForm(initial={'test_field': 1}, data={'test_field': [2]})
        self.assertTrue(changed_form.has_changed())
        unchanged_form = TestForm(initial={'test_field': 1}, data={'test_field': [1]})
        self.assertFalse(unchanged_form.has_changed())

        # list value in initial (usual situation for a MultipleChoiceField subclass like SearchableField)
        changed_form = TestForm(initial={'test_field': [1]}, data={'test_field': [2]})
        self.assertTrue(changed_form.has_changed())
        unchanged_form = TestForm(initial={'test_field': [1]}, data={'test_field': [1]})
        self.assertFalse(unchanged_form.has_changed())


class HealthTests(TestCase):
    def test_health(self):
        self.assertEqual(
            self.client.get("/health/").status_code,
            200,
        )
            
