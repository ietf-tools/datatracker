# Copyright The IETF Trust 2021, All Rights Reserved
# -*- coding: utf-8 -*-
"""Tests of forms in the Meeting application"""
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings

from ietf.meeting.forms import FileUploadForm, ApplyToAllFileUploadForm, InterimSessionModelForm
from ietf.utils.test_utils import TestCase


@override_settings(
    MEETING_APPLICATION_OCTET_STREAM_OVERRIDES={'.md': 'text/markdown'},  # test relies on .txt not mapping
    MEETING_VALID_UPLOAD_EXTENSIONS={'minutes': ['.txt', '.md']},  # test relies on .exe being absent
    MEETING_VALID_UPLOAD_MIME_TYPES={'minutes': ['text/plain', 'text/markdown']},
    MEETING_VALID_MIME_TYPE_EXTENSIONS={'text/plain': ['.txt'], 'text/markdown': ['.md']},
    MEETING_VALID_UPLOAD_MIME_FOR_OBSERVED_MIME={'text/plain': ['text/plain', 'text/markdown']},
)
class FileUploadFormTests(TestCase):
    class TestClass(FileUploadForm):
        doc_type = 'minutes'

    def test_accepts_valid_data(self):
        test_file = SimpleUploadedFile(
            name='file.txt',
            content=b'plain text',
            content_type='text/plain',
        )

        form = FileUploadFormTests.TestClass(files={'file': test_file})
        self.assertTrue(form.is_valid(), 'Test data are valid input')
        cleaned_file = form.cleaned_data['file']
        self.assertEqual(cleaned_file.name, 'file.txt', 'Uploaded filename should not be changed')
        with cleaned_file.open('rb') as f:
            self.assertEqual(f.read(), b'plain text', 'Uploaded file contents should not be changed')
        self.assertEqual(cleaned_file.content_type, 'text/plain', 'Content-Type should be overridden')

    def test_overrides_content_type_application_octet_stream(self):
        test_file = SimpleUploadedFile(
            name='file.md',
            content=b'plain text',
            content_type='application/octet-stream',
        )

        form = FileUploadFormTests.TestClass(files={'file': test_file})
        self.assertTrue(form.is_valid(), 'Test data are valid input')
        cleaned_file = form.cleaned_data['file']
        # Test that the test_file is what actually came out of the cleaning process.
        # This is not technically required here, but the other tests check that test_file's
        # content_type has not been changed. If cleaning does not modify the content_type
        # when it succeeds, then those other tests are not actually testing anything.
        self.assertEqual(cleaned_file, test_file, 'Cleaning should return the file object that was passed in')
        self.assertEqual(cleaned_file.name, 'file.md', 'Uploaded filename should not be changed')
        with cleaned_file.open('rb') as f:
            self.assertEqual(f.read(), b'plain text', 'Uploaded file contents should not be changed')
        self.assertEqual(cleaned_file.content_type, 'text/markdown', 'Content-Type should be overridden')

    def test_overrides_only_application_octet_stream(self):
        test_file = SimpleUploadedFile(
            name='file.md',
            content=b'plain text',
            content_type='application/json'
        )

        form = FileUploadFormTests.TestClass(files={'file': test_file})
        self.assertFalse(form.is_valid(), 'Test data are invalid input')
        self.assertEqual(test_file.name, 'file.md', 'Uploaded filename should not be changed')
        self.assertEqual(test_file.content_type, 'application/json', 'Uploaded Content-Type should not be changed')

    def test_overrides_only_requested_extensions_when_valid_ext(self):
        test_file = SimpleUploadedFile(
            name='file.txt',
            content=b'plain text',
            content_type='application/octet-stream',
        )

        form = FileUploadFormTests.TestClass(files={'file': test_file})
        self.assertFalse(form.is_valid(), 'Test data are invalid input')
        self.assertEqual(test_file.name, 'file.txt', 'Uploaded filename should not be changed')
        self.assertEqual(test_file.content_type, 'application/octet-stream', 'Uploaded Content-Type should not be changed')

    def test_overrides_only_requested_extensions_when_invalid_ext(self):
        test_file = SimpleUploadedFile(
            name='file.exe',
            content=b'plain text',
            content_type='application/octet-stream'
        )

        form = FileUploadFormTests.TestClass(files={'file': test_file})
        self.assertFalse(form.is_valid(), 'Test data are invalid input')
        self.assertEqual(test_file.name, 'file.exe', 'Uploaded filename should not be changed')
        self.assertEqual(test_file.content_type, 'application/octet-stream', 'Uploaded Content-Type should not be changed')


class ApplyToAllFileUploadFormTests(TestCase):
    class TestClass(ApplyToAllFileUploadForm):
        doc_type = 'minutes'

    def test_has_apply_to_all_field_by_default(self):
        form = ApplyToAllFileUploadFormTests.TestClass(show_apply_to_all_checkbox=True)
        self.assertIn('apply_to_all', form.fields)

    def test_no_show_apply_to_all_field(self):
        form = ApplyToAllFileUploadFormTests.TestClass(show_apply_to_all_checkbox=False)
        self.assertNotIn('apply_to_all', form.fields)


class InterimSessionModelFormTests(TestCase):
    @override_settings(MEETECHO_API_CONFIG={})  # setting needs to exist, don't care about its value in this test
    def test_remote_participation_options(self):
        """Only offer Meetecho conference creation when configured"""
        form = InterimSessionModelForm()
        choice_vals = [choice[0] for choice in form.fields['remote_participation'].choices]
        self.assertIn('meetecho', choice_vals)
        self.assertIn('manual', choice_vals)

        del settings.MEETECHO_API_CONFIG
        form = InterimSessionModelForm()
        choice_vals = [choice[0] for choice in form.fields['remote_participation'].choices]
        self.assertNotIn('meetecho', choice_vals)
        self.assertIn('manual', choice_vals)
