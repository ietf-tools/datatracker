# Create your views here.
from django.http import HttpResponse,HttpResponseRedirect
from django import newforms as forms
from django.template import RequestContext, Context, loader
from django.shortcuts import get_object_or_404, render_to_response
from django.db.models import Q
from django.views.generic.list_detail import object_detail
from ietf.idtracker.models import InternetDraft, IDInternal, IDState, IDSubState

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
    InternetDraftForm = forms.models.form_for_model(InternetDraft, formfield_callback=myfields)
    idform = InternetDraftForm(request.POST)
    InternalForm = forms.models.form_for_model(IDInternal, formfield_callback=myfields)
    form = InternalForm(request.POST)
    t = loader.get_template('idtracker/idtracker_search.html')
    # if there's a post, do the search and supply results to the template
    if request.method == 'POST':
	qdict = { 'filename': 'draft__filename__contains',
		  'job_owner': 'job_owner',
		  'group': 'draft__group__acronym',
		  'cur_state': 'cur_state',
		  'cur_sub_state': 'cur_sub_state',
		  'rfc_number': 'draft__rfc_number',
		  'area_acronym': 'area_acronym',
		  'note': 'note__contains',
		}
	q_objs = [Q(**{qdict[k]: request.POST[k]})
		for k in qdict.keys()
		if request.POST[k] != '']
	matches = IDInternal.objects.all().filter(*q_objs)
#	matches = IDInternal.objects.all()
#	if request.POST['filename']:
#	    matches = matches.filter(draft__filename__contains=request.POST["filename"])
#	if request.POST['job_owner']:
#	    matches = matches.filter(job_owner=request.POST['job_owner'])
#	if request.POST['group']:
#	    matches = matches.filter(draft__group__acronym=request.POST['group_acronym'])
#	if request.POST['cur_state']:
#	    matches = matches.filter(cur_state=request.POST['cur_state'])
#	if request.POST['cur_sub_state']:
#	    matches = matches.filter(cur_sub_state=request.POST['cur_sub_state'])
#	if request.POST['rfc_number']:
#	    matches = matches.filter(draft__rfc_number=request.POST['rfc_number'])
#	if request.POST['area_acronym']:
#	    matches = matches.filter(area_acronym=request.POST['area_acronym'])
#	if request.POST['note']:
#	    matches = matches.filter(note__contains=request.POST['note'])
	matches = matches.order_by('cur_state', 'cur_sub_state_id')
    else:
	matches = None

    c = RequestContext(request, {
	'form': form,
	'idform': idform,
	'matches': matches,
    })
    return HttpResponse(t.render(c))

def edit_idinternal(request, id=None):
    #draft = InternetDraft.objects.get(pk=id)
    draft = get_object_or_404(InternetDraft.objects, pk=id)
    IDEntryForm = forms.models.form_for_instance(draft)
    # todo: POST handling for idform
    idform = IDEntryForm()
    idinternal = draft.idinternal()
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

    t = loader.get_template('idtracker/idtracker_edit.html')

    c = RequestContext(request, {
	'form': form,
	'idform': idform,
	'draft': draft,
    })
    return HttpResponse(t.render(c))

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
