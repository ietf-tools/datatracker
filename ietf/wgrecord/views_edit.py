# Copyright The IETF Trust 2011, All Rights Reserved

import re, os, string
from datetime import datetime, date, time, timedelta
from django.shortcuts import render_to_response, get_object_or_404, redirect
from django.core.urlresolvers import reverse
from django.template import RequestContext
from django import forms
from django.forms.util import ErrorList
from django.core.exceptions import ObjectDoesNotExist

from utils import log_state_changed, log_info_changed, update_telechat
from mails import email_secretariat
from ietf.ietfauth.decorators import group_required
from ietf.iesg.models import TelechatDates

from doc.models import Document, DocHistory, DocEvent, save_document_in_history, TelechatDocEvent, InitialReviewDocEvent
from name.models import CharterDocStateName, GroupStateName, GroupTypeName, DocTypeName, RoleName
from person.models import Person, Email
from group.models import Group, GroupEvent, GroupHistory, GroupURL, Role, RoleHistory, save_group_in_history

from utils import add_wg_comment
from views_search import json_emails
    
class ChangeStateForm(forms.Form):
    charter_state = forms.ModelChoiceField(CharterDocStateName.objects.all(), label="Charter state", empty_label=None, required=True)
    state = forms.ModelChoiceField(GroupStateName.objects.filter(slug__in=["proposed", "active", "conclude"]), label="WG state", empty_label=None, required=True)
    confirm_state = forms.BooleanField(widget=forms.HiddenInput, required=False, initial=True)
    initial_time = forms.IntegerField(initial=1, label="Review time", help_text="(in weeks)", required=False)
    message = forms.CharField(widget=forms.Textarea, help_text="Message the the secretariat", required=False)
    comment = forms.CharField(widget=forms.Textarea, help_text="Comment for the WG history", required=False)
    def __init__(self, *args, **kwargs):
        if 'queryset' in kwargs:
            qs = kwargs.pop('queryset')
        else:
            qs = None
        super(ChangeStateForm, self).__init__(*args, **kwargs)
        if qs:
            self.fields['charter_state'].queryset = qs

@group_required('Area_Director','Secretariat')
def change_state(request, name):
    """Change state of WG and charter, notifying parties as necessary
    and logging the change as a comment."""
    # Get WG by acronym, redirecting if there's a newer acronym
    try:
        wg = Group.objects.get(acronym=name)
    except ObjectDoesNotExist:
        wglist = GroupHistory.objects.filter(acronym=name)
        if wglist:
            return redirect('wg_change_state', name=wglist[0].group.acronym)
        else:
            raise Http404
    # Get charter
    charter = wg.charter if wg.charter else None
    initial_review = charter.latest_event(InitialReviewDocEvent, type="initial_review")

    login = request.user.get_profile()

    if request.method == 'POST':
        form = ChangeStateForm(request.POST)
        if form.is_valid():
            if initial_review and form.cleaned_data['charter_state'].slug != "infrev" and initial_review.expires > datetime.now() and not form.cleaned_data['confirm_state']:
                form._errors['charter_state'] = "warning"
            else:
                state = form.cleaned_data['state']
                charter_state = form.cleaned_data['charter_state']
                comment = form.cleaned_data['comment']
                message = form.cleaned_data['message']
                
                change = False
                if charter:
                    # The WG has a charter
                    if charter_state != charter.charter_state:
                        # Charter state changed
                        change = True
                        save_document_in_history(charter)
                    
                        prev = charter.charter_state
                        charter.charter_state = charter_state
                        
                        e = log_state_changed(request, charter, login, prev, comment)
                        charter.time = datetime.now()
                        charter.save()
                else:
                    # WG does not yet have a charter
                    if charter_state != "infrev":
                        # This is an error
                        raise Http404

                if state != wg.state:
                    # WG state changed
                    change = True
                    save_group_in_history(wg)

                    prev = wg.state
                    wg.state = state
                
                    wg.save()
                if change:
                    if charter:
                        messages = {}
                        messages['extrev'] = "The WG has been set to External review by %s. Please schedule discussion for the next IESG telechat." % login.name
                    
                        if message != "":
                            email_secretariat(request, wg, "state-%s" % charter.charter_state_id, message)
                        if charter.charter_state_id == "extrev":
                            email_secretariat(request, wg, "state-%s" % charter.charter_state_id, messages['extrev'])

                        if form.cleaned_data["charter_state"] == "infrev":
                            e = DocEvent()
                            e.type = "started_iesg_process"
                            e.by = login
                            e.doc = charter
                            e.desc = "IESG process started in state <b>%s</b>" % charter.charter_state.name
                            e.save()

                        if form.cleaned_data["initial_time"] != 0:
                            e = InitialReviewDocEvent()
                            e.type = "initial_review"
                            e.by = login
                            e.doc = charter
                            e.expires = datetime.now() + timedelta(weeks=form.cleaned_data["initial_time"])
                            e.desc = "Initial review time expires %s" % e.expires.strftime("%Y-%m-%d")
                            e.save()
                
                return redirect('record_view', name=wg.acronym)
    else:
        if wg.state_id != "proposed":
            states = CharterDocStateName.objects.filter(slug__in=["infrev", "intrev", "extrev", "iesgrev", "approved"])
            form = ChangeStateForm(queryset=states, initial=dict(charter_state=charter.charter_state_id, state=wg.state_id))
        else:
            form = ChangeStateForm(initial=dict(charter_state=charter.charter_state_id, state=wg.state_id))

    group_hists = GroupHistory.objects.filter(group=wg).exclude(state=wg.state).order_by("-time")[:1]
    if group_hists:
        prev_state = group_hists[0].state
    else:
        prev_state = None
    if charter:
        charter_hists = DocHistory.objects.filter(doc__name=charter.name).exclude(charter_state=charter.charter_state).order_by("-time")[:1]
        if charter_hists:
            prev_charter_state = charter_hists[0].charter_state
        else:
            prev_charter_state = None
    else:
        prev_charter_state = None

    return render_to_response('wgrecord/change_state.html',
                              dict(form=form,
                                   wg=wg,
                                   login=login,
                                   prev_state=prev_state,
                                   prev_charter_state=prev_charter_state),
                              context_instance=RequestContext(request))

