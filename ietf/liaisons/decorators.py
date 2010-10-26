from ietf.ietfauth.decorators import _CheckLogin403
from ietf.liaisons.accounts import can_add_liaison


def can_submit_liaison(view_func=None):

    def decorate(view_func):
        return _CheckLogin403(
            view_func,
            lambda u: can_add_liaison(u),
            "Restricted to participants who are authorized to submit liaison statements on behalf of the various IETF entities")
    if view_func:
        return decorate(view_func)
    return decorate
