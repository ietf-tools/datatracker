import copy

from django.utils.translation import gettext_lazy as _

from oidc_provider import settings


STANDARD_CLAIMS = {
    'name': '',
    'given_name': '',
    'family_name': '',
    'middle_name': '',
    'nickname': '',
    'preferred_username': '',
    'profile': '',
    'picture': '',
    'website': '',
    'gender': '',
    'birthdate': '',
    'zoneinfo': '',
    'locale': '',
    'updated_at': '',
    'email': '',
    'email_verified': '',
    'phone_number': '',
    'phone_number_verified': '',
    'address': {
        'formatted': '',
        'street_address': '',
        'locality': '',
        'region': '',
        'postal_code': '',
        'country': '',
    },
}


class ScopeClaims(object):

    def __init__(self, token):
        self.user = token.user
        claims = copy.deepcopy(STANDARD_CLAIMS)
        self.userinfo = settings.get('OIDC_USERINFO', import_str=True)(claims, self.user)
        self.scopes = token.scope
        self.client = token.client

    def create_response_dic(self):
        """
        Generate the dic that will be jsonify. Checking scopes given vs
        registered.

        Returns a dic.
        """
        dic = {}

        for scope in self.scopes:
            if scope in self._scopes_registered():
                dic.update(getattr(self, 'scope_' + scope)())

        dic = self._clean_dic(dic)

        return dic

    def _scopes_registered(self):
        """
        Return a list that contains all the scopes registered
        in the class.
        """
        scopes = []

        for name in dir(self.__class__):
            if name.startswith('scope_'):
                scope = name.split('scope_')[1]
                scopes.append(scope)

        return scopes

    def _clean_dic(self, dic):
        """
        Clean recursively all empty or None values inside a dict.
        """
        aux_dic = dic.copy()
        for key, value in iter(dic.items()):

            if value is None or value == '':
                del aux_dic[key]
            elif type(value) is dict:
                cleaned_dict = self._clean_dic(value)
                if not cleaned_dict:
                    del aux_dic[key]
                    continue
                aux_dic[key] = cleaned_dict
        return aux_dic

    @classmethod
    def get_scopes_info(cls, scopes=None):
        if scopes is None:
            scopes = []
        scopes_info = []

        for name in dir(cls):
            if name.startswith('info_'):
                scope_name = name.split('info_')[1]
                if scope_name in scopes:
                    touple_info = getattr(cls, name)
                    scopes_info.append({
                        'scope': scope_name,
                        'name': touple_info[0],
                        'description': touple_info[1],
                    })

        return scopes_info


class StandardScopeClaims(ScopeClaims):
    """
    Based on OpenID Standard Claims.
    See: http://openid.net/specs/openid-connect-core-1_0.html#StandardClaims
    """

    info_profile = (
        _(u'Basic profile'),
        _(u'Access to your basic information. Includes names, gender, birthdate '
          'and other information.'),
    )

    def scope_profile(self):
        dic = {
            'name': self.userinfo.get('name'),
            'given_name': (self.userinfo.get('given_name') or
                           getattr(self.user, 'first_name', None)),
            'family_name': (self.userinfo.get('family_name') or
                            getattr(self.user, 'last_name', None)),
            'middle_name': self.userinfo.get('middle_name'),
            'nickname': self.userinfo.get('nickname') or getattr(self.user, 'username', None),
            'preferred_username': self.userinfo.get('preferred_username'),
            'profile': self.userinfo.get('profile'),
            'picture': self.userinfo.get('picture'),
            'website': self.userinfo.get('website'),
            'gender': self.userinfo.get('gender'),
            'birthdate': self.userinfo.get('birthdate'),
            'zoneinfo': self.userinfo.get('zoneinfo'),
            'locale': self.userinfo.get('locale'),
            'updated_at': self.userinfo.get('updated_at'),
        }

        return dic

    info_email = (
        _(u'Email'),
        _(u'Access to your email address.'),
    )

    def scope_email(self):
        dic = {
            'email': self.userinfo.get('email') or getattr(self.user, 'email', None),
            'email_verified': self.userinfo.get('email_verified'),
        }

        return dic

    info_phone = (
        _(u'Phone number'),
        _(u'Access to your phone number.'),
    )

    def scope_phone(self):
        dic = {
            'phone_number': self.userinfo.get('phone_number'),
            'phone_number_verified': self.userinfo.get('phone_number_verified'),
        }

        return dic

    info_address = (
        _(u'Address information'),
        _(u'Access to your address. Includes country, locality, street and other information.'),
    )

    def scope_address(self):
        dic = {
            'address': {
                'formatted': self.userinfo.get('address', {}).get('formatted'),
                'street_address': self.userinfo.get('address', {}).get('street_address'),
                'locality': self.userinfo.get('address', {}).get('locality'),
                'region': self.userinfo.get('address', {}).get('region'),
                'postal_code': self.userinfo.get('address', {}).get('postal_code'),
                'country': self.userinfo.get('address', {}).get('country'),
            }
        }

        return dic
