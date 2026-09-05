# Copyright The IETF Trust 2026, All Rights Reserved

from django.test.utils import override_settings

from ietf.api.models import MIN_TOKEN_LENGTH, AppApiToken
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
        self.assertGreaterEqual(len(raw_token), MIN_TOKEN_LENGTH, "generated token is too short")
        self.assertNotEqual(raw_token, AppApiToken.generate_token(), "generated the same token twice")
