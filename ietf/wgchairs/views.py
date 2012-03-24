from django.conf import settings
from ietf.idtracker.models import IETFWG, InternetDraft
from django.shortcuts import get_object_or_404, render_to_response
from django.template import RequestContext
from django.http import HttpResponseForbidden, Http404

from ietf.idrfc.views_search import SearchForm, search_query
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


def manage_workflow(request, acronym):
    wg = get_object_or_404(IETFWG, group_acronym__acronym=acronym, group_type=1)
    user = request.user
    if not can_manage_workflow_in_group(user, wg):
        return HttpResponseForbidden("You don't have permission to access this view")
    workflow = get_workflow_for_wg(wg)
    default_workflow = get_default_workflow_for_wg()
    formset = None
    if request.method == 'POST':
        form = workflow_form_factory(request, wg=wg, user=user)
        if form.is_valid():
            form.save()
        elif isinstance(form, TransitionFormSet):
            formset = form
    tags = workflow.selected_tags.all()
    default_tags = default_workflow.annotation_tags.all()
    states = workflow.selected_states.all().order_by('statedescription__order')
    default_states = default_workflow.states.all().order_by('statedescription__order')
    for i in default_states:
        if states.filter(name=i.name).count() == 1:
            i.used = True
        if i.name in REQUIRED_STATES:
            i.freeze = True
    for i in default_tags:
        if tags.filter(name=i.name).count() == 1:
            i.used = True
    if not formset:
        formset = TransitionFormSet(queryset=workflow.transitions.all(), user=user, wg=wg)

    return render_to_response('wgchairs/manage_workflow.html',
                              {'wg': wg,
                               'workflow': workflow,
                               'default_workflow': default_workflow,
                               'states': states,
                               'tags': tags,
                               'default_states': default_states,
                               'default_tags': default_tags,
                               'formset': formset,
                               'selected': 'manage_workflow',
                              }, RequestContext(request))

def manage_workflowREDESIGN(request, acronym):
    from ietf.doc.models import State
    from ietf.group.models import GroupStateTransitions

    MANDATORY_STATES = ('c-adopt', 'wg-doc', 'sub-pub')

    wg = get_object_or_404(IETFWG, group_acronym__acronym=acronym, group_type=1)
    user = request.user
    if not can_manage_workflow_in_group(user, wg):
        return HttpResponseForbidden("You don't have permission to access this view")

    if request.method == 'POST':
        action = request.POST.get("action")
        if action == "setstateactive":
            active = request.POST.get("active") == "1"
            try:
                state = State.objects.exclude(slug__in=MANDATORY_STATES).get(pk=request.POST.get("state"))
            except State.DoesNotExist:
                return HttpResponse("Invalid state %s" % request.POST.get("state"))

            if active:
                wg.unused_states.remove(state)
            else:
                wg.unused_states.add(state)

        if action == "setnextstates":
            try:
                state = State.objects.get(pk=request.POST.get("state"))
            except State.DoesNotExist:
                return HttpResponse("Invalid state %s" % request.POST.get("state"))

            next_states = State.objects.filter(type='draft-stream-ietf', pk__in=request.POST.getlist("next_states"))
            unused = wg.unused_states.all()
            if set(next_states.exclude(pk__in=unused)) == set(state.next_states.exclude(pk__in=unused)):
                # just use the default
                wg.groupstatetransitions_set.filter(state=state).delete()
            else:
                transitions, _ = GroupStateTransitions.objects.get_or_create(group=wg, state=state)
                transitions.next_states = next_states

        if action == "settagactive":
            active = request.POST.get("active") == "1"
            try:
                tag = DocTagName.objects.get(pk=request.POST.get("tag"))
            except DocTagName.DoesNotExist:
                return HttpResponse("Invalid tag %s" % request.POST.get("tag"))

            if active:
                wg.unused_tags.remove(tag)
            else:
                wg.unused_tags.add(tag)


    # put some info for the template on tags and states
    unused_tags = wg.unused_tags.all().values_list('slug', flat=True)
    tags = DocTagName.objects.filter(slug__in=get_tags_for_stream_id("ietf"))
    for t in tags:
        t.used = t.slug not in unused_tags

    unused_states = wg.unused_states.all().values_list('slug', flat=True)
    states = State.objects.filter(type="draft-stream-ietf")
    transitions = dict((o.state, o) for o in wg.groupstatetransitions_set.all())
    for s in states:
        s.used = s.slug not in unused_states
        s.mandatory = s.slug in MANDATORY_STATES

        default_n = s.next_states.all()
        if s in transitions:
            n = transitions[s].next_states.all()
        else:
            n = default_n

        s.next_states_checkboxes = [(x in n, x in default_n, x) for x in states]
        s.used_next_states = [x for x in n if x.slug not in unused_states]

    return render_to_response('wgchairs/manage_workflowREDESIGN.html',
                              {'wg': wg,
                               'states': states,
                               'tags': tags,
                               'selected': 'manage_workflow',
                              }, RequestContext(request))


if settings.USE_DB_REDESIGN_PROXY_CLASSES:
    manage_workflow = manage_workflowREDESIGN

