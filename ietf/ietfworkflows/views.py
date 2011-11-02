from django.http import HttpResponseRedirect, HttpResponseForbidden
from django.shortcuts import get_object_or_404, render_to_response
from django.template import RequestContext

from ietf.idtracker.models import InternetDraft
from ietf.ietfworkflows.models import Stream, StreamDelegate
from ietf.ietfworkflows.forms import (DraftTagsStateForm,
                                      DraftStreamForm,
                                      NoWorkflowStateForm,
                                      StreamDelegatesForm)
from ietf.ietfworkflows.streams import (get_stream_from_draft,
                                        get_streamed_draft)
from ietf.ietfworkflows.utils import (get_workflow_history_for_draft,
                                      get_workflow_for_draft,
                                      get_annotation_tags_for_draft,
                                      get_state_for_draft)
from ietf.ietfworkflows.accounts import (can_edit_state, can_edit_stream,
                                         is_chair_of_stream)


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


def _edit_draft_stream(request, draft, form_class=DraftTagsStateForm):
    user = request.user
    workflow = get_workflow_for_draft(draft)
    if not workflow and form_class == DraftTagsStateForm:
        form_class = NoWorkflowStateForm
    if request.method == 'POST':
        form = form_class(user=user, draft=draft, data=request.POST)
        if form.is_valid():
            form.save()
            return HttpResponseRedirect('.')
    else:
        form = form_class(user=user, draft=draft)
    state = get_state_for_draft(draft)
    stream = get_stream_from_draft(draft)
    history = get_workflow_history_for_draft(draft, 'objectworkflowhistoryentry')
    tags = get_annotation_tags_for_draft(draft)
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


def edit_state(request, name):
    draft = get_object_or_404(InternetDraft, filename=name)
    if not can_edit_state(request.user, draft):
        return HttpResponseForbidden('You have no permission to access this view')
    return _edit_draft_stream(request, draft, DraftTagsStateForm)


def edit_stream(request, name):
    draft = get_object_or_404(InternetDraft, filename=name)
    if not can_edit_stream(request.user, draft):
        return HttpResponseForbidden('You have no permission to access this view')
    return _edit_draft_stream(request, draft, DraftStreamForm)


def stream_delegates(request, stream_name):
    stream = get_object_or_404(Stream, name=stream_name)
    if not is_chair_of_stream(request.user, stream):
        return HttpResponseForbidden('You have no permission to access this view')
    chairs = stream.get_chairs()
    form = StreamDelegatesForm(stream=stream)
    if request.method == 'POST':
        if request.POST.get('delete', False):
            pk_list = request.POST.getlist('remove_delegate')
            StreamDelegate.objects.filter(stream=stream, person__pk__in=pk_list).delete()
        else:
            form = StreamDelegatesForm(request.POST, stream=stream)
            if form.is_valid():
                form.save()
                form = StreamDelegatesForm(stream=stream)
    delegates = stream.get_delegates()
    return render_to_response('ietfworkflows/stream_delegates.html',
                              {'stream': stream,
                               'chairs': chairs,
                               'delegates': delegates,
                               'form': form,
                               },
                              context_instance=RequestContext(request))
