from oic.utils.authn.authn_context import make_auth_verify
from oic.utils.authn.user import UserAuthnMethod

__author__ = "danielevertsson"


class MultiAuthnMethod(UserAuthnMethod):
    """
    Small auth module just to kick off multi auth chains (it must be the first module in the chain).

    Do no instantiate this object, use setup_multi_auth instead!
    """

    def __init__(self, auth_module):
        UserAuthnMethod.__init__(self, None)
        self.auth_module = auth_module

    def __call__(self, **kwargs):
        cookie = self.create_cookie(
            kwargs["query"], "query", UserAuthnMethod.MULTI_AUTH_COOKIE
        )
        resp = self.auth_module(**kwargs)
        resp.headers.append(cookie)
        return resp


def setup_multi_auth(auth_broker, urls, auth_modules):
    """
    Set up multiauthn chain.

    :param auth_broker: auth broker
    :param urls: list of (callback) endpoint URLS and their associated callback functions
    :param auth_modules: list of auth modules specifying the order of the multi auth chain
    :return: a multi auth object which must be added to the list of callback endpoints
    """
    multi_auth = MultiAuthnMethod(auth_modules[0][0])

    for i, module_pair in enumerate(auth_modules):
        (module_instance, callback_regexp) = module_pair
        auth_broker.add("", module_instance, 0, "")

        next_module_instance = None

        if i < len(auth_modules) - 1:
            next_module_instance = auth_modules[i + 1][0]

        urls.append(
            (
                callback_regexp,
                make_auth_verify(module_instance.verify, next_module_instance),
            )
        )

    return multi_auth


class AuthnIndexedEndpointWrapper(UserAuthnMethod):
    """
    Wrapper class for using an authn module with multiple endpoints.

    Encapsulates the desired index of the endpoint.
    """

    def __init__(self, authn_instance, end_point_index):
        # Must be initiated before super constructor is called
        self.authn_instance = authn_instance
        UserAuthnMethod.__init__(self, None)
        self.end_point_index = end_point_index

    def __call__(self, **kwargs):
        return self.authn_instance(end_point_index=self.end_point_index, **kwargs)

    def verify(self, **kwargs):
        return self.authn_instance.verify(
            end_point_index=self.end_point_index, **kwargs
        )

    @property
    def srv(self):
        return self.authn_instance.srv

    @srv.setter
    def srv(self, v):
        self.authn_instance.srv = v

    def done(self, areq):
        return self.authn_instance.done(areq)
