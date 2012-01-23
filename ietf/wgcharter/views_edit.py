# Copyright The IETF Trust 2011, All Rights Reserved

import re, os, string, datetime

from django.shortcuts import render_to_response, get_object_or_404, redirect
from django.core.urlresolvers import reverse
from django.template import RequestContext
from django import forms
from django.forms.util import ErrorList

from utils import *
from mails import email_secretariat
from ietf.ietfauth.decorators import group_required
from ietf.iesg.models import TelechatDate

from redesign.doc.models import *
from redesign.name.models import *
from redesign.person.models import *
from redesign.group.models import *
from redesign.group.utils import save_group_in_history

from views_search import json_emails
    
class ChangeStateForm(forms.Form):
    charter_state = forms.ModelChoiceField(State.objects.filter(type="charter"), label="Charter state", empty_label=None, required=False)
    confirm_state = forms.BooleanField(widget=forms.HiddenInput, required=False, initial=True)
    initial_time = forms.IntegerField(initial=0, label="Review time", help_text="(in weeks)", required=False)
    message = forms.CharField(widget=forms.Textarea, help_text="Message to the secretariat", required=False)
    comment = forms.CharField(widget=forms.Textarea, help_text="Comment for the WG history", required=False)
    def __init__(self, *args, **kwargs):
        if 'queryset' in kwargs:
            qs = kwargs.pop('queryset')
        else:
            qs = None
        if 'hide' in kwargs:
            self.hide = kwargs.pop('hide')
        else:
            self.hide = None
        super(ChangeStateForm, self).__init__(*args, **kwargs)
        if qs:
            self.fields['charter_state'].queryset = qs
        # hide requested fields
        if self.hide:
            for f in self.hide:
                self.fields[f].widget = forms.HiddenInput

