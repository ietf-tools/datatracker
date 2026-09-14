# Copyright The IETF Trust 2026, All Rights Reserved
"""Tests for the account migration API"""

import sys
import uuid

from unittest import mock

from cryptography.fernet import Fernet

from django.test import override_settings
from django.urls import reverse as urlreverse
from django.utils import timezone

import debug                            # pyflakes:ignore

from ietf.ietfauth import api_migration
from ietf.name.models import ExtResourceName
from ietf.person.factories import (
    EmailFactory,
    PersonFactory,
    PersonUUIDFactory,
    UserFactory,
)
from ietf.person.models import Email, PersonExtResource
from ietf.utils.exception_filter import AuthorizationAwareReporterFilter
from ietf.utils.test_utils import APITestCase

CLAIM_TOKEN = "claim-email-token"
VERIFY_TOKEN = "verify-token"
PASSWORD_KEY = Fernet.generate_key()


def seal(password):
    return Fernet(PASSWORD_KEY).encrypt(password.encode()).decode()


@override_settings(
    APP_API_TOKENS={"ietf.ietfauth.api_migration.verify": [VERIFY_TOKEN]},
    ACCOUNT_MIGRATION_PASSWORD_KEY=PASSWORD_KEY,
)
class VerifyTests(APITestCase):
    def setUp(self):
        super().setUp()
        self.url = urlreverse("ietf.api.migration_api.verify")
        self.person = PersonFactory()
        self.password = f"{self.person.user.username}+password"

    def body(self, identifier=None, password=None):
        return {
            "username_or_email": self.person.user.username
            if identifier is None
            else identifier,
            "encrypted_password": seal(
                self.password if password is None else password
            ),
        }

    def verify(self, identifier=None, password=None, **kwargs):
        return self.client.post(
            self.url,
            self.body(identifier, password),
            format="json",
            headers={"X-Api-Key": VERIFY_TOKEN},
            **kwargs,
        )

    def test_requires_a_valid_api_key(self):
        self.assertEqual(
            self.client.post(self.url, self.body(), format="json").status_code, 403
        )
        self.assertEqual(
            self.client.post(
                self.url, self.body(), format="json", headers={"X-Api-Key": "nope"}
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                self.url, self.body(), format="json", headers={"X-Api-Key": VERIFY_TOKEN}
            ).status_code,
            200,
        )

    def test_a_token_in_the_authorization_header_is_not_accepted(self):
        self.assertEqual(
            self.client.post(
                self.url,
                self.body(),
                format="json",
                headers={"Authorization": f"Token {VERIFY_TOKEN}"},
            ).status_code,
            403,
        )

    def test_verify_by_username(self):
        r = self.verify()
        self.assertEqual(r.status_code, 200)
        payload = r.json()
        self.assertEqual(payload["person_uuid"], str(self.person.primary_uuid))
        self.assertEqual(
            payload["name"],
            {
                "full": self.person.name,
                "plain": self.person.plain_name(),
                "first": self.person.first_name(),
                "last": self.person.last_name(),
            },
        )
        self.assertEqual(payload["legacy_sub"], str(self.person.user.pk))
        self.assertFalse(payload["already_linked"])

    def test_verify_by_email_address(self):
        address = self.person.email_set.get().address
        r = self.verify(identifier=address)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["person_uuid"], str(self.person.primary_uuid))

    def test_verify_is_case_insensitive(self):
        for identifier in (
            self.person.user.username.upper(),
            self.person.email_set.get().address.upper(),
        ):
            r = self.verify(identifier=identifier)
            self.assertEqual(r.status_code, 200, identifier)

    def test_an_inactive_address_is_a_valid_identifier(self):
        """Expected: the flow has to recognise an inactive address the person types

        Distinct from an inactive User, which is refused. Email.active says the address
        stopped being used - often because mail to it bounced - not that the account
        behind it is closed, and claim-email/ reactivates exactly these.
        """
        inactive = EmailFactory(person=self.person, active=False)
        r = self.verify(identifier=inactive.address)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["person_uuid"], str(self.person.primary_uuid))

    def test_an_inactive_user_is_always_refused(self):
        """However the account was reached: a closed account cannot enroll"""
        self.person.user.is_active = False
        self.person.user.save()
        inactive_address = EmailFactory(person=self.person, active=False).address
        for identifier in (
            self.person.user.username,
            self.person.email_set.filter(active=True).first().address,
            inactive_address,
        ):
            self.assertEqual(self.verify(identifier=identifier).status_code, 401, identifier)

    def test_response_carries_no_username_or_password_material(self):
        payload = self.verify().json()
        self.assertEqual(
            set(payload.keys()),
            {
                "person_uuid",
                "name",
                "emails",
                "pronouns",
                "github_username",
                "portrait_url",
                "legacy_sub",
                "last_login",
                "already_linked",
            },
        )

    def test_emails_carry_flags_and_include_inactive(self):
        primary = self.person.email_set.get()
        primary.primary = True
        primary.save()
        inactive = EmailFactory(person=self.person, active=False)
        payload = self.verify().json()
        self.assertEqual(
            payload["emails"][0],
            {"address": primary.address, "primary": True, "active": True},
        )
        self.assertIn(
            {"address": inactive.address, "primary": False, "active": False},
            payload["emails"],
        )

    def test_profile_fields(self):
        self.person.pronouns_selectable = ["they/them"]
        self.person.save()
        PersonExtResource.objects.create(
            person=self.person,
            name=ExtResourceName.objects.get(slug="github_username"),
            value="somebody",
        )
        self.person.user.last_login = timezone.now()
        self.person.user.save()
        payload = self.verify().json()
        self.assertEqual(payload["pronouns"], "they/them")
        self.assertEqual(payload["github_username"], "somebody")
        self.assertIsNotNone(payload["last_login"])
        self.assertIsNone(payload["portrait_url"])

    def test_portrait_url_is_absolute(self):
        person = PersonFactory(with_bio=True)
        self.assertTrue(person.photo, "Test is broken")
        r = self.verify(
            identifier=person.user.username, password=f"{person.user.username}+password"
        )
        self.assertTrue(r.json()["portrait_url"].startswith("https://"))

    def test_failures_are_indistinguishable(self):
        no_person = UserFactory()
        inactive = PersonFactory()
        inactive.user.is_active = False
        inactive.user.save()

        failures = [
            self.verify(password="wrong"),
            self.verify(identifier="nobody@example.com"),
            self.verify(
                identifier=no_person.username, password=f"{no_person.username}+password"
            ),
            self.verify(
                identifier=inactive.user.username,
                password=f"{inactive.user.username}+password",
            ),
        ]
        for r in failures:
            self.assertEqual(r.status_code, 401)
        self.assertEqual(len({r.content for r in failures}), 1)

    def test_ambiguous_identifier_is_refused(self):
        UserFactory(username=self.person.user.username.upper())
        self.assertEqual(self.verify().status_code, 401)

    def test_a_username_and_another_persons_address_is_refused(self):
        """One string naming two Persons is not resolved by proving one of the passwords"""
        other = PersonFactory()
        shared = EmailFactory(person=other).address
        claimant = PersonFactory(user__username=shared)
        self.assertNotEqual(claimant, other, "Test is broken")

        r = self.verify(
            identifier=shared, password=f"{claimant.user.username}+password"
        )
        self.assertEqual(r.status_code, 401)

    def test_a_username_and_an_unowned_address_still_verifies(self):
        """An Email with no Person names nobody, so there is nothing to be ambiguous with"""
        claimant = PersonFactory(user__username="orphan@example.com")
        Email.objects.create(
            address="orphan@example.com", person=None, origin="author: some-draft"
        )
        r = self.verify(
            identifier="orphan@example.com",
            password=f"{claimant.user.username}+password",
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["person_uuid"], str(claimant.primary_uuid))

    def test_plaintext_password_is_refused(self):
        r = self.client.post(
            self.url,
            {
                "username_or_email": self.person.user.username,
                "encrypted_password": self.password,
            },
            format="json",
            headers={"X-Api-Key": VERIFY_TOKEN},
        )
        self.assertEqual(r.status_code, 400)

    def test_wrong_key_is_not_a_credential_failure(self):
        r = self.client.post(
            self.url,
            {
                "username_or_email": self.person.user.username,
                "encrypted_password": Fernet(Fernet.generate_key())
                .encrypt(self.password.encode())
                .decode(),
            },
            format="json",
            headers={"X-Api-Key": VERIFY_TOKEN},
        )
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["errors"][0]["code"], "undecryptable_password")

    @override_settings(ACCOUNT_MIGRATION_PASSWORD_KEY=b"not-a-fernet-key")
    def test_an_unusable_server_key_is_not_a_client_error(self):
        """The datatracker's own misconfiguration must not read as a bad request

        Answering 400 would leave every enrollment failing with the one code that tells
        the account app it sent something wrong, and nothing would reach ADMINS.
        """
        with self.assertRaises(ValueError):
            self.verify()

    def test_a_traceback_cannot_carry_the_plaintext_password(self):
        """A 500 anywhere under verify/ mails ADMINS every frame local

        LOGGING sends ERROR to AdminEmailHandler with include_html, and the reporter
        dumps frame locals uncleansed unless sensitive_variables is on the stack.

        Asserts on the frames that hold the password rather than on the rendered report:
        this test's own frame holds the literal too, and nothing protects that.
        """
        identifier, secret = "someone@example.com", "s3cret-plaintext"
        with mock.patch.object(
            api_migration.User.objects, "filter", side_effect=RuntimeError("boom")
        ):
            try:
                api_migration.authenticate_person(identifier, secret)
            except RuntimeError:
                tb = sys.exc_info()[2]

        cleansed = AuthorizationAwareReporterFilter.cleansed_substitute
        frames = {}
        while tb is not None:
            frames[tb.tb_frame.f_code.co_name] = tb.tb_frame
            tb = tb.tb_next
        self.assertIn("authenticate_person", frames, "Test is broken")
        self.assertIn("sensitive_variables_wrapper", frames, "Test is broken")

        reported = {
            name: dict(
                AuthorizationAwareReporterFilter().get_traceback_frame_variables(
                    None, frame
                )
            )
            for name, frame in frames.items()
        }
        for name in ("authenticate_person", "sensitive_variables_wrapper"):
            self.assertNotIn(
                secret, " ".join(str(v) for v in reported[name].values()), name
            )

        # The decorated frame is cleansed wholesale; in the decorator's own frame only
        # the call arguments are, which is where the password is.
        self.assertTrue(
            all(v == cleansed for v in reported["authenticate_person"].values())
        )
        self.assertEqual(reported["sensitive_variables_wrapper"]["func_args"], cleansed)

    def test_malformed_request(self):
        r = self.client.post(
            self.url,
            {"encrypted_password": seal("x")},
            format="json",
            headers={"X-Api-Key": VERIFY_TOKEN},
        )
        self.assertEqual(r.status_code, 400)


