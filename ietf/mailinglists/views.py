# Copyright The IETF Trust 2007, All Rights Reserved

from forms import NonWgStep1, ListReqStep1, PickApprover, DeletionPickApprover, UrlMultiWidget, Preview, ListReqAuthorized, ListReqClose, MultiEmailField, AdminRequestor, ApprovalComment, ListApprover
from models import NonWgMailingList, MailingList, Domain
from ietf.idtracker.models import Area, PersonOrOrgInfo, AreaDirector, WGChair
from django import newforms as forms
from django.shortcuts import get_object_or_404, render_to_response
from django.template import RequestContext
from django.db.models import Q
from django.contrib.sites.models import Site
from ietf.contrib import wizard, form_decorator
from ietf.utils.mail import send_mail_subj
from datetime import datetime

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
    #'admin': MultiEmailField(label='List Administrator(s)', widget=forms.Textarea(attrs={'rows': 3, 'cols': 50})),
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
		self.form_list.append(forms.form_for_instance(NonWgMailingList.objects.get(pk=form.clean_data['list_id']), formfield_callback=nonwg_callback))
	    elif form.clean_data['add_edit'] == 'delete':
		list = NonWgMailingList.objects.get(pk=form.clean_data['list_id_delete'])
		self.form_list.append(gen_approval([ad.person_id for ad in list.area.areadirector_set.all()], DeletionPickApprover))
		self.form_list.append(Preview)
	else:
	    self.clean_forms.append(form)
	if step == 1:
	    form0 = self.clean_forms[0]
	    add_edit = form0.clean_data['add_edit']
	    if add_edit == 'add' or add_edit == 'edit':
		self.form_list.append(gen_approval([ad.person_id for ad in Area.objects.get(area_acronym=form.clean_data['area']).areadirector_set.all()], PickApprover))
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

list_fields = {
    'mailing_list_id': None,
    'request_date': None,
    'auth_person': None,
    'approved': None,
    'approved_date': None,
    'reason_to_delete': None,
    'add_comment': None,
    'mail_type': None,
    'mail_cat': None,
    'admins': MultiEmailField(label='List Administrator(s)', widget=AdminRequestor(attrs={'cols': 41, 'rows': 4})),
    'initial_members': MultiEmailField(label='Initial list member(s)', widget=forms.Textarea(attrs={'cols': 41, 'rows': 4}), required=False),
}

list_labels = {
    'post_who': 'Who is allowed to post to this list?',
}

# would like something to display @domain after the email list name?
list_widgets = {
    'subscription': forms.Select(choices=MailingList.SUBSCRIPTION_CHOICES),
    'post_who': forms.Select(choices=(('1', 'List members only'), ('0', 'Open'))),
    'post_admin': forms.Select(choices=(('0', 'No'), ('1', 'Yes'))),
    'archive_private': forms.Select(choices=(('0', 'No'), ('1', 'Yes'))),
    'domain_name': forms.HiddenInput(),
}

list_attrs = {
    'requestor': { 'size': 55 },
    'requestor_email': { 'size': 55 },
    'mlist_name': { 'size': 10 },
    'short_desc': { 'size': 55 },
    'long_desc': { 'cols': 41, 'rows': 4, 'wrap': 'virtual' },
    'admins': { 'cols': 41, 'rows': 4 },
    'initial_members': { 'cols': 41, 'rows': 4 },
    'welcome_message': { 'cols': 41, 'rows': 4 },
    'welcome_new': { 'cols': 41, 'rows': 4 },
    'archive_remote': { 'cols': 41, 'rows': 4 },
}

list_callback = form_decorator(fields=list_fields, widgets=list_widgets, attrs=list_attrs)

def gen_list_approval(approvers, requestor, parent):
    class ListApproval(parent):
	_approvers = approvers
	_requestor = requestor
	def __init__(self, *args, **kwargs):
	    super(ListApproval, self).__init__(self._approvers, self._requestor, *args, **kwargs)
    return ListApproval

