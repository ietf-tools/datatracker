# Copyright The IETF Trust 2026, All Rights Reserved
import re
from unittest import mock

from django.contrib.auth.models import User
from django.urls import reverse as urlreverse

from ietf.api.models import MIN_TOKEN_LENGTH, AppApiToken
from ietf.utils.test_utils import TestCase


class AppApiTokenAdminTests(TestCase):
    def setUp(self):
        super().setUp()
        User.objects.create_superuser("admin", "admin@example.org", "admin+password")
        self.client.login(username="admin", password="admin+password")
        self.add_url = urlreverse("admin:api_appapitoken_add")

    def post_data(self, **kwargs):
        data = {
            "client": "test client",
            "description": "",
            "enabled": "on",
            "new_token": "",
            # the endpoints inline will not validate without its management form
            "AppApiToken_endpoints-TOTAL_FORMS": "0",
            "AppApiToken_endpoints-INITIAL_FORMS": "0",
            "AppApiToken_endpoints-MIN_NUM_FORMS": "0",
            "AppApiToken_endpoints-MAX_NUM_FORMS": "1000",
        }
        data.update(kwargs)
        return data

    def displayed_token(self, response):
        """Raw token from the copy widget in the admin message, None if absent"""
        match = re.search(
            r'class="copy-token">.*?value="([^"]*)"',
            response.content.decode(),
            re.DOTALL,
        )
        return match.group(1) if match else None

    def create_token(
        self,
        raw_token="an-existing-token-" + "a" * MIN_TOKEN_LENGTH,
        client="existing client",
    ):
        token = AppApiToken(client=client)
        token.set_token(raw_token)
        token.save()
        return token

    def change_url(self, token):
        return urlreverse("admin:api_appapitoken_change", args=[token.pk])

    def test_add_generates_token(self):
        r = self.client.post(self.add_url, self.post_data(), follow=True)
        self.assertEqual(r.status_code, 200)
        token = AppApiToken.objects.get()  # also asserts that only one was created
        self.assertEqual(token.client, "test client")

        raw_token = self.displayed_token(r)
        self.assertIsNotNone(raw_token, "no token was displayed after creation")
        self.assertEqual(
            AppApiToken.hash(raw_token),
            token.token,
            "displayed token is not the one that was stored",
        )
        self.assertContains(r, "will not be shown again")
        self.assertContains(
            r,
            "ietf/js/api/admin-token-copy.js",
            msg_prefix="copy-to-clipboard script was not loaded",
        )

    def test_add_with_supplied_token(self):
        raw_token = "a-supplied-token-" + "a" * MIN_TOKEN_LENGTH
        r = self.client.post(
            self.add_url, self.post_data(new_token=raw_token), follow=True
        )
        self.assertEqual(r.status_code, 200)
        token = AppApiToken.objects.get()
        self.assertEqual(
            token.token,
            AppApiToken.hash(raw_token),
            "supplied token was not hashed for storage",
        )
        self.assertEqual(
            self.displayed_token(r), raw_token, "supplied token was not displayed"
        )

    def test_change_form_does_not_expose_token(self):
        token = self.create_token()
        r = self.client.get(self.change_url(token))
        self.assertEqual(r.status_code, 200)
        content = r.content.decode()
        self.assertNotIn(
            token.token, content, "stored hash leaked into the change form"
        )
        input_tag = re.search(r'<input[^>]*name="new_token"[^>]*>', content)
        self.assertIsNotNone(input_tag, "new_token field is missing from the form")
        self.assertNotIn(
            "value=", input_tag.group(0), "new_token field was not rendered empty"
        )

    def test_change_preserves_token_when_blank(self):
        # a blank new_token means "keep the token that is already set"
        token = self.create_token()
        original_token = token.token
        r = self.client.post(
            self.change_url(token),
            self.post_data(client="renamed client"),
            follow=True,
        )
        self.assertEqual(r.status_code, 200)
        token.refresh_from_db()
        self.assertEqual(token.client, "renamed client", "other fields were not saved")
        self.assertEqual(token.token, original_token, "existing token was modified")
        self.assertNotContains(
            r,
            "will not be shown again",
            msg_prefix="a token was displayed although none was set",
        )

    def test_change_sets_new_token(self):
        token = self.create_token()
        raw_token = "a-replacement-token-" + "a" * MIN_TOKEN_LENGTH
        r = self.client.post(
            self.change_url(token), self.post_data(new_token=raw_token), follow=True
        )
        self.assertEqual(r.status_code, 200)
        token.refresh_from_db()
        self.assertEqual(
            token.token, AppApiToken.hash(raw_token), "new token was not stored"
        )
        self.assertEqual(
            self.displayed_token(r), raw_token, "new token was not displayed"
        )

    def test_new_token_validation_errors(self):
        existing_raw_token = "an-existing-token-" + "a" * MIN_TOKEN_LENGTH
        self.create_token(existing_raw_token)

        # status 200 rather than a redirect means the form was redisplayed with errors
        r = self.client.post(
            self.add_url, self.post_data(new_token="a" * (MIN_TOKEN_LENGTH - 1))
        )
        self.assertContains(r, "Token is too short", status_code=200)

        r = self.client.post(self.add_url, self.post_data(new_token=existing_raw_token))
        self.assertContains(r, "Token already exists", status_code=200)

        self.assertEqual(
            AppApiToken.objects.count(), 1, "a rejected token was created anyway"
        )

    def test_save_model_updates_token_cache(self):
        """Saving changes through the admin must update the hashed token cache"""
        with mock.patch("ietf.api.admin.cached_hashed_token_store") as mocked:
            self.client.post(self.add_url, self.post_data())
            self.assertIn(
                mock.call(force_update=True),
                mocked.call_args_list,
                "AppApiTokenAdmin did not refresh the token cache",
            )

            mocked.reset_mock()  # isolate the assertion below to this second save
            self.client.post(
                urlreverse("admin:api_knownapiendpoint_add"),
                {"name": "ietf.api.foobar", "enabled": "on"},
            )
            self.assertIn(
                mock.call(force_update=True),
                mocked.call_args_list,
                "KnownApiEndpointAdmin did not refresh the token cache",
            )

    def test_search_by_token_value(self):
        raw_token = "a-searchable-token-" + "a" * MIN_TOKEN_LENGTH
        token = self.create_token(raw_token, client="searchable client")
        other_token = self.create_token(
            "another-token-" + "a" * MIN_TOKEN_LENGTH, client="other client"
        )
        url = urlreverse("admin:api_appapitoken_changelist")

        def search(term):
            r = self.client.get(url, {"q": term})
            self.assertEqual(r.status_code, 200)
            return r.context["cl"].queryset

        self.assertCountEqual(
            search(raw_token), [token], "search did not match the raw token value"
        )
        self.assertCountEqual(
            search(f"  {raw_token}  "),
            [token],
            "search did not match a token value with surrounding whitespace",
        )
        self.assertCountEqual(
            search("other client"),
            [other_token],
            "search no longer matches the ordinary search fields",
        )
        self.assertCountEqual(
            search("neither-a-token-nor-a-client"),
            [],
            "search matched something it should not have",
        )
