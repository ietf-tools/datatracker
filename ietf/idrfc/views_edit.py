# changing state and metadata and commenting on Internet Drafts for
# Area Directors and Secretariat

import re, os
from datetime import datetime, date, time, timedelta
from django.http import HttpResponse, HttpResponseRedirect, Http404
from django.shortcuts import render_to_response, get_object_or_404
from django.core.urlresolvers import reverse as urlreverse
from django.template.loader import render_to_string
from django.template import RequestContext
from django import forms
from django.utils.html import strip_tags
from django.db.models import Max
from django.conf import settings

from ietf.utils.mail import send_mail_text
from ietf.ietfauth.decorators import group_required
from ietf.idtracker.templatetags.ietf_filters import in_group
from ietf.idtracker.models import *
from ietf.iesg.models import *
from ietf.idrfc.mails import *
from ietf.idrfc.utils import *
from ietf.idrfc.lastcall import request_last_call

from doc.models import Document, Event, Status, Telechat, save_document_in_history, DocHistory
from name.models import IesgDocStateName, IntendedStdLevelName, DocInfoTagName, get_next_iesg_states, DocStateName
    
class ChangeStateForm(forms.Form):
    state = forms.ModelChoiceField(IDState.objects.all(), empty_label=None, required=True)
    substate = forms.ModelChoiceField(IDSubState.objects.all(), required=False)

@group_required('Area_Director','Secretariat')
def change_state(request, name):
    """Change state of Internet Draft, notifying parties as necessary
    and logging the change as a comment."""
    doc = get_object_or_404(InternetDraft, filename=name)
    if not doc.idinternal or doc.status.status == "Expired":
        raise Http404()

    login = IESGLogin.objects.get(login_name=request.user.username)

    if request.method == 'POST':
        form = ChangeStateForm(request.POST)
        if form.is_valid():
            state = form.cleaned_data['state']
            sub_state = form.cleaned_data['substate']
            internal = doc.idinternal
            if state != internal.cur_state or sub_state != internal.cur_sub_state:
                internal.change_state(state, sub_state)
                internal.event_date = date.today()
                internal.mark_by = login
                internal.save()

                change = log_state_changed(request, doc, login)
                email_owner(request, doc, internal.job_owner, login, change)

                if internal.cur_state.document_state_id == IDState.LAST_CALL_REQUESTED:
                    request_last_call(request, doc)

                    return render_to_response('idrfc/last_call_requested.html',
                                              dict(doc=doc,
                                                   url=doc.idinternal.get_absolute_url()),
                                              context_instance=RequestContext(request))
                
            return HttpResponseRedirect(internal.get_absolute_url())

    else:
        init = dict(state=doc.idinternal.cur_state_id,
                    substate=doc.idinternal.cur_sub_state_id)
        form = ChangeStateForm(initial=init)

    next_states = IDNextState.objects.filter(cur_state=doc.idinternal.cur_state)
    prev_state_formatted = format_document_state(doc.idinternal.prev_state,
                                                 doc.idinternal.prev_sub_state)

    return render_to_response('idrfc/change_state.html',
                              dict(form=form,
                                   doc=doc,
                                   prev_state_formatted=prev_state_formatted,
                                   next_states=next_states),
                              context_instance=RequestContext(request))

class ChangeStateFormREDESIGN(forms.Form):
    state = forms.ModelChoiceField(IesgDocStateName.objects.all(), empty_label=None, required=True)
    # FIXME: no tags yet
    #substate = forms.ModelChoiceField(IDSubState.objects.all(), required=False)

