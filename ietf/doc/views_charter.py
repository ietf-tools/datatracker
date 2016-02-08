import os, datetime, shutil, textwrap, json

from django.http import HttpResponse, HttpResponseRedirect, HttpResponseNotFound, HttpResponseForbidden, Http404
from django.shortcuts import render_to_response, get_object_or_404, redirect
from django.core.urlresolvers import reverse as urlreverse
from django.template import RequestContext
from django import forms
from django.utils.safestring import mark_safe
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required

import debug                            # pyflakes:ignore

from ietf.doc.models import ( Document, DocHistory, State, DocEvent, BallotDocEvent,
    BallotPositionDocEvent, InitialReviewDocEvent, NewRevisionDocEvent,
    WriteupDocEvent, save_document_in_history )
from ietf.doc.utils import ( add_state_change_event, close_open_ballots,
    create_ballot_if_not_open, get_chartering_type )
from ietf.doc.utils_charter import ( historic_milestones_for_charter,
    approved_revision, default_review_text, default_action_text,
    generate_ballot_writeup, generate_issue_ballot_mail, next_approved_revision, next_revision,
    derive_new_work_text )
from ietf.doc.mails import email_state_changed, email_charter_internal_review
from ietf.group.models import ChangeStateGroupEvent, MilestoneGroupEvent
from ietf.group.utils import save_group_in_history, save_milestone_in_history, can_manage_group_type
from ietf.ietfauth.utils import has_role, role_required
from ietf.name.models import GroupStateName
from ietf.person.models import Person
from ietf.utils.history import find_history_active_at
from ietf.utils.mail import send_mail_preformatted 
from ietf.utils.textupload import get_cleaned_text_file_content
from ietf.group.mails import email_admin_re_charter

class ChangeStateForm(forms.Form):
    charter_state = forms.ModelChoiceField(State.objects.filter(used=True, type="charter"), label="Charter state", empty_label=None, required=False)
    initial_time = forms.IntegerField(initial=0, label="Review time", help_text="(in weeks)", required=False)
    message = forms.CharField(widget=forms.Textarea, help_text="Leave blank to change state without notifying the Secretariat.", required=False, label=mark_safe("Message to the Secretariat"))
    comment = forms.CharField(widget=forms.Textarea, help_text="Optional comment for the charter history.", required=False)
    def __init__(self, *args, **kwargs):
        self.hide = kwargs.pop('hide', None)
        group = kwargs.pop('group')
        super(ChangeStateForm, self).__init__(*args, **kwargs)
        state_field = self.fields["charter_state"]
        if group.type_id == "wg":
            state_field.queryset = state_field.queryset.filter(slug__in=("infrev", "intrev", "extrev", "iesgrev"))
        else:
            state_field.queryset = state_field.queryset.filter(slug__in=("intrev", "extrev", "approved"))
        # hide requested fields
        if self.hide:
            for f in self.hide:
                self.fields[f].widget = forms.HiddenInput()

