import base64
import binascii
from hashlib import md5, sha256
import json

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.conf import settings


CLIENT_TYPE_CHOICES = [
    ('confidential', 'Confidential'),
    ('public', 'Public'),
]

RESPONSE_TYPE_CHOICES = [
    ('code', 'code (Authorization Code Flow)'),
    ('id_token', 'id_token (Implicit Flow)'),
    ('id_token token', 'id_token token (Implicit Flow)'),
    ('code token', 'code token (Hybrid Flow)'),
    ('code id_token', 'code id_token (Hybrid Flow)'),
    ('code id_token token', 'code id_token token (Hybrid Flow)'),
]

JWT_ALGS = [
    ('HS256', 'HS256'),
    ('RS256', 'RS256'),
]


class ResponseTypeManager(models.Manager):
    def get_by_natural_key(self, value):
        return self.get(value=value)


class ResponseType(models.Model):
    objects = ResponseTypeManager()

    value = models.CharField(
        max_length=30,
        choices=RESPONSE_TYPE_CHOICES,
        unique=True,
        verbose_name=_(u'Response Type Value'))
    description = models.CharField(
        max_length=50,
    )

    def natural_key(self):
        return self.value,  # natural_key must return tuple

    def __str__(self):
        return u'{0}'.format(self.description)


class Client(models.Model):

    name = models.CharField(max_length=100, default='', verbose_name=_(u'Name'))
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name=_(u'Owner'), blank=True,
        null=True, default=None, on_delete=models.SET_NULL, related_name='oidc_clients_set')
    client_type = models.CharField(
        max_length=30,
        choices=CLIENT_TYPE_CHOICES,
        default='confidential',
        verbose_name=_(u'Client Type'),
        help_text=_(u'<b>Confidential</b> clients are capable of maintaining the confidentiality'
                    u' of their credentials. <b>Public</b> clients are incapable.'))
    client_id = models.CharField(max_length=255, unique=True, verbose_name=_(u'Client ID'))
    client_secret = models.CharField(max_length=255, blank=True, verbose_name=_(u'Client SECRET'))
    response_types = models.ManyToManyField(ResponseType)
    jwt_alg = models.CharField(
        max_length=10,
        choices=JWT_ALGS,
        default='RS256',
        verbose_name=_(u'JWT Algorithm'),
        help_text=_(u'Algorithm used to encode ID Tokens.'))
    date_created = models.DateField(auto_now_add=True, verbose_name=_(u'Date Created'))
    website_url = models.CharField(
        max_length=255, blank=True, default='', verbose_name=_(u'Website URL'))
    terms_url = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name=_(u'Terms URL'),
        help_text=_(u'External reference to the privacy policy of the client.'))
    contact_email = models.CharField(
        max_length=255, blank=True, default='', verbose_name=_(u'Contact Email'))
    logo = models.FileField(
        blank=True, default='', upload_to='oidc_provider/clients', verbose_name=_(u'Logo Image'))
    reuse_consent = models.BooleanField(
        default=True,
        verbose_name=_('Reuse Consent?'),
        help_text=_('If enabled, server will save the user consent given to a specific client, '
                    'so that user won\'t be prompted for the same authorization multiple times.'))
    require_consent = models.BooleanField(
        default=True,
        verbose_name=_('Require Consent?'),
        help_text=_('If disabled, the Server will NEVER ask the user for consent.'))
    _redirect_uris = models.TextField(
        default='', verbose_name=_(u'Redirect URIs'),
        help_text=_(u'Enter each URI on a new line.'))
    _post_logout_redirect_uris = models.TextField(
        blank=True,
        default='',
        verbose_name=_(u'Post Logout Redirect URIs'),
        help_text=_(u'Enter each URI on a new line.'))
    _scope = models.TextField(
        blank=True,
        default='',
        verbose_name=_(u'Scopes'),
        help_text=_('Specifies the authorized scope values for the client app.'))

    class Meta:
        verbose_name = _(u'Client')
        verbose_name_plural = _(u'Clients')

    def __str__(self):
        return u'{0}'.format(self.name)

    def __unicode__(self):
        return self.__str__()

    def response_type_values(self):
        return (response_type.value for response_type in self.response_types.all())

    def response_type_descriptions(self):
        # return as a list, rather than a generator, so descriptions display correctly in admin
        return [response_type.description for response_type in self.response_types.all()]

    @property
    def redirect_uris(self):
        return self._redirect_uris.splitlines()

    @redirect_uris.setter
    def redirect_uris(self, value):
        self._redirect_uris = '\n'.join(value)

    @property
    def post_logout_redirect_uris(self):
        return self._post_logout_redirect_uris.splitlines()

    @post_logout_redirect_uris.setter
    def post_logout_redirect_uris(self, value):
        self._post_logout_redirect_uris = '\n'.join(value)

    @property
    def scope(self):
        return self._scope.split()

    @scope.setter
    def scope(self, value):
        self._scope = ' '.join(value)

    @property
    def default_redirect_uri(self):
        return self.redirect_uris[0] if self.redirect_uris else ''


