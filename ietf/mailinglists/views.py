from forms import NonWgStep1, ListReqStep1, PickApprover, DeletionPickApprover, UrlMultiWidget
from models import NonWgMailingList
from ietf.idtracker.models import Areas
from django import newforms as forms
from django.shortcuts import render_to_response
from ietf.contrib import wizard, form_decorator

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
    'area': Areas.objects.filter(status=1)
}

nonwg_callback = form_decorator(fields=nonwg_fields, widgets=nonwg_widgets, attrs=nonwg_attrs, querysets=nonwg_querysets)

def gen_approval(approvers, parent):
    class BoundApproval(parent):
	_approvers = approvers
	def __init__(self, *args, **kwargs):
	    super(BoundApproval, self).__init__(self._approvers, *args, **kwargs)
    return BoundApproval

class NonWgWizard(wizard.Wizard):
    form0 = None
    def get_template(self):
	templates = []
	if self.form0:
	    action = {'add': 'addedit', 'edit': 'addedit', 'delete': 'delete'}[self.form0.clean_data['add_edit']]
	    templates.append("mailinglists/nwg_wizard_%s_step%d.html" % (action, self.step))
	    templates.append("mailinglists/nwg_wizard_%s.html" % (action))
	templates.append("mailinglists/nwg_wizard_step%d.html" % (self.step))
	templates.append("mailinglists/nwg_wizard.html")
	return templates
    def failed_hash(self, step):
	raise NotImplementedError("step %d hash failed" % step)
    def process_step(self, request, form, step):
	form.full_clean()
	if step == 0:
	    self.form0 = form
	    if form.clean_data['add_edit'] == 'add':
		self.form_list.append(forms.form_for_model(NonWgMailingList, formfield_callback=nonwg_callback))
	    elif form.clean_data['add_edit'] == 'edit':
		self.form_list.append(forms.form_for_instance(NonWgMailingList.objects.get(pk=form.clean_data['list_id']), formfield_callback=nonwg_callback))
	    elif form.clean_data['add_edit'] == 'delete':
		list = NonWgMailingList.objects.get(pk=form.clean_data['list_id_delete'])
		self.form_list.append(gen_approval([ad.person_id for ad in list.area.areadirectors_set.all()], DeletionPickApprover))
	if step == 1:
	    form0 = self.get_form(0, request.POST)
	    form0.full_clean()
	    self.form0 = form0
	    add_edit = form0.clean_data['add_edit']
	    if add_edit == 'add' or add_edit == 'edit':
		self.form_list.append(gen_approval([ad.person_id for ad in Areas.objects.get(area_acronym=form.clean_data['area']).areadirectors_set.all()], PickApprover))
        super(NonWgWizard, self).process_step(request, form, step)

def non_wg_wizard(request):
    wiz = NonWgWizard([ NonWgStep1 ])
    return wiz(request)

class ListReqWizard(wizard.Wizard):
    def get_template(self):
	return "mailinglists/nwg_wizard.html"
    # want to implement parse_params to get domain for list
    def process_step(self, request, form, step):
	form.full_clean()
        super(ListReqWizard, self).process_step(request, form, step)

def list_req_wizard(request):
    wiz = ListReqWizard([ ListReqStep1 ])
    return wiz(request)

def non_wg_submit(request):
    form = NonWgStep1()
    return render_to_response('mailinglists/step1.html', { 'form': form })