@group_required('Area_Director','Secretariat')
def change_stateREDESIGN(request, name):
    """Change state of Internet Draft, notifying parties as necessary
    and logging the change as a comment."""
    doc = get_object_or_404(Document, docalias__name=name)
    if (not doc.latest_event(type="started_iesg_process")) or doc.state_id == "expired":
        raise Http404()

    login = request.user.get_profile().email()

    if request.method == 'POST':
        form = ChangeStateForm(request.POST)
        if form.is_valid():
            state = form.cleaned_data['state']
            if state != doc.iesg_state:
                save_document_in_history(doc)
                
                prev = doc.iesg_state
                doc.iesg_state = state

                e = log_state_changed(request, doc, login, prev)
                
                doc.time = e.time
                doc.save()

                email_state_changed(request, doc, e.desc)
                email_owner(request, doc, doc.ad, login, e.desc)

                if doc.iesg_state_id == "lc-req":
                    request_last_call(request, doc)

                    return render_to_response('idrfc/last_call_requested.html',
                                              dict(doc=doc,
                                                   url=doc.get_absolute_url()),
                                              context_instance=RequestContext(request))
                
            return HttpResponseRedirect(doc.get_absolute_url())

    else:
        form = ChangeStateForm(initial=dict(state=doc.iesg_state_id))

    next_states = get_next_iesg_states(doc.iesg_state)
    prev_state = None
    
    hists = DocHistory.objects.filter(doc=doc).exclude(iesg_state=doc.iesg_state).order_by("-time")[:1]
    if hists:
        prev_state = hists[0].iesg_state

    return render_to_response('idrfc/change_stateREDESIGN.html',
                              dict(form=form,
                                   doc=doc,
                                   prev_state=prev_state,
                                   next_states=next_states),
                              context_instance=RequestContext(request))

if settings.USE_DB_REDESIGN_PROXY_CLASSES:
    change_state = change_stateREDESIGN
    ChangeStateForm = ChangeStateFormREDESIGN


def dehtmlify_textarea_text(s):
    return s.replace("<br>", "\n").replace("<b>", "").replace("</b>", "").replace("  ", " ")

class EditInfoForm(forms.Form):
    intended_status = forms.ModelChoiceField(IDIntendedStatus.objects.all(), empty_label=None, required=True)
    status_date = forms.DateField(required=False, help_text="Format is YYYY-MM-DD")
    area_acronym = forms.ModelChoiceField(Area.active_areas(), required=True, empty_label=None)
    via_rfc_editor = forms.BooleanField(required=False, label="Via IRTF or RFC Editor")
    job_owner = forms.ModelChoiceField(IESGLogin.objects.filter(user_level__in=(IESGLogin.AD_LEVEL, IESGLogin.INACTIVE_AD_LEVEL)).order_by('user_level', 'last_name'), label="Responsible AD", empty_label=None, required=True)
    state_change_notice_to = forms.CharField(max_length=255, label="Notice emails", help_text="Separate email addresses with commas", required=False)
    note = forms.CharField(widget=forms.Textarea, label="IESG note", required=False)
    telechat_date = forms.TypedChoiceField(coerce=lambda x: datetime.datetime.strptime(x, '%Y-%m-%d').date(), empty_value=None, required=False)
    returning_item = forms.BooleanField(required=False)

    def __init__(self, *args, **kwargs):
        old_ads = kwargs.pop('old_ads')
        
        super(self.__class__, self).__init__(*args, **kwargs)

        job_owners = IESGLogin.objects.in_bulk([t[0] for t in self.fields['job_owner'].choices])
        if old_ads:
            # separate active ADs from inactive
            choices = []
            separated = False
            for t in self.fields['job_owner'].choices:
                if job_owners[t[0]].user_level != IESGLogin.AD_LEVEL and not separated:
                    choices.append(("", "----------------"))
                    separated = True
                choices.append(t)
            self.fields['job_owner'].choices = choices
        else:
            # remove old ones
            self.fields['job_owner'].choices = filter(
                lambda t: job_owners[t[0]].user_level == IESGLogin.AD_LEVEL,
                self.fields['job_owner'].choices)
        
        # telechat choices
        dates = TelechatDates.objects.all()[0].dates()
        init = kwargs['initial']['telechat_date']
        if init and init not in dates:
            dates.insert(0, init)

        choices = [("", "(not on agenda)")]
        for d in dates:
            choices.append((d, d.strftime("%Y-%m-%d")))

        self.fields['telechat_date'].choices = choices

        if kwargs['initial']['area_acronym'] == Acronym.INDIVIDUAL_SUBMITTER:
            # default to "gen"
            kwargs['initial']['area_acronym'] = 1008
        else:
            # hide area acronym if one has been assigned already
            del self.fields['area_acronym']
        
        # returning item is rendered non-standard
        self.standard_fields = [x for x in self.visible_fields() if x.name not in ('returning_item',)]

    def clean_status_date(self):
        d = self.cleaned_data['status_date']
        if d:
            if d < date.today():
                raise forms.ValidationError("Date must not be in the past.")
            if d >= date.today() + timedelta(days=365 * 2):
                raise forms.ValidationError("Date must be within two years.")
        
        return d

    def clean_note(self):
        # note is stored munged in the database
        return self.cleaned_data['note'].replace('\n', '<br>').replace('\r', '').replace('  ', '&nbsp; ')


