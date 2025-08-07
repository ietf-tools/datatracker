__author__ = "rolandh"


class ClaimsMode(object):
    def __init__(self, user2mode):
        self.user2mode = user2mode

    def aggregate(self, uid, info=None):
        """
        Determine whether the claims for a user should be aggregated.

        :param uid: user id
        :param info: claims
        :return: True if the claims should be aggregated, otherwist False
        """
        if uid in self.user2mode and self.user2mode[uid] == "aggregate":
            return True

        return False
