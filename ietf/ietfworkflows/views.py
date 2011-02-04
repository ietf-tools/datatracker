from ietf.idtracker.models import InternetDraft
from django.shortcuts import get_object_or_404, render_to_response
from django.template import RequestContext

from ietf.ietfworkflows.forms import DraftStateForm
from ietf.ietfworkflows.streams import (get_stream_from_draft,
                                        get_streamed_draft)
from ietf.ietfworkflows.utils import (get_workflow_history_for_draft,
                                      get_workflow_for_draft,
                                      get_annotation_tags_for_draft,
                                      get_state_for_draft)


REDUCED_HISTORY_LEN = 20


def stream_history(request, name):
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


def edit_state(request, name):
    user = request.user
    draft = get_object_or_404(InternetDraft, filename=name)
    state = get_state_for_draft(draft)
    stream = get_stream_from_draft(draft)
    workflow = get_workflow_for_draft(draft)
    history = get_workflow_history_for_draft(draft, 'objectworkflowhistoryentry')
    tags = get_annotation_tags_for_draft(draft)
    if request.method == 'POST':
        form = DraftStateForm(user=user, draft=draft, data=request.POST)
    else:
        form = DraftStateForm(user=user, draft=draft)
    return render_to_response('ietfworkflows/state_edit.html',
                              {'draft': draft,
                               'state': state,
                               'stream': stream,
                               'workflow': workflow,
                               'history': history,
                               'tags': tags,
                               'form': form,
                              },
                              context_instance=RequestContext(request))


def edit_tags(request, name):
    pass


def edit_stream(request, name):
    pass
