import logging

from django.http import JsonResponse

from oidc_provider.lib.errors import TokenIntrospectionError
from oidc_provider.lib.utils.common import run_processing_hook
from oidc_provider.lib.utils.oauth2 import extract_client_auth
from oidc_provider.models import Token, Client
from oidc_provider import settings

logger = logging.getLogger(__name__)

INTROSPECTION_SCOPE = 'token_introspection'


class TokenIntrospectionEndpoint(object):

    def __init__(self, request):
        self.request = request
        self.params = {}
        self.token = None
        self.id_token = None
        self.client = None
        self._extract_params()

    def _extract_params(self):
        # Introspection only supports POST requests
        self.params['token'] = self.request.POST.get('token')
        client_id, client_secret = extract_client_auth(self.request)
        self.params['client_id'] = client_id
        self.params['client_secret'] = client_secret

    def validate_params(self):
        if not (self.params['client_id'] and self.params['client_secret']):
            logger.debug('[Introspection] No client credentials provided')
            raise TokenIntrospectionError()
        if not self.params['token']:
            logger.debug('[Introspection] No token provided')
            raise TokenIntrospectionError()
        try:
            self.token = Token.objects.get(access_token=self.params['token'])
        except Token.DoesNotExist:
            logger.debug('[Introspection] Token does not exist: %s', self.params['token'])
            raise TokenIntrospectionError()
        if self.token.has_expired():
            logger.debug('[Introspection] Token is not valid: %s', self.params['token'])
            raise TokenIntrospectionError()

        try:
            self.client = Client.objects.get(
                client_id=self.params['client_id'],
                client_secret=self.params['client_secret'])
        except Client.DoesNotExist:
            logger.debug('[Introspection] No valid client for id: %s',
                         self.params['client_id'])
            raise TokenIntrospectionError()
        if INTROSPECTION_SCOPE not in self.client.scope:
            logger.debug('[Introspection] Client %s does not have introspection scope',
                         self.params['client_id'])
            raise TokenIntrospectionError()

        self.id_token = self.token.id_token

        if settings.get('OIDC_INTROSPECTION_VALIDATE_AUDIENCE_SCOPE'):
            if not self.token.id_token:
                logger.debug('[Introspection] Token not an authentication token: %s',
                             self.params['token'])
                raise TokenIntrospectionError()

            audience = self.token.id_token.get('aud')
            if not audience:
                logger.debug('[Introspection] No audience found for token: %s',
                             self.params['token'])
                raise TokenIntrospectionError()

            if audience not in self.client.scope:
                logger.debug('[Introspection] Client %s does not audience scope %s',
                             self.params['client_id'], audience)
                raise TokenIntrospectionError()

    def create_response_dic(self):
        response_dic = {}
        if self.id_token:
            for k in ('aud', 'sub', 'exp', 'iat', 'iss'):
                response_dic[k] = self.id_token[k]
        response_dic['active'] = True
        response_dic['client_id'] = self.token.client.client_id
        if settings.get('OIDC_INTROSPECTION_RESPONSE_SCOPE_ENABLE'):
            response_dic['scope'] = ' '.join(self.token.scope)
        response_dic = run_processing_hook(response_dic,
                                           'OIDC_INTROSPECTION_PROCESSING_HOOK',
                                           client=self.client,
                                           id_token=self.id_token)

        return response_dic

    @classmethod
    def response(cls, dic, status=200):
        """
        Create and return a response object.
        """
        response = JsonResponse(dic, status=status)
        response['Cache-Control'] = 'no-store'
        response['Pragma'] = 'no-cache'

        return response
