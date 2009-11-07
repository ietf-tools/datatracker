# Copyright The IETF Trust 2007, All Rights Reserved

from django import newforms as forms
from models import NonWgMailingList
from ietf.idtracker.models import PersonOrOrgInfo
import re

class NonWgStep1(forms.Form):
    add_edit = forms.ChoiceField(choices=(
	('add', 'Add a new entry'),
	('edit', 'Modify an existing entry'),
	('delete', 'Delete an existing entry'),
	), widget=forms.RadioSelect)
    list_id = forms.ChoiceField(required=False)
    list_id_delete = forms.ChoiceField(required=False)
    def __init__(self, *args, **kwargs):
	super(NonWgStep1, self).__init__(*args, **kwargs)
	choices=[('', '--Select a list here')] + NonWgMailingList.choices()
	self.fields['list_id'].choices = choices
	self.fields['list_id_delete'].choices = choices
    def clean_list_id(self):
	if self.clean_data.get('add_edit', None) == 'edit':
	   if not self.clean_data.get('list_id'):
	       raise forms.ValidationError, 'Please pick a mailing list to modify'
	return self.clean_data['list_id']
    def clean_list_id_delete(self):
	if self.clean_data.get('add_edit', None) == 'delete':
	   if not self.clean_data.get('list_id_delete'):
	       raise forms.ValidationError, 'Please pick a mailing list to delete'
	return self.clean_data['list_id_delete']

# multiwidget for separate scheme and rest for urls
class UrlMultiWidget(forms.MultiWidget):
    def decompress(self, value):
	if value:
	    if '//' in value:
		(scheme, rest) = value.split('//', 1)
		scheme += '//'
	    else:
		scheme = 'http://'
		rest = value
	    return [scheme, rest]
	else:
	    return ['', '']

    def __init__(self, choices=(('http://', 'http://'), ('https://', 'https://')), attrs=None):
	widgets = (forms.RadioSelect(choices=choices, attrs=attrs), forms.TextInput(attrs=attrs))
	super(UrlMultiWidget, self).__init__(widgets, attrs)

    def format_output(self, rendered_widgets):
	return u'%s\n%s\n<br/>' % ( u'<br/>\n'.join(["%s" % w for w in rendered_widgets[0]]), rendered_widgets[1] )

    # If we have two widgets, return the concatenation of the values
    #  (Except, if _0 is "n/a" then return an empty string)
    # _0 might not exist if no radio button is selected (i.e., an
    #  empty form), so return empty string.
    # Otherwise, just return the value.
    def value_from_datadict(self, data, name):
	try:
	    scheme = data[name + '_0']
	    if scheme == 'n/a':
		return ''
	    return scheme + data[name + '_1']
	except KeyError:
	    try:
		return data[name]
	    except KeyError:
		return ''

class PickApprover(forms.Form):
    """
    When instantiating, supply a list of person tags in approvers=
    """
    approver = forms.ChoiceField(choices=(
	('', '-- Pick an approver from the list below'),
    ))
    def __init__(self, approvers, *args, **kwargs):
	super(PickApprover, self).__init__(*args, **kwargs)
	self.fields['approver'].choices = [('', '-- Pick an approver from the list below')] + [(person.person_or_org_tag, str(person)) for person in PersonOrOrgInfo.objects.filter(pk__in=approvers)]

class DeletionPickApprover(PickApprover):
    ds_name = forms.CharField(label = 'Enter your name', widget = forms.TextInput(attrs = {'size': 45}))
    ds_email = forms.EmailField(label = 'Enter your email', widget = forms.TextInput(attrs = {'size': 45}))
    msg_to_ad = forms.CharField(label = 'Message to the Area Director', widget = forms.Textarea(attrs = {'rows': 5, 'cols': 50}))

# A form with no required fields, to allow a preview action
class Preview(forms.Form):
    #preview = forms.BooleanField(required=False)
    pass

class MultiEmailField(forms.CharField):
    '''Ensure that each of a carraige-return-separated
    list of e-mail addresses is valid.'''
    def clean(self, value):
	value = super(MultiEmailField, self).clean(value)
	bad = list()
	for addr in value.split("\n"):
	    addr = addr.strip()
	    if addr != '' and not(forms.fields.email_re.search(addr)):
		bad.append(addr)
	if len(bad) > 0:
	    raise forms.ValidationError, "The following email addresses seem to be invalid: %s" % ", ".join(["'" + addr + "'" for addr in bad])
	return value
