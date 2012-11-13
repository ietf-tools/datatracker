import re, os, string, datetime, shutil

from django.http import HttpResponse, HttpResponseRedirect, Http404
from django.shortcuts import render_to_response, get_object_or_404, redirect
from django.template.loader import render_to_string
from django.core.urlresolvers import reverse as urlreverse
from django.core.urlresolvers import reverse
from django.template import RequestContext
from django import forms
from django.forms.util import ErrorList
from django.utils import simplejson
from django.utils.html import strip_tags, escape
from django.utils.safestring import mark_safe
from django.conf import settings
from django.contrib import messages

from ietf.utils.mail import send_mail_text, send_mail_preformatted
from ietf.utils.textupload import get_cleaned_text_file_content
from ietf.ietfauth.decorators import has_role, role_required
from ietf.iesg.models import TelechatDate
from ietf.doc.models import *
from ietf.doc.utils import *
from ietf.name.models import *
from ietf.person.models import *
from ietf.group.models import *
from ietf.group.utils import save_group_in_history
from ietf.wgcharter.mails import *
from ietf.wgcharter.utils import *

import debug

class ChangeStateForm(forms.Form):
    charter_state = forms.ModelChoiceField(State.objects.filter(type="charter", slug__in=["infrev", "intrev", "extrev", "iesgrev"]), label="Charter state", empty_label=None, required=False)
    initial_time = forms.IntegerField(initial=0, label="Review time", help_text="(in weeks)", required=False)
    message = forms.CharField(widget=forms.Textarea, help_text="Leave blank to change state without notifying the Secretariat", required=False, label=mark_safe("Message to<br> Secretariat"))
    comment = forms.CharField(widget=forms.Textarea, help_text="Optional comment for the charter history", required=False)
    def __init__(self, *args, **kwargs):
        self.hide = kwargs.pop('hide', None)
        super(ChangeStateForm, self).__init__(*args, **kwargs)
        # hide requested fields
        if self.hide:
            for f in self.hide:
                self.fields[f].widget = forms.HiddenInput