def get_initial_state_change_notice(doc):
    # set change state notice to something sensible
    receivers = []
    if doc.group_id == Acronym.INDIVIDUAL_SUBMITTER:
        for a in doc.authors.all():
            # maybe it would be more appropriate to use a.email() ?
            e = a.person.email()[1]
            if e:
                receivers.append(e)
    else:
        receivers.append("%s-chairs@%s" % (doc.group.acronym, settings.TOOLS_SERVER))
        for editor in doc.group.ietfwg.wgeditor_set.all():
            e = editor.person.email()[1]
            if e:
                receivers.append(e)

    receivers.append("%s@%s" % (doc.filename, settings.TOOLS_SERVER))
    return ", ".join(receivers)

def get_new_ballot_id():
    return IDInternal.objects.aggregate(Max('ballot'))['ballot__max'] + 1
    
@group_required('Area_Director','Secretariat')
def edit_info(request, name):
    """Edit various Internet Draft attributes, notifying parties as
    necessary and logging changes as document comments."""
    doc = get_object_or_404(InternetDraft, filename=name)
    if doc.status.status == "Expired":
        raise Http404()

    login = IESGLogin.objects.get(login_name=request.user.username)

    new_document = False
    if not doc.idinternal:
        new_document = True
        doc.idinternal = IDInternal(draft=doc,
                                    rfc_flag=type(doc) == Rfc,
                                    cur_state_id=IDState.PUBLICATION_REQUESTED,
                                    prev_state_id=IDState.PUBLICATION_REQUESTED,
                                    state_change_notice_to=get_initial_state_change_notice(doc),
                                    primary_flag=1,
                                    area_acronym_id=Acronym.INDIVIDUAL_SUBMITTER,
                                    # would be better to use NULL to
                                    # signify an empty ballot
                                    ballot_id=get_new_ballot_id(),
                                    via_rfc_editor = False,
                                    )

    if doc.idinternal.agenda:
        initial_telechat_date = doc.idinternal.telechat_date
    else:
        initial_telechat_date = None

    if request.method == 'POST':
        form = EditInfoForm(request.POST,
                            old_ads=False,
                            initial=dict(telechat_date=initial_telechat_date,
                                         area_acronym=doc.idinternal.area_acronym_id))
        if form.is_valid():
            changes = []
            r = form.cleaned_data
            entry = "%s has been changed to <b>%s</b> from <b>%s</b>"
            if new_document:
                # Django barfs in the diff below because these fields
                # can't be NULL
                doc.idinternal.job_owner = r['job_owner']
                if 'area_acronym' in r:
                    doc.idinternal.area_acronym = r['area_acronym']
                
                replaces = doc.replaces_set.all()
                if replaces:
                    c = "Earlier history may be found in the Comment Log for <a href=\"%s\">%s</a>" % (replaces[0], replaces[0].idinternal.get_absolute_url())
                    add_document_comment(request, doc, c, include_by=False)
                    
            orig_job_owner = doc.idinternal.job_owner

            # update the attributes, keeping track of what we're doing

            # coalesce some of the changes into one comment, mail them below
            def diff(obj, attr, name):
                v = getattr(obj, attr)
                if r[attr] != v:
                    changes.append(entry % (name, r[attr], v))
                    setattr(obj, attr, r[attr])

            diff(doc, 'intended_status', "Intended Status")
            diff(doc.idinternal, 'status_date', "Status date")
            if 'area_acronym' in r and r['area_acronym']:
                diff(doc.idinternal, 'area_acronym', 'Area acronym')
            diff(doc.idinternal, 'job_owner', 'Responsible AD')
            diff(doc.idinternal, 'state_change_notice_to', "State Change Notice email list")

            if changes and not new_document:
                add_document_comment(request, doc, "<br>".join(changes))

            # handle note (for some reason the old Perl code didn't
            # include that in the changes)
            if r['note'] != doc.idinternal.note:
                if not r['note']:
                    if doc.idinternal.note:
                        add_document_comment(request, doc, "Note field has been cleared")
                else:
                    if doc.idinternal.note:
                        add_document_comment(request, doc, "[Note]: changed to '%s'" % r['note'])
                    else:
                        add_document_comment(request, doc, "[Note]: '%s' added" % r['note'])
                    
                doc.idinternal.note = r['note']

            update_telechat(request, doc.idinternal,
                            r['telechat_date'], r['returning_item'])

            if in_group(request.user, 'Secretariat'):
                doc.idinternal.via_rfc_editor = bool(r['via_rfc_editor'])

            doc.idinternal.email_display = str(doc.idinternal.job_owner)
            doc.idinternal.token_name = str(doc.idinternal.job_owner)
            doc.idinternal.token_email = doc.idinternal.job_owner.person.email()[1]
            doc.idinternal.mark_by = login
            doc.idinternal.event_date = date.today()

            if changes and not new_document:
                email_owner(request, doc, orig_job_owner, login, "\n".join(changes))
            if new_document:
                add_document_comment(request, doc, "Draft added in state %s" % doc.idinternal.cur_state.state)
                
            doc.idinternal.save()
            doc.save()
            return HttpResponseRedirect(doc.idinternal.get_absolute_url())
    else:
        init = dict(intended_status=doc.intended_status_id,
                    status_date=doc.idinternal.status_date,
                    area_acronym=doc.idinternal.area_acronym_id,
                    job_owner=doc.idinternal.job_owner_id,
                    state_change_notice_to=doc.idinternal.state_change_notice_to,
                    note=dehtmlify_textarea_text(doc.idinternal.note),
                    telechat_date=initial_telechat_date,
                    returning_item=doc.idinternal.returning_item,
                    )

        form = EditInfoForm(old_ads=False, initial=init)

    if not in_group(request.user, 'Secretariat'):
        form.standard_fields = [x for x in form.standard_fields if x.name != "via_rfc_editor"]

        
    return render_to_response('idrfc/edit_info.html',
                              dict(doc=doc,
                                   form=form,
                                   user=request.user,
                                   login=login),
                              context_instance=RequestContext(request))

class NameFromEmailModelChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return obj.get_name()

class EditInfoFormREDESIGN(forms.Form):
    intended_std_level = forms.ModelChoiceField(IntendedStdLevelName.objects.all(), empty_label=None, required=True)
    status_date = forms.DateField(required=False, help_text="Format is YYYY-MM-DD")
    via_rfc_editor = forms.BooleanField(required=False, label="Via IRTF or RFC Editor")
    ad = NameFromEmailModelChoiceField(Email.objects.filter(role__name__in=("ad", "ex-ad")).order_by('role__name', 'person__name'), label="Responsible AD", empty_label=None, required=True)
    notify = forms.CharField(max_length=255, label="Notice emails", help_text="Separate email addresses with commas", required=False)
    note = forms.CharField(widget=forms.Textarea, label="IESG note", required=False)
    telechat_date = forms.TypedChoiceField(coerce=lambda x: datetime.datetime.strptime(x, '%Y-%m-%d').date(), empty_value=None, required=False)
    returning_item = forms.BooleanField(required=False)

    def __init__(self, *args, **kwargs):
        old_ads = kwargs.pop('old_ads')
        
        super(self.__class__, self).__init__(*args, **kwargs)

        # fix up ad field
        choices = self.fields['ad'].choices
        ex_ads = dict((e.pk, e) for e in Email.objects.filter(role__name="ex-ad"))
        if old_ads:
            # separate active ADs from inactive
            for i, t in enumerate(choices):
                if t[0] in ex_ads:
                    choices.insert(i, ("", "----------------"))
                    break
        else:
            # remove old ones
            self.fields['ad'].choices = [t for t in choices if t[0] not in ex_ads]
        
        # telechat choices
        dates = TelechatDates.objects.all()[0].dates()
        init = kwargs['initial']['telechat_date']
        if init and init not in dates:
            dates.insert(0, init)

        choices = [("", "(not on agenda)")]
        for d in dates:
            choices.append((d, d.strftime("%Y-%m-%d")))

        self.fields['telechat_date'].choices = choices

        # returning item is rendered non-standard
        self.standard_fields = [x for x in self.visible_fields() if x.name not in ('returning_item',)]

    def clean_status_date(self):
        d = self.cleaned_data['status_date']
        if d:
            if d < date.today():
                raise forms.ValidationError("Date must not be in the past.")
            if d >= date.today() + timedelta(days=365 * 2):
                raise forms.ValidationError("Date must be within two years.")
        
        return d

    def clean_note(self):
        # note is stored munged in the database
        return self.cleaned_data['note'].replace('\n', '<br>').replace('\r', '').replace('  ', '&nbsp; ')


