from django.contrib import messages
from django.core.urlresolvers import reverse
from django.db.models import Count
from django.forms.models import inlineformset_factory, modelformset_factory
from django.forms.formsets import formset_factory
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext

from ietf.doc.models import DocEvent, Document, BallotPositionDocEvent, TelechatDocEvent, WriteupDocEvent, save_document_in_history
from ietf.doc.proxy import InternetDraft
from ietf.doc.utils import active_ballot_positions
from ietf.group.models import Group
from ietf.name.models import BallotPositionName
from ietf.person.models import Person
from ietf.idrfc.lastcall import request_last_call
from ietf.idrfc.mails import email_owner, email_state_changed
from ietf.idrfc.utils import log_state_changed, add_document_comment
#from ietf.idrfc.views_doc import get_ballot
from ietf.iesg.models import TelechatDate, TelechatAgendaItem, WGAction
from ietf.iesg.views import _agenda_data

from forms import *
from models import *

import datetime
'''
EXPECTED CHANGES:
- group pages will be just another doc, charter doc
- charter docs to discuss will be passed in the 'docs' section of agenda
- expand get_section_header to include section 4
- get rid of get_group_header, and group() view

'''
# -------------------------------------------------
# Notes on external helpers
# -------------------------------------------------
'''
active_ballot_positions: takes one argument, doc.  returns a dictionary with a key for each ad Person
object

_agenda_data: takes a request object and a date string
'''

# -------------------------------------------------
# Helper Functions
# -------------------------------------------------
def get_next_telechat_date():
    '''
    This function returns the date of the next telechat
    '''
    return TelechatDate.objects.filter(date__gte=datetime.date.today()).order_by('date')[0].date
    
def get_last_telechat_date():
    '''
    This function returns the date of the last telechat
    Tried TelechatDocEvent.objects.latest but that will return today's telechat
    '''
    return TelechatDate.objects.filter(date__lt=datetime.date.today()).order_by('-date')[0].date
    #return '2011-11-01' # uncomment for testing
    
def get_section_header(file,agenda):
    '''
    This function takes a filename and an agenda dictionary and returns the 
    agenda section header as a string for use in the doc template
    '''
    h1 = {'2':'Protocol Actions','3':'Document Actions'}
    h2a = {'1':'WG Submissions','2':'Individual Submissions'}
    h2b = {'1':'WG Submissions','2':'Individual Submissions via AD','3':'IRTF and Independent Submission Stream Documents'}
    h3 = {'1':'New Item','2':'Returning Item','3':'For Action'}
    
    doc = InternetDraft.objects.get(filename=file)
    test = {'obj':doc}
    for k,v in agenda['docs'].iteritems():
        if test in v:
            section = k
            count = '%s of %s' % (v.index(test) + 1, len(v))
            break
    
    header = [ '%s %s\n' % (section[1], h1[section[1]]) ]
    header.append('%s.%s %s\n' % (section[1], section[2], h2a[section[2]] if section[1] == '2' else h2b[section[2]]))
    header.append('%s.%s.%s %s\n' % (section[1], section[2], section[3], h3[section[3]]))
    header.append(count)
    
    return header
    
def get_group_header(group,agenda):
    '''
    This function takes a group name and an agenda dictionary and returns the 
    agenda section header as a string for use in the doc template
    '''
    h1 = {'4':'Working Group Actions'}
    h2 = {'1':'WG Creation','2':'WG Rechartering'}
    h3a = {'1':'Proposed for IETF Review','2':'Proposed for IETF Approval'}
    h3b = {'1':'Under Evalutaion for IETF Review','2':'Proposed for IETF Approval'}
    
    for k,v in agenda['wgs'].iteritems():
        c = 0
        for g in v:
            c += 1
            if g['obj'].group_acronym_id == group.id:            
                section = k
                count = '%s of %s' % (c, len(v))
                break
    
    header = [ '%s %s\n' % (section[1], h1[section[1]]) ]
    header.append('%s.%s %s\n' % (section[1], section[2], h2[section[2]]))
    header.append('%s.%s.%s %s\n' % (section[1], section[2], section[3], h3a[section[3]] if section[2] == '1' else h3b[section[3]]))
    header.append(count)
    
    return header

def get_group_list(agenda):
    '''
    This function takes an agenda object and returns a list of group names, in order,
    for those groups that show in section 4 of the agenda
    '''
    entries = []
    for key in sorted(agenda['wgs']):
        entries.extend(agenda['wgs'][key])
    
    group_ids = [x['obj'].group_acronym_id for x in entries]
    groups = [ Group.objects.get(id=id) for id in group_ids ]
    return groups
    
def get_first_doc(agenda):
    '''
    This function takes an agenda dictionary and returns the first document in the agenda
    TODO should handle group
    '''
    for k,v in sorted(agenda['docs'].iteritems()):
        if v:
            return v[0]['obj']
    
    return None
    
# -------------------------------------------------
# View Functions
# -------------------------------------------------
def bash(request, date):
    
    agenda = _agenda_data(request, date=date)
    
    return render_to_response('telechat/bash.html', {
        'agenda': agenda,
        'date': date},
        RequestContext(request, {}),
    )
    
