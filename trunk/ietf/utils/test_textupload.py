# Copyright The IETF Trust 2014-2020, All Rights Reserved
# -*- coding: utf-8 -*-


from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile

from .textupload import get_cleaned_text_file_content
from ietf.utils.test_utils import TestCase


class GetCleanedTextFileContentTest(TestCase):
    def test_no_file(self):
        self.assertEqual(get_cleaned_text_file_content(None), "")

    def test_valid_file(self):
        data = 'testing 👾'
        uploaded_file = SimpleUploadedFile('data.txt', data.encode('utf-8'))
        self.assertEqual(get_cleaned_text_file_content(uploaded_file), data)

    def test_invalid_mime_type_gif(self):
        data = 'GIF89a;'
        uploaded_file = SimpleUploadedFile('data.txt', data.encode('utf-8'))
        with self.assertRaises(ValidationError) as context:
            get_cleaned_text_file_content(uploaded_file)
        self.assertIn('does not appear to be a text file', context.exception.message)
        self.assertIn('image/gif', context.exception.message)

    def test_invalid_mime_type_rst(self):
        data = r'{\rtf1}'
        uploaded_file = SimpleUploadedFile('data.txt', data.encode('utf-8'))
        with self.assertRaises(ValidationError) as context:
            get_cleaned_text_file_content(uploaded_file)
        self.assertIn('does not appear to be a text file', context.exception.message)
        self.assertIn('text/rtf', context.exception.message)
