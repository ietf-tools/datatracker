from ietf.idtracker.models import IETFWG
from django.shortcuts import get_object_or_404, render_to_response
from django.template import RequestContext
from django.http import HttpResponseForbidden

from ietf.wgchairs.forms import RemoveDelegateForm, add_form_factory
from ietf.wgchairs.accounts import can_manage_delegates_in_group
from ietf.ietfworkflows.utils import get_workflow_for_wg


def manage_delegates(request, acronym):
    wg = get_object_or_404(IETFWG, group_acronym__acronym=acronym, group_type=1)
    user = request.user
    if not can_manage_delegates_in_group(user, wg):
        return HttpResponseForbidden('You have no permission to access this view')
    delegates = wg.wgdelegate_set.all()
    add_form = add_form_factory(request, wg, user)
    if request.method == 'POST':
        if request.POST.get('remove', None):
            form = RemoveDelegateForm(wg=wg, data=request.POST.copy())
            if form.is_valid():
                form.save()
        elif add_form.is_valid():
            add_form.save()
            add_form = add_form.get_next_form()
    return render_to_response('wgchairs/manage_delegates.html',
                              {'wg': wg,
                               'delegates': delegates,
                               'selected': 'manage_delegates',
                               'can_add': delegates.count() < 3,
                               'add_form': add_form,
                              }, RequestContext(request))


def manage_workflow(request, acronym):
    wg = get_object_or_404(IETFWG, group_acronym__acronym=acronym, group_type=1)
    workflow = get_workflow_for_wg(wg)
    return render_to_response('wgchairs/manage_workflow.html',
                              {'wg': wg,
                               'workflow': workflow,
                              }, RequestContext(request))
