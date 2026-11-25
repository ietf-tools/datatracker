# Copyright The IETF Trust 2026, All Rights Reserved
# -*- coding: utf-8 -*-


import os
import tempfile

from docutils.utils import SystemMessage

from django.template import Context

import debug  # pyflakes:ignore

from ietf.dbtemplate.factories import DBTemplateFactory
from ietf.dbtemplate.forms import DBTemplateForm
from ietf.dbtemplate.template import RSTTemplate
from ietf.utils.test_utils import TestCase


class RSTTemplateTests(TestCase):
    def setUp(self):
        super().setUp()
        fd, self.other_file = tempfile.mkstemp(suffix=".txt")
        with os.fdopen(fd, "w") as f:
            f.write("text from another file\n")

    def tearDown(self):
        os.unlink(self.other_file)
        super().tearDown()

    def render(self, content):
        return RSTTemplate(content).render(Context({}))

    def no_outside_content(self):
        """reStructuredText that would bring in a file, a URL or HTML of its own"""
        return {
            "include": ".. include:: %s\n   :encoding: utf-8\n" % self.other_file,
            "include literal": ".. include:: %s\n   :literal:\n   :encoding: utf-8\n" % self.other_file,
            "csv-table file": ".. csv-table:: Table\n   :file: %s\n   :encoding: utf-8\n" % self.other_file,
            "csv-table url": ".. csv-table:: Table\n   :url: http://localhost:1/table.csv\n",
            "raw": ".. raw:: html\n\n   <b>bold</b>\n",
            "raw file": ".. raw:: html\n   :file: %s\n   :encoding: utf-8\n" % self.other_file,
            "raw url": ".. raw:: html\n   :url: http://localhost:1/page.html\n",
        }

    def test_renders(self):
        html = self.render(
            "Heading\n=======\n\n* one\n* ``two``\n\nSee `the IETF <https://www.ietf.org/>`_ "
            "or write to someone@example.com.\n\n1 < 2 & 3 > 2\n"
        )
        self.assertIn("<h1>Heading</h1>", html)
        self.assertIn("<li>one</li>", html)
        self.assertIn("two", html)
        self.assertIn('<a href="https://www.ietf.org/">the IETF</a>', html)
        self.assertIn('<a href="mailto:someone', html)
        self.assertIn("1 &lt; 2 &amp; 3 &gt; 2", html)

    def test_substitutes(self):
        html = RSTTemplate("Dear $name,\n").render(Context({"name": "Someone"}))
        self.assertIn("Dear Someone,", html)

    def test_no_outside_content(self):
        for name, content in self.no_outside_content().items():
            with self.assertRaises(SystemMessage, msg=name):
                self.render(content)

    def test_form_refuses_outside_content(self):
        template = DBTemplateFactory(type_id="rst", content="Heading\n=======\n")
        for name, content in self.no_outside_content().items():
            form = DBTemplateForm(instance=template, data={"content": content})
            self.assertFalse(form.is_valid(), name)
            self.assertNotIn("text from another file", str(form.errors), name)
        form = DBTemplateForm(instance=template, data={"content": "Another heading\n===============\n"})
        self.assertTrue(form.is_valid())

    def test_error_message_is_escaped(self):
        with self.assertRaises(SystemMessage) as cm:
            self.render("`<b>bold</b>`_\n")
        self.assertIn("&lt;b&gt;bold&lt;/b&gt;", cm.exception.args[0])
        self.assertNotIn("<b>", cm.exception.args[0])

    def test_links_and_images(self):
        html = self.render(
            "`a link <javascript:void(0)>`_\n\n"
            ".. image:: https://www.example.com/picture.png\n   :target: javascript:void(0)\n"
        )
        self.assertNotIn("javascript", html)
        self.assertIn("a link", html)