@group_required('Area_Director','Secretariat')
def change_state(request, name, option=None):
    """Change state of WG and charter, notifying parties as necessary
    and logging the change as a comment."""
    # Get WG by acronym, redirecting if there's a newer acronym
    try:
        wg = Group.objects.get(acronym=name)
        charter = set_or_create_charter(wg)
    except Group.DoesNotExist:
        wglist = GroupHistory.objects.filter(acronym=name)
        if wglist:
            return redirect('wg_change_state', name=wglist[0].group.acronym)
        else:
            raise Http404()

    initial_review = charter.latest_event(InitialReviewDocEvent, type="initial_review")

    login = request.user.get_profile()

    if request.method == 'POST':
        form = ChangeStateForm(request.POST)
        if form.is_valid():
            if initial_review and form.cleaned_data['charter_state'] and form.cleaned_data['charter_state'].slug != "infrev" and initial_review.expires > datetime.datetime.now() and not form.cleaned_data['confirm_state']:
                form._errors['charter_state'] = "warning"
            else:
                if option == "initcharter" or option == "recharter":
                    charter_state = State.objects.get(type="charter", slug="infrev")
                    charter_rev = charter.rev
                elif option == "abandon":
                    if wg.state_id == "proposed":
                        charter_state = State.objects.get(type="charter", slug="notrev")
                    else:
                        charter_state = State.objects.get(type="charter", slug="approved")
                    charter_rev = approved_revision(charter.rev)
                else:
                    charter_state = form.cleaned_data['charter_state']
                    charter_rev = charter.rev

                comment = form.cleaned_data['comment']
                message = form.cleaned_data['message']
                
                change = False
                if charter:
                    # The WG has a charter
                    if charter_state != charter.get_state():
                        # Charter state changed
                        change = True
                        save_charter_in_history(charter)
                    
                        prev = charter.get_state()
                        charter.set_state(charter_state)
                        charter.rev = charter_rev
                        
                        if option != "abandon":
                            e = log_state_changed(request, charter, login, prev, comment)
                        else:
                            # Special log for abandoned efforts
                            e = DocEvent(doc=charter, by=login)
                            e.type = "changed_document"
                            e.desc = "IESG has abandoned the chartering effort"
                            
                            if comment:
                                e.desc += "<br>%s" % comment
                                
                            e.save()

                        charter.time = datetime.datetime.now()
                        charter.save()
                else:
                    # WG does not yet have a charter
                    if charter_state != "infrev":
                        # This is an error
                        raise Http404()

                if change and charter:
                    messages = {}
                    messages['extrev'] = "The WG has been set to External review by %s. Please schedule discussion for the next IESG telechat." % login.plain_name()

                    if message:
                        email_secretariat(request, wg, "state-%s" % charter_state.slug, message)
                    if charter_state.slug == "extrev":
                        email_secretariat(request, wg, "state-%s" % charter_state.slug, messages['extrev'])

                    if charter_state.slug == "infrev":
                        e = DocEvent()
                        e.type = "started_iesg_process"
                        e.by = login
                        e.doc = charter
                        e.desc = "IESG process started in state <b>%s</b>" % charter_state.name
                        e.save()

                if charter_state.slug == "infrev" and form.cleaned_data["initial_time"] and form.cleaned_data["initial_time"] != 0:
                    e = InitialReviewDocEvent()
                    e.type = "initial_review"
                    e.by = login
                    e.doc = charter
                    e.expires = datetime.datetime.now() + datetime.timedelta(weeks=form.cleaned_data["initial_time"])
                    e.desc = "Initial review time expires %s" % e.expires.strftime("%Y-%m-%d")
                    e.save()
                
                return redirect('wg_view', name=wg.acronym)
    else:
        if option == "recharter":
            hide = ['charter_state']
            init = dict(initial_time=1, message="%s has initiated a recharter effort on the WG %s (%s)" % (login.plain_name(), wg.name, wg.acronym))
        elif option == "initcharter":
            hide = ['charter_state']
            init = dict(initial_time=1, message="%s has initiated chartering of the proposed WG %s (%s)" % (login.plain_name(), wg.name, wg.acronym))
        elif option == "abandon":
            hide = ['initial_time', 'charter_state']
            init = dict(message="%s has abandoned the chartering effort on the WG %s (%s)" % (login.plain_name(), wg.name, wg.acronym))
        else:
            hide = ['initial_time']
            init = dict(charter_state=wg.charter.get_state_slug(), state=wg.state_id)
        states = State.objects.filter(type="charter", slug__in=["infrev", "intrev", "extrev", "iesgrev"])
        form = ChangeStateForm(queryset=states, hide=hide, initial=init)

    group_hists = GroupHistory.objects.filter(group=wg).exclude(state=wg.state).order_by("-time")[:1]
    prev_charter_state = None
    if charter:
        charter_hists = DocHistory.objects.filter(doc=charter).exclude(states__type="charter", states__slug=charter.get_state_slug()).order_by("-time")[:1]
        if charter_hists:
            prev_charter_state = charter_hists[0].get_state()

    title = {
        "initcharter": "Initiate chartering of WG %s" % wg.acronym,
        "recharter": "Recharter WG %s" % wg.acronym,
        "abandon": "Abandon effort on WG %s" % wg.acronym,
        }.get(option)
    if not title:
        title = "Change state of WG %s" % wg.acronym

    return render_to_response('wgcharter/change_state.html',
                              dict(form=form,
                                   wg=wg,
                                   login=login,
                                   option=option,
                                   prev_charter_state=prev_charter_state,
                                   title=title),
                              context_instance=RequestContext(request))
def parse_emails_string(s):
    return Email.objects.filter(address__in=[x.strip() for x in s.split(",") if x.strip()]).select_related("person")