@login_required
def change_state(request, name, option=None):
    """Change state of charter, notifying parties as necessary and
    logging the change as a comment."""
    charter = get_object_or_404(Document, type="charter", name=name)
    group = charter.group

    if not can_manage_group_type(request.user, group.type_id):
        return HttpResponseForbidden("You don't have permission to access this view")

    chartering_type = get_chartering_type(charter)

    initial_review = charter.latest_event(InitialReviewDocEvent, type="initial_review")
    if charter.get_state_slug() != "infrev" or (initial_review and initial_review.expires < datetime.datetime.now()) or chartering_type == "rechartering":
        initial_review = None

    login = request.user.person

    if request.method == 'POST':
        form = ChangeStateForm(request.POST, group=group)
        if form.is_valid():
            clean = form.cleaned_data
            charter_rev = charter.rev

            if option in ("initcharter", "recharter"):
                if group.type_id == "wg":
                    charter_state = State.objects.get(used=True, type="charter", slug="infrev")
                else:
                    charter_state = clean['charter_state']

                # make sure we have the latest revision set, if we
                # abandoned a charter before, we could have reset the
                # revision to latest approved
                prev_revs = charter.history_set.order_by('-rev')[:1]
                if prev_revs and prev_revs[0].rev > charter_rev:
                    charter_rev = prev_revs[0].rev

                if "-" not in charter_rev:
                    charter_rev = charter_rev + "-00"
            elif option == "abandon":
                oldstate = group.state
                if oldstate.slug in ("proposed", "bof", "unknown"):
                    charter_state = State.objects.get(used=True, type="charter", slug="notrev")
                    #TODO : set an abandoned state and leave some comments here
                    group.state = GroupStateName.objects.get(slug='abandon')
                    group.save()
                    e = ChangeStateGroupEvent(group=group, type="changed_state")
                    e.time = group.time
                    e.by = login
                    e.state_id = group.state.slug
                    e.desc = "Group state changed to %s from %s" % (group.state, oldstate)
                    e.save()

                else:
                    charter_state = State.objects.get(used=True, type="charter", slug="approved")
                    charter_rev = approved_revision(charter.rev)
            else:
                charter_state = clean['charter_state']

            comment = clean['comment'].rstrip()
            message = clean['message']

            if charter_state != charter.get_state():
                # Charter state changed
                save_document_in_history(charter)

                prev_state = charter.get_state()
                new_state = charter_state
                charter.set_state(new_state)
                charter.rev = charter_rev

                if option != "abandon":
                    add_state_change_event(charter, login, prev_state, new_state)
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

                if charter_state.slug == 'intrev':
                    email_charter_internal_review(request,charter)

                if message or charter_state.slug == "intrev" or charter_state.slug == "extrev":
                    email_admin_re_charter(request, group, "Charter state changed to %s" % charter_state.name, message,'charter_state_edit_admin_needed')

                # TODO - do we need a seperate set of recipients for state changes to charters vrs other kind of documents
                email_state_changed(request, charter, "State changed to %s." % charter_state, 'doc_state_edited')

                if charter_state.slug == "intrev" and group.type_id == "wg":
                    if request.POST.get("ballot_wo_extern"):
                        create_ballot_if_not_open(charter, login, "r-wo-ext")
                    else:
                        create_ballot_if_not_open(charter, login, "r-extrev")
                    default_review_text(group, charter, login)
                    default_action_text(group, charter, login)
                elif charter_state.slug in ["extrev","iesgrev"]:
                    create_ballot_if_not_open(charter, login, "approve")
                elif charter_state.slug == "approved":
                    change_group_state_after_charter_approval(group, login)
                    fix_charter_revision_after_approval(charter, login)

            if charter_state.slug == "infrev" and clean["initial_time"] and clean["initial_time"] != 0:
                e = InitialReviewDocEvent(type="initial_review", by=login, doc=charter)
                e.expires = datetime.datetime.now() + datetime.timedelta(weeks=clean["initial_time"])
                e.desc = "Initial review time expires %s" % e.expires.strftime("%Y-%m-%d")
                e.save()

            return redirect('doc_view', name=charter.name)
    else:
        hide = ['initial_time']
        s = charter.get_state()
        init = dict(charter_state=s.pk if s and option != "recharter" else None)

        if option == "abandon":
            hide = ['initial_time', 'charter_state']

        if group.type_id == "wg":
            if option == "recharter":
                hide = ['initial_time', 'charter_state', 'message']
                init = dict()
            elif option == "initcharter":
                hide = ['charter_state']
                init = dict(initial_time=1, message='%s has initiated chartering of the proposed %s:\n "%s" (%s).' % (login.plain_name(), group.type.name, group.name, group.acronym))
            elif option == "abandon":
                hide = ['initial_time', 'charter_state']
                init = dict(message='%s has abandoned the chartering effort on the %s:\n "%s" (%s).' % (login.plain_name(), group.type.name, group.name, group.acronym))
        form = ChangeStateForm(hide=hide, initial=init, group=group)

    prev_charter_state = None
    charter_hists = DocHistory.objects.filter(doc=charter).exclude(states__type="charter", states__slug=charter.get_state_slug()).order_by("-time")[:1]
    if charter_hists:
        prev_charter_state = charter_hists[0].get_state()

    title = {
        "initcharter": "Initiate chartering of %s %s" % (group.acronym, group.type.name),
        "recharter": "Recharter %s %s" % (group.acronym, group.type.name),
        "abandon": "Abandon effort on %s %s" % (group.acronym, group.type.name),
        }.get(option)
    if not title:
        title = "Change chartering state of %s %s" % (group.acronym, group.type.name)

    def state_pk(slug):
        return State.objects.get(used=True, type="charter", slug=slug).pk

    info_msg = {}
    if group.type_id == "wg":
        info_msg[state_pk("infrev")] = 'The proposed charter for %s "%s" (%s) has been set to Informal IESG review by %s.' % (group.type.name, group.name, group.acronym, login.plain_name())
        info_msg[state_pk("intrev")] = 'The proposed charter for %s "%s" (%s) has been set to Internal review by %s.\nPlease place it on the next IESG telechat if it has not already been placed.' % (group.type.name, group.name, group.acronym, login.plain_name())
        info_msg[state_pk("extrev")] = 'The proposed charter for %s "%s" (%s) has been set to External review by %s.\nPlease send out the external review announcement to the appropriate lists.\n\nSend the announcement to other SDOs: Yes\nAdditional recipients of the announcement: ' % (group.type.name, group.name, group.acronym, login.plain_name())

    states_for_ballot_wo_extern = State.objects.none()
    if group.type_id == "wg":
        states_for_ballot_wo_extern = State.objects.filter(used=True, type="charter", slug="intrev").values_list("pk", flat=True)

    return render_to_response('doc/charter/change_state.html',
                              dict(form=form,
                                   doc=group.charter,
                                   login=login,
                                   option=option,
                                   prev_charter_state=prev_charter_state,
                                   title=title,
                                   initial_review=initial_review,
                                   chartering_type=chartering_type,
                                   info_msg=json.dumps(info_msg),
                                   states_for_ballot_wo_extern=json.dumps(list(states_for_ballot_wo_extern)),
                                   ),
                              context_instance=RequestContext(request))

