# Copyright The IETF Trust 2007, All Rights Reserved

# Portion Copyright (C) 2008-2009 Nokia Corporation and/or its subsidiary(-ies).
# All rights reserved. Contact: Pasi Eronen <pasi.eronen@nokia.com>
# 
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions 
# are met:
# 
#  * Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 
#  * Redistributions in binary form must reproduce the above
#    copyright notice, this list of conditions and the following
#    disclaimer in the documentation and/or other materials provided
#    with the distribution.
# 
#  * Neither the name of the Nokia Corporation and/or its
#    subsidiary(-ies) nor the names of its contributors may be used
#    to endorse or promote products derived from this software
#    without specific prior written permission.
# 
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import codecs, re, os, glob
from ietf.idtracker.models import IDInternal, InternetDraft,AreaGroup, Position, IESGLogin, Acronym
from django.views.generic.list_detail import object_list
from django.views.generic.simple import direct_to_template
from django.views.decorators.vary import vary_on_cookie
from django.core.urlresolvers import reverse as urlreverse
from django.http import Http404, HttpResponse, HttpResponseForbidden, HttpResponseRedirect
from django.template import RequestContext, Context, loader
from django.shortcuts import render_to_response, get_object_or_404
from django.conf import settings
from django import forms
from ietf.iesg.models import TelechatDates, TelechatAgendaItem, WGAction
from ietf.idrfc.idrfc_wrapper import IdWrapper, RfcWrapper
from ietf.idrfc.models import RfcIndex
from ietf.idrfc.utils import update_telechat
from ietf.ietfauth.decorators import group_required
from ietf.idtracker.templatetags.ietf_filters import in_group
import datetime 

def date_threshold():
    """Return the first day of the month that is 185 days ago."""
    ret = datetime.date.today() - datetime.timedelta(days=185)
    ret = ret - datetime.timedelta(days=ret.day - 1)
    return ret

def inddocs(request):
   queryset_list_ind = InternetDraft.objects.filter(idinternal__via_rfc_editor=1, idinternal__rfc_flag=0, idinternal__noproblem=1, idinternal__dnp=0).order_by('-b_approve_date')
   queryset_list_ind_dnp = IDInternal.objects.filter(via_rfc_editor = 1,rfc_flag=0,dnp=1).order_by('-dnp_date')
   return object_list(request, queryset=queryset_list_ind, template_name='iesg/independent_doc.html', allow_empty=True, extra_context={'object_list_dnp':queryset_list_ind_dnp })

def wgdocs(request,cat):
   is_recent = 0
   queryset_list=[]
   queryset_list_doc=[]
   if cat == 'new':
      is_recent = 1
      queryset = InternetDraft.objects.filter(b_approve_date__gte = date_threshold(), intended_status__in=[1,2,6,7],idinternal__via_rfc_editor=0,idinternal__primary_flag=1).order_by("-b_approve_date")
      queryset_doc = InternetDraft.objects.filter(b_approve_date__gte = date_threshold(), intended_status__in=[3,5],idinternal__via_rfc_editor=0, idinternal__primary_flag=1).order_by("-b_approve_date")
   elif cat == 'prev':
      queryset = InternetDraft.objects.filter(b_approve_date__lt = date_threshold(), b_approve_date__gte = '1997-12-1', intended_status__in=[1,2,6,7],idinternal__via_rfc_editor=0,idinternal__primary_flag=1).order_by("-b_approve_date")
      queryset_doc = InternetDraft.objects.filter(b_approve_date__lt = date_threshold(), b_approve_date__gte = '1998-10-15', intended_status__in=[3,5],idinternal__via_rfc_editor=0,idinternal__primary_flag=1).order_by("-b_approve_date")
   else:
     raise Http404
   for item in list(queryset):
      queryset_list.append(item)
      try:
        ballot_id=item.idinternal.ballot_id
      except AttributeError:
        ballot_id=0
      for sub_item in list(InternetDraft.objects.filter(idinternal__ballot=ballot_id,idinternal__primary_flag=0)):
         queryset_list.append(sub_item)
   for item2 in list(queryset_doc):
      queryset_list_doc.append(item2)
      try:
        ballot_id=item2.idinternal.ballot_id
      except AttributeError:
        ballot_id=0
      for sub_item2 in list(InternetDraft.objects.filter(idinternal__ballot=ballot_id,idinternal__primary_flag=0)):
         queryset_list_doc.append(sub_item2)
   return render_to_response( 'iesg/ietf_doc.html', {'object_list': queryset_list, 'object_list_doc':queryset_list_doc, 'is_recent':is_recent}, context_instance=RequestContext(request) )