@role_required("Area Director", "Secretariat")
def change_state(request, name, option=None):
    """Change state of WG and charter, notifying parties as necessary
    and logging the change as a comment."""
    charter = get_object_or_404(Document, type="charter", name=name)
    wg = charter.group

    chartering_type = get_chartering_type(charter)

    initial_review = charter.latest_event(InitialReviewDocEvent, type="initial_review")
    if charter.get_state_slug() != "infrev" or (initial_review and initial_review.expires < datetime.datetime.now()) or chartering_type == "rechartering":
        initial_review = None

    login = request.user.get_profile()

    if request.method == 'POST':
        form = ChangeStateForm(request.POST)
        if form.is_valid():
            clean = form.cleaned_data
            charter_rev = charter.rev

            if option in ("initcharter", "recharter"):
                charter_state = State.objects.get(type="charter", slug="infrev")
                # make sure we have the latest revision set, if we
                # abandoned a charter before, we could have reset the
                # revision to latest approved
                prev_revs = charter.history_set.order_by('-rev')[:1]
                if prev_revs and prev_revs[0].rev > charter_rev:
                    charter_rev = prev_revs[0].rev

                if "-" not in charter_rev:
                    charter_rev = charter_rev + "-00"
            elif option == "abandon":
                oldstate = wg.state_id
                if oldstate in ("proposed","bof","unknown"):
                    charter_state = State.objects.get(type="charter", slug="notrev")
                    #TODO : set an abandoned state and leave some comments here
                    wg.state=GroupStateName.objects.get(slug='abandon')
                    wg.save()
                    e = ChangeStateGroupEvent(group=wg, type="changed_state")
                    e.time = wg.time
                    e.by = login
                    e.state_id = clean["state"].slug
                    e.desc = "Group state changed to %s from %s" % clean["state"].name,oldstate
                    e.save()
                    
                else:
                    charter_state = State.objects.get(type="charter", slug="approved")
                    charter_rev = approved_revision(charter.rev)
            else:
                charter_state = clean['charter_state']

            comment = clean['comment'].rstrip()
            message = clean['message']

            if charter_state != charter.get_state():
                # Charter state changed
                save_document_in_history(charter)

                prev = charter.get_state()
                charter.set_state(charter_state)
                charter.rev = charter_rev

                if option != "abandon":
                    log_state_changed(request, charter, login, prev)
                else:
                    # kill hanging ballots
                    close_open_ballots(charter, login)

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

                if message:
                    email_secretariat(request, wg, "state-%s" % charter_state.slug, message)

                email_state_changed(request, charter, "State changed to %s." % charter_state)

                if charter_state.slug == "intrev":
                    if request.POST.get("ballot_wo_extern"):
                        create_ballot_if_not_open(charter, login, "r-wo-ext")
                    else:
                        create_ballot_if_not_open(charter, login, "r-extrev")
                    default_review_text(wg, charter, login)
                    default_action_text(wg, charter, login)
                elif charter_state.slug == "iesgrev":
                    create_ballot_if_not_open(charter, login, "approve")

            if charter_state.slug == "infrev" and clean["initial_time"] and clean["initial_time"] != 0:
                e = InitialReviewDocEvent(type="initial_review", by=login, doc=charter)
                e.expires = datetime.datetime.now() + datetime.timedelta(weeks=clean["initial_time"])
                e.desc = "Initial review time expires %s" % e.expires.strftime("%Y-%m-%d")
                e.save()

            return redirect('doc_view', name=charter.name)
    else:
        if option == "recharter":
            hide = ['initial_time', 'charter_state', 'message']
            init = dict()
        elif option == "initcharter":
            hide = ['charter_state']
            init = dict(initial_time=1, message='%s has initiated chartering of the proposed WG:\n "%s" (%s).' % (login.plain_name(), wg.name, wg.acronym))
        elif option == "abandon":
            hide = ['initial_time', 'charter_state']
            init = dict(message='%s has abandoned the chartering effort on the WG:\n "%s" (%s).' % (login.plain_name(), wg.name, wg.acronym))
        else:
            hide = ['initial_time']
            s = charter.get_state()
            init = dict(charter_state=s.pk if s else None)
        form = ChangeStateForm(hide=hide, initial=init)

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
        title = "Change chartering state of WG %s" % wg.acronym

    def state_pk(slug):
        return State.objects.get(type="charter", slug=slug).pk

    info_msg = {
        state_pk("infrev"): 'The WG "%s" (%s) has been set to Informal IESG review by %s.' % (wg.name, wg.acronym, login.plain_name()),
        state_pk("intrev"): 'The WG "%s" (%s) has been set to Internal review by %s.\nPlease place it on the next IESG telechat and inform the IAB.' % (wg.name, wg.acronym, login.plain_name()),
        state_pk("extrev"): 'The WG "%s" (%s) has been set to External review by %s.\nPlease send out the external review announcement to the appropriate lists.\n\nSend the announcement to other SDOs: Yes\nAdditional recipients of the announcement: ' % (wg.name, wg.acronym, login.plain_name()),
        }

    states_for_ballot_wo_extern = State.objects.filter(type="charter", slug="intrev").values_list("pk", flat=True)

    return render_to_response('wgcharter/change_state.html',
                              dict(form=form,
                                   doc=wg.charter,
                                   login=login,
                                   option=option,
                                   prev_charter_state=prev_charter_state,
                                   title=title,
                                   initial_review=initial_review,
                                   chartering_type=chartering_type,
                                   info_msg=simplejson.dumps(info_msg),
                                   states_for_ballot_wo_extern=simplejson.dumps(list(states_for_ballot_wo_extern)),
                                   ),
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
    doc = get_object_or_404(Document, type="charter", name=name)
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
                                   login=login,
                                   okstates=['intrev','extrev','iesgrev'],
                                   ),
                              context_instance=RequestContext(request))

class NotifyForm(forms.Form):
    notify = forms.CharField(max_length=255, help_text="List of email addresses to receive state notifications, separated by comma", label="Notification list", required=False)

    def clean_notify(self):
        return self.cleaned_data["notify"].strip()

@role_required("Area Director", "Secretariat")
def edit_notify(request, name):
    doc = get_object_or_404(Document, type="charter", name=name)
    login = request.user.get_profile()

    init = {'notify': doc.notify}

    if request.method == "POST":
        form = NotifyForm(request.POST, initial=init)
        if form.is_valid():
            n = form.cleaned_data["notify"]
            if n != doc.notify:
                save_document_in_history(doc)

                e = DocEvent(doc=doc, by=login)
                e.desc = "Notification list changed to %s" % (escape(n) or "none")
                if doc.notify:
                    e.desc += " from %s" % escape(doc.notify)
                e.type = "changed_document"
                e.save()

                doc.notify = n
                doc.time = e.time
                doc.save()

            return redirect("doc_view", name=doc.name)
    else:
        form = NotifyForm(initial=init)

    return render_to_response('wgcharter/edit_notify.html',
                              dict(doc=doc,
                                   form=form,
                                   user=request.user,
                                   login=login),
                              context_instance=RequestContext(request))

