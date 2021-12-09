# Copyright The IETF Trust 2021, All Rights Reserved
# -*- coding: utf-8 -*-
"""HedgeDoc API utilities tests"""
import requests_mock

from ietf.utils.tests import TestCase
from ietf.utils.hedgedoc import Note


class NoteTests(TestCase):
    SAMPLE_MARKDOWN = ''.join((
        '# Standard Markdown\n',
        'This is a small sample of markdown text. It uses GFM-style line breaks.\n',
        '\n',
        'This is a second paragraph.\n',
        'It has line breaks in GFM style.\n',
        'And also some standard line breaks.  \n',
        'That is all.\n',
    ))
    SAMPLE_MARKDOWN_OUTPUT = ''.join((
        '# Standard Markdown   {#standard-markdown}\n',
        '\n',
        'This is a small sample of markdown text. It uses GFM-style line breaks.\n',
        '\n',
        'This is a second paragraph.  \n',
        'It has line breaks in GFM style.  \n',
        'And also some standard line breaks.   \n',
        'That is all.\n',
        '\n',
    ))

    def test_retrieves_note(self):
        with requests_mock.Mocker() as mock:
            mock.get('https://notes.ietf.org/my_id/download', text=self.SAMPLE_MARKDOWN)
            n = Note('my_id')
            result = n.get_source()
        self.assertEqual(result, self.SAMPLE_MARKDOWN_OUTPUT)

    def test_uses_preprocess_class_method(self):
        """Imported text should be processed by the preprocess_source class method"""
        with requests_mock.Mocker() as mock:
            mock.get('https://notes.ietf.org/my_id/download', text=self.SAMPLE_MARKDOWN)
            n = Note('my_id')
            result = n.get_source()
        self.assertEqual(result, Note.preprocess_source(self.SAMPLE_MARKDOWN))
