# Copyright The IETF Trust 2026, All Rights Reserved
"""Account migration API

Serves the account app's backend while people move their datatracker accounts to the
external identity provider. Every response is Person-scoped: no User.username, no
User.email and no password material, so the account app never learns the legacy username
it is the point of the migration to stop using.

Each endpoint carries its own api_key_endpoint so its token can be withdrawn on its own.
"""

from urllib.parse import urljoin

from drf_spectacular.utils import extend_schema
from rest_framework import exceptions, serializers, status
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from django.conf import settings
from django.contrib.auth.models import User
from django.core.validators import validate_email
from django.db import transaction

from ietf.api.authentication import ApiKeyAuthentication, BearerTokenAuthentication
from ietf.person.models import Email, ExternalIdentity, Person, PersonUUID
from ietf.utils import log

GITHUB_USERNAME_SLUG = "github_username"

# Recorded on Emails this API creates, so a support question about where an address came
# from has an answer that names the flow rather than a person.
CLAIM_ORIGIN = "account migration"


class VerificationFailed(exceptions.APIException):
    """The one failure verify/ has

    An unknown address, a wrong password, a disabled account and an account with no Person
    all raise this, so the endpoint cannot be used to work out which addresses exist.
    """

    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = "Unable to verify those credentials."
    default_code = "verification_failed"


def authenticate_person(identifier, password):
    """The Person whose account these credentials prove, or None

    Applies CaseInsensitiveModelBackend's semantics to User.username and extends them to
    the Person's Email addresses, because the address is what people know they have. Runs
    a password hash even when nothing matched, so an unknown identifier and a wrong
    password take comparable time.

    An identifier matching more than one User proves nothing about which one the caller
    meant, so it is refused rather than resolved arbitrarily.
    """
    candidates = list(User.objects.filter(username__iexact=identifier)[:2])
    if len(candidates) > 1:
        return None
    user = candidates[0] if candidates else None
    if user is None:
        # Email.address is a case-insensitive primary key, so this matches at most one row.
        email = Email.objects.filter(address__iexact=identifier).first()
        user = email.person.user if email and email.person else None
    if user is None:
        User().set_password(password)
        return None
    if not (user.check_password(password) and user.is_active):
        return None
    return Person.objects.filter(user=user).first()


def portrait_url(person):
    """Absolute URL of the Person's full-frame photo, or None

    The full frame rather than a thumbnail: the provider stores this as the source the
    smaller renderings are derived from.
    """
    if not person.photo:
        return None
    return urljoin(settings.IDTRACKER_BASE_URL, person.photo.url)


def github_username(person):
    return (
        person.personextresource_set.filter(name_id=GITHUB_USERNAME_SLUG)
        .values_list("value", flat=True)
        .first()
    )


def email_payload(person):
    """Every Email of the Person, primary first, then active ones oldest first

    Inactive addresses are included rather than filtered out: the enrollment flow offers
    the active ones but has to recognise an inactive address the person types, which
    claim-email/ reactivates instead of rejecting.
    """
    return [
        {"address": email.address, "primary": email.primary, "active": email.active}
        for email in person.email_set.order_by("-primary", "-active", "time")
    ]


def is_linked(person):
    return person.external_identities.filter(
        state=ExternalIdentity.State.ACTIVE
    ).exists()


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
    password = serializers.CharField(
        trim_whitespace=False, style={"input_type": "password"}
    )


class VerifyResponseSerializer(serializers.Serializer):
    """The account the credentials proved, as much of it as enrollment needs

    Output only, and deliberately not read_only=True field by field: read_only implies
    required=False, which would leave a generated client treating every field as optional.

    person_uuid is null only where the Person's UUID rows are inconsistent, which is a
    data fault rather than a normal outcome.
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
class VerifyView(APIView):
    """Prove a datatracker password and get back the Person behind it"""

    api_key_endpoint = "ietf.ietfauth.api_migration.verify"
    # The account app's legacy client sends Authorization: Token; X-Api-Key is what the
    # rest of this API uses. Both carry an APP_API_TOKENS token for the endpoint above.
    authentication_classes = [ApiKeyAuthentication, BearerTokenAuthentication]  # noqa: RUF012

    @extend_schema(
        operation_id="account_migration_verify",
        summary="Validate datatracker credentials",
        description=(
            "Validate a datatracker login and return the Person it belongs to, so the "
            "account app can offer that person's addresses and profile while it builds "
            "their new account.\n\n"
            "Matching on the identifier is case-insensitive, and it may be either the "
            "datatracker username or any of the Person's email addresses.\n\n"
            "Every failure is the same 401. An unknown address, a wrong password, a "
            "disabled account and an account with no Person are not distinguished, so "
            "the response cannot be used to discover which addresses exist. There is no "
            "lockout: repeated failures neither block the caller nor let one person "
            "deny another their enrollment.\n\n"
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
        responses={
            200: VerifyResponseSerializer,
            401: None,
        },
    )
    def post(self, request):
        request_serializer = VerifyRequestSerializer(data=request.data)
        request_serializer.is_valid(raise_exception=True)
        identifier = request_serializer.validated_data["username_or_email"]

        person = authenticate_person(
            identifier, request_serializer.validated_data["password"]
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
                    "already_linked": is_linked(person),
                }
            ).data
        )


class AddressBelongsToAnotherPerson(exceptions.APIException):
    """The address is another Person's

    Distinct from every other claim-email/ failure because it is the one the flow can act
    on: offer a different address, or route the person to support, who may find this is a
    Person merge rather than a mistake. An Email is never moved between Persons.
    """

    status_code = status.HTTP_409_CONFLICT
    default_detail = "That address belongs to a different person."
    default_code = "address_belongs_to_another_person"


class AddressHasNoOwner(exceptions.APIException):
    """The address exists but no Person owns it

    Refused rather than adopted. These rows come from places that record an address
    without establishing who is behind it - draft submissions, roles - and history points
    through them. Handing one to whoever proved a password would attribute that history on
    no evidence, and the endpoint cannot tell the true owner from a namesake. Support
    establishes ownership; enrollment does not.
    """

    status_code = status.HTTP_409_CONFLICT
    default_detail = "That address is not attached to any person."
    default_code = "address_has_no_owner"


def person_for_uuid(person_uuid):
    """The Person any UUID the datatracker has issued belongs to

    Resolves prior UUIDs as well as the primary, so a caller holding a UUID from before a
    merge still reaches the surviving Person.
    """
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
    # See VerifyView on why both header shapes are accepted.
    authentication_classes = [ApiKeyAuthentication, BearerTokenAuthentication]  # noqa: RUF012

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
            404: None,
            409: None,
        },
    )
    @transaction.atomic
    def post(self, request):
        request_serializer = ClaimEmailRequestSerializer(data=request.data)
        request_serializer.is_valid(raise_exception=True)
        person_uuid = request_serializer.validated_data["person_uuid"]
        address = request_serializer.validated_data["address"]

        person = person_for_uuid(person_uuid)
        email = Email.objects.filter(address__iexact=address).first()
        if email is None:
            email = Email.objects.create(
                address=address, person=person, origin=CLAIM_ORIGIN
            )
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
