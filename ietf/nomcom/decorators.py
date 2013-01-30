from ietf.ietfauth.decorators import passes_test_decorator, has_role

from ietf.nomcom.utils import get_nomcom_by_year


def member_required(role=None):
    def _is_nomcom_member(user, *args, **kwargs):
        year = kwargs.get('year', None)
        if year:
            nomcom = get_nomcom_by_year(year=year)
            if has_role(user, "Secretariat"):
                return True
            if role == 'chair':
                return nomcom.group.is_chair(user)
            else:
                return nomcom.group.is_member(user)
        return False
    return passes_test_decorator(_is_nomcom_member, 'Restricted to NomCom %s' % role)
