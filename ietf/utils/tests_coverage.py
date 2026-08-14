# Copyright The IETF Trust 2025, All Rights Reserved
"""Tests of the coverage.py module"""

from unittest import mock

from django.test import override_settings

from .coverage import CoverageManager
from .test_utils import TestCase


class CoverageManagerTests(TestCase):
    @override_settings(
        BASE_DIR="/path/to/project/ietf",
        TEST_CODE_COVERAGE_EXCLUDE_FILES=["a.py"],
        TEST_CODE_COVERAGE_EXCLUDE_LINES=["some-regex"],
    )
    @mock.patch("ietf.utils.coverage.Coverage")
    def test_coverage_manager(self, mock_coverage):
        """CoverageManager managed coverage correctly in non-production mode

        Presumes we're not running tests in production mode.
        """
        cm = CoverageManager()
        self.assertFalse(cm.started)

        cm.start()
        self.assertTrue(cm.started)
        self.assertEqual(cm.checker, mock_coverage.return_value)
        self.assertTrue(mock_coverage.called)
        coverage_kwargs = mock_coverage.call_args.kwargs
        self.assertEqual(coverage_kwargs["source"], ["/path/to/project/ietf"])
        self.assertEqual(coverage_kwargs["omit"], ["a.py"])
        self.assertTrue(isinstance(cm.checker.exclude, mock.Mock))
        assert isinstance(cm.checker.exclude, mock.Mock)  # for type checker
        self.assertEqual(cm.checker.exclude.call_count, 1)
        cm.checker.exclude.assert_called_with("some-regex")

    @mock.patch("ietf.utils.coverage.Coverage")
    def test_coverage_manager_is_defanged_in_production(self, mock_coverage):
        """CoverageManager is a no-op in production mode"""
        # Be careful faking settings.SERVER_MODE, but there's really no other way to
        # test this.
        with override_settings(SERVER_MODE="production"):
            cm = CoverageManager()
            cm.start()

        # Check that nothing actually happened
        self.assertFalse(mock_coverage.called)
        self.assertIsNone(cm.checker)
        self.assertFalse(cm.started)

        # Check that other methods are guarded appropriately
        cm.stop()
        cm.save()
        self.assertIsNone(cm.report())
