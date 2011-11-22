import datetime

from django import forms
from django.conf import settings
from django.core.mail import EmailMessage
from django.db.models import Q
from django.forms.models import BaseModelFormSet
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe

from ietf.wgchairs.models import WGDelegate, ProtoWriteUp
from ietf.wgchairs.accounts import get_person_for_user
from ietf.ietfworkflows.constants import REQUIRED_STATES
from ietf.ietfworkflows.utils import (get_default_workflow_for_wg, get_workflow_for_wg,
                                      update_tags, FOLLOWUP_TAG, get_state_by_name)
from ietf.ietfworkflows.models import AnnotationTag, State
from ietf.idtracker.models import PersonOrOrgInfo
from ietf.utils.mail import send_mail_text

from workflows.models import Transition

from redesign.doc.models import WriteupDocEvent
from redesign.person.models import Person, Email
from redesign.group.models import Role, RoleName
from redesign.name.models import DocTagName


class RelatedWGForm(forms.Form):

    can_cancel = False

    def __init__(self, *args, **kwargs):
        self.wg = kwargs.pop('wg', None)
        self.user = kwargs.pop('user', None)
        self.message = {}
        super(RelatedWGForm, self).__init__(*args, **kwargs)

    def get_message(self):
        return self.message

    def set_message(self, msg_type, msg_value):
        self.message = {'type': msg_type,
                        'value': msg_value,
                       }


class TagForm(RelatedWGForm):

    tags = forms.ModelMultipleChoiceField(AnnotationTag.objects.filter(wgworkflow__name='Default WG Workflow'),
                                          widget=forms.CheckboxSelectMultiple, required=False)

    def save(self):
        workflow = get_workflow_for_wg(self.wg)
        workflow.selected_tags.clear()
        for tag in self.cleaned_data['tags']:
            workflow.selected_tags.add(tag)
        return workflow


class StateForm(RelatedWGForm):

    states = forms.ModelMultipleChoiceField(State.objects.filter(wgworkflow__name='Default WG Workflow'),
                                            widget=forms.CheckboxSelectMultiple, required=False)

    def update_transitions(self, workflow):
        for transition in workflow.transitions.all():
            if not workflow.selected_states.filter(pk=transition.destination.pk).count():
                transition.delete()
                continue
            for state in transition.states.all():
                if not workflow.selected_states.filter(pk=state.pk).count():
                    transition.states.remove(state)
            if not transition.states.count():
                transition.delete()
                continue

    def save(self):
        workflow = get_workflow_for_wg(self.wg)
        workflow.selected_states.clear()
        for state in self.cleaned_data['states']:
            workflow.selected_states.add(state)
        for name in REQUIRED_STATES:
            rstate = get_state_by_name(name)
            if rstate:
                workflow.selected_states.add(rstate)
        self.update_transitions(workflow)
        return workflow


class DeleteTransitionForm(RelatedWGForm):

    transitions = forms.ModelMultipleChoiceField(Transition.objects.all(),
                                                 widget=forms.CheckboxSelectMultiple)

    def __init__(self, *args, **kwargs):
        super(DeleteTransitionForm, self).__init__(*args, **kwargs)
        workflow = get_workflow_for_wg(self.wg)
        self.fields['transitions'].queryset = self.fields['transitions'].queryset.filter(workflow=workflow)

    def save(self):
        for transition in self.cleaned_data['transitions']:
            transition.delete()


class TransitionForm(forms.ModelForm):

    states = forms.ModelMultipleChoiceField(State.objects.filter(wgworkflow__name='Default WG Workflow'))

    class Meta:
        model = Transition
        fields = ('DELETE', 'name', 'states', 'destination', )

    def __init__(self, *args, **kwargs):
        self.wg = kwargs.pop('wg', None)
        self.user = kwargs.pop('user', None)
        super(TransitionForm, self).__init__(*args, **kwargs)
        workflow = get_workflow_for_wg(self.wg)
        self.fields['states'].queryset = workflow.selected_states.all()
        self.fields['destination'].queryset = workflow.selected_states.all()
        self.fields['destination'].required = True
        if self.instance.pk:
            self.fields['states'].initial = [i.pk for i in self.instance.states.all()]
        self.instance.workflow = workflow

    def as_row(self):
        return self._html_output(u'<td>%(errors)s%(field)s%(help_text)s</td>', u'<td colspan="2">%s</td>', '</td>', u'<br />%s', False)

    def save(self, *args, **kwargs):
        instance = super(TransitionForm, self).save(*args, **kwargs)
        for state in self.cleaned_data['states']:
            state.transitions.add(instance)


