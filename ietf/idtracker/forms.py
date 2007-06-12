from django import newforms as forms
from models import IESGLogin, IDStatus, Area, IDState, IDSubState

class IDSearch(forms.Form):
    search_job_owner = forms.ChoiceField(choices=())
    search_group_acronym = forms.CharField(widget=forms.TextInput(attrs={'size': 6, 'maxlength': 10}))
    search_status_id = forms.ModelChoiceField(IDStatus.objects.all(), empty_label="--All")
    search_area_acronym = forms.ModelChoiceField(Area.objects.filter(status=Area.ACTIVE), empty_label="--All/Any")
    search_cur_state = forms.ModelChoiceField(IDState.objects.all(), empty_label="--All/Any")
    sub_state_id = forms.ModelChoiceField(IDSubState.objects.all(), empty_label="--All Substates")
    search_filename = forms.CharField(widget=forms.TextInput(attrs={'size': 15, 'maxlength': 60}))
    search_rfcnumber = forms.CharField(widget=forms.TextInput(attrs={'size': 5, 'maxlength': 60}))
    def __init__(self, *args, **kwargs):
        super(IDSearch, self).__init__(*args, **kwargs)
	self.fields['search_job_owner'].choices = [('', '--All/Any')] + [(ad.id, "%s, %s" % (ad.last_name, ad.first_name)) for ad in IESGLogin.objects.filter(user_level=1).order_by('last_name')] + [('-99', '----------')] + [(ad.id, "%s, %s" % (ad.last_name, ad.first_name)) for ad in IESGLogin.objects.filter(user_level=2).order_by('last_name')]

class EmailFeedback(forms.Form):
    category = forms.CharField(widget=forms.HiddenInput())
    name = forms.CharField(label='Your Name')
    email = forms.EmailField(label='Your Email')
    subject = forms.CharField(widget=forms.TextInput(attrs={'size': 72}))
    message = forms.CharField(widget=forms.Textarea(attrs={'rows': 10, 'cols': 70}))
    def clean_category(self):
	value = self.clean_data.get('category', 'bugs')
	if value not in ('bugs', 'discuss'):
	    raise forms.ValidationError, 'Unknown category, try "discuss" or "bugs".'
	return value

