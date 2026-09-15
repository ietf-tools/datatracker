# Copyright The IETF Trust 2026, All Rights Reserved
"""Tests for the account migration API"""

import sys
import uuid

from contextlib import contextmanager
from unittest import mock

from base64 import b64encode

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from drf_spectacular.generators import SchemaGenerator

from django.contrib.auth.hashers import get_hasher
from django.test import TestCase, override_settings
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
# 2048 rather than the 3072 a deployment should use: this runs on every test.
_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
PRIVATE_KEY = _KEY.private_bytes(
    serialization.Encoding.PEM,
    serialization.PrivateFormat.PKCS8,
    serialization.NoEncryption(),
)
OAEP = padding.OAEP(
    mgf=padding.MGF1(algorithm=hashes.SHA256()),
    algorithm=hashes.SHA256(),
    label=None,
)


def seal(password, key=None):
    """Encrypt as the account app does - to the public key, base64 encoded"""
    public_key = (key or _KEY).public_key()
    return b64encode(public_key.encrypt(password.encode(), OAEP)).decode()


@override_settings(
    APP_API_TOKENS={"ietf.ietfauth.api_migration.verify": [VERIFY_TOKEN]},
    ACCOUNT_MIGRATION_PRIVATE_KEY=PRIVATE_KEY,
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
            r = self.verify(identifier=identifier)
            self.assertEqual(r.status_code, 400, identifier)
            self.assertEqual(
                r.json()["errors"][0]["code"], "verification_failed", identifier
            )

    @contextmanager
    def counted_hashes(self):
        """Count argon2 operations, however the hasher is reached

        encode is the one primitive both paths run: Argon2PasswordHasher.verify is
        decode plus encode plus a constant-time compare, and check_password's
        unusable-encoding branch reaches encode through make_password. Patching the
        memoized hasher instance catches both without changing what either returns.
        """
        hasher = get_hasher("default")
        calls = []
        real_encode = hasher.encode

        def encode(*args, **kwargs):
            calls.append(kwargs.get("salt", args[1] if len(args) > 1 else None))
            return real_encode(*args, **kwargs)

        with mock.patch.object(hasher, "encode", encode):
            yield calls

    def test_every_outcome_costs_one_hash(self):
        """Otherwise the response time says whether the identifier named an account"""
        no_person = UserFactory()
        inactive = PersonFactory()
        inactive.user.is_active = False
        inactive.user.save()
        unusable = PersonFactory()
        unusable.user.set_unusable_password()
        unusable.user.save()
        colliding = PersonFactory()
        shared = EmailFactory(person=colliding).address
        PersonFactory(user__username=shared)
        UserFactory(username="TwinName")
        UserFactory(username="twinname")

        cases = {
            "success": (None, None),
            "wrong password": (None, "wrong"),
            "unknown identifier": ("nobody@example.com", None),
            "user with no Person": (no_person.username, f"{no_person.username}+password"),
            "inactive user": (inactive.user.username, None),
            "unusable password": (unusable.user.username, None),
            "identifier naming two Persons": (shared, None),
            "case-ambiguous username": ("twinname", None),
        }
        for label, (identifier, password) in cases.items():
            with self.counted_hashes() as calls:
                self.verify(identifier=identifier, password=password)
            self.assertEqual(len(calls), 1, f"{label}: {len(calls)} hashes")

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

    def test_github_username_is_deterministic(self):
        """Nothing stops two of them, so the one returned must not be the database's choice"""
        name = ExtResourceName.objects.get(slug="github_username")
        for value in ("zzz-second", "aaa-first"):
            PersonExtResource.objects.create(
                person=self.person, name=name, value=value
            )
        self.assertEqual(self.verify().json()["github_username"], "aaa-first")

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
            self.assertEqual(r.status_code, 400)
            self.assertEqual(r.json()["errors"][0]["code"], "verification_failed")
        self.assertEqual(len({r.content for r in failures}), 1)

    def test_ambiguous_identifier_is_refused(self):
        UserFactory(username=self.person.user.username.upper())
        r = self.verify()
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["errors"][0]["code"], "verification_failed")

    def test_a_username_and_another_persons_address_is_refused(self):
        """One string naming two Persons is not resolved by proving one of the passwords"""
        other = PersonFactory()
        shared = EmailFactory(person=other).address
        claimant = PersonFactory(user__username=shared)
        self.assertNotEqual(claimant, other, "Test is broken")

        r = self.verify(
            identifier=shared, password=f"{claimant.user.username}+password"
        )
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["errors"][0]["code"], "verification_failed")

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
        self.assertEqual(r.json()["errors"][0]["code"], "undecryptable_password")

    def test_wrong_key_is_not_a_credential_failure(self):
        """Encrypted to somebody else's public key"""
        stranger = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        r = self.client.post(
            self.url,
            {
                "username_or_email": self.person.user.username,
                "encrypted_password": seal(self.password, key=stranger),
            },
            format="json",
            headers={"X-Api-Key": VERIFY_TOKEN},
        )
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["errors"][0]["code"], "undecryptable_password")

    @override_settings(ACCOUNT_MIGRATION_PRIVATE_KEY=b"not-a-pem")
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
        """Also 400, so the code is what tells it apart from a failed verification"""
        r = self.client.post(
            self.url,
            {"encrypted_password": seal("x")},
            format="json",
            headers={"X-Api-Key": VERIFY_TOKEN},
        )
        self.assertEqual(r.status_code, 400)
        self.assertEqual(
            [(e["attr"], e["code"]) for e in r.json()["errors"]],
            [("username_or_email", "required")],
        )


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
        self.assertEqual(r.status_code, 400)
        self.assertEqual(
            r.json()["errors"][0]["code"], "address_belongs_to_another_person"
        )
        self.assertEqual(Email.objects.get(address=address).person, other)

    def test_refuses_an_unowned_address(self):
        orphan = self.unowned_email()
        r = self.claim(orphan.address)
        self.assertEqual(r.status_code, 400)
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
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["errors"][0]["code"], "unknown_person_uuid")
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
        self.assertEqual(r.status_code, 400)
        self.assertEqual(
            r.json()["errors"][0]["code"], "address_belongs_to_another_person"
        )


