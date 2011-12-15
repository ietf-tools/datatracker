from ietf.ietfauth.decorators import passes_test_decorator
from ietf.liaisons.accounts import can_add_liaison

can_submit_liaison = passes_test_decorator(lambda u: can_add_liaison(u),
                                           "Restricted to participants who are authorized to submit liaison statements on behalf of the various IETF entities")
