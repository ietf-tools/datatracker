from django import newforms as forms
from models import NonWgMailingList, ImportedMailingList
from ietf.idtracker.models import PersonOrOrgInfo, GroupIETF

class NonWgStep1(forms.Form):
    add_edit = forms.ChoiceField(choices=(
	('add', 'Add a new entry'),
	('edit', 'Modify an existing entry'),
	('delete', 'Delete an existing entry'),
	), widget=forms.RadioSelect)
    list_id = forms.ChoiceField(required=False)
    list_id_delete = forms.ChoiceField(required=False)
    def add_edit_fields(self):
	field = self['add_edit']
	return field.as_widget(field.field.widget)
    def __init__(self, *args, **kwargs):
	super(NonWgStep1, self).__init__(*args, **kwargs)
	choices=[('', '-- Select an item from the list below')] + NonWgMailingList.choices()
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

class ListReqStep1(forms.Form):
    DOMAIN_CHOICES = (
	('ietf.org', 'ietf.org'),
	('iab.org', 'iab.org'),
	('irtf.org', 'irtf.org'),
    )
    mail_type = forms.ChoiceField(choices=(
	('newwg', 'Create new WG email list at ietf.org'),
	('movewg', 'Move existing WG email list to ietf.org'),
	('closewg', 'Close existing WG email list at ietf.org'),
	('newnon', 'Create new non-WG email list at selected domain above'),
	('movenon', 'Move existing non-WG email list to selected domain above'),
	('closenon', 'Close existing non-WG email list at selected domain above'),
	), widget=forms.RadioSelect)
    group = forms.ChoiceField(required=False)
    domain_name = forms.ChoiceField(choices=DOMAIN_CHOICES, required=False)
    list_to_close = forms.ChoiceField(required=False)
    def mail_type_fields(self):
	field = self['mail_type']
	return field.as_widget(field.field.widget)
    def __init__(self, *args, **kwargs):
	dname = kwargs.get('dname', 'ietf.org')
	super(ListReqStep1, self).__init__(*args, **kwargs)
	self.fields['group'].choices = [('', '-- Select Working Group')] + GroupIETF.choices()
	self.fields['list_to_close'].choices = [('', '-- Select List To Close')] + ImportedMailingList.choices(dname)
	self.fields['domain_name'].initial = dname
    def clean_group(self):
	if self.clean_data.get('mail_type', '').endswith('wg'):
	    if not self.clean_data.get('group'):
		raise forms.ValidationError, 'Please pick a working group'
	return self.clean_data['group']
    def clean_list_to_close(self):
	if self.clean_data.get('mail_type', '') == 'closenon':
	    if not self.clean_data.get('list_to_close'):
		raise forms.ValidationError, 'Please pick a list to close'
	return self.clean_data['list_to_close']

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
    # Otherwise, just return the value.
    def value_from_datadict(self, data, name):
	try:
	    scheme = data[name + '_0']
	    if scheme == 'n/a':
		return ''
	    return scheme + data[name + '_1']
	except KeyError:
	    return data[name]

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
