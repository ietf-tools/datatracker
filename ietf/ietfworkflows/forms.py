import datetime

from django.conf import settings
from django import forms
from django.template.loader import render_to_string
from workflows.models import State
from workflows.utils import set_workflow_for_object

from ietf.idtracker.models import PersonOrOrgInfo, IETFWG, InternetDraft
from ietf.wgchairs.accounts import get_person_for_user
from ietf.ietfworkflows.models import Stream, StreamDelegate
from ietf.ietfworkflows.utils import (get_workflow_for_draft, get_workflow_for_wg,
                                      get_state_for_draft, get_state_by_name,
                                      update_state, FOLLOWUP_TAG,
                                      get_annotation_tags_for_draft,
                                      update_tags, update_stream)
from ietf.ietfworkflows.accounts import is_secretariat
from ietf.ietfworkflows.streams import (get_stream_from_draft, get_streamed_draft,
                                        get_stream_by_name, set_stream_for_draft)
from ietf.ietfworkflows.constants import CALL_FOR_ADOPTION, IETF_STREAM
from ietf.doc.utils import get_tags_for_stream_id
from ietf.doc.models import save_document_in_history, DocEvent, Document
from ietf.name.models import DocTagName, StreamName, RoleName
from ietf.group.models import Group, GroupStateTransitions, Role
from ietf.group.utils import save_group_in_history
from ietf.person.models import Person, Email

class StreamDraftForm(forms.Form):

    can_cancel = False
    template = None

    def __init__(self, *args, **kwargs):
        self.draft = kwargs.pop('draft', None)
        self.user = kwargs.pop('user', None)
        self.person = get_person_for_user(self.user)
        self.workflow = get_workflow_for_draft(self.draft)
        self.message = {}
        super(StreamDraftForm, self).__init__(*args, **kwargs)

    def get_message(self):
        return self.message

    def set_message(self, msg_type, msg_value):
        self.message = {'type': msg_type,
                        'value': msg_value,
                       }

    def __unicode__(self):
        return render_to_string(self.template, {'form': self})


class NoWorkflowStateForm(StreamDraftForm):
    comment = forms.CharField(widget=forms.Textarea)
    weeks = forms.IntegerField(required=False)
    wg = forms.ChoiceField(required=False)

    template = 'ietfworkflows/noworkflow_state_form.html'

    def __init__(self, *args, **kwargs):
        super(NoWorkflowStateForm, self).__init__(*args, **kwargs)
        self.wgs = None
        if is_secretariat(self.user):
            wgs = IETFWG.objects.all().order_by('group_acronym__acronym')
        else:
            if settings.USE_DB_REDESIGN_PROXY_CLASSES:
                wgs = IETFWG.objects.filter(type="wg", state="active", role__name__in=("chair", "delegate"), role__person__user=self.user).order_by('acronym').distinct()
            else:
                wgs = set([i.group_acronym for i in self.person.wgchair_set.all()]).union(set([i.wg for i in self.person.wgdelegate_set.all()]))
                wgs = list(wgs)
                wgs.sort(lambda x, y: cmp(x.group_acronym.acronym, y.group_acronym.acronym))
        self.wgs = wgs
        if settings.USE_DB_REDESIGN_PROXY_CLASSES:
            self.fields['wg'].choices = [(i.pk, '%s - %s' % (i.acronym, i.name)) for i in self.wgs]
        else:
            self.fields['wg'].choices = [(i.pk, '%s - %s' % (i.group_acronym.acronym, i.group_acronym.name)) for i in self.wgs]

    def save(self):
        comment = self.cleaned_data.get('comment').strip()
        weeks = self.cleaned_data.get('weeks')
        wg = IETFWG.objects.get(pk=self.cleaned_data.get('wg'))
        estimated_date = None
        if weeks:
            now = datetime.date.today()
            estimated_date = now + datetime.timedelta(weeks=weeks)
        if settings.USE_DB_REDESIGN_PROXY_CLASSES:
            # do changes on real Document object instead of proxy to avoid trouble
            doc = Document.objects.get(pk=self.draft.pk)
            save_document_in_history(doc)

            doc.time = datetime.datetime.now()

            new_stream = StreamName.objects.get(slug="ietf")

            if doc.stream != new_stream:
                e = DocEvent(type="changed_stream")
                e.time = doc.time
                e.by = self.user.get_profile()
                e.doc = doc
                e.desc = u"Changed to <b>%s</b>" % new_stream.name
                if doc.stream:
                    e.desc += u" from %s" % doc.stream.name
                e.save()
                doc.stream = new_stream

            if doc.group.pk != wg.pk:
                e = DocEvent(type="changed_group")
                e.time = doc.time
                e.by = self.user.get_profile()
                e.doc = doc
                e.desc = u"Changed group to <b>%s (%s)</b>" % (wg.name, wg.acronym.upper())
                if doc.group.type_id != "individ":
                    e.desc += " from %s (%s)" % (doc.group.name, doc.group.acronym)
                e.save()
                doc.group_id = wg.pk

            doc.save()
            self.draft = InternetDraft.objects.get(pk=doc.pk) # make sure proxy object is updated
        else:
            workflow = get_workflow_for_wg(wg)
            set_workflow_for_object(self.draft, workflow)
            stream = get_stream_by_name(IETF_STREAM)
            streamed = get_streamed_draft(self.draft)
            if not streamed:
                set_stream_for_draft(self.draft, stream)
                streamed = get_streamed_draft(self.draft)
            streamed.stream = stream
            streamed.group = wg
            streamed.save()

        if settings.USE_DB_REDESIGN_PROXY_CLASSES:
            from ietf.doc.models import State
            to_state = State.objects.get(slug="c-adopt", type="draft-stream-%s" % self.draft.stream_id)
        else:
            to_state = get_state_by_name(CALL_FOR_ADOPTION)
        update_state(self.request, self.draft,
                     comment=comment,
                     person=self.person,
                     to_state=to_state,
                     estimated_date=estimated_date)

        if settings.USE_DB_REDESIGN_PROXY_CLASSES:
            if comment:
                e = DocEvent(type="added_comment")
                e.time = self.draft.time
                e.by = self.person
                e.doc_id = self.draft.pk
                e.desc = comment
                e.save()