def get_doc_section(id):
    states = [16,17,18,19,20,21]
    if id.document().intended_status.intended_status_id in [1,2,6,7]:
        s = "2"
    else:
        s = "3"
    if id.rfc_flag == 0:
        g = id.document().group_acronym()
    else:
        g = id.document().group_acronym
    if g and str(g) != 'none':
        s = s + "1"
    elif (s == "3") and id.via_rfc_editor > 0:
        s = s + "3"
    else:
        s = s + "2"
    if not id.rfc_flag and id.cur_state.document_state_id not in states:
        s = s + "3"
    elif id.returning_item > 0:
        s = s + "2"
    else:
        s = s + "1"
    return s

def agenda_docs(date, next_agenda):
    if next_agenda:
        matches = IDInternal.objects.filter(telechat_date=date, primary_flag=1, agenda=1)
    else:
        matches = IDInternal.objects.filter(telechat_date=date, primary_flag=1)
    idmatches = matches.filter(rfc_flag=0).order_by('ballot')
    rfcmatches = matches.filter(rfc_flag=1).order_by('ballot')
    res = {}
    for id in list(idmatches)+list(rfcmatches):
        section_key = "s"+get_doc_section(id)
        if section_key not in res:
            res[section_key] = []
        if id.note:
            id.note = id.note.replace(u"\240",u"&nbsp;")
        res[section_key].append({'obj':id})
    return res

def agenda_wg_actions(date):
    mapping = {12:'411', 13:'412',22:'421',23:'422'}
    matches = WGAction.objects.filter(agenda=1,telechat_date=date,category__in=mapping.keys()).order_by('category')
    res = {}
    for o in matches:
        section_key = "s"+mapping[o.category]
        if section_key not in res:
            res[section_key] = []
        area = AreaGroup.objects.get(group=o.group_acronym)
        res[section_key].append({'obj':o, 'area':str(area.area)})
    return res

def agenda_management_issues(date):
    return TelechatAgendaItem.objects.filter(type=3).order_by('id')

def _agenda_data(request, date=None):
    if not date:
        date = TelechatDates.objects.all()[0].date1
        next_agenda = True
    else:
        y,m,d = date.split("-")
        date = datetime.date(int(y), int(m), int(d))
        next_agenda = None
    #date = "2006-03-16"
    docs = agenda_docs(date, next_agenda)
    mgmt = agenda_management_issues(date)
    wgs = agenda_wg_actions(date)
    data = {'date':str(date), 'docs':docs,'mgmt':mgmt,'wgs':wgs}
    for key, filename in {'action_items':settings.IESG_TASK_FILE,
                          'roll_call':settings.IESG_ROLL_CALL_FILE,
                          'minutes':settings.IESG_MINUTES_FILE}.items():
        try:
            f = codecs.open(filename, 'r', 'utf-8', 'replace')
            text = f.read().strip()
            f.close()
            data[key] = text
        except IOError:
            data[key] = "(Error reading "+key+")"
    return data

@vary_on_cookie
def agenda(request, date=None):
    data = _agenda_data(request, date)
    data['private'] = 'private' in request.REQUEST
    return render_to_response("iesg/agenda.html", data, context_instance=RequestContext(request))

def agenda_txt(request):
    data = _agenda_data(request)
    return render_to_response("iesg/agenda.txt", data, context_instance=RequestContext(request), mimetype="text/plain")