class EditInfoForm(forms.Form):
    name = forms.CharField(max_length=255, label="WG Name", required=True)
    acronym = forms.CharField(max_length=8, label="WG Acronym", required=True)
    confirm_acronym = forms.BooleanField(widget=forms.HiddenInput, required=False, initial=True)
    chairs = forms.CharField(max_length=255, label="WG Chairs", help_text="Type in a name", required=False)
    secretaries = forms.CharField(max_length=255, label="WG Secretaries", help_text="Type in a name", required=False)
    techadv = forms.CharField(max_length=255, label="WG Technical Advisors", help_text="Type in a name", required=False)
    ad = forms.ModelChoiceField(Person.objects.filter(email__role__name__in=("ad", "ex-ad")).order_by('email__role__name', 'name'), label="Shepherding AD", empty_label="-", required=False)
    parent = forms.ModelChoiceField(Group.objects.filter(type="area", state="active").order_by('name'), label="IETF Area", empty_label="-", required=False)
    list_email = forms.CharField(max_length=64, required=False)
    list_subscribe = forms.CharField(max_length=255, required=False)
    list_archive = forms.CharField(max_length=255, required=False)
    urls = forms.CharField(widget=forms.Textarea, label="Additional URLs", help_text="Format: http://site/url (optional description). Separate by newline.", required=False)
    comments = forms.CharField(widget=forms.Textarea, label="Reason for chartering", required=False)
    telechat_date = forms.TypedChoiceField(coerce=lambda x: datetime.strptime(x, '%Y-%m-%d').date(), empty_value=None, required=False)

    def __init__(self, *args, **kwargs):
        super(self.__class__, self).__init__(*args, **kwargs)

        # fix up ad field
        choices = self.fields['ad'].choices
        ex_ads = dict((e.pk, e) for e in Person.objects.filter(email__role__name="ex-ad").distinct())

        # remove old ones
        self.fields['ad'].choices = [t for t in choices if t[0] not in ex_ads]

        # telechat choices
        dates = TelechatDates.objects.all()[0].dates()
        if 'telechat_date' in kwargs['initial']:
            init = kwargs['initial']['telechat_date']
            if init and init not in dates:
                dates.insert(0, init)

        choices = [("", "(not on agenda)")]
        for d in dates:
            choices.append((d, d.strftime("%Y-%m-%d")))

        self.fields['telechat_date'].choices = choices

def not_valid_acronym(value):
    try:
        Group.objects.get(acronym=value)
    except ObjectDoesNotExist:
        gh = GroupHistory.objects.filter(acronym=value)
        if gh:
            return True
        else:
            return False
    return True

