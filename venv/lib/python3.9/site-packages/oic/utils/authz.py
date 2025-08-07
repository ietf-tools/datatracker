import logging
import time
from typing import Any
from typing import Dict

from oic.utils.authn.user import ToOld
from oic.utils.http_util import CookieDealer
from oic.utils.sanitize import sanitize

logger = logging.getLogger(__name__)


class AuthzHandling(CookieDealer):
    """Class that allows an entity to manage authorization."""

    def __init__(self):
        self.permdb: Dict[str, Any] = {}

    def __call__(self, *args, **kwargs):
        return ""

    def permissions(self, cookie=None, **kwargs):
        if cookie is None:
            return None
        else:
            logger.debug("kwargs: %s" % sanitize(kwargs))

            val = self.getCookieValue(cookie, self.srv.cookie_name)
            if val is None:
                return None
            else:
                uid, _ts, typ = val

            if typ == "uam":  # short lived
                _now = int(time.time())
                if _now > (int(_ts) + int(self.cookie_ttl * 60)):
                    logger.debug("Authentication timed out")
                    raise ToOld(
                        "%d > (%d + %d)" % (_now, int(_ts), int(self.cookie_ttl * 60))
                    )
            else:
                if "max_age" in kwargs and kwargs["max_age"]:
                    _now = int(time.time())
                    if _now > (int(_ts) + int(kwargs["max_age"])):
                        logger.debug("Authentication too old")
                        raise ToOld(
                            "%d > (%d + %d)" % (_now, int(_ts), int(kwargs["max_age"]))
                        )

            return self.permdb[uid]


class UserInfoConsent(AuthzHandling):
    def __call__(self, user, userinfo, **kwargs):
        pass


class Implicit(AuthzHandling):
    def __init__(self, permission="implicit"):
        AuthzHandling.__init__(self)
        self.permission = permission

    def permissions(self, cookie=None, **kwargs):
        return self.permission
