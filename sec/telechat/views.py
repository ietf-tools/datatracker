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
from ietf.name.models import BallotPositionName
from ietf.person.models import Person
from ietf.idrfc.lastcall import request_last_call
from ietf.idrfc.mails import email_owner, email_state_changed
from ietf.idrfc.utils import log_state_changed, add_document_comment
from ietf.idrfc.views_doc import get_ballot
#from ietf.idtracker.models import InternetDraft
from ietf.iesg.models import TelechatDate, TelechatAgendaItem, WGAction
from ietf.iesg.views import _agenda_data

from forms import *
from models import *

import datetime

# -------------------------------------------------
# Helper Functions
# -------------------------------------------------
def get_telechat_dates():
    '''
    This function returns a list of telechat dates ( as date objects ) in desecending order
    '''
    # TODO this may change with Ole date changes
    dates = TelechatDocEvent.objects.values('telechat_date').order_by('-telechat_date').annotate(Count('telechat_date'))
    return [ d['telechat_date'] for d in dates if d['telechat_date'] ]

def get_next_telechat_date():
    '''
    This function returns the date of the next telechat
    '''
    return TelechatDate.objects.filter(date__gte=datetime.date.today()).order_by('-date')[0].date
    
def get_last_telechat_date():
    '''
    This function returns the date of the last telechat
    Tried TelechatDocEvent.objects.latest but that will return today's telechat
    '''
    return TelechatDocEvent.objects.filter(telechat_date__lt=datetime.date.today()).order_by('-telechat_date')[0].telechat_date
    #return '2011-11-01'
    
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
    #assert False, (date, name)
    #if name:
    #   doc = get_object_or_404(Document, docalias__name=name)
    #else:
    #    pass
    doc = Document.objects.get(docalias__name=name)
        
    started_process = doc.latest_event(type="started_iesg_process")
    login = request.user.get_profile()

    # is it necessary to check iesg_state?
    #if not doc.get_state(state_type='draft-iesg') or not started_process:
    #    raise Http404()
    
    # setup ballot
    #assert False, name
    
    ballot, x = get_ballot(name)
    # sort on AD last name
    positions = sorted(ballot.position_list(), key=lambda a: a['ad_name'].split()[-1])
    
    # setup form initials
    initial_ballot = []
    open_positions = 0
    for item in positions:
        initial_ballot.append({'name':item['ad_name'],'id':item['ad_username'],'position':BALLOT_NAMES[item['position']]})
        if item['position'] == 'No Record':
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
                    if form.initial['position'] == 'norecord':
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
    This view takes two arguments: 
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
    elif nav == 'previous' and index != 0:
        target = names[index - 1]
        
    url = reverse('telechat_doc_detail', kwargs={'date':date,'name':target})
    return HttpResponseRedirect(url)
        
def group(request, id):
    '''
    This view takes one argument id and displays group information for section 4, WG Actions
    '''
    group = id
    agenda = _agenda_data(request, date=None)
    
    return render_to_response('telechat/group.html', {
        'group': group,
        'agenda': agenda},
        RequestContext(request, {}),
    )

def main(request):
    '''
    The is the main view where the user selects an old telechat or creates a new one.
    
    NOTES ON EXTERNAL HELPER FUNCTIONS:
    _agenda_data():     returns dictionary of agenda sections
    get_ballot(name):   returns a BallotWrapper and RfcWrapper or IdWrapper
    '''
    #agenda = _agenda_data(request, date=None)
    if request.method == 'POST':
            date=request.POST['date']
            url = reverse('telechat_doc', kwargs={'date':date})
            return HttpResponseRedirect(url)
    
    dates = get_telechat_dates()
    choices = [ (d.strftime('%Y-%m-%d'),
                 d.strftime('%Y-%m-%d')) for d in dates ]
    form = DateSelectForm(choices=choices)
    
    # TODO rewrite this for new impl
    #existing = [ x.telechat_date.strftime('%Y-%m-%d') for x in Telechat.objects.all() ]
    #existing = get_telechat_dates()
    #rec = TelechatDate.objects.all()[0]
    #new_choices = [ (r,r) for r in (rec.date1,rec.date2,rec.date3,rec.date4) if r not in existing]
    next = get_next_telechat_date()
    new_choices = [ (next.strftime('%Y-%m-%d'),next.strftime('%Y-%m-%d')) ]
    new_form = DateSelectForm(choices=new_choices)

    return render_to_response('telechat/main.html', {
        'form': form,
        'new_form': new_form},
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
    # TODO do we need AND LT next Telechat for this query?
    events = DocEvent.objects.filter(type='iesg_approved',time__gt=get_last_telechat_date())
    docs = [ e.doc for e in events ]
    # TODO can pass all docs and do sorting in template in django 1.2
    pa_docs = [ d for d in docs if d.intended_std_level.slug not in ('inf','exp','hist') ]
    da_docs = [ d for d in docs if d.intended_std_level.slug in ('inf','exp','hist') ]

    agenda = _agenda_data(request, date=date)
    
    return render_to_response('telechat/minutes.html', {
        'agenda': agenda,
        'date': date,
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
    
    return render_to_response('telechat/roll_call.html', {
        'agenda': agenda,
        'date': date},
        RequestContext(request, {}),
    )
    