class AdForm(forms.Form):
    ad = forms.ModelChoiceField(Person.objects.filter(role__name="ad", role__group__state="active").order_by('name'),
                                label="Responsible AD", empty_label="(None)", required=True)

    def __init__(self, *args, **kwargs):
        super(self.__class__, self).__init__(*args, **kwargs)

        # if previous AD is now ex-AD, append that person to the list
        ad_pk = self.initial.get('ad')
        choices = self.fields['ad'].choices
        if ad_pk and ad_pk not in [pk for pk, name in choices]:
            self.fields['ad'].choices = list(choices) + [("", "-------"), (ad_pk, Person.objects.get(pk=ad_pk).plain_name())]

@role_required("Area Director", "Secretariat")
def edit_ad(request, name):
    """Change the responsible Area Director for this charter."""

    charter = get_object_or_404(Document, type="charter", name=name)
    login = request.user.get_profile()

    if request.method == 'POST':
        form = AdForm(request.POST)
        if form.is_valid():
            new_ad = form.cleaned_data['ad']
            if new_ad != charter.ad:
                save_document_in_history(charter)
                e = DocEvent(doc=charter, by=login)
                e.desc = "Responsible AD changed to %s" % new_ad.plain_name()
                if charter.ad:
                   e.desc += " from %s" % charter.ad.plain_name()
                e.type = "changed_document"
                e.save()
                charter.ad = new_ad
                charter.time = e.time
                charter.save()

            return HttpResponseRedirect(reverse('doc_view', kwargs={'name': charter.name}))
    else:
        init = { "ad" : charter.ad_id }
        form = AdForm(initial=init)

    return render_to_response('wgcharter/change_ad.html',
                              {'form':   form,
                               'charter': charter,
                              },
                              context_instance = RequestContext(request))


class UploadForm(forms.Form):
    content = forms.CharField(widget=forms.Textarea, label="Charter text", help_text="Edit the charter text", required=False)
    txt = forms.FileField(label=".txt format", help_text="Or upload a .txt file", required=False)

    def clean_content(self):
        return self.cleaned_data["content"].replace("\r", "")

    def clean_txt(self):
        return get_cleaned_text_file_content(self.cleaned_data["txt"])

    def save(self, wg, rev):
        filename = os.path.join(settings.CHARTER_PATH, '%s-%s.txt' % (wg.charter.canonical_name(), rev))
        with open(filename, 'wb') as destination:
            if self.cleaned_data['txt']:
                destination.write(self.cleaned_data['txt'])
            else:
                destination.write(self.cleaned_data['content'].encode("utf-8"))

@role_required('Area Director','Secretariat')
def submit(request, name=None, acronym=None, option=None):
    if name:
        if not name.startswith('charter-'):
            name = "charter-ietf-" + name
    elif acronym:
        name = "charter-ietf-" + acronym
    charter = get_object_or_404(Document, type="charter", name=name)
    wg = charter.group

    login = request.user.get_profile()

    path = os.path.join(settings.CHARTER_PATH, '%s-%s.txt' % (charter.canonical_name(), charter.rev))
    not_uploaded_yet = charter.rev.endswith("-00") and not os.path.exists(path)

    if not_uploaded_yet:
        # this case is special - we recently chartered or rechartered and have no file yet
        next_rev = charter.rev
    else:
        # search history for possible collisions with abandoned efforts
        prev_revs = list(charter.history_set.order_by('-time').values_list('rev', flat=True))
        next_rev = next_revision(charter.rev)
        while next_rev in prev_revs:
            next_rev = next_revision(next_rev)

    if request.method == 'POST':
        form = UploadForm(request.POST, request.FILES)
        if form.is_valid():
            save_document_in_history(charter)
            # Also save group history so we can search for it
            save_group_in_history(wg)

            charter.rev = next_rev

            e = NewRevisionDocEvent(doc=charter, by=login, type="new_revision")
            e.desc = "New version available: <b>%s-%s.txt</b>" % (charter.canonical_name(), charter.rev)
            e.rev = charter.rev
            e.save()
            
            # Save file on disk
            form.save(wg, charter.rev)

            charter.time = datetime.datetime.now()
            charter.save()

            if option:
                return redirect('charter_startstop_process', name=charter.name, option=option)
            else:
                return redirect("doc_view", name=charter.name)
    else:
        init = { "content": ""}
        c = charter

        if not_uploaded_yet:
            # use text from last approved revision
            last_approved = charter.rev.split("-")[0]
            h = charter.history_set.filter(rev=last_approved).order_by("-time", "-id")
            if h:
                c = h[0]

        filename = os.path.join(settings.CHARTER_PATH, '%s-%s.txt' % (c.canonical_name(), c.rev))

        try:
            with open(filename, 'r') as f:
                init["content"] = f.read()
        except IOError:
            pass
        form = UploadForm(initial=init)
    return render_to_response('wgcharter/submit.html',
                              {'form': form,
                               'next_rev': next_rev,
                               'wg': wg },
                              context_instance=RequestContext(request))

