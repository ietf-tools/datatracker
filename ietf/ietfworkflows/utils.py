import copy
import datetime

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.mail import EmailMessage
from django.template.loader import render_to_string

from workflows.models import State, StateObjectRelation
from workflows.utils import (get_workflow_for_object, set_workflow_for_object,
                             get_state, set_state)

from ietf.ietfworkflows.streams import (get_streamed_draft, get_stream_from_draft,
                                        set_stream_for_draft)
from ietf.ietfworkflows.models import (WGWorkflow, AnnotationTagObjectRelation,
                                       AnnotationTag, ObjectAnnotationTagHistoryEntry,
                                       ObjectHistoryEntry, StateObjectRelationMetadata,
                                       ObjectWorkflowHistoryEntry, ObjectStreamHistoryEntry)


WAITING_WRITEUP = 'WG Consensus: Waiting for Write-Up'
FOLLOWUP_TAG = 'Doc Shepherd Follow-up Underway'


def get_default_workflow_for_wg():
    try:
        workflow = WGWorkflow.objects.get(name='Default WG Workflow')
        return workflow
    except WGWorkflow.DoesNotExist:
        return None


def clone_transition(transition):
    new = copy.copy(transition)
    new.pk = None
    new.save()

    # Reference original initial states
    for state in transition.states.all():
        new.states.add(state)
    return new


def clone_workflow(workflow, name):
    new = WGWorkflow.objects.create(name=name, initial_state=workflow.initial_state)

    # Reference default states
    for state in workflow.states.all():
        new.selected_states.add(state)

    # Reference default annotation tags
    for tag in workflow.annotation_tags.all():
        new.selected_tags.add(tag)

    # Reference cloned transitions
    for transition in workflow.transitions.all():
        new.transitions.add(clone_transition(transition))
    return new


def get_workflow_for_wg(wg, default=None):
    workflow = get_workflow_for_object(wg)
    try:
        workflow = workflow and workflow.wgworkflow
    except WGWorkflow.DoesNotExist:
        workflow = None
    if not workflow:
        if default:
            workflow = default
        else:
            workflow = get_default_workflow_for_wg()
        if not workflow:
            return None
        workflow = clone_workflow(workflow, name='%s workflow' % wg)
        set_workflow_for_object(wg, workflow)
    return workflow


def get_workflow_for_draft(draft):
    workflow = get_workflow_for_object(draft)
    try:
        workflow = workflow and workflow.wgworkflow
    except WGWorkflow.DoesNotExist:
        workflow = None
    if not workflow:
        streamed_draft = get_streamed_draft(draft)
        if not streamed_draft or not streamed_draft.stream:
            return None
        stream = streamed_draft.stream
        if stream.with_groups:
            if not streamed_draft.group:
                return None
            else:
                workflow = get_workflow_for_wg(streamed_draft.group, streamed_draft.stream.workflow)
        else:
            workflow = stream.workflow
        set_workflow_for_object(draft, workflow)
    return workflow


def get_workflow_history_for_draft(draft, entry_type=None):
    ctype = ContentType.objects.get_for_model(draft)
    filter_param = {'content_type': ctype,
                    'content_id': draft.pk}
    if entry_type:
        filter_param.update({'%s__isnull' % entry_type: False})
    history = ObjectHistoryEntry.objects.filter(**filter_param).\
        select_related('objectworkflowhistoryentry', 'objectannotationtaghistoryentry',
                       'objectstreamhistoryentry')
    return history


def get_annotation_tags_for_draft(draft):
    ctype = ContentType.objects.get_for_model(draft)
    tags = AnnotationTagObjectRelation.objects.filter(content_type=ctype, content_id=draft.pk)
    return tags


def get_state_for_draft(draft):
    return get_state(draft)


def get_state_by_name(state_name):
    try:
        return State.objects.get(name=state_name)
    except State.DoesNotExist:
        return None


def get_annotation_tag_by_name(tag_name):
    try:
        return AnnotationTag.objects.get(name=tag_name)
    except AnnotationTag.DoesNotExist:
        return None


def set_tag(obj, tag):
    ctype = ContentType.objects.get_for_model(obj)
    (relation, created) = AnnotationTagObjectRelation.objects.get_or_create(
        content_type=ctype,
        content_id=obj.pk,
        annotation_tag=tag)
    return relation


def set_tag_by_name(obj, tag_name):
    try:
        tag = AnnotationTag.objects.get(name=tag_name)
        return set_tag(obj, tag)
    except AnnotationTag.DoesNotExist:
        return None


def reset_tag(obj, tag):
    ctype = ContentType.objects.get_for_model(obj)
    try:
        tag_relation = AnnotationTagObjectRelation.objects.get(
            content_type=ctype,
            content_id=obj.pk,
            annotation_tag=tag)
        tag_relation.delete()
        return True
    except AnnotationTagObjectRelation.DoesNotExist:
        return False


