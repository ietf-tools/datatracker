from forms import NonWgStep1, ListReqStep1, PickApprover, DeletionPickApprover, UrlMultiWidget, Preview, ListReqAuthorized, ListReqClose
from models import NonWgMailingList, MailingList
from ietf.idtracker.models import Area, PersonOrOrgInfo
from django import newforms as forms
from django.shortcuts import render_to_response
from django.template import RequestContext
from ietf.contrib import wizard, form_decorator
from ietf.utils.mail import send_mail_subj

def formchoice(form, field):
    if not(form.is_valid()):
	return None
    d = str(form.clean_data[field])
    for k, v in form.fields[field].choices:
	if str(k) == d:
	    return v
	# oddly, one of the forms stores the translated value
	# in clean_data; the other stores the key.  This second
	# if wouldn't be needed if both stored the key.
	# This whole function wouldn't be needed if both stored
	# the value.
	if str(v) == d:
	    return v
    return None

nonwg_fields = {
    'id': None,
    'status': None,
    'ds_name': None,
    'ds_email': None,
    'msg_to_ad': None,
}

nonwg_attrs = {
    's_name': {'size': 50},
    's_email': {'size': 50},
    'list_name': {'size': 80},
}

nonwg_widgets = {
    'list_url': UrlMultiWidget(choices=(('http://', 'http://'), ('https://', 'https://'), ('mailto:', 'mailto:'))),
    'admin': forms.Textarea(attrs = {'rows': 3, 'cols': 50}),
    'purpose': forms.Textarea(attrs = {'rows': 4, 'cols': 70}),
    'subscribe_url': UrlMultiWidget(choices=(('n/a', 'Not Applicable'), ('http://', 'http://'), ('https://', 'https://'))),
    'subscribe_other': forms.Textarea(attrs = {'rows': 3, 'cols': 50}),
}

nonwg_querysets = {
    'area': Area.objects.filter(status=1)
}

nonwg_callback = form_decorator(fields=nonwg_fields, widgets=nonwg_widgets, attrs=nonwg_attrs, querysets=nonwg_querysets)

def gen_approval(approvers, parent):
    class BoundApproval(parent):
	_approvers = approvers
	def __init__(self, *args, **kwargs):
	    super(BoundApproval, self).__init__(self._approvers, *args, **kwargs)
    return BoundApproval

