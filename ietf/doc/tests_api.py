# Copyright The IETF Trust 2026, All Rights Reserved
from unittest import mock

from django.test.utils import override_settings
from django.urls import reverse as urlreverse

from ietf.utils.test_utils import APITestCase


class RfcPopularityViewTests(APITestCase):
    @override_settings(
        APP_API_TOKENS={
            "ietf.api.reef_api": ["valid-token"],
            "ietf.api.red_api": ["red-token"],
        }
    )
    @mock.patch("ietf.doc.api.update_rfc_searchindex_popularities_task")
    def test_notify_rfc_popularity_updated(self, mock_task):
        url = urlreverse("ietf.api.reef_api.notify_rfc_popularity_updated")

        response = self.client.post(url)
        self.assertEqual(response.status_code, 403)
        response = self.client.post(url, headers={"X-Api-Key": "invalid-token"})
        self.assertEqual(response.status_code, 403)
        response = self.client.post(url, headers={"X-Api-Key": "red-token"})
        self.assertEqual(response.status_code, 403)
        response = self.client.get(url, headers={"X-Api-Key": "valid-token"})
        self.assertEqual(response.status_code, 405)
        self.assertFalse(mock_task.delay.called)

        response = self.client.post(url, headers={"X-Api-Key": "valid-token"})
        self.assertEqual(response.status_code, 202)
        self.assertEqual(mock_task.delay.call_count, 1)
        self.assertEqual(mock_task.delay.call_args, mock.call())
