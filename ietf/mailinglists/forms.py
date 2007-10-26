# Copyright The IETF Trust 2007, All Rights Reserved

from django import newforms as forms
from models import NonWgMailingList, ImportedMailingList
from ietf.idtracker.models import PersonOrOrgInfo, IETFWG
import re

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
	#return field.as_widget(field.field.widget)
        return [re.sub(r'input ','input onClick="activate_nwg_widgets()" ',str(i)) for i in field.as_widget(field.field.widget)]
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
	), widget=forms.RadioSelect())
    group = forms.ModelChoiceField(queryset=IETFWG.objects.all().filter(status=IETFWG.ACTIVE).select_related(depth=1).order_by('acronym.acronym'), required=False, empty_label="--Select Working Group")
    domain_name = forms.ChoiceField(choices=DOMAIN_CHOICES, required=False, widget = forms.Select(attrs={'onChange': 'set_domain(this)'}), initial='ietf.org')
    list_to_close = forms.ModelChoiceField(queryset=ImportedMailingList.objects.all(), required=False, empty_label="--Select Mailing List")
    def mail_type_fields(self):
	field = self['mail_type']
	# RadioSelect() doesn't pass its attributes through to the <input>
	# elements, so in order to get the javascript onClick we add it here.
	return [re.sub(r'input ','input onClick="activate_widgets()" ',str(i)) for i in field.as_widget(field.field.widget)]
    def __init__(self, *args, **kwargs):
	super(ListReqStep1, self).__init__(*args, **kwargs)
	# Base the queryset for list_to_close on the initial value
	# for the domain_name field.
	self.fields['list_to_close'].queryset = ImportedMailingList.choices(self.initial.get('domain_name', 'ietf.org'))
	# This is necessary after changing a ModelChoiceField's
	# queryset.
	self.fields['list_to_close'].widget.choices = self.fields['list_to_close'].choices
    def clean_group(self):
	group = self.clean_data['group']
	action = self.clean_data.get('mail_type', '')
	if action.endswith('wg'):
	    if not self.clean_data.get('group'):
		raise forms.ValidationError, 'Please pick a working group'
	    group_list_exists = ImportedMailingList.objects.filter(group_acronym=group).count()
	    if action.startswith('close'):
	        if group_list_exists == 0:
		    raise forms.ValidationError, 'The %s mailing list does not exist.' % group
	    else:
	        if group_list_exists:
		    raise forms.ValidationError, 'The %s mailing list already exists.' % group
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

class ListApprover(forms.Form):
    """
    When instantiating, supply a list of AreaDirector, WGChair and/or Role
    objects (or other objects with a person_id and appropriate str value).
    """
    approver = forms.ChoiceField(choices=(
	('', '-- Pick an approver from the list below'),
    ))
    def __init__(self, approvers, requestor=None, *args, **kwargs):
	super(ListApprover, self).__init__(*args, **kwargs)
	self.fields['approver'].choices = [('', '-- Pick an approver from the list below')] + [(item.person_id, str(item)) for item in approvers]
	if requestor:
	    self.fields['approver'].initial = requestor.person_id
	    self.fields['approver'].widget = forms.widgets.HiddenInput()

class DeletionPickApprover(PickApprover):
    ds_name = forms.CharField(label = 'Enter your name', widget = forms.TextInput(attrs = {'size': 45}))
    ds_email = forms.EmailField(label = 'Enter your email', widget = forms.TextInput(attrs = {'size': 45}))
    msg_to_ad = forms.CharField(label = 'Message to the Area Director', widget = forms.Textarea(attrs = {'rows': 5, 'cols': 50}))

# A form with no required fields, to allow a preview action
class Preview(forms.Form):
    #preview = forms.BooleanField(required=False)
    pass

class ListReqAuthorized(forms.Form):
    authorized = forms.BooleanField()
    def clean_authorized(self):
	if not(self.clean_data.get('authorized', 0)):
	    raise forms.ValidationError, 'You must assert that you are authorized to perform this action.'
	return self.clean_data['authorized']

class ListReqClose(forms.Form):
    requestor = forms.CharField(label = "Requestor's full name", widget = forms.TextInput(attrs = {'size': 55}))
    requestor_email = forms.EmailField(label = "Requestor's email address", widget = forms.TextInput(attrs = {'size': 55}))
    mlist_name = forms.CharField(label = 'Mailing List Name')	# will turn into just display field by template.
    domain_name = forms.CharField(widget = forms.HiddenInput())
    reason_to_delete = forms.CharField(label = 'Reason for closing list', widget = forms.Textarea(attrs = {'rows': 4, 'cols': 60}))

class AdminRequestor(forms.MultiWidget):
    def decompress(self, value):
	# This implementation moves the requestor to the listbox
	# if there are any validation errors.
	# If we could find the requestor, we could instead
	# check the checkbox, but for now let's try this.
	return ['', '', value]
    def __init__(self, attrs=None):
	widgets = (forms.CheckboxInput(attrs={'onClick': 'checkthis()'}), forms.TextInput(attrs={'size': 55, 'disabled': True}), forms.Textarea(attrs=attrs))
	super(AdminRequestor, self).__init__(widgets, attrs)
    def format_output(self, rendered_widgets):
	return u'<br/>\n'.join(["<label>%s Same as requestor</label>" % rendered_widgets[0]] + rendered_widgets[1:])
    def value_from_datadict(self, data, name):
	try:
	    radio = data.get(name + '_0', "off")
	    rest = data[name + '_2']
	    if radio == 'on':
		# This has some deep assumptions about how
		# this is used.
		key = name.replace('admins', 'requestor_email')
		try:
		    ret = data[key] + "\r\n" + rest
		    return ret.strip()
		except KeyError:
		    return rest
	    else:
		return rest
	except KeyError:
	    try:
		return data[name]
	    except KeyError:
		return ''

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

class ApprovalComment(forms.Form):
    add_comment = forms.CharField(label="Approver's comments to the requestor (will be emailed to the requestor)", widget=forms.Textarea(attrs={'cols':41, 'rows': 4}))