@group_required('Area_Director','Secretariat')
def edit_info(request, name=None):
    """Edit or create a WG, notifying parties as
    necessary and logging changes as group events."""
    import sys
    if request.path_info == reverse('wg_edit_info', kwargs={'name': name}):
        # Editing. Get group
        wg = get_object_or_404(Group, acronym=name)
        new_wg = False
    elif request.path_info == reverse('wg_create'):
        wg = None
        new_wg = True

    login = request.user.get_profile()

    if wg and wg.charter:
        e = wg.charter.latest_event(TelechatDocEvent, type="scheduled_for_telechat")
        initial_telechat_date = e.telechat_date if e else None
    else:
        initial_telechat_date = None

    if request.method == 'POST':
        form = EditInfoForm(request.POST, initial=dict(telechat_date=initial_telechat_date))
        if form.is_valid():
            if (new_wg or form.cleaned_data['acronym'] != wg.acronym) and not_valid_acronym(form.cleaned_data['acronym']) and not form.cleaned_data['confirm_acronym']:
                try:
                    Group.objects.get(acronym=form.cleaned_data['acronym'])
                    form._errors['acronym'] = "error"
                except ObjectDoesNotExist:
                    form._errors['acronym'] = "warning"
            else:
                r = form.cleaned_data

                if not new_wg:
                    gh = save_group_in_history(wg)
                else:
                    # Create WG
                    wg = Group(name=r["name"],
                               acronym=r["acronym"],
                               type=GroupTypeName.objects.get(name="WG"),
                               state=GroupStateName.objects.get(name="Proposed"))
                    wg.save()

                    e = GroupEvent(group=wg, type="proposed")
                    e.time = datetime.now()
                    e.by = login
                    e.desc = "Proposed group"
                    e.save()
                if not wg.charter:
                    # Create adjoined charter
                    try:
                        charter = Document.objects.get(name="charter-ietf-"+r["acronym"])
                    except ObjectDoesNotExist:
                        charter = Document(type=DocTypeName.objects.get(name="Charter"), 
                                           title=r["name"], 
                                           abstract=r["name"], 
                                           name="charter-ietf-" + r["acronym"],
                                           )
                        charter.charter_state = CharterDocStateName.objects.get(slug="infrev")
                        charter.group = wg
                        charter.save()

                    e = DocEvent(doc=charter, type="started_iesg_process")
                    e.time = datetime.now()
                    e.by = login
                    e.desc = "Started IESG process on charter"
                    e.save()

                    wg.charter = charter
                    wg.save()
                
                changes = []
                
                def desc(attr, new, old):
                    entry = "%(attr)s has been changed to <b>%(new)s</b> from <b>%(old)s</b>"
                    if new_wg:
                        entry = "%(attr)s has been changed to <b>%(new)s</b>"

                    return entry % dict(attr=attr, new=new, old=old)

                def get_model_fields_as_dict(obj):
                    return dict((field.name, getattr(obj, field.name))
                                for field in obj._meta.fields
                                if field is not obj._meta.pk)

                def diff(attr, name):
                    v = getattr(wg, attr)
                    if r[attr] != v:
                        changes.append(desc(name, r[attr], v))
                        setattr(wg, attr, r[attr])
                        if attr == "acronym":
                            c = wg.charter
                            save_document_in_history(c)
                            # copy fields
                            fields = get_model_fields_as_dict(c) 
                            fields["name"] = "charter-ietf-%s" % (r[attr])
                            new_c = Document(**fields)
                            new_c.save()
                            # Set WG charter to new one
                            wg.charter = new_c
                            wg.save()
                            # Move history
                            for h in c.history_set.all():
                                h.doc = new_c
                                h.save()
                            # Move events
                            for e in c.docevent_set.all():
                                e.doc = new_c
                                e.save()
                            # And remove the previous charter entry
                            #c.delete()

                # update the attributes, keeping track of what we're doing
                diff('name', "Name")
                diff('acronym', "Acronym")
                diff('ad', "Shepherding AD")
                diff('parent', "IETF Area")
                diff('list_email', "Mailing list email")
                diff('list_subscribe', "Mailing list subscribe address")
                diff('list_archive', "Mailing list archive")
                diff('comments', "Comment")

                def get_sorted_string(attr, splitter):
                    if splitter == '\n':
                        out = sorted(r[attr].splitlines())
                    else:
                        out = sorted(r[attr].split(splitter))
                    if out == ['']:
                        out = []
                    return out

                # update roles
                for attr_role in [('chairs', 'Chair'), ('secretaries', 'Secretary'), ('techadv', 'Tech Advisor')]:
                    attr = attr_role[0]
                    rname = attr_role[1]
                    new = get_sorted_string(attr, ",")
                    old = map(lambda x: x.email.address, wg.role_set.filter(name__name=rname).order_by('email__address'))
                    if new != old:
                        # Remove old roles and save them in history
                        for role in wg.role_set.filter(name__name=rname):
                            role.delete()
                        # Add new ones
                        rolename = RoleName.objects.get(name=rname)
                        for e in new:
                            email = Email.objects.get(address=e)
                            role = Role(name=rolename, email=email, group=wg)
                            role.save()

                # update urls
                new_urls = get_sorted_string('urls', '\n')
                old_urls = map(lambda x: x.url + " (" + x.name + ")", wg.groupurl_set.order_by('url'))
                if new_urls != old_urls:
                    # Remove old urls
                    for u in wg.groupurl_set.all():
                        u.delete()
                    # Add new ones
                    for u in [u for u in new_urls if u != ""]:
                        m = re.search('(?P<url>.+) \((?P<name>.+)\)', u)
                        url = GroupURL(url=m.group('url'), name=m.group('name'), group=wg)
                        url.save()

                wg.time = datetime.now()

                if changes and not new_wg:
                    for c in changes:
                        log_info_changed(request, wg, login, c)

                update_telechat(request, wg.charter, login, r['telechat_date'])
                
                wg.save()
                if new_wg:
                    return redirect('wg_change_state', name=wg.acronym)
                else:
                    return redirect('record_view', name=wg.acronym)
    else:
        if wg:
            init = dict(name=wg.name if wg.name else None,
                        acronym=wg.acronym,
                        chairs=json_emails(map(lambda x: x.email, wg.role_set.filter(name="Chair"))),
                        secretaries=json_emails(map(lambda x: x.email, wg.role_set.filter(name="Secr"))),
                        techadv=json_emails(map(lambda x: x.email, wg.role_set.filter(name="Techadv"))),
                        charter=wg.charter.name if wg.charter else None,
                        ad=wg.ad.id if wg.ad else None,
                        parent=wg.parent.id if wg.parent else None,
                        list_email=wg.list_email if wg.list_email else None,
                        list_subscribe=wg.list_subscribe if wg.list_subscribe else None,
                        list_archive=wg.list_archive if wg.list_archive else None,
                        urls=string.join(map(lambda x: x.url + " (" + x.name + ")", wg.groupurl_set.all()), "\n"),
                        comments=wg.comments if wg.comments else None,
                        telechat_date=initial_telechat_date,
                        )
        else:
            init = dict(ad=login.id,
                        )
        form = EditInfoForm(initial=init)

    return render_to_response('wgrecord/edit_info.html',
                              dict(wg=wg,
                                   form=form,
                                   user=request.user,
                                   login=login),
                              context_instance=RequestContext(request))