class EditInfoForm(forms.Form):
    name = forms.CharField(max_length=255, label="WG Name", required=True)
    acronym = forms.CharField(max_length=8, label="WG Acronym", required=True)
    chairs = forms.CharField(max_length=255, label="WG Chairs", help_text="Type in a name", required=False)
    secretaries = forms.CharField(max_length=255, label="WG Secretaries", help_text="Type in a name", required=False)
    techadv = forms.CharField(max_length=255, label="WG Technical Advisors", help_text="Type in a name", required=False)
    ad = forms.ModelChoiceField(Person.objects.filter(role__name="ad", role__group__state="active").order_by('name'), label="Shepherding AD", empty_label="-", required=False)
    parent = forms.ModelChoiceField(Group.objects.filter(type="area", state="active").order_by('name'), label="IETF Area", empty_label="-", required=False)
    list_email = forms.CharField(max_length=64, required=False)
    list_subscribe = forms.CharField(max_length=255, required=False)
    list_archive = forms.CharField(max_length=255, required=False)
    urls = forms.CharField(widget=forms.Textarea, label="Additional URLs", help_text="Format: http://site/url (optional description). Separate multiple entries with newline.", required=False)
    telechat_date = forms.TypedChoiceField(coerce=lambda x: datetime.datetime.strptime(x, '%Y-%m-%d').date(), empty_value=None, required=False)

    def __init__(self, *args, **kwargs):
        self.cur_acronym = kwargs.pop('cur_acronym')
        if 'hide' in kwargs:
            self.hide = kwargs.pop('hide')
        else:
            self.hide = None
        super(self.__class__, self).__init__(*args, **kwargs)

        # hide requested fields
        if self.hide:
            for f in self.hide:
                self.fields[f].widget = forms.HiddenInput

        # if previous AD is now ex-AD, append that person to the list
        ad_pk = self.initial.get('ad')
        choices = self.fields['ad'].choices
        if ad_pk and ad_pk not in [pk for pk, name in choices]:
            self.fields['ad'].choices = list(choices) + [("", "-------"), (ad_pk, Person.objects.get(pk=ad_pk).plain_name())]
        # telechat choices
        dates = [d.date for d in TelechatDate.objects.active().order_by('date')]
        if 'telechat_date' in kwargs['initial']:
            init = kwargs['initial']['telechat_date']
            if init and init not in dates:
                dates.insert(0, init)

        self.fields['telechat_date'].choices = [("", "(not on agenda)")] + [(d, d.strftime("%Y-%m-%d")) for d in dates]

    def clean_acronym(self):
        acronym = self.cleaned_data['acronym']
        if self.cur_acronym and acronym != self.cur_acronym:
            if Group.objects.filter(acronym=acronym):
                raise forms.ValidationError("Acronym used in a previous WG. Please pick another.")
            if GroupHistory.objects.filter(acronym=acronym):
                raise forms.ValidationError("Acronym used in a previous WG. Please pick another.")
        return acronym

    def clean_chairs(self):
        return parse_emails_string(self.cleaned_data["chairs"])

    def clean_secretaries(self):
        return parse_emails_string(self.cleaned_data["secretaries"])

    def clean_techadv(self):
        return parse_emails_string(self.cleaned_data["techadv"])

    def clean_urls(self):
        return [x.strip() for x in self.cleaned_data["urls"].splitlines() if x.strip()]

def format_urls(set, fs="\n"):
    ostr = ""
    for i,x in enumerate(set):
        if i != 0:
            ostr += fs
        if x.name:
            ostr += x.url + " (" + x.name + ")"
        else:
            ostr += x.url
        
    return ostr
        