class TransitionFormSet(BaseModelFormSet):

    form = TransitionForm
    can_delete = True
    extra = 2
    max_num = 0
    can_order = False
    model = Transition

    def __init__(self, *args, **kwargs):
        self.wg = kwargs.pop('wg', None)
        self.user = kwargs.pop('user', None)
        super(TransitionFormSet, self).__init__(*args, **kwargs)

    def _construct_form(self, i, **kwargs):
        kwargs = kwargs or {}
        kwargs.update({'wg': self.wg, 'user': self.user})
        return super(TransitionFormSet, self)._construct_form(i, **kwargs)

    def as_table(self):
        html = u''
        csscl = 'oddrow'
        for form in self.forms:
            html += u'<tr class="%s">' % csscl
            html += form.as_row()
            html += u'</tr>'
            if csscl == 'oddrow':
                csscl = 'evenrow'
            else:
                csscl = 'oddrow'
        return mark_safe(u'\n'.join([unicode(self.management_form), html]))


def workflow_form_factory(request, wg, user):

    if request.POST.get('update_transitions', None):
        return TransitionFormSet(wg=wg, user=user, data=request.POST)
    elif request.POST.get('update_states', None):
        return StateForm(wg=wg, user=user, data=request.POST)
    return TagForm(wg=wg, user=user, data=request.POST)


class RemoveDelegateForm(RelatedWGForm):

    delete = forms.MultipleChoiceField()

    def __init__(self, *args, **kwargs):
        super(RemoveDelegateForm, self).__init__(*args, **kwargs)
        self.fields['delete'].choices = [(i.pk, i.pk) for i in self.wg.wgdelegate_set.all()]

    def save(self):
        delegates = self.cleaned_data.get('delete')
        WGDelegate.objects.filter(pk__in=delegates).delete()
        self.set_message('success', 'Delegates removed')

def assign_shepherd(user, internetdraft, shepherd):
    if internetdraft.shepherd == shepherd:
        return
    
    from redesign.doc.models import save_document_in_history, DocEvent, Document

    # saving the proxy object is a bit of a mess, so convert it to a
    # proper document
    doc = Document.objects.get(name=internetdraft.name)
    
    save_document_in_history(doc)

    doc.time = datetime.datetime.now()
    doc.shepherd = shepherd
    doc.save()

    e = DocEvent(type="changed_document")
    e.time = doc.time
    e.doc = doc
    e.by = user.get_profile()
    if not shepherd:
        e.desc = u"Unassigned shepherd"
    else:
        e.desc = u"Changed shepherd to %s" % shepherd.name
    e.save()

    # update proxy too
    internetdraft.shepherd = shepherd

class AddDelegateForm(RelatedWGForm):

    email = forms.EmailField()
    form_type = forms.CharField(widget=forms.HiddenInput, initial='single')

    def __init__(self, *args, **kwargs):
        self.shepherd = kwargs.pop('shepherd', False)
        super(AddDelegateForm, self).__init__(*args, **kwargs)
        self.next_form = self

    def get_next_form(self):
        return self.next_form

    def get_person(self, email):
        persons = PersonOrOrgInfo.objects.filter(emailaddress__address=email).filter(
            Q(iesglogin__isnull=False)|
            Q(legacywgpassword__isnull=False)|
            Q(legacyliaisonuser__isnull=False)).distinct()
        if not persons:
            raise PersonOrOrgInfo.DoesNotExist
        if len(persons) > 1:
            raise PersonOrOrgInfo.MultipleObjectsReturned
        return persons[0]

    def save(self):
        email = self.cleaned_data.get('email')
        if settings.USE_DB_REDESIGN_PROXY_CLASSES:
            try:
                person = Person.objects.filter(email__address=email).exclude(user=None).distinct().get()
            except Person.DoesNotExist:
                self.next_form = NotExistDelegateForm(wg=self.wg, user=self.user, email=email, shepherd=self.shepherd)
                self.next_form.set_message('doesnotexist', 'There is no user with this email allowed to login to the system')
                return
            except Person.MultipleObjectsReturned:
                self.next_form = MultipleDelegateForm(wg=self.wg, user=self.user, email=email, shepherd=self.shepherd)
                self.next_form.set_message('multiple', 'There are multiple users with this email in the system')
                return
        else:
            try:
                person = self.get_person(email)
            except PersonOrOrgInfo.DoesNotExist:
                self.next_form = NotExistDelegateForm(wg=self.wg, user=self.user, email=email, shepherd=self.shepherd)
                self.next_form.set_message('doesnotexist', 'There is no user with this email allowed to login to the system')
                return
            except PersonOrOrgInfo.MultipleObjectsReturned:
                self.next_form = MultipleDelegateForm(wg=self.wg, user=self.user, email=email, shepherd=self.shepherd)
                self.next_form.set_message('multiple', 'There are multiple users with this email in the system')
                return
        if self.shepherd:
            self.assign_shepherd(person)
        else:
            self.create_delegate(person)

    def assign_shepherd(self, person):
        if settings.USE_DB_REDESIGN_PROXY_CLASSES:
            assign_shepherd(self.user, self.shepherd, person)
        else:
            self.shepherd.shepherd = person
            self.shepherd.save()
        self.next_form = AddDelegateForm(wg=self.wg, user=self.user, shepherd=self.shepherd)
        self.next_form.set_message('success', 'Shepherd assigned successfully')

    def create_delegate(self, person):
        if settings.USE_DB_REDESIGN_PROXY_CLASSES:
            created = False
            e = Email.objects.get(address=self.cleaned_data.get('email'))
            if not Role.objects.filter(name="delegate", group=self.wg, person=person, email=e):
                delegate, created = Role.objects.get_or_create(
                    name=RoleName.objects.get(slug="delegate"), group=self.wg, person=e.person, email=e)
        else:
            (delegate, created) = WGDelegate.objects.get_or_create(wg=self.wg,
                                                                   person=person)
        if not created:
            self.set_message('error', 'The email belongs to a person who is already a delegate')
        else:
            self.next_form = AddDelegateForm(wg=self.wg, user=self.user)
            self.next_form.set_message('success', 'A new delegate has been added')