class AnnouncementTextForm(forms.Form):
    announcement_text = forms.CharField(widget=forms.Textarea, required=True)

    def clean_announcement_text(self):
        return self.cleaned_data["announcement_text"].replace("\r", "")

@role_required('Area Director','Secretariat')
def announcement_text(request, name, ann):
    """Editing of announcement text"""
    charter = get_object_or_404(Document, type="charter", name=name)
    wg = charter.group

    login = request.user.get_profile()

    if ann == "action":
        existing = charter.latest_event(WriteupDocEvent, type="changed_action_announcement")
    elif ann == "review":
        existing = charter.latest_event(WriteupDocEvent, type="changed_review_announcement")
    if not existing:
        if ann == "action":
            existing = default_action_text(wg, charter, login)
        elif ann == "review":
            existing = default_review_text(wg, charter, login)

    form = AnnouncementTextForm(initial=dict(announcement_text=existing.text))

    if request.method == 'POST':
        form = AnnouncementTextForm(request.POST)
        if "save_text" in request.POST and form.is_valid():
            t = form.cleaned_data['announcement_text']
            if t != existing.text:
                e = WriteupDocEvent(doc=charter, by=login)
                e.by = login
                e.type = "changed_%s_announcement" % ann
                e.desc = "WG %s text was changed" % ann
                e.text = t
                e.save()
                
                charter.time = e.time
                charter.save()

            if request.GET.get("next", "") == "approve":
                return redirect('charter_approve', name=charter.canonical_name())

            return redirect('doc_writeup', name=charter.canonical_name())

        if "regenerate_text" in request.POST:
            if ann == "action":
                e = default_action_text(wg, charter, login)
            elif ann == "review":
                e = default_review_text(wg, charter, login)
            # make sure form has the updated text
            form = AnnouncementTextForm(initial=dict(announcement_text=e.text))

        if "send_text" in request.POST and form.is_valid():
            msg = form.cleaned_data['announcement_text']
            import email
            parsed_msg = email.message_from_string(msg.encode("utf-8"))

            send_mail_text(request, parsed_msg["To"],
                           parsed_msg["From"], parsed_msg["Subject"],
                           parsed_msg.get_payload())
            messages.success(request, "The email To: '%s' with Subjet: '%s' has been sent." % (parsed_msg["To"],parsed_msg["Subject"],))
            return redirect('doc_writeup', name=charter.name)

    return render_to_response('wgcharter/announcement_text.html',
                              dict(charter=charter,
                                   announcement=ann,
                                   back_url=urlreverse("doc_writeup", kwargs=dict(name=charter.name)),
                                   announcement_text_form=form,
                                   ),
                              context_instance=RequestContext(request))

class BallotWriteupForm(forms.Form):
    ballot_writeup = forms.CharField(widget=forms.Textarea, required=True)

    def clean_ballot_writeup(self):
        return self.cleaned_data["ballot_writeup"].replace("\r", "")
        