@group_required('Area_Director','Secretariat')
def edit_info(request, name=None):
    """Edit or create a WG, notifying parties as
    necessary and logging changes as group events."""
    import sys
    if request.path_info == reverse('wg_edit_info', kwargs={'name': name}):
        # Editing. Get group
        wg = get_object_or_404(Group, acronym=name)
        charter = set_or_create_charter(wg)
        new_wg = False
    elif request.path_info == reverse('wg_create'):
        wg = None
        new_wg = True

    login = request.user.get_profile()

    if not new_wg:
        e = charter.latest_event(TelechatDocEvent, type="scheduled_for_telechat")
        initial_telechat_date = e.telechat_date if e else None
    else:
        initial_telechat_date = None

    if request.method == 'POST':
        form = EditInfoForm(request.POST, initial=dict(telechat_date=initial_telechat_date), cur_acronym=wg.acronym if wg else None)
        if form.is_valid():
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
                
                e = ChangeStateGroupEvent(group=wg, type="changed_state")
                e.time = datetime.datetime.now()
                e.by = login
                e.state_id = "proposed"
                e.desc = "Proposed group"
                e.save()
            if not wg.charter:
                # Create adjoined charter
                charter = set_or_create_charter(wg)
                charter.set_state(State.objects.get(type="charter", slug="infrev"))
                charter.save()
                
                e = DocEvent(doc=charter, type="started_iesg_process")
                e.time = datetime.datetime.now()
                e.by = login
                e.desc = "Started IESG process on charter"
                e.save()
                
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
                        save_charter_in_history(c)
                        # and add a DocAlias
                        DocAlias.objects.create(
                            name = "charter-ietf-%s" % r['acronym'],
                            document = charter
                            )

            # update the attributes, keeping track of what we're doing
            diff('name', "Name")
            diff('acronym', "Acronym")
            diff('ad', "Shepherding AD")
            diff('parent', "IETF Area")
            diff('list_email', "Mailing list email")
            diff('list_subscribe', "Mailing list subscribe address")
            diff('list_archive', "Mailing list archive")
            
            # update roles
            for attr, slug in [('chairs', 'chair'), ('secretaries', 'secr'), ('techadv', 'techadv')]:
                rname = RoleName.objects.get(slug=slug)
                new = r[attr]
                old = Email.objects.filter(role__group=wg, role__name=rname).select_related("person")
                if set(new) != set(old):
                    changes.append(desc(rname.name,
                                        ",".join(x.get_name() for x in new),
                                        ",".join(x.get_name() for x in new)))
                    wg.role_set.filter(name=rname).delete()
                    for e in new:
                        Role.objects.get_or_create(name=rname, email=e, group=wg, person=e.person)

            # update urls
            new_urls = r['urls']
            old_urls = format_urls(wg.groupurl_set.order_by('url'), ", ")
            if ", ".join(sorted(new_urls)) != old_urls:
                changes.append(desc('urls', ", ".join(sorted(new_urls)), old_urls))
                wg.groupurl_set.all().delete()
                # Add new ones
                for u in new_urls:
                    m = re.search('(?P<url>[\w\d:#@%/;$()~_?\+-=\\\.&]+)( \((?P<name>.+)\))?', u)
                    if m:
                        if m.group('name'):
                            url = GroupURL(url=m.group('url'), name=m.group('name'), group=wg)
                        else:
                            url = GroupURL(url=m.group('url'), name='', group=wg)
                        url.save()

            wg.time = datetime.datetime.now()

            if changes and not new_wg:
                for c in changes:
                    log_info_changed(request, wg, login, c)

            update_telechat(request, wg.charter, login, r['telechat_date'])
            
            wg.save()
            if new_wg:
                return redirect('wg_startstop_process', name=wg.acronym, option="initcharter")
            else:
                return redirect('wg_view', name=wg.acronym)
    else: # form.is_valid()
        if not new_wg:
            init = dict(name=wg.name,
                        acronym=wg.acronym,
                        chairs=json_emails([x.email for x in wg.role_set.filter(name="Chair")]),
                        secretaries=json_emails([x.email for x in wg.role_set.filter(name="Secr")]),
                        techadv=json_emails([x.email for x in wg.role_set.filter(name="Techadv")]),
                        charter=wg.charter.name if wg.charter else None,
                        ad=wg.ad.id if wg.ad else None,
                        parent=wg.parent.id if wg.parent else None,
                        list_email=wg.list_email if wg.list_email else None,
                        list_subscribe=wg.list_subscribe if wg.list_subscribe else None,
                        list_archive=wg.list_archive if wg.list_archive else None,
                        urls=format_urls(wg.groupurl_set.all()),
                        telechat_date=initial_telechat_date,
                        )
            hide = None
        else:
            init = dict(ad=login.id,
                        )
            hide = ['chairs', 'techadv', 'list_email', 'list_subscribe', 'list_archive', 'urls', 'telechat_date']
        form = EditInfoForm(initial=init, cur_acronym=wg.acronym if wg else None, hide=hide)

    return render_to_response('wgcharter/edit_info.html',
                              dict(wg=wg,
                                   form=form,
                                   user=request.user,
                                   login=login),
                              context_instance=RequestContext(request))

class ConcludeForm(forms.Form):
    instructions = forms.CharField(widget=forms.Textarea, required=True)

@group_required('Area_Director','Secretariat')
def conclude(request, name):
    """Request the closing of a WG, prompting for instructions."""
    try:
        wg = Group.objects.get(acronym=name)
    except Group.DoesNotExist:
        wglist = GroupHistory.objects.filter(acronym=name)
        if wglist:
            return redirect('wg_conclude', name=wglist[0].group.acronym)
        else:
            raise Http404

    login = request.user.get_profile()

#                 if state != wg.state:
#                     # WG state changed
#                     change = True
#                     save_group_in_history(wg)

#                     prev = wg.state
#                     wg.state = state

#                     ge = log_group_state_changed(request, wg, login, comment)
                
#                     wg.save()

    if request.method == 'POST':
        form = ConcludeForm(request.POST)
        if form.is_valid():
            instructions = form.cleaned_data['instructions']

            email_secretariat(request, wg, "conclude", instructions)

            return redirect('wg_view', name=wg.acronym)
    else:
        form = ConcludeForm()

    return render_to_response('wgcharter/conclude.html',
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
            return redirect('wg_view', name=wg.acronym)
    else:
        form = AddCommentForm()
  
    return render_to_response('wgcharter/add_comment.html',
                              dict(wg=wg,
                                   form=form),
                              context_instance=RequestContext(request))