class ChangeTitleForm(forms.Form):
    charter_title = forms.CharField(widget=forms.TextInput, label="Charter title", help_text="Enter new charter title.", required=True)
    message = forms.CharField(widget=forms.Textarea, help_text="Leave blank to change the title without notifying the Secretariat.", required=False, label=mark_safe("Message to Secretariat"))
    comment = forms.CharField(widget=forms.Textarea, help_text="Optional comment for the charter history.", required=False)
    def __init__(self, *args, **kwargs):
        charter = kwargs.pop('charter')
        super(ChangeTitleForm, self).__init__(*args, **kwargs)
        charter_title_field = self.fields["charter_title"]
        charter_title_field.initial = charter.title;

@login_required
def change_title(request, name, option=None):
    """Change title of charter, notifying parties as necessary and
    logging the title as a comment."""
    charter = get_object_or_404(Document, type="charter", name=name)
    group = charter.group
    if not can_manage_group_type(request.user, group.type_id):
        return HttpResponseForbidden("You don't have permission to access this view")
    login = request.user.person
    if request.method == 'POST':
        form = ChangeTitleForm(request.POST, charter=charter)
        if form.is_valid():
            clean = form.cleaned_data
            charter_rev = charter.rev
            new_title = clean['charter_title']
            comment = clean['comment'].rstrip()
            message = clean['message']
            prev_title = charter.title
            if new_title != prev_title:
                # Charter title changed
                save_document_in_history(charter)
                charter.title=new_title
                charter.rev = charter_rev
                if not comment:
                    comment = "Changed charter title from '%s' to '%s'." % (prev_title, new_title)
                event = DocEvent(type="added_comment", doc=charter, by=login)
                event.desc = comment
                event.save()
                charter.time = datetime.datetime.now()
                charter.save()
                if message:
                    email_admin_re_charter(request, group, "Charter title changed to %s" % new_title, message,'charter_state_edit_admin_needed')
                email_state_changed(request, charter, "Title changed to %s." % new_title,'doc_state_edited')
            return redirect('doc_view', name=charter.name)
    else:
        form = ChangeTitleForm(charter=charter)
    title = "Change charter title of %s %s" % (group.acronym, group.type.name)
    return render_to_response('doc/charter/change_title.html',
                              dict(form=form,
                                   doc=group.charter,
                                   login=login,
                                   title=title,
                                   ),
                              context_instance=RequestContext(request))

