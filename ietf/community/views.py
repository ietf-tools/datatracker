import datetime
import hashlib

from django.conf import settings
from django.contrib.auth.models import User
from django.http import HttpResponse, Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, render_to_response
from django.template import RequestContext
from django.utils import simplejson
from django.utils.translation import ugettext as _

from ietf.community.models import CommunityList
from redesign.group.models import Group


def _manage_list(request, clist):
    return render_to_response('community/manage_clist.html',
                              {'cl': clist},
                              context_instance=RequestContext(request))


def manage_personal_list(request, username):
    user = get_object_or_404(User, username=username)
    clist = CommunityList.objects.get_or_create(user=request.user)[0]
    if not clist.check_manager(request.user):
        return HttpResponseForbidden('You have no permission to access this view')
    return _manage_list(request, clist)


def manage_group_list(request, acronym):
    group = get_object_or_404(Group, acronym=acronym)
    if group.type.slug not in ('area', 'wg'):
        raise Http404
    clist = CommunityList.objects.get_or_create(group=group)[0]
    if not clist.check_manager(request.user):
        return HttpResponseForbidden('You have no permission to access this view')
    return _manage_list(request, clist)
