# Copyright The IETF Trust 2007, All Rights Reserved

from django import forms
from models import IESGLogin, IDStatus, Area, IDState, IDSubState

class IDSearch(forms.Form):
    search_job_owner = forms.ChoiceField(choices=(), required=False)
    search_group_acronym = forms.CharField(widget=forms.TextInput(attrs={'size': 7, 'maxlength': 10}), required=False)
    search_status_id = forms.ModelChoiceField(IDStatus.objects.all(), empty_label="--All", required=False)
    search_area_acronym = forms.ModelChoiceField(Area.active_areas(), empty_label="--All/Any", required=False)
    search_cur_state = forms.ModelChoiceField(IDState.objects.all(), empty_label="--All/Any", required=False)
    sub_state_id = forms.ChoiceField(choices=(), required=False)
    search_filename = forms.CharField(widget=forms.TextInput(attrs={'size': 15, 'maxlength': 60}), required=False)
    search_rfcnumber = forms.IntegerField(widget=forms.TextInput(attrs={'size': 5, 'maxlength': 60}), required=False)
    def __init__(self, *args, **kwargs):
        super(IDSearch, self).__init__(*args, **kwargs)
	self.fields['search_job_owner'].choices = [('', '--All/Any')] + [(ad.id, "%s, %s" % (ad.last_name, ad.first_name)) for ad in IESGLogin.objects.filter(user_level=1).order_by('last_name')] + [('-99', '------------------')] + [(ad.id, "%s, %s" % (ad.last_name, ad.first_name)) for ad in IESGLogin.objects.filter(user_level=2).order_by('last_name')]
	self.fields['sub_state_id'].choices = [('', '--All Substates'), ('0', 'None')] + [(state.sub_state_id, state.sub_state) for state in IDSubState.objects.all()]


# changes done by convert-096.py:changed newforms to forms
