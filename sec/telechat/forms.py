#from ietf.idrfc.views_ballot import BALLOT_CHOICES
from redesign.name.models import BallotPositionName # IesgDocStateName
from redesign.person.models import Person

from django import forms

BALLOT_CHOICES = (("Yes", "Yes"),
                  ("No Objection", "No Objection"),
                  ("Discuss", "Discuss"),
                  ("Abstain", "Abstain"),
                  ("Recuse", "Recuse"),
                  ("No Record","No Record"))
                  
STATE_CHOICES = (("remains","Remains under discussion by the IESG"),
                 ("approved","Has been approved by the IESG"),
                 ("note","Need note"))

BALLOT_NAMES = dict(BallotPositionName.objects.values_list('name','slug'))
#IESG_STATE_CHOICES = IesgDocStateName.objects.values_list('slug','name').order_by('order')
IESG_STATE_CHOICES = ''
TAG_CHOICES = (('','--Select Sub State'),('ad-f-up','AD Followup'),('extpty','External Party'),('need-rev','Revised ID Needed'))
AD_CHOICES = Person.objects.filter(role__name__name='Area Director').values_list('id','name')

class BallotForm(forms.Form):
    name = forms.CharField(max_length=50,widget=forms.HiddenInput)
    id = forms.IntegerField(widget=forms.HiddenInput)
    #position = forms.ChoiceField(widget=forms.RadioSelect,choices=BALLOT_CHOICES,required=False)
    position = forms.ModelChoiceField(queryset=BallotPositionName.objects.all().order_by('order'), widget=forms.RadioSelect, initial="norecord", required=True)
    
class DocumentStateForm(forms.Form):
    state = forms.ChoiceField(widget=forms.RadioSelect,choices=STATE_CHOICES,required=False)
    iesg_state = forms.ChoiceField(choices=IESG_STATE_CHOICES, required=False)
    tag = forms.ChoiceField(choices=TAG_CHOICES, required=False)
    iana_note = forms.CharField(widget=forms.Textarea, required=False)
    other_note = forms.CharField(widget=forms.Textarea, required=False)
    ad = forms.ChoiceField(choices=AD_CHOICES, required=False)
    