def get_initial_notify(doc):
    # set change state notice to something sensible
    receivers = []
    if doc.group.type_id == "individ":
        for a in doc.authors.all():
            receivers.append(e.address)
    else:
        receivers.append("%s-chairs@%s" % (doc.group.acronym, settings.TOOLS_SERVER))
        for editor in Email.objects.filter(role__name="wgeditor", role__group=doc.group):
            receivers.append(e.address)

    receivers.append("%s@%s" % (doc.name, settings.TOOLS_SERVER))
    return ", ".join(receivers)

@group_required('Area_Director','Secretariat')
def edit_infoREDESIGN(request, name):
    """Edit various Internet Draft attributes, notifying parties as
    necessary and logging changes as document events."""
    doc = get_object_or_404(Document, docalias__name=name)
    if doc.state_id == "expired":
        raise Http404()

    login = request.user.get_profile().email()

    new_document = False
    if not doc.iesg_state: # FIXME: should probably get this as argument to view
        new_document = True
        doc.iesg_state = IesgDocStateName.objects.get(slug="pub-req")
        doc.notify = get_initial_notify(doc)

    e = doc.latest_event(Telechat, type="scheduled_for_telechat")
    initial_telechat_date = e.telechat_date if e else None
    initial_returning_item = bool(e and e.returning_item)

    if request.method == 'POST':
        form = EditInfoForm(request.POST,
                            old_ads=False,
                            initial=dict(telechat_date=initial_telechat_date))
        if form.is_valid():
            save_document_in_history(doc)
            
            r = form.cleaned_data
            if new_document:
                # fix so Django doesn't barf in the diff below because these
                # fields can't be NULL
                doc.ad = r['ad']
                
                replaces = Document.objects.filter(docalias__relateddocument__source=doc, docalias__relateddocument__relationship="replaces")
                if replaces:
                    # this should perhaps be somewhere else, e.g. the
                    # place where the replace relationship is established
                    e = Event()
                    e.type = "added_comment"
                    e.by = Email.objects.get(address="(System)")
                    e.doc = doc
                    e.desc = "Earlier history may be found in the Comment Log for <a href=\"%s\">%s</a>" % (replaces[0], replaces[0].get_absolute_url())
                    e.save()

                e = Event()
                e.type = "started_iesg_process"
                e.by = login
                e.doc = doc
                e.desc = "IESG process started in state <b>%s</b>" % doc.iesg_state.name
                e.save()
                    
            orig_ad = doc.ad

            changes = []

            def desc(attr, new, old):
                entry = "%(attr)s has been changed to <b>%(new)s</b> from <b>%(old)s</b>"
                if new_document:
                    entry = "%(attr)s has been changed to <b>%(new)s</b>"
                
                return entry % dict(attr=attr, new=new, old=old)
            
            def diff(attr, name):
                v = getattr(doc, attr)
                if r[attr] != v:
                    changes.append(desc(name, r[attr], v))
                    setattr(doc, attr, r[attr])

            # update the attributes, keeping track of what we're doing
            diff('intended_std_level', "Intended Status")
            diff('ad', "Responsible AD")
            diff('notify', "State Change Notice email list")

            if r['note'] != doc.note:
                if not r['note']:
                    if doc.note:
                        changes.append("Note field has been cleared")
                else:
                    if doc.note:
                        changes.append("Note changed to '%s'" % r['note'])
                    else:
                        changes.append("Note added '%s'" % r['note'])
                    
                doc.note = r['note']

            for c in changes:
                e = Event(doc=doc, by=login)
                e.type = "changed_document"
                e.desc = c + " by %s" % login.get_name()
                e.save()

            update_telechat(request, doc, login,
                            r['telechat_date'], r['returning_item'])

            e = doc.latest_event(Status, type="changed_status_date")
            status_date = e.date if e else None
            if r["status_date"] != status_date:
                e = Status(doc=doc, by=login)
                e.type ="changed_status_date"
                d = desc("Status date", r["status_date"], status_date)
                changes.append(d)
                e.desc = d + " by %s" % login.get_name()
                e.date = r["status_date"]
                e.save()
            
            if in_group(request.user, 'Secretariat'):
                via_rfc = DocInfoTagName.objects.get(slug="via-rfc")
                if r['via_rfc_editor']:
                    doc.tags.add(via_rfc)
                else:
                    doc.tags.remove(via_rfc)

            doc.time = datetime.datetime.now()

            if changes and not new_document:
                email_owner(request, doc, orig_ad, login, "\n".join(changes))
                
            doc.save()
            return HttpResponseRedirect(doc.get_absolute_url())
    else:
        e = doc.latest_event(Status)
        status = e.date if e else None
        init = dict(intended_std_level=doc.intended_std_level,
                    status_date=status,
                    ad=doc.ad,
                    notify=doc.notify,
                    note=dehtmlify_textarea_text(doc.note),
                    telechat_date=initial_telechat_date,
                    returning_item=initial_returning_item,
                    )

        form = EditInfoForm(old_ads=False, initial=init)

    if not in_group(request.user, 'Secretariat'):
        # filter out Via RFC Editor
        form.standard_fields = [x for x in form.standard_fields if x.name != "via_rfc_editor"]
        
    return render_to_response('idrfc/edit_infoREDESIGN.html',
                              dict(doc=doc,
                                   form=form,
                                   user=request.user,
                                   login=login),
                              context_instance=RequestContext(request))

