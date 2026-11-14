# Copyright The IETF Trust 2026, All Rights Reserved
"""Tests of forms in the Submit application"""

from ietf.doc.forms import ExtResourceForm
from ietf.submit.forms import SubmissionExtResourceForm
from ietf.submit.models import SubmissionExtResource
from ietf.utils.test_utils import TestCase


class SubmissionExtResourceFormTests(TestCase):
    """Validation shared with DocExtResourceForm is covered in ietf.doc.tests_forms"""

    def test_extresource_form_class(self):
        form = ExtResourceForm(
            data=dict(resources="webpage https://example.com/a/page"),
            extresource_form_class=SubmissionExtResourceForm,
        )
        self.assertTrue(form.is_valid(), form.errors)
        resource = form.cleaned_data["resources"][0]
        self.assertIsInstance(resource, SubmissionExtResource)
        self.assertIsNone(resource.pk)
