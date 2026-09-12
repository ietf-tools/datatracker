# Copyright The IETF Trust 2026, All Rights Reserved

from django.test.utils import override_settings

from ietf.api.models import MIN_TOKEN_LENGTH, AppApiToken, KnownApiEndpoint
from ietf.utils.test_utils import TestCase


class AppApiTokenTests(TestCase):
    def test_hash(self):
        hashed = AppApiToken.hash("a-token")
        self.assertRegex(hashed, r"^[0-9a-f]+$")
        self.assertLessEqual(
            len(hashed),
            AppApiToken._meta.get_field("token").max_length,
            "hashed token does not fit in the field",
        )
        self.assertEqual(
            hashed, AppApiToken.hash("a-token"), "hash changed on subsequent call"
        )
        self.assertNotEqual(hashed, AppApiToken.hash("another-token"), "hash collides")
        with override_settings(APP_API_TOKEN_SALT_BYTES=b"a-different-salt"):
            self.assertNotEqual(
                hashed, AppApiToken.hash("a-token"), "hash does not depend on salt"
            )

    def test_set_token(self):
        raw_token = "a" * MIN_TOKEN_LENGTH
        original_hash = AppApiToken.hash(raw_token)
        token = AppApiToken(client="test client")
        token.set_token(raw_token)
        self.assertEqual(token.token, original_hash, "minimum length token is rejected")
        self.assertNotIn(raw_token, token.token, "raw token landed in the token field")

        with self.assertRaises(ValueError, msg="too-short token is not rejected"):
            token.set_token("a" * (MIN_TOKEN_LENGTH - 1))
        self.assertEqual(
            token.token, original_hash, "rejected token disturbed the token field"
        )

    def test_validate_new_token(self):
        other_raw_token = "other-token-" + "a" * MIN_TOKEN_LENGTH
        other = AppApiToken(client="other client")
        other.set_token(other_raw_token)
        other.save()

        raw_token = "a-token-" + "a" * MIN_TOKEN_LENGTH
        token = AppApiToken(client="test client")
        token.set_token(raw_token)
        token.save()

        # acceptable cases - should not raise anything
        token.validate_new_token("a-brand-new-token-" + "a" * MIN_TOKEN_LENGTH)
        token.validate_new_token(raw_token)  # its own token is not a collision

        with self.assertRaises(ValueError):
            token.validate_new_token("a" * (MIN_TOKEN_LENGTH - 1))
        with self.assertRaises(ValueError):
            token.validate_new_token(other_raw_token)

    def test_generate_token(self):
        raw_token = AppApiToken.generate_token()
        self.assertGreaterEqual(
            len(raw_token), MIN_TOKEN_LENGTH, "generated token is too short"
        )
        self.assertNotEqual(
            raw_token, AppApiToken.generate_token(), "generated the same token twice"
        )

    def make_token(self, client, raw_token, endpoints, enabled=True):
        token = AppApiToken(client=client, enabled=enabled)
        token.set_token(raw_token)
        token.save()
        token.endpoints.set(endpoints)
        return token

    def test_as_hashed_token_dict(self):
        enabled_endpoint = KnownApiEndpoint.objects.create(name="ietf.api.enabled")
        shared_endpoint = KnownApiEndpoint.objects.create(name="ietf.api.shared")
        disabled_endpoint = KnownApiEndpoint.objects.create(
            name="ietf.api.disabled", enabled=False
        )

        raw_tokens = {
            name: f"{name}-token-" + "a" * MIN_TOKEN_LENGTH
            for name in ["first", "second", "disabled", "unlinked"]
        }
        self.make_token(
            "first client",
            raw_tokens["first"],
            [enabled_endpoint, shared_endpoint, disabled_endpoint],
        )
        self.make_token("second client", raw_tokens["second"], [shared_endpoint])
        self.make_token(
            "disabled client",
            raw_tokens["disabled"],
            [enabled_endpoint],
            enabled=False,
        )
        self.make_token("unlinked client", raw_tokens["unlinked"], [])

        # the endpoints are prefetched, so the query count does not grow with the
        # number of tokens
        with self.assertNumQueries(2):
            token_dict = AppApiToken.objects.as_hashed_token_dict()

        self.assertCountEqual(
            token_dict.keys(),
            [enabled_endpoint.name, shared_endpoint.name],
            "unexpected set of endpoints in the token dict",
        )
        self.assertCountEqual(
            token_dict[enabled_endpoint.name],
            [AppApiToken.hash(raw_tokens["first"])],
            "disabled token appeared in the token dict",
        )
        self.assertCountEqual(
            token_dict[shared_endpoint.name],
            [
                AppApiToken.hash(raw_tokens["first"]),
                AppApiToken.hash(raw_tokens["second"]),
            ],
            "endpoint did not collect every token that reaches it",
        )
