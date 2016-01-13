from ietf.group.models import Role

def can_manage_community_list_for_group(user, group):
    if not user or not user.is_authenticated() or not group:
        return False

    if group.type_id == 'area':
        return Role.objects.filter(name__slug='ad', person__user=user, group=group).exists()
    elif group.type_id in ('wg', 'rg'):
        return Role.objects.filter(name__slug='chair', person__user=user, group=group).exists()
    else:
        return False

