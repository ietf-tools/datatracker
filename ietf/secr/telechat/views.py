import os
import datetime

from django.contrib import messages
from django.forms.formsets import formset_factory
from django.shortcuts import render_to_response, get_object_or_404, redirect
from django.template import RequestContext

from ietf.doc.models import DocEvent, Document, BallotDocEvent, BallotPositionDocEvent, WriteupDocEvent, save_document_in_history
from ietf.doc.utils import get_document_content, add_state_change_event
from ietf.person.models import Person
from ietf.doc.lastcall import request_last_call
from ietf.doc.mails import email_state_changed
from ietf.iesg.models import TelechatDate, TelechatAgendaItem, Telechat
from ietf.iesg.agenda import agenda_data, get_doc_section
from ietf.ietfauth.utils import role_required
from ietf.secr.telechat.forms import BallotForm, ChangeStateForm, DateSelectForm, TELECHAT_TAGS



'''
EXPECTED CHANGES:
x group pages will be just another doc, charter doc
x consolidate views (get rid of get_group_header,group,group_navigate)

'''
# -------------------------------------------------
# Notes on external helpers
# -------------------------------------------------
'''
active_ballot_positions: takes one argument, doc.  returns a dictionary with a key for each ad Person object
NOTE: this function has been deprecated as of Datatracker 4.34.  Should now use methods on the Document.
For example: doc.active_ballot().active_ad_positions()

agenda_data: takes a date string in the format YYYY-MM-DD.
'''

# -------------------------------------------------
# Helper Functions
# -------------------------------------------------
def get_doc_list(agenda):
    '''
    This function takes an agenda dictionary and returns a list of
    Document objects in the order they appear in the agenda sections 1-3.
    '''
    docs = []
    for num, section in sorted(agenda['sections'].iteritems()):
        if "docs" in section:
            docs.extend(section["docs"])

    return docs

def get_doc_writeup(doc):
    '''
    This function takes a Document object and returns the ballot writeup for display
    in the detail view.  In the case of Conflict Review documents we actually
    want to display the contents of the document
    '''
    writeup = 'This document has no writeup'
    if doc.type_id == 'draft':
        latest = doc.latest_event(WriteupDocEvent, type='changed_ballot_writeup_text')
        if latest and doc.has_rfc_editor_note:
            rfced_note = doc.latest_event(WriteupDocEvent, type="changed_rfc_editor_note_text")
            writeup = latest.text + "\n\n" + rfced_note.text
        else:
            writeup = latest.text
    if doc.type_id == 'charter':
        latest = doc.latest_event(WriteupDocEvent, type='changed_ballot_writeup_text')
        if latest:
            writeup = latest.text
    elif doc.type_id == 'conflrev':
        path = os.path.join(doc.get_file_path(),doc.filename_with_rev())
        writeup = get_document_content(doc.name,path,split=False,markup=False)
    return writeup

def get_last_telechat_date():
    '''
    This function returns the date of the last telechat
    Tried TelechatDocEvent.objects.latest but that will return today's telechat
    '''
    return TelechatDate.objects.filter(date__lt=datetime.date.today()).order_by('-date')[0].date
    #return '2011-11-01' # uncomment for testing

def get_next_telechat_date():
    '''
    This function returns the date of the next telechat
    '''
    return TelechatDate.objects.filter(date__gte=datetime.date.today()).order_by('date')[0].date

def get_section_header(doc, agenda):
    '''
    This function takes a filename and an agenda dictionary and returns the
    agenda section header as a list for use in the doc template
    '''
    num = get_doc_section(doc)

    header = []

    split = num.split(".")

    for i in xrange(num.count(".")):
        parent_num = ".".join(split[:i + 1])
        parent = agenda["sections"].get(parent_num)
        if parent:
            if "." not in parent_num:
                parent_num += "."
            header.append(u"%s %s" % (parent_num, parent["title"]))

    section = agenda["sections"][num]
    header.append(u"%s %s" % (num, section["title"]))

    count = '%s of %s' % (section["docs"].index(doc) + 1, len(section["docs"]))
    header.append(count)

    return header

def get_first_doc(agenda):
    '''
    This function takes an agenda dictionary and returns the first document in the agenda
    '''
    for num, section in sorted(agenda['sections'].iteritems()):
        if "docs" in section and section["docs"]:
            return section["docs"][0]

    return None