class AdForm(forms.Form):
    ad = forms.ModelChoiceField(Person.objects.filter(role__name="ad", role__group__state="active", role__group__type="area").order_by('name'),
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
    login = request.user.person

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

            return redirect('doc_view', name=charter.name)
    else:
        init = { "ad" : charter.ad_id }
        form = AdForm(initial=init)

    return render_to_response('doc/charter/change_ad.html',
                              {'form':   form,
                               'charter': charter,
                              },
                              context_instance = RequestContext(request))


class UploadForm(forms.Form):
    content = forms.CharField(widget=forms.Textarea, label="Charter text", help_text="Edit the charter text.", required=False)
    txt = forms.FileField(label=".txt format", help_text="Or upload a .txt file.", required=False)

    def clean_content(self):
        return self.cleaned_data["content"].replace("\r", "")

    def clean_txt(self):
        return get_cleaned_text_file_content(self.cleaned_data["txt"])

    def save(self, group, rev):
        filename = os.path.join(settings.CHARTER_PATH, '%s-%s.txt' % (group.charter.canonical_name(), rev))
        with open(filename, 'wb') as destination:
            if self.cleaned_data['txt']:
                destination.write(self.cleaned_data['txt'])
            else:
                destination.write(self.cleaned_data['content'].encode("utf-8"))

@login_required
def submit(request, name=None, option=None):
    if not name.startswith('charter-'):
        raise Http404

    charter = get_object_or_404(Document, type="charter", name=name)
    group = charter.group

    if not can_manage_group_type(request.user, group.type_id):
        return HttpResponseForbidden("You don't have permission to access this view")

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
            save_group_in_history(group)

            charter.rev = next_rev

            e = NewRevisionDocEvent(doc=charter, by=request.user.person, type="new_revision")
            e.desc = "New version available: <b>%s-%s.txt</b>" % (charter.canonical_name(), charter.rev)
            e.rev = charter.rev
            e.save()

            # Save file on disk
            form.save(group, charter.rev)

            if option in ['initcharter','recharter'] and charter.ad == None:
                charter.ad = getattr(group.ad_role(),'person',None)

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
    return render_to_response('doc/charter/submit.html',
                              {'form': form,
                               'next_rev': next_rev,
                               'group': group,
                               'name': name },
                              context_instance=RequestContext(request))

class ActionAnnouncementTextForm(forms.Form):
    announcement_text = forms.CharField(widget=forms.Textarea, required=True)

    def clean_announcement_text(self):
        return self.cleaned_data["announcement_text"].replace("\r", "")


class ReviewAnnouncementTextForm(forms.Form):
    announcement_text = forms.CharField(widget=forms.Textarea, required=True)
    new_work_text = forms.CharField(widget=forms.Textarea, required=True)

    def clean_announcement_text(self):
        return self.cleaned_data["announcement_text"].replace("\r", "")


@role_required('Area Director','Secretariat')
def review_announcement_text(request, name):
    """Editing of review announcement text"""
    charter = get_object_or_404(Document, type="charter", name=name)
    group = charter.group

    login = request.user.person

    existing = charter.latest_event(WriteupDocEvent, type="changed_review_announcement")
    existing_new_work = charter.latest_event(WriteupDocEvent, type="changed_new_work_text")

    if not existing:
        (existing, existing_new_work) = default_review_text(group, charter, login)

    if not existing:
        raise Http404

    if not existing_new_work:
        existing_new_work = WriteupDocEvent(doc=charter, by=login)
        existing_new_work.by = login 
        existing_new_work.type = "changed_new_work_text"
        existing_new_work.desc = "%s review text was changed" % group.type.name
        existing_new_work.text = derive_new_work_text(existing.text,group)
        existing_new_work.time = datetime.datetime.now()
        existing_new_work.save()

    new_work_text = existing_new_work.text

    form = ReviewAnnouncementTextForm(initial=dict(announcement_text=existing.text,new_work_text=new_work_text))

    if request.method == 'POST':
        form = ReviewAnnouncementTextForm(request.POST)
        if "save_text" in request.POST and form.is_valid():

            now = datetime.datetime.now()
            (e1, e2) = (None, None)

            t = form.cleaned_data['announcement_text']
            if t != existing.text:
                e1 = WriteupDocEvent(doc=charter, by=login)
                e1.by = login
                e1.type = "changed_review_announcement" 
                e1.desc = "%s review text was changed" % (group.type.name)
                e1.text = t
                e1.time = now
                e1.save()

            t = form.cleaned_data['new_work_text']
            if t != new_work_text:
                e2 = WriteupDocEvent(doc=charter, by=login)
                e2.by = login
                e2.type = "changed_new_work_text" 
                e2.desc = "%s new work message text was changed" % (group.type.name)
                e2.text = t
                e2.time = now
                e2.save()

            if e1 or e2:
                charter.time = now
                charter.save()

            if request.GET.get("next", "") == "approve":
                return redirect('charter_approve', name=charter.canonical_name())

            return redirect('doc_writeup', name=charter.canonical_name())

        if "regenerate_text" in request.POST:
            (e1, e2) = default_review_text(group, charter, login)
            form = ReviewAnnouncementTextForm(initial=dict(announcement_text=e1.text,new_work_text=e2.text))

        if any([x in request.POST for x in ['send_annc_only','send_nw_only','send_both']]) and form.is_valid():
            if any([x in request.POST for x in ['send_annc_only','send_both']]):
                parsed_msg = send_mail_preformatted(request, form.cleaned_data['announcement_text'])
                messages.success(request, "The email To: '%s' with Subject: '%s' has been sent." % (parsed_msg["To"],parsed_msg["Subject"],))
            if any([x in request.POST for x in ['send_nw_only','send_both']]):
                parsed_msg = send_mail_preformatted(request, form.cleaned_data['new_work_text'])
                messages.success(request, "The email To: '%s' with Subject: '%s' has been sent." % (parsed_msg["To"],parsed_msg["Subject"],))
            return redirect('doc_writeup', name=charter.name)

    return render_to_response('doc/charter/review_announcement_text.html',
                              dict(charter=charter,
                                   back_url=urlreverse("doc_writeup", kwargs=dict(name=charter.name)),
                                   announcement_text_form=form,
                                   ),
                              context_instance=RequestContext(request))

@role_required('Area Director','Secretariat')
def action_announcement_text(request, name):
    """Editing of action announcement text"""
    charter = get_object_or_404(Document, type="charter", name=name)
    group = charter.group

    login = request.user.person

    existing = charter.latest_event(WriteupDocEvent, type="changed_action_announcement")
    if not existing:
            existing = default_action_text(group, charter, login)

    if not existing:
        raise Http404

    form = ActionAnnouncementTextForm(initial=dict(announcement_text=existing.text))

    if request.method == 'POST':
        form = ActionAnnouncementTextForm(request.POST)
        if "save_text" in request.POST and form.is_valid():
            t = form.cleaned_data['announcement_text']
            if t != existing.text:
                e = WriteupDocEvent(doc=charter, by=login)
                e.by = login
                e.type = "changed_action_announcement" 
                e.desc = "%s action text was changed" % group.type.name
                e.text = t
                e.save()

                charter.time = e.time
                charter.save()

            if request.GET.get("next", "") == "approve":
                return redirect('charter_approve', name=charter.canonical_name())

            return redirect('doc_writeup', name=charter.canonical_name())

        if "regenerate_text" in request.POST:
            e = default_action_text(group, charter, login)
            form = ActionAnnouncementTextForm(initial=dict(announcement_text=e.text))

        if "send_text" in request.POST and form.is_valid():
            parsed_msg = send_mail_preformatted(request, form.cleaned_data['announcement_text'])
            messages.success(request, "The email To: '%s' with Subject: '%s' has been sent." % (parsed_msg["To"],parsed_msg["Subject"],))
            return redirect('doc_writeup', name=charter.name)

    return render_to_response('doc/charter/action_announcement_text.html',
                              dict(charter=charter,
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

    ballot = charter.latest_event(BallotDocEvent, type="created_ballot")
    if not ballot:
        raise Http404

    login = request.user.person

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

                existing = e

            if "send_ballot" in request.POST and approval:
                if has_role(request.user, "Area Director") and not charter.latest_event(BallotPositionDocEvent, type="changed_ballot_position", ad=login, ballot=ballot):
                    # sending the ballot counts as a yes
                    pos = BallotPositionDocEvent(doc=charter, by=login)
                    pos.type = "changed_ballot_position"
                    pos.ad = login
                    pos.pos_id = "yes"
                    pos.desc = "[Ballot Position Update] New position, %s, has been recorded for %s" % (pos.pos.name, pos.ad.plain_name())
                    pos.save()
                    # Consider mailing this position to 'ballot_saved'

                msg = generate_issue_ballot_mail(request, charter, ballot)
                send_mail_preformatted(request, msg)

                e = DocEvent(doc=charter, by=login)
                e.by = login
                e.type = "sent_ballot_announcement"
                e.desc = "Ballot has been sent"
                e.save()

                return render_to_response('doc/charter/ballot_issued.html',
                                          dict(doc=charter,
                                               ),
                                          context_instance=RequestContext(request))

    return render_to_response('doc/charter/ballot_writeupnotes.html',
                              dict(charter=charter,
                                   ballot_issued=bool(charter.latest_event(type="sent_ballot_announcement")),
                                   ballot_writeup_form=form,
                                   reissue=reissue,
                                   approval=approval,
                                   ),
                              context_instance=RequestContext(request))

def change_group_state_after_charter_approval(group, by):
    new_state = GroupStateName.objects.get(slug="active")
    if group.state == new_state:
        return None

    save_group_in_history(group)
    group.state = new_state
    group.time = datetime.datetime.now()
    group.save()

    # create an event for the group state change, too
    e = ChangeStateGroupEvent(group=group, type="changed_state")
    e.time = group.time
    e.by = by
    e.state_id = "active"
    e.desc = "Charter approved, group active"
    e.save()

    return e

def fix_charter_revision_after_approval(charter, by):
    # according to spec, 00-02 becomes 01, so copy file and record new revision
    try:
        old = os.path.join(charter.get_file_path(), '%s-%s.txt' % (charter.canonical_name(), charter.rev))
        new = os.path.join(charter.get_file_path(), '%s-%s.txt' % (charter.canonical_name(), next_approved_revision(charter.rev)))
        shutil.copy(old, new)
    except IOError:
        return HttpResponse("There was an error copying %s to %s" %
                            ('%s-%s.txt' % (charter.canonical_name(), charter.rev),
                             '%s-%s.txt' % (charter.canonical_name(), next_approved_revision(charter.rev))))

    e = NewRevisionDocEvent(doc=charter, by=by, type="new_revision")
    e.rev = next_approved_revision(charter.rev)
    e.desc = "New version available: <b>%s-%s.txt</b>" % (charter.canonical_name(), e.rev)
    e.save()

    charter.rev = e.rev
    charter.time = e.time
    charter.save()

@role_required("Secretariat")
def approve(request, name):
    """Approve charter, changing state, fixing revision, copying file to final location."""
    charter = get_object_or_404(Document, type="charter", name=name)
    group = charter.group

    login = request.user.person

    e = charter.latest_event(WriteupDocEvent, type="changed_action_announcement")
    if not e:
        announcement = default_action_text(group, charter, login).text
    else:
        announcement = e.text

    if request.method == 'POST':
        new_charter_state = State.objects.get(used=True, type="charter", slug="approved")
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

        group_state_change_event = change_group_state_after_charter_approval(group, login)
        if group_state_change_event:
            change_description += " and group state has been changed to %s" % group.state.name

        add_state_change_event(charter, login, prev_charter_state, new_charter_state)

        fix_charter_revision_after_approval(charter, login)

        email_admin_re_charter(request, group, "Charter state changed to %s" % new_charter_state.name, change_description,'charter_state_edit_admin_needed')

        # move milestones over
        milestones_to_delete = list(group.groupmilestone_set.filter(state__in=("active", "review")))

        for m in group.groupmilestone_set.filter(state="charter"):
            # see if we got this milestone already (i.e. it was copied
            # verbatim to the charter)
            found = False
            for i, o in enumerate(milestones_to_delete):
                if o.desc == m.desc and o.due == m.due and set(o.docs.all()) == set(m.docs.all()):
                    found = True
                    break

            if found:
                # keep existing, whack charter milestone
                if not o.state_id == "active":
                    save_milestone_in_history(o)
                    o.state_id = "active"
                    o.save()
                    MilestoneGroupEvent.objects.create(
                        group=group, type="changed_milestone", by=login,
                        desc="Changed milestone \"%s\", set state to active from review" % o.desc,
                        milestone=o)

                del milestones_to_delete[i]

                # don't generate a DocEvent for this, it's implicit in the approval event
                save_milestone_in_history(m)
                m.state_id = "deleted"
                m.save()
            else:
                # move charter milestone
                save_milestone_in_history(m)
                m.state_id = "active"
                m.save()

                MilestoneGroupEvent.objects.create(
                    group=group, type="changed_milestone", by=login,
                    desc="Added milestone \"%s\", due %s, from approved charter" % (m.desc, m.due),
                    milestone=m)

        for m in milestones_to_delete:
            save_milestone_in_history(m)
            m.state_id = "deleted"
            m.save()

            MilestoneGroupEvent.objects.create(
                group=group, type="changed_milestone", by=login,
                desc="Deleted milestone \"%s\", not present in approved charter" % m.desc,
                milestone=m)

        # send announcement
        send_mail_preformatted(request, announcement)

        return HttpResponseRedirect(charter.get_absolute_url())

    return render_to_response('doc/charter/approve.html',
                              dict(charter=charter,
                                   announcement=announcement),
                              context_instance=RequestContext(request))

def charter_with_milestones_txt(request, name, rev):
    charter = get_object_or_404(Document, type="charter", docalias__name=name)

    revision_event = charter.latest_event(NewRevisionDocEvent, type="new_revision", rev=rev)
    if not revision_event:
        return HttpResponseNotFound("Revision %s not found in database" % rev)

    # read charter text
    c = find_history_active_at(charter, revision_event.time) or charter
    filename = '%s-%s.txt' % (c.canonical_name(), rev)

    charter_text = ""

    try:
        with open(os.path.join(settings.CHARTER_PATH, filename), 'r') as f:
            charter_text = unicode(f.read(), errors='ignore')
    except IOError:
        charter_text = "Error reading charter text %s" % filename

    milestones = historic_milestones_for_charter(charter, rev)

    # wrap the output nicely
    wrapper = textwrap.TextWrapper(initial_indent="", subsequent_indent=" " * 11, width=80, break_long_words=False)
    for m in milestones:
        m.desc_filled = wrapper.fill(m.desc)

    return render_to_response('doc/charter/charter_with_milestones.txt',
                              dict(charter_text=charter_text,
                                   milestones=milestones),
                              context_instance=RequestContext(request),
                              content_type="text/plain; charset=%s"%settings.DEFAULT_CHARSET)
