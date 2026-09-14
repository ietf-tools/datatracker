# Copyright The IETF Trust 2026, All Rights Reserved
"""Account migration API

Serves the account app's backend while people move their datatracker accounts to the
external identity provider. Every response is Person-scoped: no User.username, no
User.email and no password material, so the account app never learns the legacy username
it is the point of the migration to stop using.

Each endpoint carries its own api_key_endpoint so its token can be withdrawn on its own.
"""

from urllib.parse import urljoin

from cryptography.fernet import Fernet, InvalidToken
from drf_spectacular.utils import extend_schema
from rest_framework import exceptions, serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from django.conf import settings
from django.contrib.auth.models import User

from ietf.api.authentication import ApiKeyAuthentication, BearerTokenAuthentication
from ietf.person.models import Email, Person
from ietf.utils import log

GITHUB_USERNAME_SLUG = "github_username"


class VerificationFailed(exceptions.APIException):
    """The one failure verify/ has

    An unknown address, a wrong password, a disabled account and an account with no Person
    all raise this, so the endpoint cannot be used to work out which addresses exist.
    """

    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = "Unable to verify those credentials."
    default_code = "verification_failed"


class UndecryptablePassword(exceptions.APIException):
    """The password envelope did not open

    Not a 401: it says nothing about the credentials, and answering with one would leave a
    key that has drifted out of step looking exactly like every user typing the wrong
    password.
    """

    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Unable to decrypt the password."
    default_code = "undecryptable_password"


def decrypt_password(envelope):
    """The plaintext password inside a Fernet envelope

    The caller encrypts under a key shared with the datatracker so that the password does
    not travel in the clear. There is no plaintext path: a password that arrives
    unencrypted cannot open and is refused like any other malformed envelope.
    """
    try:
        return Fernet(settings.ACCOUNT_MIGRATION_PASSWORD_KEY).decrypt(
            envelope.encode()
        ).decode()
    except (InvalidToken, UnicodeDecodeError, ValueError):
        # from None: nothing about the envelope should reach a chained traceback.
        raise UndecryptablePassword() from None


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
            "encrypted_password is the password sealed with the Fernet key shared with "
            "the datatracker; the password is never sent in the clear and there is no "
            "unencrypted alternative. An envelope that does not open is a 400, which "
            "means the keys are out of step - it is not a statement about the "
            "credentials.\n\n"
            "Matching on the identifier is case-insensitive, and it may be either the "
            "datatracker username or any of the Person's email addresses.\n\n"
            "Every credential failure is the same 401. An unknown address, a wrong "
            "password, a disabled account and an account with no Person are not "
            "distinguished, so the response cannot be used to discover which addresses "
            "exist. There is no lockout: repeated failures neither block the caller nor "
            "let one person deny another their enrollment.\n\n"
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
            400: None,
            401: None,
        },
    )
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
