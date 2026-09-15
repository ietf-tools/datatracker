# Copyright The IETF Trust 2026, All Rights Reserved
"""Account migration API

Serves the account app's backend while people move their datatracker accounts to the
external identity provider. Responses are Person-scoped - no User.username, no
User.email, no password material - and each endpoint has its own api_key_endpoint so its
token can be withdrawn separately.
"""

from base64 import b64decode
from urllib.parse import urljoin

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from drf_spectacular.utils import extend_schema
from drf_standardized_errors.openapi_serializers import ClientErrorEnum
from drf_standardized_errors.openapi_validation_errors import extend_validation_errors
from rest_framework import exceptions, serializers, status
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from django.conf import settings
from django.contrib.auth.models import User
from django.core.validators import validate_email
from django.views.decorators.debug import sensitive_variables
from django.db import IntegrityError, transaction

from ietf.person.models import Email, Person, PersonUUID
from ietf.utils import log

GITHUB_USERNAME_SLUG = "github_username"

# Origin of Emails this API creates, so support can see where an address came from.
CLAIM_ORIGIN = "account migration"


class VerificationFailed(exceptions.ValidationError):
    """The one failure verify/ has, so it cannot be used to find which addresses exist

    Not a 401: the caller is authenticated, and the password that failed is payload. A
    401 would also owe a WWW-Authenticate challenge (RFC 9110) there is nothing to fill.
    """

    default_detail = "Unable to verify those credentials."
    default_code = "verification_failed"


class UndecryptablePassword(exceptions.ValidationError):
    """Its own code, so a drifted key does not look like every user mistyping"""

    default_detail = "Unable to decrypt the password."
    default_code = "undecryptable_password"


@sensitive_variables()
def decrypt_password(envelope):
    """The plaintext inside a base64 RSA-OAEP envelope

    Encrypted to the datatracker's public key, so only the datatracker can open it and a
    leak at the caller exposes nothing already sent. No plaintext path: an unencrypted
    password is refused like any other malformed envelope.

    A private key this end cannot load raises rather than returning 400, which would
    report the datatracker's own misconfiguration as the caller's mistake.
    """
    private_key = serialization.load_pem_private_key(
        settings.ACCOUNT_MIGRATION_PRIVATE_KEY, password=None
    )
    try:
        plaintext = private_key.decrypt(
            b64decode(envelope, validate=True),
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )
        return plaintext.decode()
    except (ValueError, UnicodeDecodeError):
        # from None: nothing about the envelope should reach a chained traceback.
        raise UndecryptablePassword() from None


@sensitive_variables()
def authenticate_person(identifier, password):
    """The Person whose account these credentials prove, or None

    CaseInsensitiveModelBackend's semantics for User.username, extended to the Person's
    Email addresses because the address is what people know they have. Hashes a password
    when nothing matched, so an unknown identifier costs about what a wrong one does.

    An identifier naming two Persons is refused rather than resolved arbitrarily - two
    usernames differing only in case, or one Person's username that is another's address.
    The password cannot settle it: it proves only that the caller holds one of the two.
    """
    candidates = list(User.objects.filter(username__iexact=identifier)[:2])
    if len(candidates) > 1:
        return None
    user = candidates[0] if candidates else None
    # Email.address is a case-insensitive primary key, so this matches at most one row.
    email = Email.objects.filter(address__iexact=identifier).first()
    # An Email with no Person names nobody, so it cannot disagree with the username.
    addressee = email.person if email else None

    if user is None:
        user = addressee.user if addressee else None
    person = Person.objects.filter(user=user).first() if user else None
    if addressee is not None and person is not None and addressee != person:
        return None
    if user is None:
        User().set_password(password)
        return None
    if not (user.check_password(password) and user.is_active):
        return None
    return person


def portrait_url(person):
    """Absolute URL of the full-frame photo, which the provider derives thumbnails from"""
    if not person.photo:
        return None
    return urljoin(settings.IDTRACKER_BASE_URL, person.photo.url)


def github_username(person):
    """The Person's GitHub username, or None

    Ordered because nothing stops a Person having two: the profile editor takes resources
    as free text and never checks that a tag appears once. Repeatable beats arbitrary.
    """
    return (
        person.personextresource_set.filter(name_id=GITHUB_USERNAME_SLUG)
        .order_by("value")
        .values_list("value", flat=True)
        .first()
    )


def email_payload(person):
    """Every Email of the Person, primary first, then active ones oldest first

    Inactive ones included: enrollment offers the active addresses but must recognise an
    inactive one the person types, which claim-email/ reactivates.
    """
    return [
        {"address": email.address, "primary": email.primary, "active": email.active}
        for email in person.email_set.order_by("-primary", "-active", "time")
    ]


class NameSerializer(serializers.Serializer):
    full = serializers.CharField()
    plain = serializers.CharField()
    first = serializers.CharField()
    last = serializers.CharField()