@override_settings(
    APP_API_TOKENS={
        "ietf.ietfauth.api_migration.verify": [VERIFY_TOKEN],
        "ietf.ietfauth.api_migration.claim_email": [CLAIM_TOKEN],
    },
    ACCOUNT_MIGRATION_PRIVATE_KEY=PRIVATE_KEY,
)
class TokenScopeTests(APITestCase):
    """Each endpoint's token opens only that endpoint

    Every other test class configures one token, so none of them would notice one
    endpoint honouring another's. Per-endpoint api_key_endpoint names exist so a token
    can be withdrawn on its own, which only means anything if this holds.
    """

    def setUp(self):
        super().setUp()
        self.person = PersonFactory()
        self.verify_url = urlreverse("ietf.api.migration_api.verify")
        self.claim_url = urlreverse("ietf.api.migration_api.claim-email")
        self.verify_body = {
            "username_or_email": self.person.user.username,
            "encrypted_password": seal(f"{self.person.user.username}+password"),
        }
        self.claim_body = {
            "person_uuid": str(self.person.primary_uuid),
            "address": "new@example.com",
        }

    def post(self, url, body, token):
        return self.client.post(
            url, body, format="json", headers={"X-Api-Key": token}
        )

    def test_each_token_opens_only_its_own_endpoint(self):
        self.assertEqual(
            self.post(self.verify_url, self.verify_body, VERIFY_TOKEN).status_code, 200
        )
        self.assertEqual(
            self.post(self.claim_url, self.claim_body, CLAIM_TOKEN).status_code, 200
        )
        self.assertEqual(
            self.post(self.verify_url, self.verify_body, CLAIM_TOKEN).status_code, 403
        )
        self.assertEqual(
            self.post(self.claim_url, self.claim_body, VERIFY_TOKEN).status_code, 403
        )

    def test_a_logged_in_session_is_not_enough(self):
        """SessionAuthentication is in the DRF defaults, so it reaches these endpoints"""
        self.assertTrue(
            self.client.login(
                username=self.person.user.username,
                password=f"{self.person.user.username}+password",
            ),
            "Test is broken",
        )
        for url, body in ((self.verify_url, self.verify_body), (self.claim_url, self.claim_body)):
            self.assertEqual(
                self.client.post(url, body, format="json").status_code, 403, url
            )


class SchemaTests(TestCase):
    """The generated OpenAPI schema describes the errors these endpoints actually raise

    drf-standardized-errors builds the error responses, and listing a status code in
    extend_schema's responses suppresses that generation - so a well-meant annotation can
    silently replace a documented error with "no response body".
    """

    @classmethod
    def setUpTestData(cls):
        cls.schema = SchemaGenerator().get_schema(request=None, public=True)

    def codes_for(self, path, status_code):
        """Every value the `code` enum can take in that response, refs followed"""
        response = self.schema["paths"][path]["post"]["responses"][str(status_code)]
        self.assertIn("content", response, f"{path} {status_code} has no body")
        codes = set()

        def walk(node):
            if isinstance(node, dict):
                if "$ref" in node:
                    name = node["$ref"].rsplit("/", 1)[1]
                    walk(self.schema["components"]["schemas"][name])
                    return
                for key, value in node.items():
                    if key == "code":
                        target = value
                        if "$ref" in target:
                            target = self.schema["components"]["schemas"][
                                target["$ref"].rsplit("/", 1)[1]
                            ]
                        codes.update(target.get("enum", []))
                    else:
                        walk(value)
            elif isinstance(node, list):
                for item in node:
                    walk(item)

        walk(response["content"]["application/json"]["schema"])
        return codes

    def test_verify_documents_its_own_failures(self):
        path = "/api/accounts/migration/verify/"
        codes = self.codes_for(path, 400)
        self.assertIn("verification_failed", codes)
        self.assertIn("undecryptable_password", codes)
        self.assertIn("required", codes, "serializer validation should still be described")
        self.assertNotIn(
            "401",
            self.schema["paths"][path]["post"]["responses"],
            "a credential failure is a 400 with a code, not a 401",
        )

    def test_claim_email_documents_its_own_refusals(self):
        codes = self.codes_for("/api/accounts/migration/claim-email/", 400)
        self.assertLessEqual(
            {
                "address_belongs_to_another_person",
                "address_has_no_owner",
                "unknown_person_uuid",
            },
            codes,
        )
        self.assertNotIn(
            "409",
            self.schema["paths"]["/api/accounts/migration/claim-email/"]["post"][
                "responses"
            ],
            "a refusal is about the data supplied, not the state of a resource",
        )
