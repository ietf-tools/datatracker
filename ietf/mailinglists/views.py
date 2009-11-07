# Copyright The IETF Trust 2007, All Rights Reserved

from forms import NonWgStep1, PickApprover, DeletionPickApprover, UrlMultiWidget, Preview
from models import NonWgMailingList
from ietf.idtracker.models import Area, PersonOrOrgInfo, Role, IETFWG
from django import newforms as forms
from django.shortcuts import render_to_response
from django.template import RequestContext
from ietf.contrib import wizard, form_decorator
from ietf.utils.mail import send_mail_subj

def get_approvers_from_area (area_id) :
    if not area_id :
        return [ad.person_id for ad in Role.objects.filter(role_name__in=("IETF", "IAB", ))]
    else :
        return [ad.person_id for ad in Area.objects.get(area_acronym=area_id).areadirector_set.all()]

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
    'area': forms.ModelChoiceField(Area.objects.filter(status=1), required=False, empty_label='none'),
}

nonwg_attrs = {
    's_name': {'size': 50},
    's_email': {'size': 50},
    'list_name': {'size': 80},
}

nonwg_widgets = {
    'list_url': UrlMultiWidget(choices=(('http://', 'http://'), ('https://', 'https://'), ('mailto:', 'mailto:')), attrs = {'size': 50}),
    'admin': forms.Textarea(attrs = {'rows': 3, 'cols': 50}),
    'purpose': forms.Textarea(attrs = {'rows': 4, 'cols': 70}),
    'subscribe_url': UrlMultiWidget(choices=(('n/a', 'Not Applicable'), ('http://', 'http://'), ('https://', 'https://')), attrs = {'size': 50}),
    'subscribe_other': forms.Textarea(attrs = {'rows': 3, 'cols': 50}),
}

nonwg_callback = form_decorator(fields=nonwg_fields, widgets=nonwg_widgets, attrs=nonwg_attrs)

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
        if self.step == 2:
            form0 = self.clean_forms[0]
            add_edit = form0.clean_data['add_edit']
            if add_edit == 'delete':
                self.extra_context['list_q'] = NonWgMailingList.objects.get(pk=self.clean_forms[0].clean_data['list_id_delete'])
                self.extra_context['approver'] =  formchoice(self.clean_forms[1], 'approver')
	return super(NonWgWizard, self).render_template(*args, **kwargs)
#    def failed_hash(self, request, step):
#	raise NotImplementedError("step %d hash failed" % step)
    def process_step(self, request, form, step):

	form.full_clean()

	if step == 0:
	    self.clean_forms = [ form ]
	    if form.clean_data['add_edit'] == 'add':
		self.form_list.append(forms.form_for_model(NonWgMailingList, formfield_callback=nonwg_callback))
	    elif form.clean_data['add_edit'] == 'edit':
                list = NonWgMailingList.objects.get(pk=form.clean_data['list_id'])
                f = forms.form_for_instance(list, formfield_callback=nonwg_callback)
                # form_decorator's method of copying the initial data
                # from form_for_instance() to the ModelChoiceField doesn't
                # work, so we set it explicitly here.
                f.base_fields['area'].initial = list.area_id
                self.form_list.append(f)
	    elif form.clean_data['add_edit'] == 'delete':
		list = NonWgMailingList.objects.get(pk=form.clean_data['list_id_delete'])
		self.form_list.append(gen_approval(get_approvers_from_area(list.area is None or list.area_id), DeletionPickApprover))
		self.form_list.append(Preview)
	else:
	    self.clean_forms.append(form)
	if step == 1:
	    form0 = self.clean_forms[0]
	    add_edit = form0.clean_data['add_edit']
	    if add_edit == 'add' or add_edit == 'edit':
		self.form_list.append(gen_approval(get_approvers_from_area(form.clean_data['area']), PickApprover))
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
	approver_name = PersonOrOrgInfo.objects.get(pk=approver)
	send_mail_subj(request, [ approver_email ], None, 'mailinglists/nwg_wizard_subject.txt', 'mailinglists/nwg_wizard_done_email.txt', {'add_edit': add_edit, 'old': old, 'list': list, 'forms': self.clean_forms})
        return render_to_response( 'mailinglists/nwg_wizard_done.html', {'approver': approver_name, 'add_edit': add_edit, 'old': old, 'list': list, 'forms': self.clean_forms}, context_instance=RequestContext(request) )

def non_wg_wizard(request):
    wiz = NonWgWizard([ NonWgStep1 ])
    return wiz(request)

def list_wgwebmail(request):
    wgs = IETFWG.objects.filter(email_archive__startswith='http')
    return render_to_response('mailinglists/wgwebmail_list.html', {'object_list': wgs})