class ListReqWizard(wizard.Wizard):
    clean_forms = []
    main_step = 1
    requestor_is_approver = False
    mlist_known = True
    def get_template(self):
	'''Start with form class, then step number, then the base form.'''
	templates = []
	c = self.form_list[self.step].__name__
	templates.append("mailinglists/list_wizard_%s.html" % (c))
	templates.append("mailinglists/list_wizard_step%d.html" % (self.step))
	templates.append("mailinglists/list_wizard.html")
	return templates
    def render_template(self, *args, **kwargs):
	self.extra_context['mlist_known'] = self.mlist_known
	if self.step > 0:
	    self.extra_context['form0'] = self.clean_forms[0]
	    if self.clean_forms[0]['mail_type'].data.startswith('close'):
	        self.extra_context['req'] = 'delete'
	    else:
		self.extra_context['req'] = 'add'
	if self.step > self.main_step:
	    self.extra_context['main_form'] = self.clean_forms[self.main_step]
	    self.extra_context['requestor_is_approver'] = self.requestor_is_approver
	if self.step == self.main_step + 1:
	    self.extra_context['list'] = self.getlist()
	return super(ListReqWizard, self).render_template(*args, **kwargs)
    def parse_params(self, request, *args, **kwargs):
	super(ListReqWizard, self).parse_params(request, *args, **kwargs)
	if self.step == 0:
	    # allow javascript "redirects" to set initial values
	    self.initial[0] = request.GET
    def process_step(self, request, form, step):
	form.full_clean()
	if step == 0:
	    self.clean_forms = [ form ]
	else:
	    self.clean_forms.append(form)
	form0 = self.clean_forms[0]
	needs_auth = form0.clean_data['mail_type'].endswith('non') and form0.clean_data['domain_name'] != 'ietf.org'
	if step == 0:
	    self.main_step = 1
	    if needs_auth:
		self.form_list.append(ListReqAuthorized)
		self.main_step = 2
	    if form.clean_data['mail_type'].startswith('close'):
		self.form_list.append(ListReqClose)
		if form.clean_data['mail_type'] == 'closewg':
		    self.initial[self.main_step] = {'mlist_name': form.clean_data['group']}
		else:
		    self.initial[self.main_step] = {'mlist_name': form.clean_data['list_to_close']}
	    else:
		self.form_list.append(forms.form_for_model(MailingList, formfield_callback=list_callback))
		if form.clean_data['mail_type'].endswith('wg'):
		    self.initial[self.main_step] = {'mlist_name': form.clean_data['group']}
		else:
		    self.initial[self.main_step] = {}
		    self.mlist_known = False
	    if form.clean_data['mail_type'].endswith('wg'):
		self.initial[self.main_step].update({'domain_name': 'ietf.org'})
	    else:
		self.initial[self.main_step].update({'domain_name': form.clean_data['domain_name']})
	if step == self.main_step:
	    approvers = mlist_approvers(form0.clean_data['mail_type'], form.clean_data['domain_name'], form0.clean_data['group'])
	    requestor_email = form.clean_data['requestor_email']
	    requestor_person = None
	    for a in approvers:
		if requestor_email == a.person.email()[1]:
		    requestor_person = a
		    self.requestor_is_approver = True
	    self.form_list.append(gen_list_approval(approvers, requestor_person, ListApprover))
        super(ListReqWizard, self).process_step(request, form, step)
    def getlist(self):
	list = MailingList(**self.clean_forms[self.main_step].clean_data)
	list.mailing_list_id = None		# make sure that we create a new row
	list.mail_type = MailingList.MAILTYPE_MAP[self.clean_forms[0].clean_data['mail_type']]
	list.approved = 0
	return list
    def done(self, request, form_list):
	list = self.getlist()
	list.auth_person_id = int(self.clean_forms[self.main_step + 1].clean_data['approver'])
	list.save()
	approver_email = list.auth_person.email()
	site = Site.objects.get_current()
	if list.mail_type == 5 or list.mail_type == 6:
	    req = 'delete'
	else:
	    req = 'add'
	send_mail_subj(request, [ approver_email ], None, 'mailinglists/list_wizard_subject.txt', 'mailinglists/list_wizard_done_email.txt', {'list': list, 'forms': self.clean_forms, 'requestor_is_approver': self.requestor_is_approver, 'site': site, 'req': req})
        return render_to_response('mailinglists/list_wizard_done.html', {'list': list, 'forms': self.clean_forms, 'requestor_is_approver': self.requestor_is_approver, 'req': req}, context_instance=RequestContext(request) )

def mlist_approvers(mail_type, domain_name, group):
    approvers = []
    if domain_name == 'ietf.org':
	approvers += AreaDirector.objects.filter(area__status=Area.ACTIVE)
	if mail_type == 'movewg':
	    approvers += WGChair.objects.filter(group_acronym=group)
    if mail_type.endswith('non'):
	domain = Domain.objects.get(domain=domain_name)
	approvers += domain.approvers.all()
    return approvers

def list_req_wizard(request):
    wiz = ListReqWizard([ ListReqStep1 ])
    return wiz(request)

def list_req_help(request, field):
    return render_to_response('mailinglists/list_help_%s.html' % field, {},
	context_instance=RequestContext(request) )

def list_approve(request, object_id):
    list = get_object_or_404(MailingList, mailing_list_id=object_id)
    if list.mail_type == 5 or list.mail_type == 6:
	req = 'delete'
    else:
        req = 'add'
    action = 'toapprove'
    email_to = None
    if request.method == 'POST':
	if request.POST.has_key('approved'):
	    list.approved=1
	    list.approved_date = datetime.now()
	    list.add_comment = request.POST['add_comment']
	    list.save()
	    if list.mail_type == 6:	# deletion of non-wg list
		for nonwg in NonWgMailingList.objects.filter(Q(list_url__iendswith=list.mlist_name) | Q(list_url__iendswith='%s@%s' % (list.mlist_name, list.domain_name))):
		    nonwg.status = -1
		    nonwg.save()
	    email_to = 'ietf-action@ietf.org'
	    email_cc = [(list.requestor, list.requestor_email)]
	    action = 'approved'
	elif request.POST.has_key('disapprove'):
	    list.approved = -1
	    list.approved_date = datetime.now()
	    list.add_comment = request.POST['add_comment']
	    list.save()
	    email_to = [(list.requestor, list.requestor_email)]
	    email_cc = None
	    action = 'denied'
	if email_to is not None:
	    send_mail_subj(request, email_to, ('Mailing List Request Tool', 'ietf-secretariat-reply@ietf.org'), 'mailinglists/list_subject.txt', 'mailinglists/list_email.txt', {'list': list, 'action': action, 'req': req}, email_cc)
	# fall through
    form = ApprovalComment()
    return render_to_response('mailinglists/list_%s.html' % action, {'list': list, 'form': form, 'req': req},
	context_instance=RequestContext(request) )