class MultipleDelegateForm(AddDelegateForm):

    email = forms.EmailField(widget=forms.HiddenInput)
    form_type = forms.CharField(widget=forms.HiddenInput, initial='multiple')
    persons = forms.ChoiceField(widget=forms.RadioSelect, help_text='Please select one person from the list')
    submit_msg = 'Designate as delegate'

    def __init__(self, *args, **kwargs):
        self.email = kwargs.pop('email', None)
        super(MultipleDelegateForm, self).__init__(*args, **kwargs)
        if not self.email:
            self.email = self.data.get('email', None)
        self.fields['email'].initial = self.email
        if settings.USE_DB_REDESIGN_PROXY_CLASSES:
            self.fields['persons'].choices = [(i.pk, unicode(i)) for i in Person.objects.filter(email__address=self.email).exclude(user=None).distinct().order_by('name')]
        else:
            self.fields['persons'].choices = [(i.pk, unicode(i)) for i in PersonOrOrgInfo.objects.filter(emailaddress__address=self.email).filter(
                    Q(iesglogin__isnull=False)|
                    Q(legacywgpassword__isnull=False)|
                    Q(legacyliaisonuser__isnull=False)).distinct().order_by('first_name')]

    def save(self):
        person_id = self.cleaned_data.get('persons')
        if settings.USE_DB_REDESIGN_PROXY_CLASSES:
            person = Person.objects.get(pk=person_id)
        else:
            person = PersonOrOrgInfo.objects.get(pk=person_id)
        if self.shepherd:
            self.assign_shepherd(person)
        else:
            self.create_delegate(person)


class NotExistDelegateForm(MultipleDelegateForm):

    email = forms.EmailField(widget=forms.HiddenInput)
    form_type = forms.CharField(widget=forms.HiddenInput, initial='notexist')
    can_cancel = True
    submit_msg = 'Send email to these addresses'

    def __init__(self, *args, **kwargs):
        super(NotExistDelegateForm, self).__init__(*args, **kwargs)
        self.email_list = []
        del(self.fields['persons'])

    def get_email_list(self):
        if self.email_list:
            return self.email_list
        email_list = [self.email]
        email_list.append('IETF Secretariat <iesg-secretary@ietf.org>')
        email_list += ['%s <%s>' % i.person.email() for i in self.wg.wgchair_set.all() if i.person.email()]
        self.email_list = email_list
        return email_list

    def as_p(self):
        email_list = self.get_email_list()
        info = render_to_string('wgchairs/notexistdelegate.html', {'email_list': email_list, 'shepherd': self.shepherd})
        return info + super(NotExistDelegateForm, self).as_p()

    def send_email(self, to_email, template):
        if self.shepherd:
            subject = 'WG shepherd needs system credentials'
        else:
            subject = 'WG Delegate needs system credentials'
        if settings.USE_DB_REDESIGN_PROXY_CLASSES:
            persons = Person.objects.filter(email__address=self.email).distinct()
        else:
            persons = PersonOrOrgInfo.objects.filter(emailaddress__address=self.email).distinct()
        body = render_to_string(template,
                                {'chair': get_person_for_user(self.user),
                                 'delegate_email': self.email,
                                 'shepherd': self.shepherd,
                                 'delegate_persons': persons,
                                 'wg': self.wg,
                                })

        send_mail_text(None, to_email, settings.DEFAULT_FROM_EMAIL, subject, body)

    def save(self):
        self.next_form = AddDelegateForm(wg=self.wg, user=self.user)
        if settings.DEBUG:
            self.next_form.set_message('warning', 'Email was not sent cause tool is in DEBUG mode')
        else:
            # this is ugly...
            email_list = self.get_email_list()
            delegate = email_list[0]
            secretariat = email_list[1]
            wgchairs = email_list[2:]
            self.send_email(delegate, 'wgchairs/notexistsdelegate_delegate_email.txt')
            self.send_email(secretariat, 'wgchairs/notexistsdelegate_secretariat_email.txt')
            self.send_email(wgchairs, 'wgchairs/notexistsdelegate_wgchairs_email.txt')
            self.next_form.set_message('success', 'Email sent successfully')


