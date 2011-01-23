from ietf.idtracker.models import IETFWG, InternetDraft, IESGLogin
from django.shortcuts import get_object_or_404, render_to_response
from django.template import RequestContext
from django.http import HttpResponseForbidden, Http404

from ietf.idrfc.views_search import SearchForm, search_query
from ietf.wgchairs.forms import (RemoveDelegateForm, add_form_factory,
                                 workflow_form_factory, TransitionFormSet,
                                 WriteUpEditForm)
from ietf.wgchairs.accounts import (can_manage_delegates_in_group, get_person_for_user,
                                    can_manage_shepherds_in_group,
                                    can_manage_workflow_in_group,
                                    can_manage_shepherd_of_a_document,
                                    can_manage_writeup_of_a_document,
                                    can_manage_writeup_of_a_document_no_state,
                                    )
from ietf.ietfworkflows.streams import (get_stream_from_draft,
                                        get_streamed_draft)
from ietf.ietfworkflows.utils import (get_workflow_for_wg,
                                      get_default_workflow_for_wg,
                                      get_workflow_history_for_draft,
                                      get_workflow_for_draft,
                                      get_state_by_name,
                                      get_annotation_tags_for_draft,
                                      get_state_for_draft, WAITING_WRITEUP,
                                      FOLLOWUP_TAG)


REDUCED_HISTORY_LEN = 20


def stream_history(request, name):
    user = request.user
    person = get_person_for_user(user)
    draft = get_object_or_404(InternetDraft, filename=name)
    streamed = get_streamed_draft(draft)
    stream = get_stream_from_draft(draft)
    workflow = get_workflow_for_draft(draft)
    tags = []
    if workflow:
        tags_setted = [i.annotation_tag.pk for i in get_annotation_tags_for_draft(draft)]
        for tag in workflow.get_tags():
            tag.setted = tag.pk in tags_setted
            tags.append(tag)
    state = get_state_for_draft(draft)
    history = get_workflow_history_for_draft(draft)
    show_more = False
    if history.count > REDUCED_HISTORY_LEN:
        show_more = True
    return render_to_response('ietfworkflows/stream_history.html',
                              {'stream': stream,
                               'streamed': streamed,
                               'draft': draft,
                               'tags': tags,
                               'state': state,
                               'workflow': workflow,
                               'show_more': show_more,
                               'history': history[:REDUCED_HISTORY_LEN],
                              },
                              context_instance=RequestContext(request))
