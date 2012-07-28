import copy
import datetime

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.template.defaultfilters import pluralize

from workflows.models import State, StateObjectRelation
from workflows.utils import (get_workflow_for_object, set_workflow_for_object,
                             get_state, set_state)

from ietf.ietfworkflows.streams import (get_streamed_draft, get_stream_from_draft,
                                        set_stream_for_draft)
from ietf.ietfworkflows.models import (WGWorkflow, AnnotationTagObjectRelation,
                                       AnnotationTag, ObjectAnnotationTagHistoryEntry,
                                       ObjectHistoryEntry, StateObjectRelationMetadata,
                                       ObjectWorkflowHistoryEntry, ObjectStreamHistoryEntry)
from ietf.idtracker.models import InternetDraft
from ietf.utils.mail import send_mail
from ietf.doc.models import Document, DocEvent, save_document_in_history, DocReminder, DocReminderTypeName
from ietf.group.models import Role

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
    if settings.USE_DB_REDESIGN_PROXY_CLASSES:
        return True if get_streamed_draft(draft) else None

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
        if stream.document_group_attribute:
            group = streamed_draft.get_group()
            if not group:
                return None
            else:
                workflow = get_workflow_for_wg(group, streamed_draft.stream.workflow)
        else:
            workflow = stream.workflow
        set_workflow_for_object(draft, workflow)
    return workflow


def get_workflow_history_for_draft(draft, entry_type=None):
    if settings.USE_DB_REDESIGN_PROXY_CLASSES:
        from ietf.doc.proxy import ObjectHistoryEntryProxy
        return ObjectHistoryEntryProxy.objects.filter(doc=draft).order_by('-time', '-id').select_related('by')

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
    if settings.USE_DB_REDESIGN_PROXY_CLASSES:
        from ietf.name.proxy import AnnotationTagObjectRelationProxy
        from ietf.doc.utils import get_tags_for_stream_id
        return AnnotationTagObjectRelationProxy.objects.filter(document=draft.pk, slug__in=get_tags_for_stream_id(draft.stream_id))

    ctype = ContentType.objects.get_for_model(draft)
    tags = AnnotationTagObjectRelation.objects.filter(content_type=ctype, content_id=draft.pk)
    return tags


def get_state_for_draft(draft):
    if settings.USE_DB_REDESIGN_PROXY_CLASSES:
        return draft.get_state("draft-stream-%s" % draft.stream_id)
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

def get_notification_receivers(doc, extra_notify):
    persons = set()
    res = []
    for r in Role.objects.filter(group=doc.group, name__in=("chair", "delegate")):
        res.append(u'"%s" <%s>' % (r.person.plain_name(), r.email.address))
        persons.add(r.person)

    for email in doc.authors.all():
        if email.person not in persons:
            res.append(email.formatted_email())
            persons.add(email.person)

    for x in extra_notify:
        if not x in res:
            res.append(x)

    return res

def get_pubreq_receivers(doc, extra_notify):
    res = []

    for r in Role.objects.filter(person=doc.group.ad,name__slug='ad'):
        res.append(u'"%s" <%s>' % (r.person.plain_name(), r.email.address))

    for x in extra_notify:
        if not x in res:
            res.append(x)

    return res

def get_pubreq_cc_receivers(doc):
    res = []

    for r in Role.objects.filter(group=doc.group, name__in=("chair", "delegate")):
        res.append(u'"%s" <%s>' % (r.person.plain_name(), r.email.address))

    return res

def update_tags(request, obj, comment, person, set_tags=[], reset_tags=[], extra_notify=[]):
    if settings.USE_DB_REDESIGN_PROXY_CLASSES:
        doc = Document.objects.get(pk=obj.pk)
        save_document_in_history(doc)

        obj.tags.remove(*reset_tags)
        obj.tags.add(*set_tags)

        doc.time = datetime.datetime.now()

        e = DocEvent(type="changed_document", time=doc.time, by=person, doc=doc)
        l = []
        if set_tags:
            l.append(u"Annotation tag%s %s set." % (pluralize(set_tags), ", ".join(x.name for x in set_tags)))
        if reset_tags:
            l.append(u"Annotation tag%s %s cleared." % (pluralize(reset_tags), ", ".join(x.name for x in reset_tags)))
        e.desc = " ".join(l)
        e.save()

        receivers = get_notification_receivers(doc, extra_notify)
        send_mail(request, receivers, settings.DEFAULT_FROM_EMAIL,
                  u"Annotations tags changed for draft %s" % doc.name,
                  'ietfworkflows/annotation_tags_updated_mail.txt',
                  dict(doc=doc,
                       entry=dict(setted=", ".join(x.name for x in set_tags),
                                  unsetted=", ".join(x.name for x in reset_tags),
                                  change_date=doc.time,
                                  person=person,
                                  comment=comment)))
        return

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


