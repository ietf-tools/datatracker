import json
from collections import defaultdict

from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.core.urlresolvers import reverse as urlreverse
from django.utils.html import escape
from django.views.decorators.cache import cache_page, cache_control

from ietf.group.models import Group

def group_json(request, acronym):
    group = get_object_or_404(Group, acronym=acronym)

    return HttpResponse(json.dumps(group.json_dict(request.build_absolute_uri('/')),
                                   sort_keys=True, indent=2),
                        content_type="text/json")

@cache_control(public=True, max_age=30*60)
@cache_page(30 * 60)
def group_menu_data(request):
    groups = Group.objects.filter(state="active", type__in=("wg", "rg"), parent__state="active").order_by("acronym")

    groups_by_parent = defaultdict(list)
    for g in groups:
        url = urlreverse("ietf.group.views.group_home", kwargs={ 'group_type': g.type_id, 'acronym': g.acronym })
        groups_by_parent[g.parent_id].append({ 'acronym': g.acronym, 'name': escape(g.name), 'url': url })

    return JsonResponse(groups_by_parent)