def reset_tag_by_name(obj, tag_name):
    try:
        tag = AnnotationTag.objects.get(name=tag_name)
        return reset_tag(obj, tag)
    except AnnotationTag.DoesNotExist:
        return False


def set_state_for_draft(draft, state, estimated_date=None):
    workflow = get_workflow_for_draft(draft)
    if state in workflow.get_states():
        set_state(draft, state)
        relation = StateObjectRelation.objects.get(
            content_type=ContentType.objects.get_for_model(draft),
            content_id=draft.pk)
        metadata = StateObjectRelationMetadata.objects.get_or_create(relation=relation)[0]
        metadata.from_date = datetime.date.today()
        metadata.to_date = estimated_date
        metadata.save()
        return state
    return False


def notify_entry(entry, template, extra_notify=[]):
    doc = entry.content
    wg = doc.group.ietfwg
    mail_list = set(['%s <%s>' % i.person.email() for i in wg.wgchair_set.all() if i.person.email()])
    mail_list = mail_list.union(['%s <%s>' % i.person.email() for i in wg.wgdelegate_set.all() if i.person.email()])
    mail_list = mail_list.union(['%s <%s>' % i.person.email() for i in doc.authors.all() if i.person.email()])
    mail_list = mail_list.union(extra_notify)
    mail_list = list(mail_list)

    subject = 'Annotation tags have changed for draft %s' % doc
    body = render_to_string(template, {'doc': doc,
                                       'entry': entry,
                                      })
    mail = EmailMessage(subject=subject,
        body=body,
        to=mail_list,
        from_email=settings.DEFAULT_FROM_EMAIL)
    # Only send emails if we are not debug mode
    if not settings.DEBUG:
        mail.send()
    return mail


def notify_tag_entry(entry, extra_notify=[]):
    return notify_entry(entry, 'ietfworkflows/annotation_tags_updated_mail.txt', extra_notify)


def notify_state_entry(entry, extra_notify=[]):
    return notify_entry(entry, 'ietfworkflows/state_updated_mail.txt', extra_notify)


def notify_stream_entry(entry, extra_notify=[]):
    return notify_entry(entry, 'ietfworkflows/stream_updated_mail.txt', extra_notify)


def update_tags(obj, comment, person, set_tags=[], reset_tags=[], extra_notify=[]):
    ctype = ContentType.objects.get_for_model(obj)
    setted = []
    resetted = []
    for tag in set_tags:
        if isinstance(tag, basestring):
            if set_tag_by_name(obj, tag):
                setted.append(tag)
        else:
            if set_tag(obj, tag):
                setted.append(tag.name)
    for tag in reset_tags:
        if isinstance(tag, basestring):
            if reset_tag_by_name(obj, tag):
                resetted.append(tag)
        else:
            if reset_tag(obj, tag):
                resetted.append(tag.name)
    entry = ObjectAnnotationTagHistoryEntry.objects.create(
        content_type=ctype,
        content_id=obj.pk,
        setted=','.join(setted),
        unsetted=','.join(resetted),
        date=datetime.datetime.now(),
        comment=comment,
        person=person)
    notify_tag_entry(entry, extra_notify)


def update_state(obj, comment, person, to_state, estimated_date=None, extra_notify=[]):
    ctype = ContentType.objects.get_for_model(obj)
    from_state = get_state_for_draft(obj)
    to_state = set_state_for_draft(obj, to_state, estimated_date)
    if not to_state:
        return False
    entry = ObjectWorkflowHistoryEntry.objects.create(
        content_type=ctype,
        content_id=obj.pk,
        from_state=from_state and from_state.name or '',
        to_state=to_state and to_state.name or '',
        date=datetime.datetime.now(),
        comment=comment,
        person=person)
    notify_state_entry(entry, extra_notify)


def update_stream(obj, comment, person, to_stream, extra_notify=[]):
    ctype = ContentType.objects.get_for_model(obj)
    from_stream = get_stream_from_draft(obj)
    to_stream = set_stream_for_draft(obj, to_stream)
    entry = ObjectStreamHistoryEntry.objects.create(
        content_type=ctype,
        content_id=obj.pk,
        from_stream=from_stream and from_stream.name or '',
        to_stream=to_stream and to_stream.name or '',
        date=datetime.datetime.now(),
        comment=comment,
        person=person)
    notify_stream_entry(entry, extra_notify)


def get_full_info_for_draft(draft):
    return dict(
        streamed=get_streamed_draft(draft),
        stream=get_stream_from_draft(draft),
        workflow=get_workflow_for_draft(draft),
        tags=[i.annotation_tag for i in get_annotation_tags_for_draft(draft)],
        state=get_state_for_draft(draft),
        shepherd=draft.shepherd if draft.shepherd_id else None,
    )
