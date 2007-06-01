# Create your views here.
from django.http import HttpResponse,HttpResponseRedirect
from django import newforms as forms
from django.template import RequestContext, Context, loader
from django.shortcuts import get_object_or_404, render_to_response
from django.db.models import Q
from django.views.generic.list_detail import object_detail, object_list
from ietf.idtracker.models import InternetDraft, IDInternal, IDState, IDSubState, Rfc
from ietf.idtracker.forms import IDSearch, EmailFeedback
from ietf.utils.mail import send_mail_text

# Override default form field mappings
# group_acronym: CharField(max_length=10)
# note: CharField(max_length=100)
def myfields(f):
    if f.name == "group":
	return forms.CharField(max_length=10,
			widget=forms.TextInput(attrs={'size': 5}))
    if f.name == "note":
	return forms.CharField(max_length=100,
			widget=forms.TextInput(attrs={'size': 100}))
    return f.formfield()

def search(request):
    # for compatability with old tracker form, which has
    #  "all substates" = 6.
    args = request.REQUEST
    if args.get('sub_state_id', '') == '6':
	args['sub_state_id'] = '0'
    form = IDSearch(args)
    # if there's a post, do the search and supply results to the template
    searching = False
    # filename, rfc_number, group searches are seperate because
    # they can't be represented as simple searches in the data model.
    qdict = { 
	      'search_job_owner': 'job_owner',
	      'search_cur_state': 'cur_state',
	      'sub_state_id': 'cur_sub_state',
	      'search_area_acronym': 'area_acronym',
	    }
    q_objs = []
    for k in qdict.keys() + ['search_group_acronym', 'search_rfcnumber', 'search_filename', 'search_status_id']:
	if args.has_key(k):
	    searching = True
	    if args[k] != '' and qdict.has_key(k):
		q_objs.append(Q(**{qdict[k]: args[k]}))
    if searching:
        group = args.get('search_group_acronym', '')
	if group != '':
	    rfclist = [rfc.rfc_number for rfc in Rfc.objects.all().filter(group_acronym=group)]
	    draftlist = [draft.id_document_tag for draft in InternetDraft.objects.all().filter(group__acronym=group)]
	    q_objs.append(Q(draft__in=draftlist)&Q(rfc_flag=0)|Q(draft__in=rfclist)&Q(rfc_flag=1))
        rfc_number = args.get('search_rfcnumber', '')
	if rfc_number != '':
	    draftlist = [draft.id_document_tag for draft in InternetDraft.objects.all().filter(rfc_number=rfc_number)]
	    q_objs.append(Q(draft__in=draftlist)&Q(rfc_flag=0)|Q(draft=rfc_number)&Q(rfc_flag=1))
        filename = args.get('search_filename', '')
	if filename != '':
	    q_objs.append(Q(draft__filename__icontains=filename,rfc_flag=0))
	status = args.get('search_status_id', '')
	if status != '':
	    q_objs.append(Q(draft__status=status,rfc_flag=0))
	matches = IDInternal.objects.all().filter(*q_objs).filter(primary_flag=1)
	matches = matches.order_by('cur_state', 'cur_sub_state_id')
    else:
	matches = None

    return render_to_response('idtracker/idtracker_search.html', {
	'form': form,
	'matches': matches,
	'searching': searching,
      }, context_instance=RequestContext(request))

# proof of concept, orphaned for now
def edit_idinternal(request, id=None):
    #draft = InternetDraft.objects.get(pk=id)
    draft = get_object_or_404(InternetDraft.objects, pk=id)
    IDEntryForm = forms.models.form_for_instance(draft)
    # todo: POST handling for idform
    idform = IDEntryForm()
    idinternal = draft.idinternal
    if idinternal:
	EntryForm = forms.models.form_for_instance(idinternal)
	if request.method == 'POST':
	    form = EntryForm(request.POST)
	    if form.is_valid():
		form.save()
		return HttpResponseRedirect("/")	# really want here
	else:
	    form = EntryForm()
    else:
	form = None

    return render_to_response('idtracker/idtracker_edit.html', {
	'form': form,
	'idform': idform,
	'draft': draft,
      }, context_instance=RequestContext(request))

def state_desc(request, state, is_substate=0):
    if int(state) == 100:
	object = {
		'state': 'I-D Exists',
		'description': """
Initial (default) state for all internet drafts. Such documents are
not being tracked by the IESG as no request has been made of the
IESG to do anything with the document.
"""
		}
    elif is_substate:
	sub = get_object_or_404(IDSubState, pk=state)
	object = { 'state': sub.sub_state, 'description': sub.description }
    else:
	object = get_object_or_404(IDState, pk=state)
    return render_to_response('idtracker/state_desc.html', {'state': object},
	context_instance=RequestContext(request))

def comment(request, slug, object_id, queryset):
    draft = get_object_or_404(InternetDraft, filename=slug)
    queryset = queryset.filter(document=draft.id_document_tag)
    return object_detail(request, queryset=queryset, object_id=object_id)

def send_email(request):
    if request.method == 'POST':
	form = EmailFeedback(request.POST)
	cat = request.POST.get('category', 'bugs')
	if form.is_valid():
	    send_mail_text(request, "idtracker-%s@ietf.org" % form.clean_data['category'], (form.clean_data['name'], form.clean_data['email']), '[ID TRACKER %s] %s' % (form.clean_data['category'].upper(), form.clean_data['subject']), form.clean_data['message'])
	    return render_to_response('idtracker/email_sent.html', {},
		context_instance=RequestContext(request))
    else:
	cat = request.REQUEST.get('cat', 'bugs')
	form = EmailFeedback(initial={'category': cat})
    return render_to_response('idtracker/email_form.html', {'category': cat, 'form': form},
	context_instance=RequestContext(request))

def status(request):
    queryset = IDInternal.objects.filter(primary_flag=1).exclude(cur_state__state__in=('AD is watching', 'Dead')).order_by('cur_state', 'status_date', 'ballot_id')
    return object_list(request, template_name="idtracker/status_of_items.html", queryset=queryset, extra_context={'title': 'IESG Status of Items'})

def last_call(request):
    queryset = IDInternal.objects.filter(primary_flag=1).filter(cur_state__state__in=('In Last Call', 'Waiting for Writeup', 'Waiting for AD Go-Ahead')).order_by('cur_state', 'status_date', 'ballot_id')
    return object_list(request, template_name="idtracker/status_of_items.html", queryset=queryset, extra_context={'title': 'Documents in Last Call'})

# Wrappers around object_detail to give permalink a handle.
# The named-URLs feature in django 0.97 will eliminate the
# need for these.
def view_id(*args, **kwargs):
    return object_detail(*args, **kwargs)

def view_comment(*args, **kwargs):
    return object_detail(*args, **kwargs)

def view_ballot(*args, **kwargs):
    return object_detail(*args, **kwargs)