def doc(request, date):
    '''
    This view redirects to doc_detail using the first document in the agenda or
    displays the message "No Documents"
    '''
    
    agenda = _agenda_data(request, date=date)
    doc = get_first_doc(agenda)
    if doc:
        url = reverse('telechat_doc_detail', kwargs={'date':date,'name':doc.name})
        return HttpResponseRedirect(url)
    else:
        return render_to_response('telechat/doc.html', {
        'agenda': agenda,
        'date': date,
        'document': None},
        RequestContext(request, {}),
    )
    
def doc_detail(request, date, name):
    '''
    This view displays the ballot information for the document, and lets the user make
    changes to ballot positions and document state.
    '''
    #doc = Document.objects.get(docalias__name=name)
    doc = get_object_or_404(Document, docalias__name=name)
        
    started_process = doc.latest_event(type="started_iesg_process")
    login = request.user.get_profile()

    # is it necessary to check iesg_state?
    #if not doc.get_state(state_type='draft-iesg') or not started_process:
    #    raise Http404()
    
    ballots = active_ballot_positions(doc) # returns dict of ad:ballotpositiondocevent
    
    # setup form initials
    initial_ballot = []
    open_positions = 0
    for key in sorted(ballots, key = lambda a: a.name_parts()[3]):
        initial_ballot.append({'name':key.name,'id':key.id,'position':ballots[key].pos.slug if ballots[key] else None})
        if ballots[key] and ballots[key].pos.slug == 'norecord':
            open_positions += 1
        elif not ballots[key]:
            open_positions += 1
    
    tags = doc.tags.filter(slug__in=TELECHAT_TAGS)
    tag = tags[0].pk if tags else None
    
    initial_state = {'state':doc.get_state('draft-iesg').pk,
                     'substate':tag}
    
    BallotFormset = formset_factory(BallotForm, extra=0)
    agenda = _agenda_data(request, date=date)
    header = get_section_header(name,agenda) if name else ''
    
    if request.method == 'POST':
        button_text = request.POST.get('submit', '')
        
        # logic from idrfc/views_ballot.py EditPositionRedesign
        if button_text == 'update_ballot':
            formset = BallotFormset(request.POST, initial=initial_ballot)
            state_form = DocumentStateForm(initial=initial_state)
            for form in formset.forms:
                # has_changed doesn't work?
                if form.is_valid() and form.changed_data:
                    clean = form.cleaned_data
                    ad = Person.objects.get(id=clean['id'])
                    pos = BallotPositionDocEvent(doc=doc,by=login)
                    pos.type = "changed_ballot_position"
                    pos.ad = ad
                    pos.pos = clean['position']
                    if form.initial['position'] == None:
                        pos.desc = '[Ballot Position Update] New position, %s, has been recorded for %s by %s' % (pos.pos.name, ad.name, login.name)
                    else:
                        pos.desc = '[Ballot Position Update] Position for %s has been changed to %s by %s' % (ad.name, pos.pos.name, login.name)
                    pos.save()
                    
                    messages.success(request,'Ballot position changed.')
                    url = reverse('telechat_doc_detail', kwargs={'date':date,'name':name})
                    return HttpResponseRedirect(url)
        
        # logic from idrfc/views_edit.py change_stateREDESIGN
        elif button_text == 'update_state':
            state_form = ChangeStateForm(request.POST, initial=initial_state)
            formset = BallotFormset(initial=initial_ballot)
            if state_form.is_valid():
                state = state_form.cleaned_data['state']
                tag = state_form.cleaned_data['substate']
                comment = state_form.cleaned_data['comment'].strip()
                prev = doc.get_state("draft-iesg")

                # tag handling is a bit awkward since the UI still works
                # as if IESG tags are a substate
                prev_tag = doc.tags.filter(slug__in=(TELECHAT_TAGS))
                prev_tag = prev_tag[0] if prev_tag else None
    
                if state != prev or tag != prev_tag:                
                    save_document_in_history(doc)
                    doc.set_state(state)
                    if prev_tag:
                        doc.tags.remove(prev_tag)
                    if tag:
                        doc.tags.add(tag)
    
                    e = log_state_changed(request, doc, login, prev, prev_tag)
                    
                    if comment:
                        c = DocEvent(type="added_comment")
                        c.doc = doc
                        c.by = login
                        c.desc = comment
                        c.save()
    
                        e.desc += "<br>" + comment
                    
                    doc.time = e.time
                    doc.save()
    
                    email_state_changed(request, doc, e.desc)
                    email_owner(request, doc, doc.ad, login, e.desc)
    
                    if state.slug == "lc-req":
                        request_last_call(request, doc)
                
                messages.success(request,'Document state updated')
                url = reverse('telechat_doc_detail', kwargs={'date':date,'name':name})
                return HttpResponseRedirect(url)        
    else:
        formset = BallotFormset(initial=initial_ballot)
        state_form = ChangeStateForm(initial=initial_state)
    
    return render_to_response('telechat/doc.html', {
        'date': date,
        'document': doc,
        'agenda': agenda,
        'formset': formset,
        'header': header,
        'open_positions': open_positions,
        'state_form': state_form,
        'writeup': doc.latest_event(WriteupDocEvent).text},
        RequestContext(request, {}),
    )
    