def agenda_scribe_template(request):
    date = TelechatDates.objects.all()[0].date1
    docs = agenda_docs(date, True)
    return render_to_response('iesg/scribe_template.html', {'date':str(date), 'docs':docs}, context_instance=RequestContext(request) )

def _agenda_moderator_package(request):
    data = _agenda_data(request)
    data['ad_names'] = [str(x) for x in IESGLogin.active_iesg()]
    return render_to_response("iesg/moderator_package.html", data, context_instance=RequestContext(request))

@group_required('Area_Director','Secretariat')
def agenda_moderator_package(request):
    return _agenda_moderator_package(request)

def agenda_moderator_package_test(request):
    if request.META['REMOTE_ADDR'] == "127.0.0.1":
        return _agenda_moderator_package(request)
    else:
        return HttpResponseForbidden()

def _agenda_package(request):
    data = _agenda_data(request)
    return render_to_response("iesg/agenda_package.txt", data, context_instance=RequestContext(request), mimetype='text/plain')

@group_required('Area_Director','Secretariat')
def agenda_package(request):
    return _agenda_package(request)

def agenda_package_test(request):
    if request.META['REMOTE_ADDR'] == "127.0.0.1":
        return _agenda_package(request)
    else:
        return HttpResponseForbidden()

def agenda_documents_txt(request):
    dates = TelechatDates.objects.all()[0].dates()
    docs = []
    for date in dates:
        docs.extend(IDInternal.objects.filter(telechat_date=date, primary_flag=1, agenda=1))
    t = loader.get_template('iesg/agenda_documents.txt')
    c = Context({'docs':docs})
    return HttpResponse(t.render(c), mimetype='text/plain')

class RescheduleForm(forms.Form):
    telechat_date = forms.TypedChoiceField(coerce=lambda x: datetime.datetime.strptime(x, '%Y-%m-%d').date(), empty_value=None, required=False)
    clear_returning_item = forms.BooleanField(initial=False, required=False)

    def __init__(self, *args, **kwargs):
        dates = kwargs.pop('telechat_dates')
        
        super(self.__class__, self).__init__(*args, **kwargs)

        # telechat choices
        init = kwargs['initial']['telechat_date']
        if init and init not in dates:
            dates.insert(0, init)

        choices = [("", "(not on agenda)")]
        for d in dates:
            choices.append((d, d.strftime("%Y-%m-%d")))

        self.fields['telechat_date'].choices = choices

def handle_reschedule_form(request, idinternal, dates):
    initial = dict(
        telechat_date=idinternal.telechat_date if idinternal.agenda else None)

    formargs = dict(telechat_dates=dates,
                    prefix="%s" % idinternal.draft_id,
                    initial=initial)
    if request.method == 'POST':
        form = RescheduleForm(request.POST, **formargs)
        if form.is_valid():
            update_telechat(request, idinternal,
                            form.cleaned_data['telechat_date'])
            if form.cleaned_data['clear_returning_item']:
                idinternal.returning_item = False
            idinternal.event_date = datetime.date.today()
            idinternal.save()
    else:
        form = RescheduleForm(**formargs)

    form.show_clear = idinternal.returning_item
    return form

def agenda_documents(request):
    dates = TelechatDates.objects.all()[0].dates()
    idinternals = list(IDInternal.objects.filter(telechat_date__in=dates,primary_flag=1,agenda=1).order_by('rfc_flag', 'ballot'))
    for i in idinternals:
        i.reschedule_form = handle_reschedule_form(request, i, dates)

    # some may have been taken off the schedule by the reschedule form
    idinternals = filter(lambda x: x.agenda, idinternals)
        
    telechats = []
    for date in dates:
        matches = filter(lambda x: x.telechat_date == date, idinternals)
        res = {}
        for i in matches:
            section_key = "s" + get_doc_section(i)
            if section_key not in res:
                res[section_key] = []
            if not i.rfc_flag:
                w = IdWrapper(draft=i)
            else:
                ri = RfcIndex.objects.get(rfc_number=i.draft_id)
                w = RfcWrapper(ri)
            w.reschedule_form = i.reschedule_form
            res[section_key].append(w)
        telechats.append({'date':date, 'docs':res})
    return direct_to_template(request, 'iesg/agenda_documents.html', {'telechats':telechats, 'hide_telechat_date':True})