@override_settings(
    APP_API_TOKENS={"ietf.ietfauth.api_migration.claim_email": [CLAIM_TOKEN]}
)
class ClaimEmailTests(APITestCase):
    def setUp(self):
        super().setUp()
        self.url = urlreverse("ietf.api.migration_api.claim-email")
        self.person = PersonFactory()

    def claim(self, address, person_uuid=None, token=CLAIM_TOKEN):
        return self.client.post(
            self.url,
            {
                "person_uuid": str(
                    self.person.primary_uuid if person_uuid is None else person_uuid
                ),
                "address": address,
            },
            format="json",
            headers={"X-Api-Key": token},
        )

    def orphaned_addresses(self):
        return set(Email.objects.filter(person=None).values_list("address", flat=True))

    def unowned_email(self):
        return Email.objects.create(
            address="orphan@example.com",
            person=None,
            active=False,
            origin="author: some-draft",
        )

    def test_requires_a_valid_api_key(self):
        self.assertEqual(self.claim("new@example.com", token="nope").status_code, 403)
        self.assertEqual(self.claim("new@example.com").status_code, 200)

    def test_creates_an_unknown_address(self):
        r = self.claim("new@example.com")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(
            r.json(), {"address": "new@example.com", "primary": False, "active": True}
        )
        email = self.person.email_set.get(address="new@example.com")
        self.assertEqual(email.origin, "account migration")

    def test_reactivates_an_inactive_address(self):
        inactive = EmailFactory(person=self.person, active=False)
        r = self.claim(inactive.address)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["active"])
        inactive.refresh_from_db()
        self.assertTrue(inactive.active)

    def test_is_idempotent(self):
        for _ in range(2):
            r = self.claim("new@example.com")
            self.assertEqual(r.status_code, 200)
        self.assertEqual(
            self.person.email_set.filter(address="new@example.com").count(), 1
        )

    def test_leaves_an_existing_address_alone(self):
        existing = self.person.email_set.get()
        existing.primary = True
        existing.save()
        r = self.claim(existing.address)
        self.assertEqual(
            r.json(), {"address": existing.address, "primary": True, "active": True}
        )

    def test_does_not_change_which_address_is_primary(self):
        primary = self.person.email_set.get()
        primary.primary = True
        primary.save()
        self.claim("new@example.com")
        self.assertEqual(
            list(self.person.email_set.filter(primary=True).values_list("address", flat=True)),
            [primary.address],
        )

    def test_refuses_another_persons_address(self):
        other = PersonFactory()
        address = other.email_set.get().address
        r = self.claim(address)
        self.assertEqual(r.status_code, 409)
        self.assertEqual(
            r.json()["errors"][0]["code"], "address_belongs_to_another_person"
        )
        self.assertEqual(Email.objects.get(address=address).person, other)

    def test_refuses_an_unowned_address(self):
        orphan = self.unowned_email()
        r = self.claim(orphan.address)
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json()["errors"][0]["code"], "address_has_no_owner")
        orphan.refresh_from_db()
        self.assertIsNone(orphan.person)
        self.assertFalse(orphan.active)

    def test_never_creates_an_email_without_a_person(self):
        """Including the failing paths - a 4xx must not leave a row behind

        Email.person is nullable because history points at addresses whose owner was
        never established, but nothing here may add to that population.
        """
        other = PersonFactory()
        unowned = self.unowned_email()
        before = self.orphaned_addresses()
        for address, person_uuid in (
            ("new@example.com", None),
            (self.person.email_set.get().address, None),
            (other.email_set.get().address, None),
            (unowned.address, None),
            ("unknown-person@example.com", uuid.uuid4()),
            ("not-an-address", None),
        ):
            self.claim(address, person_uuid=person_uuid)
        self.assertEqual(self.orphaned_addresses() - before, set())

    def test_matches_an_address_case_insensitively(self):
        existing = self.person.email_set.get()
        r = self.claim(existing.address.upper())
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.person.email_set.count(), 1)

    def test_resolves_a_prior_person_uuid(self):
        prior = PersonUUIDFactory(person=self.person)
        r = self.claim("new@example.com", person_uuid=prior.uuid)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(self.person.email_set.filter(address="new@example.com").exists())

    def test_unknown_person_uuid(self):
        r = self.claim("new@example.com", person_uuid=uuid.uuid4())
        self.assertEqual(r.status_code, 404)
        self.assertFalse(Email.objects.filter(address="new@example.com").exists())

    def test_rejects_a_malformed_address(self):
        r = self.claim("not-an-address")
        self.assertEqual(r.status_code, 400)
        self.assertFalse(Email.objects.filter(address="not-an-address").exists())

    def racing_claim(self, address, winner):
        """Claim an address that another tab commits in the window we race

        The competing row has to be inserted before claim_address opens its savepoint, or
        rolling that savepoint back would take the competing row with it and the test
        would be exercising something that cannot happen. The existence check is the last
        thing to run before the savepoint, so it is what gets hooked.
        """
        real_filter = Email.objects.filter
        raced = []

        def racing_filter(*args, **kwargs):
            if raced:
                return real_filter(*args, **kwargs)
            raced.append(True)
            Email.objects.bulk_create(
                [Email(address=address, person=winner, origin="another tab")]
            )
            return Email.objects.none()

        with mock.patch.object(Email.objects, "filter", side_effect=racing_filter):
            return self.claim(address)

    def test_survives_a_concurrent_first_claim(self):
        """The loser of a create race re-reads the row instead of failing

        Email.address is the primary key, so the existence check and the insert race, and
        the doc has two enrollment tabs reaching here at once.
        """
        address = "new@example.com"
        r = self.racing_claim(address, self.person)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["address"], address)
        self.assertEqual(Email.objects.filter(address=address).count(), 1)

    def test_a_concurrent_claim_by_another_person_still_conflicts(self):
        address = "new@example.com"
        other = PersonFactory()
        r = self.racing_claim(address, other)
        self.assertEqual(r.status_code, 409)
        self.assertEqual(
            r.json()["errors"][0]["code"], "address_belongs_to_another_person"
        )
