from django import newforms as forms

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