if settings.USE_DB_REDESIGN_PROXY_CLASSES:
    EditInfoForm = EditInfoFormREDESIGN
    edit_info = edit_infoREDESIGN


@group_required('Area_Director','Secretariat')
def request_resurrect(request, name):
    """Request resurrect of expired Internet Draft."""
    doc = get_object_or_404(InternetDraft, filename=name)
    if doc.status.status != "Expired":
        raise Http404()

    if not doc.idinternal:
        doc.idinternal = IDInternal(draft=doc, rfc_flag=type(doc) == Rfc)

    login = IESGLogin.objects.get(login_name=request.user.username)

    if request.method == 'POST':
        email_resurrect_requested(request, doc, login)
        add_document_comment(request, doc, "Resurrection was requested")
        doc.idinternal.resurrect_requested_by = login
        doc.idinternal.save()
        return HttpResponseRedirect(doc.idinternal.get_absolute_url())
  
    return render_to_response('idrfc/request_resurrect.html',
                              dict(doc=doc,
                                   back_url=doc.idinternal.get_absolute_url()),
                              context_instance=RequestContext(request))

@group_required('Area_Director','Secretariat')
def request_resurrectREDESIGN(request, name):
    """Request resurrect of expired Internet Draft."""
    doc = get_object_or_404(Document, docalias__name=name)
    if doc.state_id != "expired":
        raise Http404()

    login = request.user.get_profile().email()

    if request.method == 'POST':
        email_resurrect_requested(request, doc, login)
        
        e = Event(doc=doc, by=login)
        e.type = "requested_resurrect"
        e.desc = "Resurrection was requested by %s" % login.get_name()
        e.save()
        
        return HttpResponseRedirect(doc.get_absolute_url())
  
    return render_to_response('idrfc/request_resurrect.html',
                              dict(doc=doc,
                                   back_url=doc.get_absolute_url()),
                              context_instance=RequestContext(request))

if settings.USE_DB_REDESIGN_PROXY_CLASSES:
     request_resurrect = request_resurrectREDESIGN

