# Copyright The IETF Trust 2022, All Rights Reserved
# -*- coding: utf-8 -*-
from django.template import Context, Origin, Template
from django.test import override_settings

from ietf.utils.templatetags.textfilters import linkify
from ietf.utils.test_utils import TestCase
import debug  # pyflakes: ignore


@override_settings(BASE_DIR='/fake/base/')
class OriginTests(TestCase):
    def test_origin_not_shown_in_production(self):
        template = Template(
            '{% load origin %}{% origin %}',
            origin=Origin('/fake/base/templates/my-template.html'),
        )
        with override_settings(SERVER_MODE='production'):
            self.assertEqual(template.render(Context()), '')

    def test_origin_shown_in_development_and_test(self):
        template = Template(
            '{% load origin %}{% origin %}',
            origin=Origin('/fake/base/templates/my-template.html'),
        )
        for mode in ['development', 'test']:
            with override_settings(SERVER_MODE=mode):
                output = template.render(Context())
                self.assertIn('templates/my-template.html', output)
                for component in ['fake', 'base']:
                    self.assertNotIn(component, output, 'Reported path should be relative to BASE_DIR')

    def test_origin_outside_base_dir(self):
        template = Template(
            '{% load origin %}{% origin %}',
            origin=Origin('/different/templates/my-template.html'),
        )
        with override_settings(SERVER_MODE='development'):
            for component in ['fake', 'base', 'different', 'templates']:
                output = template.render(Context())
                self.assertNotIn(component, output,
                                 'Full path components should not be revealed in html')


class TextfiltersTests(TestCase):
    def test_linkify(self):
        # Cases with autoescape = True (the default)
        self.assertEqual(
            linkify("plain string"),
            "plain string",
        )
        self.assertEqual(
            linkify("https://www.ietf.org"),
            '<a href="https://www.ietf.org">https://www.ietf.org</a>',
        )
        self.assertEqual(
            linkify('<a href="https://www.ietf.org">IETF</a>'),
            (
                '&lt;a href=&quot;<a href="https://www.ietf.org">https://www.ietf.org</a>&quot;&gt;IETF&lt;/a&gt;'
            ),
        )
        self.assertEqual(
            linkify("somebody@example.com"),
            '<a href="mailto:somebody@example.com">somebody@example.com</a>',
        )
        self.assertEqual(
            linkify("Some Body <somebody@example.com>"),
            (
                'Some Body &lt;<a href="mailto:somebody@example.com">'
                'somebody@example.com</a>&gt;'
            ),
        )
        self.assertEqual(
            linkify("<script>alert('h4x0r3d');</script>"),
            "&lt;script&gt;alert(&#x27;h4x0r3d&#x27;);&lt;/script&gt;",
        )

        # Cases with autoescape = False (these are dangerous and assume the caller
        # has sanitized already)
        self.assertEqual(
            linkify("plain string", autoescape=False),
            "plain string",
        )
        self.assertEqual(
            linkify("https://www.ietf.org", autoescape=False),
            '<a href="https://www.ietf.org">https://www.ietf.org</a>',
        )
        self.assertEqual(
            linkify('<a href="https://www.ietf.org">IETF</a>', autoescape=False),
            '<a href="https://www.ietf.org">IETF</a>',
        )
        self.assertEqual(
            linkify("somebody@example.com", autoescape=False),
            '<a href="mailto:somebody@example.com">somebody@example.com</a>',
        )
        # bleach.Linkifier translates the < -> &lt; and > -> &gt; on this one
        self.assertEqual(
            linkify("Some Body <somebody@example.com>", autoescape=False),
            (
                'Some Body &lt;<a href="mailto:somebody@example.com">'
                'somebody@example.com</a>&gt;'
            ),
        )
        self.assertEqual(
            linkify("<script>alert('friendly script');</script>", autoescape=False),
            "<script>alert('friendly script');</script>",
        )
