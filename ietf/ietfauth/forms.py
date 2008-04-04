# Copyright The IETF Trust 2007, All Rights Reserved
from django import newforms as forms
from django.conf import settings
import hmac, sha
import time

class EmailForm(forms.Form):
    email = forms.EmailField()

def email_hash(email, timestamp):
    return hmac.new(settings.SECRET_KEY, "%d%s" % (timestamp, email), sha).hexdigest()

class ChallengeForm(forms.Form):
    email = forms.EmailField()
    timestamp = forms.IntegerField()
    hash = forms.CharField()
    def clean_timestamp(self):
	now = int(time.time())
	timestamp = self.clean_data['timestamp']
	if timestamp > now:
	    raise forms.ValidationError, 'Timestamp in the future'
	if timestamp < (now - 86400*settings.PASSWORD_DAYS):
	    raise forms.ValidationError, 'Timestamp is too old'
	return timestamp
    def clean_hash(self):
    	if self.clean_data['hash'] != email_hash(self.clean_data['email'], self.clean_data['timestamp']):
	    raise forms.ValidationError, 'Hash is incorrect'
	return self.clean_data['hash']

class PWForm(forms.Form):
    password = forms.CharField(label='Enter your desired password', widget=forms.PasswordInput())
    repeat = forms.CharField(label='Re-enter the same password', widget=forms.PasswordInput())
    def clean_repeat(self):
	if self.clean_data['password'] != self.clean_data['repeat']:
	    raise forms.ValidationError, 'Passwords do not match'

# Field lengths from PersonOrOrgInfo
class FirstLastForm(forms.Form):
    first = forms.CharField(label='First Name', max_length=20, widget = forms.TextInput(attrs = {'size': 20}))
    last = forms.CharField(label='Last Name', max_length=50, widget = forms.TextInput(attrs = {'size': 50}))
