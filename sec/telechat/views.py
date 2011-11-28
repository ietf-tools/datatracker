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

    agenda = _agenda_data(request, date=None)
    
    return render_to_response('telechat/main.html', {
        'agenda': agenda},
        RequestContext(request, {}),
    )

def doc(request, name):
    
    #document = get_object_or_404(InternetDraft, name=name)
    doc = get_object_or_404(Document, docalias__name=name)
    started_process = doc.latest_event(type="started_iesg_process")
    if not doc.iesg_state or not started_process:
        raise Http404()
    login = request.user.get_profile()
    
    # setup ballot
    ballot, x = get_ballot(name)
    # sort on AD last name
    positions = sorted(ballot.position_list(), key=lambda a: a['ad_name'].split()[-1])
    initial = []
    for item in positions:
        initial.append({'name':item['ad_name'],'id':item['ad_username'],'position':BALLOT_NAMES[item['position']]})
    BallotFormset = formset_factory(BallotForm, extra=0)
    
    if request.method == 'POST':
        formset = BallotFormset(request.POST, initial=initial)
        for form in formset.forms:
            # has_changed doesn't work?
            if form.is_valid():
                if form.changed_data:
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
                    
    agenda = _agenda_data(request, date=None)
    formset = BallotFormset(initial=initial)
    state_form = DocumentStateForm(initial={'iesg_state':'iesg-eva'})
    
    return render_to_response('telechat/doc.html', {
        'document': doc,
        'agenda': agenda,
        'formset': formset,
        'state_form': state_form,
        'writeup': doc.latest_event(WriteupDocEvent).text},
        RequestContext(request, {}),
    )
    
def doc_navigate(request, name, nav):
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
    
    #document = get_object_or_404(Document, name=name)
    group = id
    agenda = _agenda_data(request, date=None)
    
    return render_to_response('telechat/group.html', {
        'group': group,
        'agenda': agenda},
        RequestContext(request, {}),
    )