def update_state(request, doc, comment, person, to_state, estimated_date=None, extra_notify=[]):
    if settings.USE_DB_REDESIGN_PROXY_CLASSES:
        doc = Document.objects.get(pk=doc.pk)
        save_document_in_history(doc)

        doc.time = datetime.datetime.now()
        from_state = doc.get_state("draft-stream-%s" % doc.stream_id)
        doc.set_state(to_state)

        e = DocEvent(type="changed_document", time=doc.time, by=person, doc=doc)
        e.desc = u"%s changed to <b>%s</b> from %s" % (to_state.type.label, to_state, from_state)
        e.save()

        # reminder
        reminder_type = DocReminderTypeName.objects.get(slug="stream-s")
        try:
            reminder = DocReminder.objects.get(event__doc=doc, type=reminder_type,
                                               active=True)
        except DocReminder.DoesNotExist:
            reminder = None

        if estimated_date:
            if not reminder:
                reminder = DocReminder(type=reminder_type)

            reminder.event = e
            reminder.due = estimated_date
            reminder.active = True
            reminder.save()
        elif reminder:
            reminder.active = False
            reminder.save()

        receivers = get_notification_receivers(doc, extra_notify)
        send_mail(request, receivers, settings.DEFAULT_FROM_EMAIL,
                  u"State changed for draft %s" % doc.name,
                  'ietfworkflows/state_updated_mail.txt',
                  dict(doc=doc,
                       entry=dict(from_state=from_state,
                                  to_state=to_state,
                                  transition_date=doc.time,
                                  person=person,
                                  comment=comment)))

        if (to_state.slug=='sub-pub'):
            receivers = get_pubreq_receivers(doc, extra_notify)
            cc_receivers = get_pubreq_cc_receivers(doc)

            send_mail(request, receivers, settings.DEFAULT_FROM_EMAIL,
                      u"Publication has been requested for draft %s" % doc.name,
                      'ietfworkflows/state_updated_mail.txt',
                      dict(doc=doc,
                           entry=dict(from_state=from_state,
                                      to_state=to_state,
                                      transition_date=doc.time,
                                      person=person,
                                      comment=comment)), cc=cc_receivers)

        return

    ctype = ContentType.objects.get_for_model(doc)
    from_state = get_state_for_draft(doc)
    to_state = set_state_for_draft(doc, to_state, estimated_date)
    if not to_state:
        return False
    entry = ObjectWorkflowHistoryEntry.objects.create(
        content_type=ctype,
        content_id=doc.pk,
        from_state=from_state and from_state.name or '',
        to_state=to_state and to_state.name or '',
        date=datetime.datetime.now(),
        comment=comment,
        person=person)
    notify_state_entry(entry, extra_notify)


def update_stream(request, doc, comment, person, to_stream, extra_notify=[]):
    if settings.USE_DB_REDESIGN_PROXY_CLASSES:
        doc = Document.objects.get(pk=doc.pk)
        save_document_in_history(doc)

        doc.time = datetime.datetime.now()
        from_stream = doc.stream
        doc.stream = to_stream
        doc.save()

        e = DocEvent(type="changed_stream", time=doc.time, by=person, doc=doc)
        e.desc = u"Stream changed to <b>%s</b>" % to_stream.name
        if from_stream:
            e.desc += u"from %s" % from_stream.name
        e.save()

        receivers = get_notification_receivers(doc, extra_notify)
        send_mail(request, receivers, settings.DEFAULT_FROM_EMAIL,
                  u"Stream changed for draft %s" % doc.name,
                  'ietfworkflows/stream_updated_mail.txt',
                  dict(doc=doc,
                       entry=dict(from_stream=from_stream,
                                  to_stream=to_stream,
                                  transition_date=doc.time,
                                  person=person,
                                  comment=comment)))
        return

    ctype = ContentType.objects.get_for_model(doc)
    from_stream = get_stream_from_draft(doc)
    to_stream = set_stream_for_draft(doc, to_stream)
    entry = ObjectStreamHistoryEntry.objects.create(
        content_type=ctype,
        content_id=doc.pk,
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
