from django.conf import settings
from ietf.idtracker.models import IETFWG, InternetDraft
from django.shortcuts import get_object_or_404, render_to_response
from django.template import RequestContext
from django.http import HttpResponseForbidden, Http404

from ietf.wgchairs.forms import (RemoveDelegateForm, add_form_factory,
                                 workflow_form_factory, TransitionFormSet,
                                 WriteUpEditForm, assign_shepherd)
from ietf.wgchairs.accounts import (can_manage_delegates_in_group, get_person_for_user,
                                    can_manage_shepherds_in_group,
                                    can_manage_workflow_in_group,
                                    can_manage_shepherd_of_a_document,
                                    can_manage_writeup_of_a_document,
                                    can_manage_writeup_of_a_document_no_state,
                                    )
from ietf.ietfworkflows.constants import REQUIRED_STATES
from ietf.ietfworkflows.utils import (get_workflow_for_wg,
                                      get_default_workflow_for_wg,
                                      get_state_by_name,
                                      get_annotation_tags_for_draft,
                                      get_state_for_draft, WAITING_WRITEUP,
                                      FOLLOWUP_TAG)
from ietf.name.models import DocTagName
from ietf.doc.models import State
from ietf.doc.utils import get_tags_for_stream_id

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
    max_delegates = getattr(settings, 'MAX_WG_DELEGATES', 3)
    return render_to_response('wgchairs/manage_delegates.html',
                              {'wg': wg,
                               'delegates': delegates,
                               'selected': 'manage_delegates',
                               'can_add': delegates.count() < max_delegates,
                               'max_delegates': max_delegates,
                               'add_form': add_form,
                              }, RequestContext(request))


def wg_shepherd_documents(request, acronym):
    wg = get_object_or_404(IETFWG, group_acronym__acronym=acronym, group_type=1)
    user = request.user
    if not can_manage_shepherds_in_group(user, wg):
        return HttpResponseForbidden('You have no permission to access this view')
    current_person = get_person_for_user(user)

    base_qs = InternetDraft.objects.filter(group=wg, states__type="draft", states__slug="active").select_related("status").order_by('title')
    documents_no_shepherd = base_qs.filter(shepherd=None)
    documents_my = base_qs.filter(shepherd=current_person)
    documents_other = base_qs.exclude(shepherd=None).exclude(shepherd__pk__in=[current_person.pk, 0])
    context = {
        'no_shepherd': documents_no_shepherd,
        'my_documents': documents_my,
        'other_shepherds': documents_other,
        'selected': 'manage_shepherds',
        'wg': wg,
    }
    return render_to_response('wgchairs/wg_shepherd_documents.html', context, RequestContext(request))