def add_form_factory(request, wg, user, shepherd=False):
    if request.method != 'POST' or request.POST.get('update_shepehrd'):
        return AddDelegateForm(wg=wg, user=user, shepherd=shepherd)

    if request.POST.get('form_type', None) == 'multiple':
        return MultipleDelegateForm(wg=wg, user=user, data=request.POST.copy(), shepherd=shepherd)
    elif request.POST.get('form_type', None) == 'notexist':
        return NotExistDelegateForm(wg=wg, user=user, data=request.POST.copy(), shepherd=shepherd)
    elif request.POST.get('form_type', None) == 'single':
        return AddDelegateForm(wg=wg, user=user, data=request.POST.copy(), shepherd=shepherd)

    return AddDelegateForm(wg=wg, user=user, shepherd=shepherd)


class WriteUpEditForm(RelatedWGForm):

    writeup = forms.CharField(widget=forms.Textarea, required=False)
    followup = forms.BooleanField(required=False)
    comment = forms.CharField(widget=forms.Textarea, required=False)

    def __init__(self, *args, **kwargs):
        self.doc = kwargs.pop('doc', None)
        self.doc_writeup = self.doc.protowriteup_set.all()
        if self.doc_writeup.count():
            self.doc_writeup = self.doc_writeup[0]
        else:
            self.doc_writeup = None
        super(WriteUpEditForm, self).__init__(*args, **kwargs)
        self.person = get_person_for_user(self.user)

    def get_writeup(self):
        return self.data.get('writeup', self.doc_writeup and self.doc_writeup.writeup or '')

    def save(self):
        if settings.USE_DB_REDESIGN_PROXY_CLASSES:
            e = WriteupDocEvent(type="changed_protocol_writeup")
            e.doc = self.doc
            e.by = self.person
            e.desc = e.get_type_display()
            e.text = self.cleaned_data['writeup']
            e.save()
            from ietf.wgchairs.models import ProtoWriteUpProxy
            self.doc_writeup = ProtoWriteUpProxy.objects.get(pk=e.pk)
        else:
            if not self.doc_writeup:
                self.doc_writeup = ProtoWriteUp.objects.create(
                    person=self.person,
                    draft=self.doc,
                    writeup=self.cleaned_data['writeup'])
            else:
                self.doc_writeup.writeup = self.cleaned_data['writeup']
                self.doc_writeup.save()

        if self.data.get('modify_tag', False):
            followup = self.cleaned_data.get('followup', False)
            comment = self.cleaned_data.get('comment', False)
            try:
                shepherd = self.doc.shepherd
            except PersonOrOrgInfo.DoesNotExist:
                shepherd = None
            if shepherd:
                if settings.USE_DB_REDESIGN_PROXY_CLASSES:
                    extra_notify = [shepherd.formatted_email()]
                else:
                    extra_notify = ['%s <%s>' % shepherd.email()]
            else:
                extra_notify = []
            if settings.USE_DB_REDESIGN_PROXY_CLASSES:
                tags = DocTagName.objects.filter(slug="sheph-u")
            else:
                tags = [FOLLOWUP_TAG]
            if followup:
                update_tags(self.doc, comment, self.person, set_tags=tags, extra_notify=extra_notify)
            else:
                update_tags(self.doc, comment, self.person, reset_tags=tags, extra_notify=extra_notify)
        return self.doc_writeup

    def is_valid(self):
        if self.data.get('confirm', False) and self.data.get('modify_tag', False):
            self.fields['comment'].required = True
        else:
            self.fields['comment'].required = False
        return super(WriteUpEditForm, self).is_valid()