def doc_navigate(request, date, name, nav):
    '''
    This view takes three arguments: 
    date - the date of the Telechat
    name - the name of the current document being displayed
    nav  - [next|previous] which direction the user wants to navigate in the list of docs
    The view retrieves the appropriate document and redirects to the doc view.
    '''
    agenda = _agenda_data(request, date=date)
    target = name
    
    # build ordered list of documents from the agenda
    docs = []
    for key in sorted(agenda['docs']):
        docs.extend(agenda['docs'][key])
    
    names = [x['obj'].name for x in docs]
    index = names.index(name)
    
    if nav == 'next' and index < len(names) - 1:
        target = names[index + 1]
    elif nav == 'next' and index == len(names) - 1:
        # go to first group doc if there is one
        group_list = get_group_list(agenda)
        if group_list:
            url = reverse('telechat_group', kwargs={'date':date,'acronym':group_list[0].acronym})
            return HttpResponseRedirect(url)
    elif nav == 'previous' and index != 0:
        target = names[index - 1]
        
    
    url = reverse('telechat_doc_detail', kwargs={'date':date,'name':target})
    return HttpResponseRedirect(url)
        
def group(request, date, acronym):
    '''
    This view takes a date and a Group acronym and displays group information for section 4, WG Actions
    '''
    group = get_object_or_404(Group, acronym=acronym)
    agenda = _agenda_data(request, date=date)
    header = get_group_header(group,agenda)
    
    # TODO set question
    if header[1].startswith('4.1'):
        question = ''
    else:
        question = 'Does anyone have an objection to the rechartering of this group?'
    
    return render_to_response('telechat/group.html', {
        'date':date,
        'group': group,
        'agenda': agenda,
        'header': header},
        RequestContext(request, {}),
    )
    
def group_navigate(request, date, acronym, nav):
    pass

def main(request):
    '''
    The is the main view where the user selects an old telechat or creates a new one.
    
    NOTES ON EXTERNAL HELPER FUNCTIONS:
    _agenda_data():     returns dictionary of agenda sections
    get_ballot(name):   returns a BallotWrapper and RfcWrapper or IdWrapper
    '''
    if request.method == 'POST':
            date=request.POST['date']
            url = reverse('telechat_doc', kwargs={'date':date})
            return HttpResponseRedirect(url)
    
    choices = [ (d.date.strftime('%Y-%m-%d'),
                 d.date.strftime('%Y-%m-%d')) for d in TelechatDate.objects.all() ]
    next_telechat = get_next_telechat_date().strftime('%Y-%m-%d')
    form = DateSelectForm(choices=choices,initial={'date':next_telechat})

    return render_to_response('telechat/main.html', {
        'form': form},
        RequestContext(request, {}),
    )
def management(request, date):
    '''
    This view displays management issues and lets the user update the status
    '''
    
    agenda = _agenda_data(request, date=date)
    issues = TelechatAgendaItem.objects.filter(type=3).order_by('id')
    #IssueFormset = modelformset_factory(TelechatAgendaItem, form=IssueModelForm, extra=0)
    
    #formset = IssueFormset(queryset = TelechatAgendaItem.objects.filter(type=3).order_by('id'))
    
    return render_to_response('telechat/management.html', {
        'agenda': agenda,
        'date': date,
        'issues': issues},
        RequestContext(request, {}),
    )
    
def minutes(request, date):
    '''
    This view shows a list of documents that were approved since the last telechat
    '''
    last_date = get_last_telechat_date()
    events = DocEvent.objects.filter(type='iesg_approved',time__gte=last_date)
    docs = [ e.doc for e in events ]
    pa_docs = [ d for d in docs if d.intended_std_level.slug not in ('inf','exp','hist') ]
    da_docs = [ d for d in docs if d.intended_std_level.slug in ('inf','exp','hist') ]

    agenda = _agenda_data(request, date=date)
    
    return render_to_response('telechat/minutes.html', {
        'agenda': agenda,
        'date': date,
        'last_date': last_date,
        'pa_docs': pa_docs,
        'da_docs': da_docs},
        RequestContext(request, {}),
    )
    
def new(request):
    '''
    This view creates a new telechat agenda and redirects to the default view
    '''
    if request.method == 'POST':
        date = request.POST['date']
        # create legacy telechat record
        Telechat.objects.create(telechat_date=date)
        
        # get new agenda
        # redirect
        
        # get first Document
        
        messages.success(request,'New Telechat Agenda created')
        url = reverse('telechat_doc', kwargs={'date':date,'name':name})
        return HttpResponseRedirect(url)  
        
def roll_call(request, date):
    
    agenda = _agenda_data(request, date=date)
    ads = Person.objects.filter(role__name='ad')
    
    return render_to_response('telechat/roll_call.html', {
        'agenda': agenda,
        'date': date,
        'people':ads},
        RequestContext(request, {}),
    )
    