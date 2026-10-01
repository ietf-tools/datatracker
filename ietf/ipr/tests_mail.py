# Copyright 2026 The IETF Trust, All Rights Reserved
import datetime
import re
from textwrap import dedent

from django.urls import reverse as urlreverse
from django.utils import timezone

from ietf.mailtrigger.utils import gather_address_lists, get_base_ipr_request_address
from ietf.utils.mail import empty_outbox, outbox
from ietf.utils.test_utils import TestCase
from ietf.utils.timezone import date_today

from ..message.models import Message
from .factories import HolderIprDisclosureFactory
from .mail import (
    UndeliverableIprResponseError,
    extract_valid_response_email_to_address,
    get_holders,
    get_pseudo_submitter,
    get_reply_to,
    get_update_cc_addrs,
    get_update_submitter_emails,
    process_response_email,
)
from .models import HolderIprDisclosure, IprEvent


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

    def send_ipr_email_helper(self) -> tuple[str, IprEvent, HolderIprDisclosure]:
        ipr = (
            HolderIprDisclosureFactory.create()
        )  # call create() explicitly so mypy sees correct type
        url = urlreverse("ietf.ipr.views.email", kwargs={"id": ipr.id})
        self.client.login(username="secretary", password="secretary+password")
        yesterday = date_today() - datetime.timedelta(1)
        data = dict(
            to="joe@test.com",
            frm="ietf-ipr@ietf.org",
            subject="test",
            reply_to=get_reply_to(),
            body="Testing.",
            response_due=yesterday.isoformat(),
        )
        empty_outbox()
        r = self.client.post(url, data, follow=True)
        self.assertEqual(r.status_code, 200)
        q = Message.objects.filter(reply_to=data["reply_to"])
        self.assertEqual(q.count(), 1)
        event = q[0].msgevents.first()
        assert event is not None
        self.assertTrue(event.response_past_due())
        self.assertEqual(len(outbox), 1)
        self.assertTrue("joe@test.com" in outbox[0]["To"])
        return data["reply_to"], event, ipr

    uninteresting_ipr_message_strings = [
        ("To: {to}\nCc: {cc}\nFrom: joe@test.com\nDate: {date}\nSubject: test\n"),
        ("Cc: {cc}\nFrom: joe@test.com\nDate: {date}\nSubject: test\n"),  # no To
        ("To: {to}\nFrom: joe@test.com\nDate: {date}\nSubject: test\n"),  # no Cc
        ("From: joe@test.com\nDate: {date}\nSubject: test\n"),  # no To or Cc
        ("Cc: {cc}\nDate: {date}\nSubject: test\n"),  # no To
        ("To: {to}\nDate: {date}\nSubject: test\n"),  # no Cc
        ("Date: {date}\nSubject: test\n"),  # no To or Cc
    ]

    def test_process_response_email(self):
        # first send a mail
        reply_to, event, _ = self.send_ipr_email_helper()

        # test process response uninteresting messages
        addrs = gather_address_lists("ipr_disclosure_submitted").as_strings()
        for message_string in self.uninteresting_ipr_message_strings:
            process_response_email(
                message_string.format(
                    to=addrs.to, cc=addrs.cc, date=timezone.now().ctime()
                )
            )

        # test process response
        message_string = dedent(
            """\
            To: {}
            From: joe@test.com
            Date: {}
            Subject: test
            """.format(reply_to, timezone.now().ctime())
        )
        process_response_email(message_string)
        self.assertFalse(event.response_past_due())

        # test with an unmatchable message identifier
        bad_reply_to = re.sub(
            r"\+.{16}@",
            "+0123456789abcdef@",
            reply_to,
        )
        self.assertNotEqual(reply_to, bad_reply_to)
        message_string = dedent(
            f"""\
            To: {bad_reply_to}
            From: joe@test.com
            Date: {timezone.now().ctime()}
            Subject: test
            """
        )
        with self.assertRaises(UndeliverableIprResponseError):
            process_response_email(message_string)

    def test_process_response_email_with_invalid_encoding(self):
        """Interesting emails with invalid encoding should be handled"""
        reply_to, _, disclosure = self.send_ipr_email_helper()
        # test process response
        message_string = """To: {}
From: joe@test.com
Date: {}
Subject: test
""".format(reply_to, timezone.now().ctime())
        message_bytes = message_string.encode("utf8") + b"\nInvalid stuff: \xfe\xff\n"
        process_response_email(message_bytes)
        result = (
            IprEvent.objects.filter(disclosure=disclosure).first().message
        )  # newest
        # \ufffd is a rhombus character with an inverse ?, used to replace invalid characters
        self.assertEqual(
            result.body,
            "Invalid stuff: \ufffd\ufffd\n\n",  # not sure where the extra \n is from
            "Invalid characters should be replaced with \ufffd characters",
        )

    def test_process_response_email_uninteresting_with_invalid_encoding(self):
        """Uninteresting emails with invalid encoding should be quietly dropped"""
        self.send_ipr_email_helper()
        addrs = gather_address_lists("ipr_disclosure_submitted").as_strings()
        for message_string in self.uninteresting_ipr_message_strings:
            message_bytes = (
                message_string.format(
                    to=addrs.to,
                    cc=addrs.cc,
                    date=timezone.now().ctime(),
                ).encode("utf8")
                + b"\nInvalid stuff: \xfe\xff\n"
            )
            process_response_email(message_bytes)

    def test_get_update_submitter_emails(self):
        ipr = HolderIprDisclosureFactory()
        update = HolderIprDisclosureFactory(
            updates=[
                ipr,
            ]
        )
        messages = get_update_submitter_emails(update)
        self.assertEqual(len(messages), 1)
        self.assertTrue(messages[0].startswith("To: %s" % ipr.submitter_email))

    def test_get_pseudo_submitter(self):
        ipr = HolderIprDisclosureFactory()
        self.assertEqual(
            get_pseudo_submitter(ipr), (ipr.submitter_name, ipr.submitter_email)
        )
        ipr.submitter_name = ""
        ipr.submitter_email = ""
        self.assertEqual(
            get_pseudo_submitter(ipr),
            (ipr.holder_contact_name, ipr.holder_contact_email),
        )
        ipr.holder_contact_name = ""
        ipr.holder_contact_email = ""
        self.assertEqual(
            get_pseudo_submitter(ipr),
            (
                "UNKNOWN NAME - NEED ASSISTANCE HERE",
                "UNKNOWN EMAIL - NEED ASSISTANCE HERE",
            ),
        )

    def test_get_holders(self):
        ipr = HolderIprDisclosureFactory()
        update = HolderIprDisclosureFactory(
            updates=[
                ipr,
            ]
        )
        result = get_holders(update)
        self.assertEqual(
            set(result), set([ipr.holder_contact_email, update.holder_contact_email])
        )

    def test_get_update_cc_addrs(self):
        ipr = HolderIprDisclosureFactory()
        update = HolderIprDisclosureFactory(
            updates=[
                ipr,
            ]
        )
        result = get_update_cc_addrs(update)
        self.assertEqual(
            set(result.split(",")),
            set(
                [
                    update.holder_contact_email,
                    ipr.submitter_email,
                    ipr.holder_contact_email,
                ]
            ),
        )
