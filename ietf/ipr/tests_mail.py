# Copyright 2026 The IETF Trust, All Rights Reserved
from ietf.ipr.mail import is_valid_response_email_to_address
from ietf.mailtrigger.utils import get_base_ipr_request_address
from ietf.utils.test_utils import TestCase


class ResponseEmailTests(TestCase):
    def test_is_valid_response_email_to_address(self):
        local, domain = get_base_ipr_request_address().split("@", maxsplit=1)
        valid_emails = [
            f"{local}+abcd1234-efgh789@{domain}",
            f"<{local}+abcd1234-EFGH789@{domain}>",
            f'"Some Name" <{local}+AbCd1234-efgh789@{domain}>',
        ]
        invalid_emails = [
            "notanipr@ietf.org",
            f"{local}+abcd1234-EFGH789@some-other-domain.example.com",
            f"{local}@{domain}",
        ]
        for email in valid_emails:
            with self.subTest(email=email):
                self.assertTrue(is_valid_response_email_to_address(email))
        for email in invalid_emails:
            with self.subTest(email=email):
                self.assertFalse(is_valid_response_email_to_address(email))
