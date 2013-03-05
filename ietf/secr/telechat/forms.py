from ietf.iesg.models import TelechatAgendaItem
from ietf.doc.models import State
from ietf.name.models import BallotPositionName, DocTagName
from ietf.person.models import Person

from django import forms

# -------------------------------------------------
# Globals
# -------------------------------------------------

TELECHAT_TAGS = ('point','ad-f-up','extpty','need-rev')

# -------------------------------------------------
# Forms
# -------------------------------------------------

class BallotForm(forms.Form):
    name = forms.CharField(max_length=50,widget=forms.HiddenInput)
    id = forms.IntegerField(widget=forms.HiddenInput)
    position = forms.ModelChoiceField(queryset=BallotPositionName.objects.exclude(slug='block').order_by('order'), widget=forms.RadioSelect, initial="norecord", required=True)
    
class ChangeStateForm(forms.Form):
    '''
    This form needs to handle documents of different types (draft, and conflrev for now).
    Start with all document states in the state ModelChoice query, on init restrict the
    query to be the same type as the initial doc_state.
    '''
    state = forms.ModelChoiceField(State.objects.all(), empty_label=None, required=True)
    substate = forms.ModelChoiceField(DocTagName.objects.filter(slug__in=(TELECHAT_TAGS)), required=False)
    
    def __init__(self,*args,**kwargs):
        super(ChangeStateForm, self).__init__(*args,**kwargs)
        state = State.objects.get(id=self.initial['state'])
        self.fields['state'].queryset = State.objects.filter(type=state.type)
        
class DateSelectForm(forms.Form):
    date = forms.ChoiceField()
    
    def __init__(self,*args,**kwargs):
        choices = kwargs.pop('choices')
        super(DateSelectForm, self).__init__(*args,**kwargs)
        self.fields['date'].widget.choices = choices

class IssueModelForm(forms.ModelForm):
    class Meta:
        model = TelechatAgendaItem
        