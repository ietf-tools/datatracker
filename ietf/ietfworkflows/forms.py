from django import forms

from ietf.ietfworkflows.utils import (get_workflow_for_draft,
                                      get_state_for_draft)


class StreamDraftForm(forms.Form):

    can_cancel = False

    def __init__(self, *args, **kwargs):
        self.draft = kwargs.pop('draft', None)
        self.user = kwargs.pop('user', None)
        self.message = {}
        super(StreamDraftForm, self).__init__(*args, **kwargs)

    def get_message(self):
        return self.message

    def set_message(self, msg_type, msg_value):
        self.message = {'type': msg_type,
                        'value': msg_value,
                       }


class DraftStateForm(StreamDraftForm):

    comment = forms.CharField(widget=forms.Textarea)
    new_state = forms.ChoiceField()
    weeks = forms.IntegerField(required=False)

    def __init__(self, *args, **kwargs):
        super(DraftStateForm, self).__init__(*args, **kwargs)
        if self.is_bound:
            for key, value in self.data.items():
                if key.startswith('transition_'):
                    new_state = self.get_new_state(key)
                    if new_state:
                        self.data.update({'new_state': new_state.id})
        self.workflow = get_workflow_for_draft(self.draft)
        self.state = get_state_for_draft(self.draft)
        self.fields['new_state'].choices = self.get_states()

    def get_new_state(self, key):
        transition_id = key.replace('transition_', '')
        transition = self.get_transitions().filter(id=transition_id)
        if transition:
            return transition[0].destination
        return None

    def get_transitions(self):
        return self.state.transitions.filter(workflow=self.workflow)

    def get_states(self):
        return [(i.pk, i.name) for i in self.workflow.get_states()]