def managing_shepherd(request, acronym, name):
    """
     View for managing the assigned shepherd of a document.
    """
    wg = get_object_or_404(IETFWG, group_acronym__acronym=acronym, group_type=1)
    user = request.user
    person = get_person_for_user(user)
    if not can_manage_shepherds_in_group(user, wg):
        return HttpResponseForbidden('You have no permission to access this view')
    doc = get_object_or_404(InternetDraft, filename=name)
    if not can_manage_shepherd_of_a_document(user, doc):
        raise Http404
    add_form = add_form_factory(request, wg, user, shepherd=doc)
    if request.method == 'POST':
        if request.POST.get('remove_shepherd'):
            if settings.USE_DB_REDESIGN_PROXY_CLASSES:
                assign_shepherd(user, doc, None)
            else:
                doc.shepherd = None
                doc.save()
        elif request.POST.get('setme'):
            if settings.USE_DB_REDESIGN_PROXY_CLASSES:
                assign_shepherd(user, doc, person)
            else:
                doc.shepherd = person
                doc.save()
        elif add_form.is_valid():
            add_form.save()
            add_form = add_form.get_next_form()
    return render_to_response('wgchairs/edit_management_shepherd.html',
                              dict(doc=doc,
                                   form=add_form,
                                   user=user,
                                   selected='manage_shepherds',
                                   wg=wg,
                                   ),
                              context_instance=RequestContext(request))


def wg_shepherd_documents(request, acronym):
    wg = get_object_or_404(IETFWG, group_acronym__acronym=acronym, group_type=1)
    user = request.user
    if not can_manage_shepherds_in_group(user, wg):
        return HttpResponseForbidden('You have no permission to access this view')
    current_person = get_person_for_user(user)

    if settings.USE_DB_REDESIGN_PROXY_CLASSES:
        base_qs = InternetDraft.objects.filter(group=wg, states__type="draft", states__slug="active").select_related("status").order_by('title')
    else:
        form = SearchForm({'by': 'group', 'group': str(wg.group_acronym.acronym),
                           'activeDrafts': 'on'})
        if not form.is_valid():
            raise ValueError("form did not validate")
        (docs, meta) = search_query(form.cleaned_data)
        base_qs = InternetDraft.objects.filter(pk__in=[i.id._draft.pk for i in docs if i.id]).select_related('status')
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


def managing_writeup(request, acronym, name):
    wg = get_object_or_404(IETFWG, group_acronym__acronym=acronym, group_type=1)
    user = request.user
    doc = get_object_or_404(InternetDraft, filename=name)
    authorized_user = can_manage_writeup_of_a_document_no_state(user, doc)
    if settings.USE_DB_REDESIGN_PROXY_CLASSES:
        from ietf.doc.models import State
        state = doc.get_state("draft-stream-%s" % doc.stream_id)
        can_edit = (state and state.slug == "writeupw") or can_manage_writeup_of_a_document_no_state(user, doc)
    else:
        can_edit = True
        current_state = get_state_for_draft(doc)
        if current_state != get_state_by_name(WAITING_WRITEUP) and not can_manage_writeup_of_a_document_no_state(user, doc):
            can_edit = False
    writeup = doc.protowriteup_set.all()
    if writeup:
        writeup = writeup[0]
    else:
        writeup = None
    error = False
    followup_tag = get_annotation_tags_for_draft(doc).filter(annotation_tag__name=FOLLOWUP_TAG)
    followup = bool(followup_tag.count())
    if request.method == 'POST':
        form = WriteUpEditForm(wg=wg, doc=doc, user=user, data=request.POST, files=request.FILES)
        form.request = request
        if request.FILES.get('uploaded_writeup', None):
            try:
                newwriteup = request.FILES['uploaded_writeup'].read().encode('ascii')
                form.data.update({'writeup': newwriteup})
            except:
                form.set_message('error', 'You have try to upload a non ascii file')
                error = True
        valid = form.is_valid()
        if (valid and not error and not request.POST.get('confirm', None)) or (not valid and not error):
            if not valid:
                form.set_message('error', 'You have to specify a comment')
            return render_to_response('wgchairs/confirm_management_writeup.html',
                                      dict(doc=doc,
                                           user=user,
                                           selected='manage_shepherds',
                                           wg=wg,
                                           followup=followup,
                                           form=form,
                                           writeup=writeup,
                                           can_edit=can_edit,
                                           authorized_user=authorized_user,
                                           ),
                                      context_instance=RequestContext(request))
        elif valid and not error:
            writeup = form.save()
            form = WriteUpEditForm(wg=wg, doc=doc, user=user)
            followup_tag = get_annotation_tags_for_draft(doc).filter(annotation_tag__name=FOLLOWUP_TAG)
            followup = bool(followup_tag.count())
    else:
        form = WriteUpEditForm(wg=wg, doc=doc, user=user)
        form.request = request
    return render_to_response('wgchairs/edit_management_writeup.html',
                              dict(doc=doc,
                                   user=user,
                                   selected='manage_shepherds',
                                   wg=wg,
                                   form=form,
                                   writeup=writeup,
                                   followup=followup,
                                   can_edit=can_edit,
                                   authorized_user=authorized_user,
                                   ),
                              context_instance=RequestContext(request))
