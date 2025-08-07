import copy

__author__ = "rolandh"


class UserInfo(object):
    """Read only interface to a user info store."""

    def __init__(self, db=None):
        self.db = db

    def filter(self, userinfo, user_info_claims=None):
        """
        Return only those claims that are asked for.

        It's a best effort task; if essential claims are not present no error is flagged.

        :param userinfo: A dictionary containing the available user info.
        :param user_info_claims: A dictionary specifying the asked for claims
        :return: A dictionary of filtered claims.
        """
        if user_info_claims is None:
            return copy.copy(userinfo)
        else:
            result = {}
            missing = []
            optional = []
            for key, restr in user_info_claims.items():
                try:
                    result[key] = userinfo[key]
                except KeyError:
                    if restr == {"essential": True}:
                        missing.append(key)
                    else:
                        optional.append(key)
            return result

    def __call__(self, userid, client_id, user_info_claims=None, **kwargs):
        try:
            return self.filter(self.db[userid], user_info_claims)
        except KeyError:
            return {}