# -------------------------------------------------
# View Functions
# -------------------------------------------------
@role_required('Secretariat')
def bash(request, date):

    agenda = agenda_data(date=date)

    return render_to_response('telechat/bash.html', {
        'agenda': agenda,
        'date': date},
        RequestContext(request, {}),
    )

@role_required('Secretariat')
def doc(request, date):
    '''
    This view redirects to doc_detail using the first document in the agenda or
    displays the message "No Documents"
    '''

    agenda = agenda_data(date=date)
    doc = get_first_doc(agenda)
    if doc:
        return redirect('telechat_doc_detail', date=date, name=doc.name)
    else:
        return render_to_response('telechat/doc.html', {
        'agenda': agenda,
        'date': date,
        'document': None},
        RequestContext(request, {}),
    )

@role_required('Secretariat')
def doc_detail(request, date, name):
    '''
    This view displays the ballot information for the document, and lets the user make
    changes to ballot positions and document state.
    '''
    doc = get_object_or_404(Document, docalias__name=name)

    # As of Datatracker v4.32, Conflict Review (conflrev) Document Types can
    # be added to the Telechat agenda.  If Document.type_id == draft use draft-iesg
    # for state type
    state_type = doc.type_id
    if doc.type_id == 'draft':
        state_type = 'draft-iesg'

    login = request.user.person

    if doc.active_ballot():
        ballots = doc.active_ballot().active_ad_positions()  # returns dict of ad:ballotpositiondocevent
    else:
        ballots = []

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

    writeup = get_doc_writeup(doc)

    initial_state = {'state':doc.get_state(state_type).pk,
                     'substate':tag}

    BallotFormset = formset_factory(BallotForm, extra=0)
    agenda = agenda_data(date=date)
    header = get_section_header(doc, agenda)

    # nav button logic
    doc_list = get_doc_list(agenda)
    nav_start = nav_end = False
    if doc == doc_list[0]:
        nav_start = True
    if doc == doc_list[-1]:
        nav_end = True

    if request.method == 'POST':
        button_text = request.POST.get('submit', '')

        # logic from doc/views_ballot.py EditPosition
        if button_text == 'update_ballot':
            formset = BallotFormset(request.POST, initial=initial_ballot)
            state_form = ChangeStateForm(initial=initial_state)
            has_changed = False
            for form in formset.forms:
                if form.is_valid() and form.changed_data:
                    # create new BallotPositionDocEvent
                    clean = form.cleaned_data
                    ad = Person.objects.get(id=clean['id'])
                    pos = BallotPositionDocEvent(doc=doc,by=login)
                    pos.type = "changed_ballot_position"
                    pos.ad = ad
                    pos.ballot = doc.latest_event(BallotDocEvent, type="created_ballot")
                    pos.pos = clean['position']
                    if form.initial['position'] == None:
                        pos.desc = '[Ballot Position Update] New position, %s, has been recorded for %s by %s' % (pos.pos.name, ad.name, login.name)
                    else:
                        pos.desc = '[Ballot Position Update] Position for %s has been changed to %s by %s' % (ad.name, pos.pos.name, login.name)
                    pos.save()
                    has_changed = True

            if has_changed:
                messages.success(request,'Ballot position changed.')
            return redirect('telechat_doc_detail', date=date, name=name)

        # logic from doc/views_draft.py change_state
        elif button_text == 'update_state':
            formset = BallotFormset(initial=initial_ballot)
            state_form = ChangeStateForm(request.POST, initial=initial_state)
            if state_form.is_valid():
                prev_state = doc.get_state(state_type)

                new_state = state_form.cleaned_data['state']
                tag = state_form.cleaned_data['substate']

                # tag handling is a bit awkward since the UI still works
                # as if IESG tags are a substate
                prev_tags = doc.tags.filter(slug__in=TELECHAT_TAGS)
                new_tags = [tag] if tag else []

                if state_form.changed_data:
                    save_document_in_history(doc)

                    if 'state' in state_form.changed_data:
                        doc.set_state(new_state)

                    if 'substate' in state_form.changed_data:
                        doc.tags.remove(*prev_tags)
                        doc.tags.add(*new_tags)

                    e = add_state_change_event(doc, login, prev_state, new_state,
                                               prev_tags=prev_tags, new_tags=new_tags)
                    doc.time = (e and e.time) or datetime.datetime.now()
                    doc.save()

                    email_state_changed(request, doc, e.desc, 'doc_state_edited')
    
                    if new_state.slug == "lc-req":
                        request_last_call(request, doc)

                messages.success(request,'Document state updated')
                return redirect('telechat_doc_detail', date=date, name=name)
    else:
        formset = BallotFormset(initial=initial_ballot)
        state_form = ChangeStateForm(initial=initial_state)

        # if this is a conflict review document add referenced document
        if doc.type_id == 'conflrev':
            conflictdoc = doc.relateddocument_set.get(relationship__slug='conflrev').target.document
        else:
            conflictdoc = None

    return render_to_response('telechat/doc.html', {
        'date': date,
        'document': doc,
        'conflictdoc': conflictdoc,
        'agenda': agenda,
        'formset': formset,
        'header': header,
        'open_positions': open_positions,
        'state_form': state_form,
        'writeup': writeup,
        'nav_start': nav_start,
        'nav_end': nav_end},
        RequestContext(request, {}),
    )