class NonWgWizard(wizard.Wizard):
    clean_forms = []
    def get_template(self):
	templates = []
	if self.step > 0:
	    action = {'add': 'addedit', 'edit': 'addedit', 'delete': 'delete'}[self.clean_forms[0].clean_data['add_edit']]
	    templates.append("mailinglists/nwg_wizard_%s_step%d.html" % (action, self.step))
	    templates.append("mailinglists/nwg_wizard_%s.html" % (action))
	templates.append("mailinglists/nwg_wizard_step%d.html" % (self.step))
	templates.append("mailinglists/nwg_wizard.html")
	return templates
    def render_template(self, *args, **kwargs):
	self.extra_context['clean_forms'] = self.clean_forms
	if self.step == 3:
	    form0 = self.clean_forms[0]
	    add_edit = form0.clean_data['add_edit']
	    if add_edit == 'add' or add_edit == 'edit':
		# Can't get the choice mapping directly from the form
		self.extra_context['area'] = formchoice(self.clean_forms[1], 'area')
		self.extra_context['approver'] = formchoice(self.clean_forms[2], 'approver')
		print "formchoice for area = %s" % formchoice(self.clean_forms[1], 'area')
	    else:
	    	print "add_edit = %s" % add_edit
	return super(NonWgWizard, self).render_template(*args, **kwargs)
    def failed_hash(self, step):
	raise NotImplementedError("step %d hash failed" % step)
    def process_step(self, request, form, step):
	form.full_clean()
	if step == 0:
	    self.clean_forms = [ form ]
	    if form.clean_data['add_edit'] == 'add':
		self.form_list.append(forms.form_for_model(NonWgMailingList, formfield_callback=nonwg_callback))
	    elif form.clean_data['add_edit'] == 'edit':
		self.form_list.append(forms.form_for_instance(NonWgMailingList.objects.get(pk=form.clean_data['list_id']), formfield_callback=nonwg_callback))
	    elif form.clean_data['add_edit'] == 'delete':
		list = NonWgMailingList.objects.get(pk=form.clean_data['list_id_delete'])
		self.form_list.append(gen_approval([ad.person_id for ad in list.area.areadirectors_set.all()], DeletionPickApprover))
		self.form_list.append(Preview)
	else:
	    self.clean_forms.append(form)
	if step == 1:
	    form0 = self.clean_forms[0]
	    add_edit = form0.clean_data['add_edit']
	    if add_edit == 'add' or add_edit == 'edit':
		self.form_list.append(gen_approval([ad.person_id for ad in Area.objects.get(area_acronym=form.clean_data['area']).areadirectors_set.all()], PickApprover))
		self.form_list.append(Preview)
        super(NonWgWizard, self).process_step(request, form, step)
    def done(self, request, form_list):
	add_edit = self.clean_forms[0].clean_data['add_edit']
	list = None
	old = None
	if add_edit == 'add' or add_edit == 'edit':
	    template = 'mailinglists/nwg_addedit_email.txt'
	    approver = self.clean_forms[2].clean_data['approver']
	    list = NonWgMailingList(**self.clean_forms[1].clean_data)
	    list.__dict__.update(self.clean_forms[2].clean_data)
	    list.id = None	# create a new row no matter what
	    list.status = 0
	    if add_edit == 'edit':
		old = NonWgMailingList.objects.get(pk=self.clean_forms[0].clean_data['list_id'])
	else:
	    template = 'mailinglists/nwg_delete_email.txt'
	    approver = self.clean_forms[1].clean_data['approver']
	    list = NonWgMailingList.objects.get(pk=self.clean_forms[0].clean_data['list_id_delete'])
	    list.__dict__.update(self.clean_forms[1].clean_data)
	    list.status = 1
	list.save()
	approver_email = PersonOrOrgInfo.objects.get(pk=approver).email()
	send_mail_subj(request, [ approver_email ], None, 'mailinglists/nwg_wizard_subject.txt', 'mailinglists/nwg_wizard_done_email.txt', {'add_edit': add_edit, 'old': old, 'list': list, 'forms': self.clean_forms})
        return render_to_response( 'mailinglists/nwg_wizard_done.html', {'forms': self.clean_forms}, context_instance=RequestContext(request) )

def non_wg_wizard(request):
    wiz = NonWgWizard([ NonWgStep1 ])
    return wiz(request)

list_fields = {
    'mailing_list_id': None,
    'request_date': None,
    'auth_person': None,
    'approved': None,
    'approved_date': None,
    'reason_to_delete': None,
}

list_widgets = {
}

list_attrs = {
}

list_callback = form_decorator(fields=list_fields, widgets=list_widgets, attrs=list_attrs)

class ListReqWizard(wizard.Wizard):
    def get_template(self):
	templates = []
	#if self.step > 0:
	#    action = {'add': 'addedit', 'edit': 'addedit', 'delete': 'delete'}[self.clean_forms[0].clean_data['add_edit']]
	#    templates.append("mailinglists/nwg_wizard_%s_step%d.html" % (action, self.step))
	#    templates.append("mailinglists/nwg_wizard_%s.html" % (action))
	c = self.form_list[self.step].__name__
	templates.append("mailinglists/list_wizard_%s.html" % (c))
	templates.append("mailinglists/list_wizard_step%d.html" % (self.step))
	templates.append("mailinglists/list_wizard.html")
	return templates
    # want to implement parse_params to get domain for list
    def process_step(self, request, form, step):
	form.full_clean()
	if step == 0:
	    self.clean_forms = [ form ]
	else:
	    self.clean_forms.append(form)
	if step == 0:
	    if form.clean_data['mail_type'].endswith('non') and form.clean_data['domain_name'] != 'ietf.org':
		self.form_list.append(ListReqAuthorized)
	    if form.clean_data['mail_type'].startswith('close'):
		self.form_list.append(ListReqClose)
	    else:
		self.form_list.append(forms.form_for_model(MailingList))
		#XXX not quite
        super(ListReqWizard, self).process_step(request, form, step)

def list_req_wizard(request):
    wiz = ListReqWizard([ ListReqStep1 ])
    return wiz(request)
