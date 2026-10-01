# Copyright 2026 The IETF Trust, All Rights Reserved
from ietf.ipr.mail import extract_valid_response_email_to_address
from ietf.mailtrigger.utils import get_base_ipr_request_address
from ietf.utils.test_utils import TestCase


class ResponseEmailTests(TestCase):
    def test_is_valid_response_email_to_address(self):
        local, domain = get_base_ipr_request_address().split("@", maxsplit=1)
        # Lists of (input, output) pairs
        test_cases = [
            # valid
            (
                f"{local}+abcd1234-efgh789@{domain}",
                f"{local}+abcd1234-efgh789@{domain}",
            ),
            (
                f"<{local}+abcd1234-EFGH789@{domain}>",
                f"{local}+abcd1234-EFGH789@{domain}",
            ),
            (
                f'"Some Name" <{local}+AbCd1234-efgh789@{domain}>',
                f"{local}+AbCd1234-efgh789@{domain}",
            ),
            # invalid
            ("notanipr@ietf.org", None),
            (f"{local}+abcd1234-EFGH789@some-other-domain.example.com", None),
            (f"{local}@{domain}", None),
        ]
        for email, expected in test_cases:
            with self.subTest(email=email):
                self.assertEqual(
                    extract_valid_response_email_to_address(email), expected
                )
