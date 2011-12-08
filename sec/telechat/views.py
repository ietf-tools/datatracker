from django.core.urlresolvers import reverse
from django.forms.formsets import formset_factory
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext

from session_messages import create_message
from redesign.doc.models import Document, BallotPositionDocEvent, WriteupDocEvent
from redesign.name.models import BallotPositionName
from redesign.person.models import Person
from ietf.idrfc.views_doc import get_ballot
from ietf.idtracker.models import InternetDraft
from ietf.iesg.models import TelechatDates, TelechatAgendaItem, WGAction
from ietf.iesg.views import _agenda_data

from forms import *

def main(request):
    '''
    The Main view.  Populates agenda dictionary for use in displaying left-pane menu.
    
    NOTES ON EXTERNAL HELPER FUNCTIONS:
    _agenda_data():     returns dictionary of agenda sections
    get_ballot(name):   returns a BallotWrapper and RfcWrapper or IdWrapper
    '''
    agenda = _agenda_data(request, date=None)
    
    return render_to_response('telechat/main.html', {
        'agenda': agenda},
        RequestContext(request, {}),
    )

def doc(request, name):
    '''
    This view displays the ballot information for the document, and lets the user make
    changes to ballot positions.
    '''

    doc = get_object_or_404(Document, docalias__name=name)
    started_process = doc.latest_event(type="started_iesg_process")

    # is it necessary to check iesg_state?
    if not doc.get_state(state_type='draft-iesg') or not started_process:
        raise Http404()
    login = request.user.get_profile()
    
    # setup ballot
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
    try:
        tag = doc.tags.get(name__in=TELECHAT_TAGS).slug
    except DocTagName.DoesNotExist:
        tag = ''
    initial_state = {'state':doc.get_state_slug(state_type='draft-iesg'),
                     'sub_state':tag}
    
    BallotFormset = formset_factory(BallotForm, extra=0)
    
    if request.method == 'POST':
        button_text = request.POST.get('submit', '')
        if button_text == 'update_ballot':
            formset = BallotFormset(request.POST, initial=initial_ballot)
            for form in formset.forms:
                # has_changed doesn't work?
                if form.is_valid() and form.changed_data:
                    clean = form.cleaned_data
                    
                    # from idrfc/views_ballot.py EditPositionRedesign
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
                    
                    create_message(request,'Ballot position changed.')
                    url = reverse('telechat_doc', kwargs={'name':name})
                    return HttpResponseRedirect(url)
        
        elif button_text == 'update_state':
            assert False, 'change state'
            
    else:
        agenda = _agenda_data(request, date=None)
        formset = BallotFormset(initial=initial_ballot)
        state_form = DocumentStateForm(initial=initial_state)
    
    return render_to_response('telechat/doc.html', {
        'document': doc,
        'agenda': agenda,
        'formset': formset,
        'open_positions': open_positions,
        'state_form': state_form,
        'writeup': doc.latest_event(WriteupDocEvent).text},
        RequestContext(request, {}),
    )
    
def doc_navigate(request, name, nav):
    '''
    This view takes two arguments: 
    name - the name of the current document being displayed
    nav  - [next|previous] which direction the user wants to navigate in the list of docs
    The view retrieves the appropriate document and redirects to the doc view.
    '''
    agenda = _agenda_data(request, date=None)
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
        
    url = reverse('telechat_doc', kwargs={'name':target})
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