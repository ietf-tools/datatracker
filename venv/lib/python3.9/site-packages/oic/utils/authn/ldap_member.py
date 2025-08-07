import logging

from oic.utils.userinfo.ldap_info import UserInfoLDAP

__author__ = "haho0032"

logger = logging.getLogger(__name__)


class UserLDAPMemberValidation(UserInfoLDAP):
    def __init__(self, verify_attr=None, verify_attr_valid=None, **kwargs):
        UserInfoLDAP.__init__(self, **kwargs)
        self.verify_attr = verify_attr
        self.verify_attr_valid = verify_attr_valid

    def __call__(self, userid, **kwargs):
        result = UserInfoLDAP.__call__(self, userid, None, False)
        if self.verify_attr in result:
            for field in result[self.verify_attr]:
                if field in self.verify_attr_valid:
                    return True
        logger.warning(userid + "tries to use the service with the values " + result)
        return False
