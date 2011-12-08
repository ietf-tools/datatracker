from redesign.doc.models import State
from redesign.name.models import BallotPositionName, DocTagName
from redesign.person.models import Person

from django import forms

# -------------------------------------------------
# Globals
# -------------------------------------------------

TELECHAT_TAGS = ('point','ad-f-up','extpty','need-rev')

BALLOT_NAMES = dict(BallotPositionName.objects.values_list('name','slug'))
IESG_STATE_CHOICES = State.objects.filter(type='draft-iesg').values_list('slug','name').order_by('order')
TAG_CHOICES = list(DocTagName.objects.filter(slug__in=TELECHAT_TAGS).values_list('slug','name').order_by('order'))
TAG_CHOICES.insert(0,('','None'))

# -------------------------------------------------
# Forms
# -------------------------------------------------

class BallotForm(forms.Form):
    name = forms.CharField(max_length=50,widget=forms.HiddenInput)
    id = forms.IntegerField(widget=forms.HiddenInput)
    position = forms.ModelChoiceField(queryset=BallotPositionName.objects.all().order_by('order'), widget=forms.RadioSelect, initial="norecord", required=True)
    
class DocumentStateForm(forms.Form):
    state = forms.ChoiceField(choices=IESG_STATE_CHOICES,required=False)
    sub_state = forms.ChoiceField(choices=TAG_CHOICES, required=False)