class DraftTagsStateForm(StreamDraftForm):

    comment = forms.CharField(widget=forms.Textarea)
    new_state = forms.ChoiceField()
    weeks = forms.IntegerField(required=False)
    tags = forms.MultipleChoiceField(widget=forms.CheckboxSelectMultiple, required=False)

    template = 'ietfworkflows/state_form.html'

    def __init__(self, *args, **kwargs):
        super(DraftTagsStateForm, self).__init__(*args, **kwargs)
        self.state = get_state_for_draft(self.draft)
        self.fields['new_state'].choices = self.get_states()
        if self.is_bound:
            for key, value in self.data.items():
                if key.startswith('transition_'):
                    new_state = self.get_new_state(key)
                    if new_state:
                        self.data = self.data.copy()
                        self.data.update({'new_state': new_state.id})
                if key.startswith('new_state_'): # hack to get value from submit buttons
                    self.data = self.data.copy()
                    self.data['new_state'] = key.replace('new_state_', '')
        if settings.USE_DB_REDESIGN_PROXY_CLASSES:
            possible_tags = get_tags_for_stream_id(self.draft.stream_id)
            if self.draft.stream_id == "ietf" and self.draft.group:
                unused_tags = self.draft.group.unused_tags.values_list("slug", flat=True)
                possible_tags = [t for t in possible_tags if t not in unused_tags]
            self.available_tags = DocTagName.objects.filter(slug__in=possible_tags)
            self.tags = self.draft.tags.filter(slug__in=possible_tags)
        else:
            self.available_tags = self.workflow.get_tags()
            self.tags = [i.annotation_tag for i in get_annotation_tags_for_draft(self.draft)]

        self.fields['tags'].choices = [(i.pk, i.name) for i in self.available_tags]
        self.fields['tags'].initial = [i.pk for i in self.tags]

    def get_new_state(self, key):
        transition_id = key.replace('transition_', '')
        transition = self.get_transitions().filter(id=transition_id)
        if transition:
            return transition[0].destination
        return None

    def get_transitions(self):
        if settings.USE_DB_REDESIGN_PROXY_CLASSES:
            return []
        return self.state.transitions.filter(workflow=self.workflow)

    def get_next_states(self):
        if settings.USE_DB_REDESIGN_PROXY_CLASSES:
            if not self.draft.stream_id:
                return []

            from ietf.doc.models import State
            state_type = "draft-stream-%s" % self.draft.stream_id
            s = self.draft.get_state(state_type)
            next_states = []
            if s:
                next_states = s.next_states.all()

                if self.draft.stream_id == "ietf" and self.draft.group:
                    transitions = self.draft.group.groupstatetransitions_set.filter(state=s)
                    if transitions:
                        next_states = transitions[0].next_states.all()
            else:
                # return the initial state
                states = State.objects.filter(type=state_type).order_by('order')
                if states:
                    next_states = states[:1]

            unused = []
            if self.draft.group:
                unused = self.draft.group.unused_states.values_list("pk", flat=True)
            return [n for n in next_states if n.pk not in unused]

        return []


    def get_states(self):
        if settings.USE_DB_REDESIGN_PROXY_CLASSES:
            if not self.draft.stream_id:
                return []

            from ietf.doc.models import State
            states = State.objects.filter(type="draft-stream-%s" % self.draft.stream_id)
            if self.draft.stream_id == "ietf" and self.draft.group:
                unused_states = self.draft.group.unused_states.values_list("pk", flat=True)
                states = [s for s in states if s.pk not in unused_states]
            return [(i.pk, i.name) for i in states]

        return [(i.pk, i.name) for i in self.workflow.get_states()]

    def save_tags(self):
        comment = self.cleaned_data.get('comment')
        new_tags = self.cleaned_data.get('tags')

        set_tags = [tag for tag in self.available_tags if str(tag.pk) in new_tags and tag not in self.tags]
        reset_tags = [tag for tag in self.available_tags if str(tag.pk) not in new_tags and tag in self.tags]
        followup = bool([tag for tag in set_tags if tag.name == FOLLOWUP_TAG])
        extra_notify = []
        if followup:
            try:
                shepherd = self.draft.shepherd
                if shepherd:
                    if settings.USE_DB_REDESIGN_PROXY_CLASSES:
                        extra_notify = [shepherd.formatted_email()]
                    else:
                        extra_notify = ['%s <%s>' % shepherd.email()]
            except PersonOrOrgInfo.DoesNotExist:
                pass
        if not set_tags and not reset_tags:
            return
        update_tags(self.request, self.draft,
                    comment=comment,
                    person=self.person,
                    set_tags=set_tags,
                    reset_tags=reset_tags,
                    extra_notify=extra_notify)

    def save_state(self):
        comment = self.cleaned_data.get('comment')
        if settings.USE_DB_REDESIGN_PROXY_CLASSES:
            from ietf.doc.models import State
        state = State.objects.get(pk=self.cleaned_data.get('new_state'))
        weeks = self.cleaned_data.get('weeks')
        estimated_date = None
        if weeks:
            now = datetime.date.today()
            estimated_date = now + datetime.timedelta(weeks=weeks)

        update_state(self.request, self.draft,
                     comment=comment,
                     person=self.person,
                     to_state=state,
                     estimated_date=estimated_date)

    def save(self):
        self.save_tags()
        if 'only_tags' not in self.data.keys():
            self.save_state()

        if settings.USE_DB_REDESIGN_PROXY_CLASSES:
            comment = self.cleaned_data.get('comment').strip()
            if comment:
                e = DocEvent(type="added_comment")
                e.time = self.draft.time
                e.by = self.person
                e.doc_id = self.draft.pk
                e.desc = comment
                e.save()


class StreamDelegatesForm(forms.Form):
    email = forms.EmailField()

    def __init__(self, *args, **kwargs):
        self.stream = kwargs.pop('stream')
        super(StreamDelegatesForm, self).__init__(*args, **kwargs)

    def get_person(self, email):
        if settings.USE_DB_REDESIGN_PROXY_CLASSES:
            persons = Person.objects.filter(email__address=email).distinct()
        else:
            persons = PersonOrOrgInfo.objects.filter(emailaddress__address=email).distinct()
        if not persons:
            return None
        return persons[0]

    def clean_email(self):
        email = self.cleaned_data.get('email')
        self.person = self.get_person(email)
        if not self.person:
            raise forms.ValidationError('There is no user with this email in the system')
        return email

    def save(self):
        if settings.USE_DB_REDESIGN_PROXY_CLASSES:
            stream_group = Group.objects.get(acronym=self.stream.slug)
            save_group_in_history(stream_group)
            Role.objects.get_or_create(person=self.person,
                                       group=stream_group,
                                       name=RoleName.objects.get(slug="delegate"),
                                       email=Email.objects.get(address=self.cleaned_data.get('email')))
            return

        StreamDelegate.objects.get_or_create(
            person=self.person,
            stream=self.stream)