class MigrationEmailSerializer(serializers.Serializer):
    address = serializers.CharField()
    primary = serializers.BooleanField()
    active = serializers.BooleanField()


class VerifyRequestSerializer(serializers.Serializer):
    username_or_email = serializers.CharField()
    encrypted_password = serializers.CharField(trim_whitespace=False)


class VerifyResponseSerializer(serializers.Serializer):
    """The account the credentials proved, as much of it as enrollment needs

    Output only, but not read_only=True per field: read_only implies required=False,
    leaving a generated client treating every field as optional. person_uuid is null only
    when the Person's UUID rows are inconsistent, which check_person_uuids reports.
    """

    person_uuid = serializers.UUIDField(allow_null=True)
    name = NameSerializer()
    emails = MigrationEmailSerializer(many=True)
    pronouns = serializers.CharField(allow_null=True)
    github_username = serializers.CharField(allow_null=True)
    portrait_url = serializers.URLField(allow_null=True)
    legacy_sub = serializers.CharField()
    last_login = serializers.DateTimeField(allow_null=True)
    already_linked = serializers.BooleanField()


@extend_schema(tags=["migration"])
@extend_validation_errors(["verification_failed", "undecryptable_password"])
class VerifyView(APIView):
    """Prove a datatracker password and get back the Person behind it"""

    api_key_endpoint = "ietf.ietfauth.api_migration.verify"

    @extend_schema(
        operation_id="account_migration_verify",
        summary="Validate datatracker credentials",
        description=(
            "Validate a datatracker login and return the Person it belongs to, so the "
            "account app can offer that person's addresses and profile while it builds "
            "their new account.\n\n"
            "encrypted_password is the password encrypted to the datatracker's public "
            "key with RSA-OAEP (SHA-256 for both the digest and MGF1, no label) and "
            "base64 encoded. The password is never sent in the clear and there is no "
            "unencrypted alternative. An envelope that does not open is a 400 with code "
            "undecryptable_password, which means the key in use is not the one this "
            "datatracker holds - it is not a statement about the credentials, and is "
            "worth alerting on rather than showing the person.\n\n"
            "Matching on the identifier is case-insensitive, and it may be either the "
            "datatracker username or any of the Person's email addresses.\n\n"
            "Every credential failure is the same 400 with code verification_failed: "
            "an unknown address, a wrong password, a disabled account, an identifier "
            "that names two people and an account with no Person are not "
            "distinguished, so the response cannot be used to discover which addresses "
            "exist. It is not a 401 - the caller is authenticated, and what failed is "
            "the password it asked about. There is no lockout: repeated failures "
            "neither block the caller nor let one person deny another their "
            "enrollment.\n\n"
            "emails carries every address of the Person, including inactive ones - offer "
            "the active ones and treat the rest as claimable. already_linked true means "
            "the Person is already attached to an account and enrollment must stop and "
            "send them to normal login instead.\n\n"
            "The response is Person-scoped. It carries no datatracker username, no "
            "password material, and no database keys apart from legacy_sub, which is the "
            "subject the datatracker used to issue for this account and is needed only "
            "to keep existing relying parties working."
        ),
        request=VerifyRequestSerializer,
        responses={200: VerifyResponseSerializer},
    )
    @sensitive_variables()
    def post(self, request):
        request_serializer = VerifyRequestSerializer(data=request.data)
        request_serializer.is_valid(raise_exception=True)
        identifier = request_serializer.validated_data["username_or_email"]

        person = authenticate_person(
            identifier,
            decrypt_password(request_serializer.validated_data["encrypted_password"]),
        )
        if person is None:
            log.log(f"account migration: verify/ rejected {identifier!r}")
            raise VerificationFailed()

        log.log(
            f"account migration: verify/ accepted {identifier!r} "
            f"as Person {person.primary_uuid}"
        )
        return Response(
            VerifyResponseSerializer(
                {
                    "person_uuid": person.primary_uuid,
                    "name": {
                        "full": person.name,
                        "plain": person.plain_name(),
                        "first": person.first_name(),
                        "last": person.last_name(),
                    },
                    "emails": email_payload(person),
                    "pronouns": person.pronouns() or None,
                    "github_username": github_username(person),
                    "portrait_url": portrait_url(person),
                    "legacy_sub": str(person.user.pk),
                    "last_login": person.user.last_login,
                    # TODO: report the real state once link/ exists and there are link
                    # records to read. Nothing can be linked before anything writes one.
                    "already_linked": False,
                }
            ).data
        )


class AddressBelongsToAnotherPerson(exceptions.APIException):
    """The address is another Person's, and an Email is never moved between Persons

    Its own code because the flow can act on it: offer another address, or route to
    support, who may find the two Persons should be merged.
    """

    status_code = status.HTTP_409_CONFLICT
    default_detail = "That address belongs to a different person."
    default_code = "address_belongs_to_another_person"