def discusses(request):
    positions = Position.objects.filter(discuss=1)
    res = []
    try:
        ids = set()
    except NameError:
        # for Python 2.3 
        from sets import Set as set
        ids = set()
    
    for p in positions:
        try:
            draft = p.ballot.drafts.filter(primary_flag=1)
            if len(draft) > 0 and draft[0].rfc_flag:
                if not -draft[0].draft_id in ids:
                    ids.add(-draft[0].draft_id)
                    try:
                        ri = RfcIndex.objects.get(rfc_number=draft[0].draft_id)
                        doc = RfcWrapper(ri)
                        if doc.in_ietf_process() and doc.ietf_process.has_active_iesg_ballot():
                            res.append(doc)
                    except RfcIndex.DoesNotExist:
                        # NOT QUITE RIGHT, although this should never happen
                        pass
            if len(draft) > 0 and not draft[0].rfc_flag and draft[0].draft.id_document_tag not in ids:
                ids.add(draft[0].draft.id_document_tag)
                doc = IdWrapper(draft=draft[0])
                if doc.in_ietf_process() and doc.ietf_process.has_active_iesg_ballot():
                    res.append(doc)
        except IDInternal.DoesNotExist:
            pass
    return direct_to_template(request, 'iesg/discusses.html', {'docs':res})


class TelechatDatesForm(forms.ModelForm):
    class Meta:
        model = TelechatDates
        fields = ['date1', 'date2', 'date3', 'date4']

@group_required('Secretariat')
def telechat_dates(request):
    dates = TelechatDates.objects.all()[0]

    if request.method == 'POST':
        if request.POST.get('rollup_dates'):
            TelechatDates.objects.all().update(
                date1=dates.date2, date2=dates.date3, date3=dates.date4,
                date4=dates.date4 + datetime.timedelta(days=14))
            form = TelechatDatesForm(instance=dates)
        else:
            form = TelechatDatesForm(request.POST, instance=dates)
            if form.is_valid():
                form.save(commit=False)
                TelechatDates.objects.all().update(date1 = dates.date1,
                                                  date2 = dates.date2,
                                                  date3 = dates.date3,
                                                  date4 = dates.date4)
    else:
        form = TelechatDatesForm(instance=dates)

    from django.contrib.humanize.templatetags import humanize
    for f in form.fields:
        form.fields[f].label = "Date " + humanize.ordinal(form.fields[f].label[4])
        form.fields[f].thursday = getattr(dates, f).isoweekday() == 4
        
    return render_to_response("iesg/telechat_dates.html",
                              dict(form=form),
                              context_instance=RequestContext(request))

def parse_wg_action_file(path):
    f = open(path, 'rU')
    
    line = f.readline()
    while line and not line.strip():
        line = f.readline()

    # name
    m = re.search(r'([^\(]*) \(', line)
    if not m:
        return None
    name = m.group(1)

    # acronym
    m = re.search(r'\((\w+)\)', line)
    if not m:
        return None
    acronym = m.group(1)

    # date
    line = f.readline()
    m = re.search(r'(\d{4})-(\d{2})-(\d{2})', line)
    while line and not m:
        line = f.readline()
        m = re.search(r'(\d{4})-(\d{2})-(\d{2})', line)

    last_updated = None
    if m:
        try:
            last_updated = datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except:
            pass

    # token
    line = f.readline()
    while line and not 'area director' in line.lower():
        line = f.readline()

    line = f.readline()
    line = f.readline()
    m = re.search(r'\s*(\w+)\s*', line)
    token = ""
    if m:
        token = m.group(1)

    return dict(filename=os.path.basename(path), name=name, acronym=acronym,
                status_date=last_updated, token=token)

