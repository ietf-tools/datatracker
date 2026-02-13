# Copyright The IETF Trust 2022, All Rights Reserved
# -*- coding: utf-8 -*-
from django.template import Context, Origin, Template
from django.test import override_settings

from django.template.defaultfilters import urlize
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
            urlize("plain string"),
            "plain string",
        )
        self.assertEqual(
            urlize("https://www.ietf.org"),
            '<a href="https://www.ietf.org" rel="nofollow">https://www.ietf.org</a>',
        )
        self.assertEqual(
            urlize("https://mailman3.ietf.org/mailman3/lists/tls@ietf.org/"),
            '<a href="https://mailman3.ietf.org/mailman3/lists/tls@ietf.org/" rel="nofollow">https://mailman3.ietf.org/mailman3/lists/tls@ietf.org/</a>',
        )
        self.assertEqual(
            urlize('<a href="https://www.ietf.org">IETF</a>'),
            (
                '&lt;a href=&quot;<a href="https://www.ietf.org" rel="nofollow">https://www.ietf.org</a>&quot;&gt;IETF&lt;/a&gt;'
            ),
        )
        self.assertEqual(
            urlize("somebody@example.com"),
            '<a href="mailto:somebody@example.com">somebody@example.com</a>',
        )
        self.assertEqual(
            urlize("Some Body <somebody@example.com>"),
            (
                'Some Body &lt;<a href="mailto:somebody@example.com">'
                'somebody@example.com</a>&gt;'
            ),
        )
        self.assertEqual(
            urlize("<script>alert('h4x0r3d');</script>"),
            "&lt;script&gt;alert(&#x27;h4x0r3d&#x27;);&lt;/script&gt;",
        )

        # Cases with autoescape = False (these are dangerous and assume the caller
        # has sanitized already)
        self.assertEqual(
            urlize("plain string", autoescape=False),
            "plain string",
        )
        self.assertEqual(
            urlize("https://www.ietf.org", autoescape=False),
            '<a href="https://www.ietf.org" rel="nofollow">https://www.ietf.org</a>',
        )
        self.assertEqual(
            urlize("somebody@example.com", autoescape=False),
            '<a href="mailto:somebody@example.com">somebody@example.com</a>',
        )