@role_required('Secretariat')
def doc_navigate(request, date, name, nav):
    '''
    This view takes three arguments:
    date - the date of the Telechat
    name - the name of the current document being displayed
    nav  - [next|previous] which direction the user wants to navigate in the list of docs
    The view retrieves the appropriate document and redirects to the doc view.
    '''
    doc = get_object_or_404(Document, docalias__name=name)
    agenda = agenda_data(date=date)
    target = name

    docs = get_doc_list(agenda)
    index = docs.index(doc)

    if nav == 'next' and index < len(docs) - 1:
        target = docs[index + 1].name
    elif nav == 'previous' and index != 0:
        target = docs[index - 1].name

    return redirect('telechat_doc_detail', date=date, name=target)

@role_required('Secretariat')
def main(request):
    '''
    The is the main view where the user selects an existing telechat or creates a new one.
    '''
    if request.method == 'POST':
        date = request.POST['date']
        return redirect('telechat_doc', date=date)

    choices = [ (d.date.strftime('%Y-%m-%d'),
                 d.date.strftime('%Y-%m-%d')) for d in TelechatDate.objects.all() ]
    next_telechat = get_next_telechat_date().strftime('%Y-%m-%d')
    form = DateSelectForm(choices=choices,initial={'date':next_telechat})

    return render_to_response('telechat/main.html', {
        'form': form},
        RequestContext(request, {}),
    )

@role_required('Secretariat')
def management(request, date):
    '''
    This view displays management issues and lets the user update the status
    '''

    agenda = agenda_data(date=date)
    issues = TelechatAgendaItem.objects.filter(type=3).order_by('id')

    return render_to_response('telechat/management.html', {
        'agenda': agenda,
        'date': date,
        'issues': issues},
        RequestContext(request, {}),
    )

@role_required('Secretariat')
def minutes(request, date):
    '''
    This view shows a list of documents that were approved since the last telechat
    '''
    # get the telechat previous to selected one
    y,m,d = date.split('-')
    current = datetime.date(int(y),int(m),int(d))

    previous = TelechatDate.objects.filter(date__lt=current).order_by("-date")[0].date
    events = DocEvent.objects.filter(type='iesg_approved',time__gte=previous,time__lt=current,doc__type='draft')
    docs = [ e.doc for e in events ]
    pa_docs = [ doc for doc in docs if doc.intended_std_level.slug not in ('inf','exp','hist') ]
    da_docs = [ doc for doc in docs if doc.intended_std_level.slug in ('inf','exp','hist') ]

    agenda = agenda_data(date=date)

    # FIXME: this doesn't show other documents

    return render_to_response('telechat/minutes.html', {
        'agenda': agenda,
        'date': date,
        'last_date': previous,
        'pa_docs': pa_docs,
        'da_docs': da_docs},
        RequestContext(request, {}),
    )

@role_required('Secretariat')
def new(request):
    '''
    This view creates a new telechat agenda and redirects to the default view
    '''
    if request.method == 'POST':
        date = request.POST['date']
        # create legacy telechat record
        Telechat.objects.create(telechat_date=date)

        messages.success(request,'New Telechat Agenda created')
        return redirect('telechat_doc', date=date)

@role_required('Secretariat')
def roll_call(request, date):
    agenda = agenda_data(date=date)
    ads = Person.objects.filter(role__name='ad', role__group__state="active",role__group__type="area")
    sorted_ads = sorted(ads, key = lambda a: a.name_parts()[3])

    return render_to_response('telechat/roll_call.html', {
        'agenda': agenda,
        'date': date,
        'people':sorted_ads},
        RequestContext(request, {}),
    )
    
