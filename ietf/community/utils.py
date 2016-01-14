from ietf.community.models import CommunityList
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

def augment_docs_with_tracking_info(docs, user):
    """Add attribute to each document with whether the document is tracked
    by the user or not."""

    tracked = set()

    if user and user.is_authenticated():
        clist = CommunityList.objects.filter(user=user).first()
        if clist:
            tracked.update(clist.get_documents().filter(pk__in=docs).values_list("pk", flat=True))

    for d in docs:
        d.tracked_in_personal_community_list = d.pk in tracked
