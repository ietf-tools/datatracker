# Copyright The IETF Trust 2022, All Rights Reserved
# -*- coding: utf-8 -*-
from django.template import Context, Origin, Template
from django.test import override_settings

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