def get_possible_wg_actions():
    res = []
    charters = glob.glob(os.path.join(settings.IESG_WG_EVALUATION_DIR, '*-charter.txt'))
    for path in charters:
        d = parse_wg_action_file(path)
        if d:
            if not d['status_date']:
                d['status_date'] = datetime.date(1900,1,1)
            res.append(d)

    res.sort(key=lambda x: x['status_date'])

    return res


@group_required('Area_Director', 'Secretariat')
def working_group_actions(request):
    current_items = WGAction.objects.order_by('status_date').select_related()

    if request.method == 'POST' and in_group(request.user, 'Secretariat'):
        filename = request.POST.get('filename')
        if filename and filename in os.listdir(settings.IESG_WG_EVALUATION_DIR):
            if 'delete' in request.POST:
                os.unlink(os.path.join(settings.IESG_WG_EVALUATION_DIR, filename))
            if 'add' in request.POST:
                d = parse_wg_action_file(os.path.join(settings.IESG_WG_EVALUATION_DIR, filename))
                qstr = "?" + "&".join("%s=%s" % t for t in d.iteritems())
                return HttpResponseRedirect(urlreverse('iesg_add_working_group_action') + qstr)
    

    skip = [c.group_acronym.acronym for c in current_items]
    possible_items = filter(lambda x: x['acronym'] not in skip,
                            get_possible_wg_actions())
    
    return render_to_response("iesg/working_group_actions.html",
                              dict(current_items=current_items,
                                   possible_items=possible_items),
                              context_instance=RequestContext(request))

class EditWGActionForm(forms.ModelForm):
    token_name = forms.ChoiceField()
    telechat_date = forms.TypedChoiceField(coerce=lambda x: datetime.datetime.strptime(x, '%Y-%m-%d').date(), empty_value=None, required=False)

    class Meta:
        model = WGAction
        fields = ['status_date', 'token_name', 'category', 'note']

    def __init__(self, *args, **kwargs):
        super(self.__class__, self).__init__(*args, **kwargs)

        # token name choices
        self.fields['token_name'].choices = [(p.first_name, p.first_name) for p in IESGLogin.active_iesg().order_by('first_name')]
        
        # telechat choices
        dates = TelechatDates.objects.all()[0].dates()
        init = kwargs['initial']['telechat_date']
        if init and init not in dates:
            dates.insert(0, init)

        choices = [("", "(not on agenda)")]
        for d in dates:
            choices.append((d, d.strftime("%Y-%m-%d")))

        self.fields['telechat_date'].choices = choices
        
        
@group_required('Secretariat')
def edit_working_group_action(request, wga_id):
    if wga_id != None:
        wga = get_object_or_404(WGAction, pk=wga_id)
    else:
        wga = WGAction()
        try:
            wga.group_acronym = Acronym.objects.get(acronym=request.GET.get('acronym'))
        except Acronym.DoesNotExist:
            pass
        
        wga.token_name = request.GET.get('token')
        try:
            d = datetime.datetime.strptime(request.GET.get('status_date'), '%Y-%m-%d').date()
        except:
            d = datetime.date.today()
        wga.status_date = d
        wga.telechat_date = TelechatDates.objects.all()[0].date1
        wga.agenda = True

    initial = dict(telechat_date=wga.telechat_date if wga.agenda else None)

    if request.method == 'POST':
        if "delete" in request.POST:
            wga.delete()
            return HttpResponseRedirect(urlreverse('iesg_working_group_actions'))

        form = EditWGActionForm(request.POST, instance=wga, initial=initial)
        if form.is_valid():
            form.save(commit=False)
            wga.agenda = bool(form.cleaned_data['telechat_date'])
            if wga.category in (11, 21):
                wga.agenda = False
            if wga.agenda:
                wga.telechat_date = form.cleaned_data['telechat_date']
            wga.save()
            return HttpResponseRedirect(urlreverse('iesg_working_group_actions'))
    else:
        form = EditWGActionForm(instance=wga, initial=initial)
        

    return render_to_response("iesg/edit_working_group_action.html",
                              dict(wga=wga,
                                   form=form),
                              context_instance=RequestContext(request))
