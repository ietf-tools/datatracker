# Copyright The IETF Trust 2011, All Rights Reserved

import re, os, string, datetime

from django.shortcuts import render_to_response, get_object_or_404, redirect
from django.core.urlresolvers import reverse
from django.template import RequestContext
from django import forms
from django.forms.util import ErrorList
from django.utils import simplejson

from utils import *
from mails import email_secretariat
from ietf.ietfauth.decorators import role_required
from ietf.iesg.models import TelechatDate

from ietf.doc.models import *
from ietf.name.models import *
from ietf.person.models import *
from ietf.group.models import *
from ietf.group.utils import save_group_in_history

class ChangeStateForm(forms.Form):
    charter_state = forms.ModelChoiceField(State.objects.filter(type="charter"), label="Charter state", empty_label=None, required=False)
    confirm_state = forms.BooleanField(widget=forms.HiddenInput, required=False, initial=True)
    initial_time = forms.IntegerField(initial=0, label="Review time", help_text="(in weeks)", required=False)
    message = forms.CharField(widget=forms.Textarea, help_text="Message to the Secretariat", required=False)
    comment = forms.CharField(widget=forms.Textarea, help_text="Optional comment for the charter history", required=False)
    def __init__(self, *args, **kwargs):
        qs = kwargs.pop('queryset', None)
        self.hide = kwargs.pop('hide', None)
        super(ChangeStateForm, self).__init__(*args, **kwargs)
        if qs:
            self.fields['charter_state'].queryset = qs
        # hide requested fields
        if self.hide:
            for f in self.hide:
                self.fields[f].widget = forms.HiddenInput

@role_required("Area Director", "Secretariat")
def change_state(request, name, option=None):
    """Change state of WG and charter, notifying parties as necessary
    and logging the change as a comment."""
    # Get WG by acronym, redirecting if there's a newer acronym
    try:
        wg = Group.objects.get(acronym=name)
    except Group.DoesNotExist:
        old = GroupHistory.objects.filter(acronym=name)
        if old:
            return redirect('wg_change_state', name=old[0].group.acronym)
        else:
            raise Http404()

    charter = set_or_create_charter(wg)

    initial_review = charter.latest_event(InitialReviewDocEvent, type="initial_review")

    login = request.user.get_profile()

    if request.method == 'POST':
        form = ChangeStateForm(request.POST)
        if form.is_valid():
            clean = form.cleaned_data
            if (initial_review and clean['charter_state'] and clean['charter_state'].slug != "infrev"
                and initial_review.expires > datetime.datetime.now() and not clean['confirm_state']):
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
                    charter_state = clean['charter_state']
                    charter_rev = charter.rev

                comment = clean['comment'].rstrip()
                message = clean['message']
                
                change = False
                if charter:
                    # The WG has a charter
                    if charter_state != charter.get_state():
                        # Charter state changed
                        change = True
                        save_document_in_history(charter)
                    
                        prev = charter.get_state()
                        charter.set_state(charter_state)
                        charter.rev = charter_rev
                        
                        if option != "abandon":
                            e = log_state_changed(request, charter, login, prev)
                        else:
                            # Special log for abandoned efforts
                            e = DocEvent(type="changed_document", doc=charter, by=login)
                            e.desc = "IESG has abandoned the chartering effort"
                            e.save()

                        if comment:
                            c = DocEvent(type="added_comment", doc=charter, by=login)
                            c.desc = comment
                            c.save()

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

                if charter_state.slug == "infrev" and clean["initial_time"] and clean["initial_time"] != 0:
                    e = InitialReviewDocEvent()
                    e.type = "initial_review"
                    e.by = login
                    e.doc = charter
                    e.expires = datetime.datetime.now() + datetime.timedelta(weeks=clean["initial_time"])
                    e.desc = "Initial review time expires %s" % e.expires.strftime("%Y-%m-%d")
                    e.save()
                
                return redirect('doc_view', name=charter.name)
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

    prev_charter_state = None
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

    def charter_pk(slug):
        return State.objects.get(type="charter", slug=slug).pk

    messages = {
        charter_pk("infrev"): "The WG %s (%s) has been set to Informal IESG review by %s." % (wg.name, wg.acronym, login.plain_name()),
        charter_pk("intrev"): "The WG %s (%s) has been set to Internal review by %s. Please place it on the next IESG telechat and inform the IAB." % (wg.name, wg.acronym, login.plain_name()),
        charter_pk("extrev"): "The WG %s (%s) has been set to External review by %s. Please send out the external review announcement to the appropriate lists.\n\nSend the announcement to other SDOs: Yes\nAdditional recipients of the announcement: " % (wg.name, wg.acronym, login.plain_name()),
        }

    return render_to_response('wgcharter/change_state.html',
                              dict(form=form,
                                   wg=wg,
                                   login=login,
                                   option=option,
                                   prev_charter_state=prev_charter_state,
                                   title=title,
                                   messages=simplejson.dumps(messages)),
                              context_instance=RequestContext(request))

class TelechatForm(forms.Form):
    telechat_date = forms.TypedChoiceField(coerce=lambda x: datetime.datetime.strptime(x, '%Y-%m-%d').date(), empty_value=None, required=False)

    def __init__(self, *args, **kwargs):
        super(self.__class__, self).__init__(*args, **kwargs)

        dates = [d.date for d in TelechatDate.objects.active().order_by('date')]
        init = kwargs['initial'].get("telechat_date")
        if init and init not in dates:
            dates.insert(0, init)

        self.fields['telechat_date'].choices = [("", "(not on agenda)")] + [(d, d.strftime("%Y-%m-%d")) for d in dates]
        

@role_required("Area Director", "Secretariat")
def telechat_date(request, name):
    wg = get_object_or_404(Group, acronym=name)
    doc = set_or_create_charter(wg)
    login = request.user.get_profile()

    e = doc.latest_event(TelechatDocEvent, type="scheduled_for_telechat")

    initial = dict(telechat_date=e.telechat_date if e else None)
    if request.method == "POST":
        form = TelechatForm(request.POST, initial=initial)

        if form.is_valid():
            update_telechat(request, doc, login, form.cleaned_data['telechat_date'])
            return redirect("doc_view", name=doc.name)
    else:
        form = TelechatForm(initial=initial)

    return render_to_response('wgcharter/edit_telechat_date.html',
                              dict(doc=doc,
                                   form=form,
                                   user=request.user,
                                   login=login),
                              context_instance=RequestContext(request))