class BaseCodeTokenModel(models.Model):

    client = models.ForeignKey(Client, verbose_name=_(u'Client'), on_delete=models.CASCADE)
    expires_at = models.DateTimeField(verbose_name=_(u'Expiration Date'))
    _scope = models.TextField(default='', verbose_name=_(u'Scopes'))

    class Meta:
        abstract = True

    @property
    def scope(self):
        return self._scope.split()

    @scope.setter
    def scope(self, value):
        self._scope = ' '.join(value)

    def __unicode__(self):
        return self.__str__()

    def has_expired(self):
        return timezone.now() >= self.expires_at


class Code(BaseCodeTokenModel):

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name=_(u'User'), on_delete=models.CASCADE)
    code = models.CharField(max_length=255, unique=True, verbose_name=_(u'Code'))
    nonce = models.CharField(max_length=255, blank=True, default='', verbose_name=_(u'Nonce'))
    is_authentication = models.BooleanField(default=False, verbose_name=_(u'Is Authentication?'))
    code_challenge = models.CharField(max_length=255, null=True, verbose_name=_(u'Code Challenge'))
    code_challenge_method = models.CharField(
        max_length=255, null=True, verbose_name=_(u'Code Challenge Method'))

    class Meta:
        verbose_name = _(u'Authorization Code')
        verbose_name_plural = _(u'Authorization Codes')

    def __str__(self):
        return u'{0} - {1}'.format(self.client, self.code)


class Token(BaseCodeTokenModel):

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, verbose_name=_(u'User'), on_delete=models.CASCADE)
    access_token = models.CharField(max_length=255, unique=True, verbose_name=_(u'Access Token'))
    refresh_token = models.CharField(max_length=255, unique=True, verbose_name=_(u'Refresh Token'))
    _id_token = models.TextField(verbose_name=_(u'ID Token'))

    class Meta:
        verbose_name = _(u'Token')
        verbose_name_plural = _(u'Tokens')

    @property
    def id_token(self):
        return json.loads(self._id_token) if self._id_token else None

    @id_token.setter
    def id_token(self, value):
        self._id_token = json.dumps(value)

    def __str__(self):
        return u'{0} - {1}'.format(self.client, self.access_token)

    @property
    def at_hash(self):
        # @@@ d-o-p only supports 256 bits (change this if that changes)
        hashed_access_token = sha256(
            self.access_token.encode('ascii')
        ).hexdigest().encode('ascii')
        return base64.urlsafe_b64encode(
            binascii.unhexlify(
                hashed_access_token[:len(hashed_access_token) // 2]
            )
        ).rstrip(b'=').decode('ascii')


class UserConsent(BaseCodeTokenModel):

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name=_(u'User'), on_delete=models.CASCADE)
    date_given = models.DateTimeField(verbose_name=_(u'Date Given'))

    class Meta:
        unique_together = ('user', 'client')


class RSAKey(models.Model):

    key = models.TextField(
        verbose_name=_(u'Key'), help_text=_(u'Paste your private RSA Key here.'))

    class Meta:
        verbose_name = _(u'RSA Key')
        verbose_name_plural = _(u'RSA Keys')

    def __str__(self):
        return u'{0}'.format(self.kid)

    def __unicode__(self):
        return self.__str__()

    @property
    def kid(self):
        return u'{0}'.format(md5(self.key.encode('utf-8')).hexdigest() if self.key else '')