class AddressHasNoOwner(exceptions.APIException):
    """The address exists but no Person owns it

    Refused, not adopted. Draft submissions and roles record addresses without
    establishing who is behind them, and history points through those rows; handing one
    to whoever proved a password would attribute that history to a possible namesake.
    """

    status_code = status.HTTP_409_CONFLICT
    default_detail = "That address is not attached to any person."
    default_code = "address_has_no_owner"


# 409 is not in DRF_STANDARDIZED_ERRORS["ALLOWED_ERROR_STATUS_CODES"], so nothing
# generates its response, and adding it there would give every operation a 409.
CLAIM_EMAIL_CONFLICT_CODES = (
    "address_belongs_to_another_person",
    "address_has_no_owner",
)


class ClaimEmailConflictSerializer(serializers.Serializer):
    code = serializers.ChoiceField(choices=CLAIM_EMAIL_CONFLICT_CODES)
    detail = serializers.CharField()
    attr = serializers.CharField(allow_null=True)


class ClaimEmailConflictResponseSerializer(serializers.Serializer):
    """The standardized-errors envelope, for the one status code it does not generate"""

    type = serializers.ChoiceField(choices=ClientErrorEnum.choices)
    errors = ClaimEmailConflictSerializer(many=True)


def claim_address(person, address):
    """The Email row for the address, creating it for the Person if there is none

    Returns (email, created). Savepointed and re-read on conflict: address is the primary
    key, and the loser of a two-tab race has to reach the ownership checks rather than
    fail a request documented as idempotent.
    """
    email = Email.objects.filter(address__iexact=address).first()
    if email is not None:
        return email, False
    try:
        with transaction.atomic():
            return (
                Email.objects.create(
                    address=address, person=person, origin=CLAIM_ORIGIN
                ),
                True,
            )
    except IntegrityError:
        return Email.objects.get(address__iexact=address), False


def person_for_uuid(person_uuid):
    """The Person a UUID belongs to, prior UUIDs included, so pre-merge UUIDs resolve"""
    return get_object_or_404(
        PersonUUID.objects.select_related("person"), uuid=person_uuid
    ).person


class ClaimEmailRequestSerializer(serializers.Serializer):
    person_uuid = serializers.UUIDField()
    address = serializers.CharField(max_length=64, validators=[validate_email])


@extend_schema(tags=["migration"])
class ClaimEmailView(APIView):
    """Attach an address to a Person, so enrollment can use it"""

    api_key_endpoint = "ietf.ietfauth.api_migration.claim_email"

    @extend_schema(
        operation_id="account_migration_claim_email",
        summary="Give a Person an address, or reactivate one it already has",
        description=(
            "Make an address usable by the Person enrolling, whether it is new to the "
            "datatracker, already theirs, or theirs but inactive. Idempotent: calling it "
            "again with the same arguments succeeds and changes nothing.\n\n"
            "person_uuid may be any UUID the datatracker has issued for the Person, not "
            "only the current primary. An unknown one is a 404.\n\n"
            "Two failures are worth handling separately, both 409, told apart by their "
            "error code. address_belongs_to_another_person means the address is someone "
            "else's; it is never moved, so offer another address or send the person to "
            "support, who may find the two Persons should be merged. "
            "address_has_no_owner means the datatracker knows the address but has never "
            "established who is behind it - support establishes that, not enrollment.\n\n"
            "The response describes the address as it now stands. It does not make the "
            "address primary - which address is primary is the person's own profile "
            "choice and is not changed here."
        ),
        request=ClaimEmailRequestSerializer,
        responses={
            200: MigrationEmailSerializer,
            409: ClaimEmailConflictResponseSerializer,
        },
    )
    @transaction.atomic
    def post(self, request):
        request_serializer = ClaimEmailRequestSerializer(data=request.data)
        request_serializer.is_valid(raise_exception=True)
        person_uuid = request_serializer.validated_data["person_uuid"]
        address = request_serializer.validated_data["address"]

        person = person_for_uuid(person_uuid)
        email, created = claim_address(person, address)
        if created:
            outcome = "created"
        elif email.person_id is None:
            log.log(
                f"account migration: claim-email/ refused {address!r} for "
                f"Person {person_uuid}, owned by no Person"
            )
            raise AddressHasNoOwner()
        elif email.person_id != person.pk:
            log.log(
                f"account migration: claim-email/ refused {address!r} for "
                f"Person {person_uuid}, held by another Person"
            )
            raise AddressBelongsToAnotherPerson()
        elif not email.active:
            email.active = True
            email.save()
            outcome = "reactivated"
        else:
            outcome = "unchanged"

        log.log(
            f"account migration: claim-email/ {outcome} {address!r} "
            f"for Person {person_uuid}"
        )
        return Response(
            MigrationEmailSerializer(
                {
                    "address": email.address,
                    "primary": email.primary,
                    "active": email.active,
                }
            ).data
        )