class ConcludeForm(forms.Form):
    comment = forms.CharField(widget=forms.Textarea, label="Instructions", required=False)

@group_required('Area_Director','Secretariat')
def conclude(request, name):
    """Request the closing of a WG, prompting for instructions."""
    try:
        wg = Group.objects.get(acronym=name)
    except ObjectDoesNotExist:
        wglist = GroupHistory.objects.filter(acronym=name)
        if wglist:
            return redirect('wg_conclude', name=wglist[0].group.acronym)
        else:
            raise Http404

    login = request.user.get_profile()

    if request.method == 'POST':
        form = ConcludeForm(request.POST)
        if form.is_valid():
            comment = form.cleaned_data['comment']
            save_group_in_history(wg)
            
            wg.state = GroupStateName.objects.get(name="Concluded")
            wg.save()

            email_secretariat(request, wg, "conclude", comment)

            return redirect('record_view', name=wg.acronym)
    else:
        form = ConcludeForm()

    return render_to_response('wgrecord/conclude.html',
                              dict(form=form,
                                   wg=wg),
                              context_instance=RequestContext(request))

class AddCommentForm(forms.Form):
    comment = forms.CharField(required=True, widget=forms.Textarea)

@group_required('Area_Director','Secretariat')
def add_comment(request, name):
    """Add comment to WG Record."""
    wg = get_object_or_404(Group, acronym=name)

    login = request.user.get_profile()

    if request.method == 'POST':
        form = AddCommentForm(request.POST)
        if form.is_valid():
            c = form.cleaned_data['comment']
            
            add_wg_comment(request, wg, c)

            #email_owner(request, doc, doc.ad, login,
            #            "A new comment added by %s" % login.name)
            return redirect('record_view', name=wg.acronym)
    else:
        form = AddCommentForm()
  
    return render_to_response('wgrecord/add_comment.html',
                              dict(wg=wg,
                                   form=form),
                              context_instance=RequestContext(request))