@group_required('Secretariat')
def resurrect(request, name):
    """Resurrect expired Internet Draft."""
    doc = get_object_or_404(InternetDraft, filename=name)
    if doc.status.status != "Expired":
        raise Http404()

    if not doc.idinternal:
        doc.idinternal = IDInternal(draft=doc, rfc_flag=type(doc) == Rfc)

    login = IESGLogin.objects.get(login_name=request.user.username)

    if request.method == 'POST':
        if doc.idinternal.resurrect_requested_by:
            email_resurrection_completed(request, doc)
        add_document_comment(request, doc, "Resurrection was completed")
        doc.idinternal.resurrect_requested_by = None
        doc.idinternal.event_date = date.today()
        doc.idinternal.save()
        doc.status = IDStatus.objects.get(status="Active")
        doc.save()
        return HttpResponseRedirect(doc.idinternal.get_absolute_url())
  
    return render_to_response('idrfc/resurrect.html',
                              dict(doc=doc,
                                   back_url=doc.idinternal.get_absolute_url()),
                              context_instance=RequestContext(request))

@group_required('Secretariat')
def resurrectREDESIGN(request, name):
    """Resurrect expired Internet Draft."""
    doc = get_object_or_404(Document, docalias__name=name)
    if doc.state_id != "expired":
        raise Http404()

    login = request.user.get_profile().email()

    if request.method == 'POST':
        save_document_in_history(doc)
        
        e = doc.latest_event(type__in=('requested_resurrect', "completed_resurrect"))
        if e and e.type == 'requested_resurrect':
            email_resurrection_completed(request, doc, requester=e.by)
            
        e = Event(doc=doc, by=login)
        e.type = "completed_resurrect"
        e.desc = "Resurrection was completed by %s" % login.get_name()
        e.save()
        
        doc.state = DocStateName.objects.get(slug="active")
        doc.time = datetime.datetime.now()
        doc.save()
        return HttpResponseRedirect(doc.get_absolute_url())
  
    return render_to_response('idrfc/resurrect.html',
                              dict(doc=doc,
                                   back_url=doc.get_absolute_url()),
                              context_instance=RequestContext(request))

if settings.USE_DB_REDESIGN_PROXY_CLASSES:
     resurrect = resurrectREDESIGN


class AddCommentForm(forms.Form):
    comment = forms.CharField(required=True, widget=forms.Textarea)

@group_required('Area_Director','Secretariat')
def add_comment(request, name):
    """Add comment to Internet Draft."""
    doc = get_object_or_404(InternetDraft, filename=name)
    if not doc.idinternal:
        raise Http404()

    login = IESGLogin.objects.get(login_name=request.user.username)

    if request.method == 'POST':
        form = AddCommentForm(request.POST)
        if form.is_valid():
            c = form.cleaned_data['comment']
            add_document_comment(request, doc, c, include_by=False)
            email_owner(request, doc, doc.idinternal.job_owner, login,
                        "A new comment added by %s" % login)
            return HttpResponseRedirect(doc.idinternal.get_absolute_url())
    else:
        form = AddCommentForm()
  
    return render_to_response('idrfc/add_comment.html',
                              dict(doc=doc,
                                   form=form,
                                   back_url=doc.idinternal.get_absolute_url()),
                              context_instance=RequestContext(request))

@group_required('Area_Director','Secretariat')
def add_commentREDESIGN(request, name):
    """Add comment to Internet Draft."""
    doc = get_object_or_404(Document, docalias__name=name)
    if not doc.iesg_state:
        raise Http404()

    login = request.user.get_profile().email()

    if request.method == 'POST':
        form = AddCommentForm(request.POST)
        if form.is_valid():
            c = form.cleaned_data['comment']
            
            e = Event(doc=doc, by=login)
            e.type = "added_comment"
            e.desc = c
            e.save()

            email_owner(request, doc, doc.ad, login,
                        "A new comment added by %s" % login.get_name())
            return HttpResponseRedirect(doc.get_absolute_url())
    else:
        form = AddCommentForm()
  
    return render_to_response('idrfc/add_comment.html',
                              dict(doc=doc,
                                   form=form,
                                   back_url=doc.get_absolute_url()),
                              context_instance=RequestContext(request))

if settings.USE_DB_REDESIGN_PROXY_CLASSES:
     add_comment = add_commentREDESIGN