@role_required('Area Director','Secretariat')
def ballot_writeupnotes(request, name):
    """Editing of ballot write-up and notes"""
    charter = get_object_or_404(Document, type="charter", name=name)
    wg = charter.group

    ballot = charter.latest_event(BallotDocEvent, type="created_ballot")
    if not ballot:
        raise Http404()

    login = request.user.get_profile()

    approval = charter.latest_event(WriteupDocEvent, type="changed_action_announcement")
    
    existing = charter.latest_event(WriteupDocEvent, type="changed_ballot_writeup_text")
    if not existing:
        existing = generate_ballot_writeup(request, charter)

    reissue = charter.latest_event(DocEvent, type="sent_ballot_announcement")
        
    form = BallotWriteupForm(initial=dict(ballot_writeup=existing.text))

    if request.method == 'POST' and ("save_ballot_writeup" in request.POST or "send_ballot" in request.POST):
        form = BallotWriteupForm(request.POST)
        if form.is_valid():
            t = form.cleaned_data["ballot_writeup"]
            if t != existing.text:
                e = WriteupDocEvent(doc=charter, by=login)
                e.by = login
                e.type = "changed_ballot_writeup_text"
                e.desc = "Ballot writeup was changed"
                e.text = t
                e.save()

            if "send_ballot" in request.POST and approval:
                if has_role(request.user, "Area Director") and not charter.latest_event(BallotPositionDocEvent, type="changed_ballot_position", ad=login, ballot=ballot):
                    # sending the ballot counts as a yes
                    pos = BallotPositionDocEvent(doc=charter, by=login)
                    pos.type = "changed_ballot_position"
                    pos.ad = login
                    pos.pos_id = "yes"
                    pos.desc = "[Ballot Position Update] New position, %s, has been recorded for %s" % (pos.pos.name, pos.ad.plain_name())
                    pos.save()

                msg = generate_issue_ballot_mail(request, charter, ballot)
                send_mail_preformatted(request, msg)

                e = DocEvent(doc=charter, by=login)
                e.by = login
                e.type = "sent_ballot_announcement"
                e.desc = "Ballot has been sent"
                e.save()

                return render_to_response('wgcharter/ballot_issued.html',
                                          dict(doc=charter,
                                               ),
                                          context_instance=RequestContext(request))
                        

    return render_to_response('wgcharter/ballot_writeupnotes.html',
                              dict(charter=charter,
                                   ballot_issued=bool(charter.latest_event(type="sent_ballot_announcement")),
                                   ballot_writeup_form=form,
                                   reissue=reissue,
                                   approval=approval,
                                   ),
                              context_instance=RequestContext(request))

@role_required("Secretariat")
def approve(request, name):
    """Approve charter, changing state, fixing revision, copying file to final location."""
    charter = get_object_or_404(Document, type="charter", name=name)
    wg = charter.group

    login = request.user.get_profile()

    e = charter.latest_event(WriteupDocEvent, type="changed_action_announcement")
    if not e:
        announcement = default_action_text(wg, charter, login).text
    else:
        announcement = e.text

    if request.method == 'POST':
        new_charter_state = State.objects.get(type="charter", slug="approved")
        prev_charter_state = charter.get_state()

        save_document_in_history(charter)
        charter.set_state(new_charter_state)

        close_open_ballots(charter, login)

        # approve
        e = DocEvent(doc=charter, by=login)
        e.type = "iesg_approved"
        e.desc = "IESG has approved the charter"
        e.save()

        change_description = e.desc

        new_state = GroupStateName.objects.get(slug="active")
        if wg.state != new_state:
            # update history with current state
            save_group_in_history(wg)
            # change wg state and save the wg
            prev_state = wg.state
            wg.state = new_state
            wg.time = e.time
            wg.save()
            # create an event for the wg state change, too
            e = ChangeStateGroupEvent(group=wg, type="changed_state")
            e.time = wg.time
            e.by = login
            e.state_id = "proposed"
            e.desc = "Proposed group"
            e.save()
            # update the change description for the email
            change_description += " and WG state has been changed to %s" % new_state.name

        e = log_state_changed(request, charter, login, prev_charter_state)

        # according to spec, 00-02 becomes 01, so copy file and record new revision
        try:
            old = os.path.join(charter.get_file_path(), '%s-%s.txt' % (charter.canonical_name(), charter.rev))
            new = os.path.join(charter.get_file_path(), '%s-%s.txt' % (charter.canonical_name(), next_approved_revision(charter.rev)))
            shutil.copy(old, new)
        except IOError:
            raise Http404("Charter text %s" % filename)

        e = NewRevisionDocEvent(doc=charter, by=login, type="new_revision")
        e.rev = next_approved_revision(charter.rev)
        e.desc = "New version available: <b>%s-%s.txt</b>" % (charter.canonical_name(), e.rev)
        e.save()

        charter.rev = e.rev
        charter.time = e.time
        charter.save()

        email_secretariat(request, wg, "state-%s" % new_charter_state.slug, change_description)

        # send announcement
        send_mail_preformatted(request, announcement)

        return HttpResponseRedirect(charter.get_absolute_url())
    
    return render_to_response('wgcharter/approve.html',
                              dict(charter=charter,
                                   announcement=announcement,
                                   wg=wg),
                              context_instance=RequestContext(request))

