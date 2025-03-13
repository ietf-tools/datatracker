# Copyright The IETF Trust 2011-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import datetime
import json
import os
import textwrap

from pathlib import Path

from django.http import HttpResponseRedirect, HttpResponseNotFound, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse as urlreverse
from django import forms
from django.utils.safestring import mark_safe
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.utils.encoding import force_str
from django.utils.html import escape

import debug                            # pyflakes:ignore

from ietf.doc.models import ( Document, DocHistory, State, DocEvent,
    BallotDocEvent, BallotPositionDocEvent, InitialReviewDocEvent, NewRevisionDocEvent,
    WriteupDocEvent, TelechatDocEvent )
from ietf.doc.utils import ( add_state_change_event, close_open_ballots,
    create_ballot, get_chartering_type )
from ietf.doc.utils_charter import ( historic_milestones_for_charter,
    approved_revision, default_review_text, default_action_text,
    generate_ballot_writeup, generate_issue_ballot_mail, next_revision,
    derive_new_work_text,
    change_group_state_after_charter_approval, fix_charter_revision_after_approval,
    split_charter_name, charter_name_for_group)
from ietf.doc.mails import email_state_changed, email_charter_internal_review
from ietf.group.mails import email_admin_re_charter
from ietf.group.models import Group, ChangeStateGroupEvent, MilestoneGroupEvent
from ietf.group.utils import save_group_in_history, save_milestone_in_history, can_manage_all_groups_of_type, \
    fill_in_charter_info
from ietf.ietfauth.utils import has_role, role_required
from ietf.name.models import GroupStateName
from ietf.person.models import Person
from ietf.utils.history import find_history_active_at
from ietf.utils.log import assertion, log
from ietf.utils.mail import send_mail_preformatted 
from ietf.utils.textupload import get_cleaned_text_file_content
from ietf.utils.response import permission_denied

class ChangeStateForm(forms.Form):
    charter_state = forms.ModelChoiceField(State.objects.filter(used=True, type="charter"), label="Charter state", empty_label=None, required=False)
    initial_time = forms.IntegerField(initial=0, label="Review time", help_text="(in weeks)", required=False)
    message = forms.CharField(widget=forms.Textarea, help_text="Leave blank to change state without notifying the Secretariat.", required=False, label=mark_safe("Message to the Secretariat"), strip=False)
    comment = forms.CharField(widget=forms.Textarea, help_text="Optional comment for the charter history.", required=False, strip=False)
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

    if not can_manage_all_groups_of_type(request.user, group.type_id):
        permission_denied(request, "You don't have permission to access this view.")

    chartering_type = get_chartering_type(charter)

    initial_review = charter.latest_event(InitialReviewDocEvent, type="initial_review")
    if charter.get_state_slug() != "infrev" or (initial_review and initial_review.expires < timezone.now()) or chartering_type == "rechartering":
        initial_review = None

    by = request.user.person

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
                    group.state = GroupStateName.objects.get(slug='abandon')
                    group.save()
                    e = ChangeStateGroupEvent(group=group, type="changed_state")
                    e.time = group.time
                    e.by = by
                    e.state_id = group.state.slug
                    e.desc = "Group state changed to \"%s\" from \"%s\"" % (group.state, oldstate)
                    e.save()

                else:
                    charter_state = State.objects.get(used=True, type="charter", slug="approved")
                    charter_rev = approved_revision(charter.rev)
            else:
                charter_state = clean['charter_state']

            comment = clean['comment'].rstrip()
            message = clean['message']

            if charter_state != charter.get_state():
                events = []
                prev_state = charter.get_state()
                new_state = charter_state
                charter.set_state(new_state)
                charter.rev = charter_rev

                if option != "abandon":
                    e = add_state_change_event(charter, by, prev_state, new_state)
                    if e:
                        events.append(e)
                else:
                    # kill hanging ballots
                    close_open_ballots(charter, by)
                    # take the doc off of a telechat if scheduled
                    telechat_doc_event = charter.latest_event(TelechatDocEvent, type='scheduled_for_telechat')
                    if telechat_doc_event and telechat_doc_event.telechat_date:
                        e = TelechatDocEvent.objects.create(doc=charter, rev=charter.rev, by=by, type='scheduled_for_telechat', telechat_date=None, desc="Removed from agenda for telechat")
                        events.append(e)

                    # Special log for abandoned efforts
                    e = DocEvent(type="changed_document", doc=charter, rev=charter.rev, by=by)
                    e.desc = "Chartering effort abandoned"
                    e.save()
                    events.append(e)

                if comment:
                    events.append(DocEvent.objects.create(type="added_comment", doc=charter, rev=charter.rev, by=by, desc=comment))

                charter.save_with_history(events)

                if charter_state.slug == 'intrev':
                    email_charter_internal_review(request,charter)

                if message or charter_state.slug == "intrev" or charter_state.slug == "extrev":
                    email_admin_re_charter(request, group, "Charter state changed to \"%s\"" % charter_state.name, message,'charter_state_edit_admin_needed')

                # TODO - do we need a separate set of recipients for state changes to charters vrs other kind of documents
                email_state_changed(request, charter, "State changed to %s." % charter_state, 'doc_state_edited')

                if charter_state.slug == "intrev" and group.type_id == "wg":
                    if request.POST.get("ballot_wo_extern"):
                        create_ballot(request, charter, by, "r-wo-ext")
                    else:
                        create_ballot(request, charter, by, "r-extrev")
                    (e1, e2) = default_review_text(group, charter, by)
                    e1.save()
                    e2.save()
                    e = default_action_text(group, charter, by)
                    e.save()
                elif charter_state.slug in ["extrev","iesgrev"]:
                    create_ballot(request, charter, by, "approve")
                elif charter_state.slug == "approved":
                    change_group_state_after_charter_approval(group, by)
                    fix_charter_revision_after_approval(charter, by)

            if charter_state.slug == "infrev" and clean["initial_time"] and clean["initial_time"] != 0:
                e = InitialReviewDocEvent(type="initial_review", by=by, doc=charter, rev=charter.rev)
                e.expires = timezone.now() + datetime.timedelta(weeks=clean["initial_time"])
                e.desc = "Initial review time expires %s" % e.expires.strftime("%Y-%m-%d")
                e.save()

            return redirect('ietf.doc.views_doc.document_main', name=charter.name)
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
                init = dict(initial_time=1, message='%s has initiated chartering of the proposed %s:\n "%s" (%s).' % (by.plain_name(), group.type.name, group.name, group.acronym))
            elif option == "abandon":
                hide = ['initial_time', 'charter_state']
                init = dict(message='%s has abandoned the chartering effort on the %s:\n "%s" (%s).' % (by.plain_name(), group.type.name, group.name, group.acronym))
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
        info_msg[state_pk("infrev")] = 'The proposed charter for %s "%s" (%s) has been set to Informal IESG review by %s.' % (group.type.name, group.name, group.acronym, by.plain_name())
        info_msg[state_pk("intrev")] = 'The proposed charter for %s "%s" (%s) has been set to Internal review by %s.\nPlease place it on the next IESG telechat if it has not already been placed.' % (group.type.name, group.name, group.acronym, by.plain_name())
        info_msg[state_pk("extrev")] = 'The proposed charter for %s "%s" (%s) has been set to External review by %s.\nPlease send out the external review announcement to the appropriate lists.\n\nSend the announcement to other SDOs: Yes\nAdditional recipients of the announcement: ' % (group.type.name, group.name, group.acronym, by.plain_name())

    states_for_ballot_wo_extern = State.objects.none()
    if group.type_id == "wg":
        states_for_ballot_wo_extern = State.objects.filter(used=True, type="charter", slug="intrev").values_list("pk", flat=True)

    return render(request, 'doc/charter/change_state.html',
                  dict(form=form,
                       doc=group.charter,
                       option=option,
                       prev_charter_state=prev_charter_state,
                       title=title,
                       initial_review=initial_review,
                       chartering_type=chartering_type,
                       info_msg=json.dumps(info_msg),
                       states_for_ballot_wo_extern=json.dumps(list(states_for_ballot_wo_extern)),
                  ))

class ChangeTitleForm(forms.Form):
    charter_title = forms.CharField(widget=forms.TextInput, label="Charter title", help_text="Enter new charter title.", required=True)
    message = forms.CharField(widget=forms.Textarea, help_text="Leave blank to change the title without notifying the Secretariat.", required=False, label=mark_safe("Message to Secretariat"), strip=False)
    comment = forms.CharField(widget=forms.Textarea, help_text="Optional comment for the charter history.", required=False, strip=False)
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
    if not can_manage_all_groups_of_type(request.user, group.type_id):
        permission_denied(request, "You don't have permission to access this view.")
    by = request.user.person
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
                events = []
                charter.title = new_title
                charter.rev = charter_rev

                if not comment:
                    comment = "Changed charter title from '%s' to '%s'." % (prev_title, new_title)
                e = DocEvent(type="added_comment", doc=charter, rev=charter.rev, by=by)
                e.desc = comment
                e.save()
                events.append(e)

                charter.save_with_history(events)

                if message:
                    email_admin_re_charter(request, group, "Charter title changed to %s" % new_title, message,'charter_state_edit_admin_needed')
                email_state_changed(request, charter, "Title changed to %s." % new_title,'doc_state_edited')
            return redirect('ietf.doc.views_doc.document_main', name=charter.name)
    else:
        form = ChangeTitleForm(charter=charter)
    title = "Change charter title of %s %s" % (group.acronym, group.type.name)
    return render(request, 'doc/charter/change_title.html',
                  dict(form=form,
                       doc=group.charter,
                       title=title,
                  ))

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
    by = request.user.person

    if request.method == 'POST':
        form = AdForm(request.POST)
        if form.is_valid():
            new_ad = form.cleaned_data['ad']
            if new_ad != charter.ad:
                events = []
                e = DocEvent(doc=charter, rev=charter.rev, by=by)
                e.desc = "Responsible AD changed to %s" % new_ad.plain_name()
                if charter.ad:
                   e.desc += " from %s" % charter.ad.plain_name()
                e.type = "changed_document"
                e.save()
                events.append(e)

                charter.ad = new_ad
                charter.save_with_history(events)

            return redirect('ietf.doc.views_doc.document_main', name=charter.name)
    else:
        init = { "ad" : charter.ad_id }
        form = AdForm(initial=init)

    return render(request, 'doc/charter/change_ad.html', {
        'form': form,
        'charter': charter,
    })


class UploadForm(forms.Form):
    content = forms.CharField(widget=forms.Textarea, label="Charter text", help_text="Edit the charter text.", required=False, strip=False)
    txt = forms.FileField(label=".txt format", help_text="Or upload a .txt file.", required=False)

    def clean_content(self):
        return self.cleaned_data["content"].replace("\r", "")

    def clean_txt(self):
        return get_cleaned_text_file_content(self.cleaned_data["txt"])

@login_required
def submit(request, name, option=None):
    # Charters are named "charter-<ietf|irtf>-<group acronym>"
    charter = Document.objects.filter(type="charter", name=name).first()
    if charter:
        group = charter.group
        assertion("charter.name == charter_name_for_group(group)")
        charter_rev = charter.rev
    else:
        top_org, group_acronym = split_charter_name(name)
        group = get_object_or_404(Group, acronym=group_acronym)
        if name != charter_name_for_group(group):
            raise Http404  # do not allow creation of misnamed charters
        charter_rev = "00-00"

    if (
        not can_manage_all_groups_of_type(request.user, group.type_id)
        or not group.features.has_chartering_process
    ):
        permission_denied(request, "You don't have permission to access this view.")

    charter_filename = Path(settings.CHARTER_PATH) / f"{name}-{charter_rev}.txt"
    not_uploaded_yet = charter_rev.endswith("-00") and not charter_filename.exists()

    if not_uploaded_yet or not charter:
        # this case is special - we recently chartered or rechartered and have no file yet
        next_rev = charter_rev
    else:
        # search history for possible collisions with abandoned efforts
        prev_revs = list(
            charter.history_set.order_by("-time").values_list("rev", flat=True)
        )
        next_rev = next_revision(charter.rev)
        while next_rev in prev_revs:
            next_rev = next_revision(next_rev)

    if request.method == "POST":
        form = UploadForm(request.POST, request.FILES)
        if form.is_valid():
            # Also save group history so we can search for it
            save_group_in_history(group)

            if not charter:
                charter = Document.objects.create(
                    name=name,
                    type_id="charter",
                    title=group.name,
                    group=group,
                    abstract=group.name,
                    rev=next_rev,
                )

                charter.set_state(
                    State.objects.get(used=True, type="charter", slug="notrev")
                )

                group.charter = charter
                group.save()
            else:
                charter.rev = next_rev

            events = []
            e = NewRevisionDocEvent(
                doc=charter, by=request.user.person, type="new_revision"
            )
            e.desc = "New version available: <b>%s-%s.txt</b>" % (
                charter.name,
                charter.rev,
            )
            e.rev = charter.rev
            e.save()
            events.append(e)

            # Save file on disk
            charter_filename = charter_filename.with_name(
                f"{name}-{charter.rev}.txt"
            )  # update rev
            with charter_filename.open("w", encoding="utf-8") as destination:
                if form.cleaned_data["txt"]:
                    content=form.cleaned_data["txt"]
                else:
                    content=form.cleaned_data["content"]
                destination.write(content)
            # Also provide a copy to the legacy ftp source directory, which is served by rsync
            # This replaces the hardlink copy that ghostlink has made in the past
            # Still using a hardlink as long as these are on the same filesystem.
            ftp_filename = Path(settings.FTP_DIR) / "charter" / charter_filename.name
            try:
                os.link(charter_filename, ftp_filename) # os.link until we are on python>=3.10
            except IOError:
                log(
                    "There was an error creating a hardlink at %s pointing to %s"
                    % (ftp_filename, charter_filename)
                )
            charter.store_str(charter_filename.name, content)     


            if option in ["initcharter", "recharter"] and charter.ad == None:
                charter.ad = getattr(group.ad_role(), "person", None)

            charter.save_with_history(events)

            if option:
                return redirect(
                    "ietf.doc.views_charter.change_state",
                    name=charter.name,
                    option=option,
                )
            else:
                return redirect("ietf.doc.views_doc.document_main", name=charter.name)
    else:
        init = {"content": ""}

        if not_uploaded_yet and charter:
            # use text from last approved revision
            last_approved = charter.rev.split("-")[0]
            h = (
                charter.history_set.filter(rev=last_approved)
                .order_by("-time", "-id")
                .first()
            )
            if h:
                assertion("h.name == charter_name_for_group(group)")
                charter_filename = charter_filename.with_name(
                    f"{name}-{h.rev}.txt"
                )  # update rev

        try:
            init["content"] = charter_filename.read_text()
        except IOError:
            pass
        form = UploadForm(initial=init)
        fill_in_charter_info(group)

    return render(
        request,
        "doc/charter/submit.html",
        {
            "form": form,
            "next_rev": next_rev,
            "group": group,
            "name": name,
        },
    )

class ActionAnnouncementTextForm(forms.Form):
    announcement_text = forms.CharField(widget=forms.Textarea, required=True, strip=False)

    def clean_announcement_text(self):
        return self.cleaned_data["announcement_text"].replace("\r", "")


class ReviewAnnouncementTextForm(forms.Form):
    announcement_text = forms.CharField(widget=forms.Textarea, required=True, strip=False)
    new_work_text = forms.CharField(widget=forms.Textarea, required=True, strip=False)

    def clean_announcement_text(self):
        return self.cleaned_data["announcement_text"].replace("\r", "")


@role_required("Area Director", "Secretariat")
def review_announcement_text(request, name):
    """Editing of review announcement text"""
    charter = get_object_or_404(Document, type="charter", name=name)
    group = charter.group

    by = request.user.person

    existing = charter.latest_event(WriteupDocEvent, type="changed_review_announcement")
    existing_new_work = charter.latest_event(
        WriteupDocEvent, type="changed_new_work_text"
    )

    if not existing:
        (existing, existing_new_work) = default_review_text(group, charter, by)

    if not existing:
        raise Http404

    if not existing_new_work:
        existing_new_work = WriteupDocEvent(doc=charter, rev=charter.rev)
        existing_new_work.by = by
        existing_new_work.type = "changed_new_work_text"
        existing_new_work.desc = "%s review text was changed" % group.type.name
        existing_new_work.text = derive_new_work_text(existing.text, group)
        existing_new_work.time = timezone.now()

    form = ReviewAnnouncementTextForm(
        initial=dict(
            announcement_text=escape(existing.text),
            new_work_text=escape(existing_new_work.text),
        )
    )

    if request.method == "POST":
        form = ReviewAnnouncementTextForm(request.POST)
        if "save_text" in request.POST and form.is_valid():
            now = timezone.now()
            events = []

            t = form.cleaned_data["announcement_text"]
            if t != existing.text:
                e = WriteupDocEvent(doc=charter, rev=charter.rev)
                e.by = by
                e.type = "changed_review_announcement"
                e.desc = "%s review text was changed" % (group.type.name)
                e.text = t
                e.time = now
                e.save()
                events.append(e)
            elif existing.pk is None:
                existing.save()
                events.append(existing)

            t = form.cleaned_data["new_work_text"]
            if t != existing_new_work.text:
                e = WriteupDocEvent(doc=charter, rev=charter.rev)
                e.by = by
                e.type = "changed_new_work_text"
                e.desc = "%s new work message text was changed" % (group.type.name)
                e.text = t
                e.time = now
                e.save()
            elif existing_new_work.pk is None:
                existing_new_work.save()
                events.append(existing_new_work)

            if events:
                charter.save_with_history(events)

            if request.GET.get("next", "") == "approve":
                return redirect(
                    "ietf.doc.views_charter.approve", name=charter.name
                )

            return redirect(
                "ietf.doc.views_doc.document_writeup", name=charter.name
            )

        if "regenerate_text" in request.POST:
            (existing, existing_new_work) = default_review_text(group, charter, by)
            existing.save()
            existing_new_work.save()
            form = ReviewAnnouncementTextForm(
                initial=dict(
                    announcement_text=escape(existing.text),
                    new_work_text=escape(existing_new_work.text),
                )
            )

        if (
            any(
                x in request.POST
                for x in ["send_annc_only", "send_nw_only", "send_both"]
            )
            and form.is_valid()
        ):
            if any(x in request.POST for x in ["send_annc_only", "send_both"]):
                parsed_msg = send_mail_preformatted(
                    request, form.cleaned_data["announcement_text"]
                )
                messages.success(
                    request,
                    "The email To: '%s' with Subject: '%s' has been sent."
                    % (
                        parsed_msg["To"],
                        parsed_msg["Subject"],
                    ),
                )
            if any(x in request.POST for x in ["send_nw_only", "send_both"]):
                parsed_msg = send_mail_preformatted(
                    request, form.cleaned_data["new_work_text"]
                )
                messages.success(
                    request,
                    "The email To: '%s' with Subject: '%s' has been sent."
                    % (
                        parsed_msg["To"],
                        parsed_msg["Subject"],
                    ),
                )
            return redirect("ietf.doc.views_doc.document_writeup", name=charter.name)

    return render(
        request,
        "doc/charter/review_announcement_text.html",
        dict(
            charter=charter,
            back_url=urlreverse(
                "ietf.doc.views_doc.document_writeup", kwargs=dict(name=charter.name)
            ),
            announcement_text_form=form,
        ),
    )

@role_required("Area Director", "Secretariat")
def action_announcement_text(request, name):
    """Editing of action announcement text"""
    charter = get_object_or_404(Document, type="charter", name=name)
    group = charter.group

    by = request.user.person

    existing = charter.latest_event(WriteupDocEvent, type="changed_action_announcement")
    if not existing:
        existing = default_action_text(group, charter, by)

    if not existing:
        raise Http404

    form = ActionAnnouncementTextForm(
        initial=dict(announcement_text=escape(existing.text))
    )

    if request.method == "POST":
        form = ActionAnnouncementTextForm(request.POST)
        if "save_text" in request.POST and form.is_valid():
            t = form.cleaned_data["announcement_text"]
            if t != existing.text:
                e = WriteupDocEvent(doc=charter, rev=charter.rev)
                e.by = by
                e.type = "changed_action_announcement"
                e.desc = "%s action text was changed" % group.type.name
                e.text = t
                e.save()
            elif existing.pk == None:
                existing.save()

            if request.GET.get("next", "") == "approve":
                return redirect(
                    "ietf.doc.views_charter.approve", name=charter.name
                )

            return redirect(
                "ietf.doc.views_doc.document_writeup", name=charter.name
            )

        if "regenerate_text" in request.POST:
            e = default_action_text(group, charter, by)
            e.save()
            form = ActionAnnouncementTextForm(
                initial=dict(announcement_text=escape(e.text))
            )

        if "send_text" in request.POST and form.is_valid():
            parsed_msg = send_mail_preformatted(
                request, form.cleaned_data["announcement_text"]
            )
            messages.success(
                request,
                "The email To: '%s' with Subject: '%s' has been sent."
                % (
                    parsed_msg["To"],
                    parsed_msg["Subject"],
                ),
            )
            return redirect("ietf.doc.views_doc.document_writeup", name=charter.name)

    return render(
        request,
        "doc/charter/action_announcement_text.html",
        dict(
            charter=charter,
            back_url=urlreverse(
                "ietf.doc.views_doc.document_writeup", kwargs=dict(name=charter.name)
            ),
            announcement_text_form=form,
        ),
    )

class BallotWriteupForm(forms.Form):
    ballot_writeup = forms.CharField(widget=forms.Textarea, required=True, strip=False)

    def clean_ballot_writeup(self):
        return self.cleaned_data["ballot_writeup"].replace("\r", "")

@role_required('Area Director','Secretariat')
def ballot_writeupnotes(request, name):
    """Editing of ballot write-up and notes"""
    charter = get_object_or_404(Document, type="charter", name=name)

    ballot = charter.latest_event(BallotDocEvent, type="created_ballot")
    if not ballot:
        raise Http404

    by = request.user.person

    approval = charter.latest_event(WriteupDocEvent, type="changed_action_announcement")

    existing = charter.latest_event(WriteupDocEvent, type="changed_ballot_writeup_text")
    if not existing:
        existing = generate_ballot_writeup(request, charter)

    reissue = charter.latest_event(DocEvent, type="sent_ballot_announcement")

    form = BallotWriteupForm(initial=dict(ballot_writeup=escape(existing.text)))

    if request.method == 'POST' and ("save_ballot_writeup" in request.POST or "send_ballot" in request.POST):
        form = BallotWriteupForm(request.POST)
        if form.is_valid():
            t = form.cleaned_data["ballot_writeup"]
            if t != existing.text:
                e = WriteupDocEvent(doc=charter, rev=charter.rev, by=by)
                e.type = "changed_ballot_writeup_text"
                e.desc = "Ballot writeup was changed"
                e.text = t
                e.save()

                existing = e
            elif existing.pk == None:
                existing.save()

            if "send_ballot" in request.POST and approval:
                if has_role(request.user, "Area Director") and not charter.latest_event(BallotPositionDocEvent, type="changed_ballot_position", balloter=by, ballot=ballot):
                    # sending the ballot counts as a yes
                    pos = BallotPositionDocEvent(doc=charter, rev=charter.rev, by=by)
                    pos.type = "changed_ballot_position"
                    pos.balloter = by
                    pos.pos_id = "yes"
                    pos.desc = "[Ballot Position Update] New position, %s, has been recorded for %s" % (pos.pos.name, pos.balloter.plain_name())
                    pos.save()
                    # Consider mailing this position to 'iesg_ballot_saved'

                msg = generate_issue_ballot_mail(request, charter, ballot)
                send_mail_preformatted(request, msg)

                e = DocEvent(doc=charter, rev=charter.rev, by=by)
                e.by = by
                e.type = "sent_ballot_announcement"
                e.desc = "Ballot has been sent"
                e.save()

                return render(request, 'doc/charter/ballot_issued.html',
                              dict(doc=charter,
                              ))

    return render(request, 'doc/charter/ballot_writeupnotes.html',
                  dict(charter=charter,
                       ballot_issued=bool(charter.latest_event(type="sent_ballot_announcement")),
                       ballot_writeup_form=form,
                       reissue=reissue,
                       approval=approval,
                  ))

@role_required("Secretariat")
def approve(request, name):
    """Approve charter, changing state, fixing revision, copying file to final location."""
    charter = get_object_or_404(Document, type="charter", name=name)
    group = charter.group

    by = request.user.person

    e = charter.latest_event(WriteupDocEvent, type="changed_action_announcement")
    if not e:
        announcement = default_action_text(group, charter, by).text
    else:
        announcement = e.text

    if request.method == 'POST':
        new_charter_state = State.objects.get(used=True, type="charter", slug="approved")
        prev_charter_state = charter.get_state()

        charter.set_state(new_charter_state)

        close_open_ballots(charter, by)

        events = []
        # approve
        e = DocEvent(doc=charter, rev=charter.rev, by=by)
        e.type = "iesg_approved"
        e.desc = "IESG has approved the charter"
        e.save()
        events.append(e)

        change_description = e.desc

        group_state_change_event = change_group_state_after_charter_approval(group, by)
        if group_state_change_event:
            change_description += " and group state has been changed to %s" % group.state.name

        e = add_state_change_event(charter, by, prev_charter_state, new_charter_state)
        if e:
            events.append(e)

        fix_charter_revision_after_approval(charter, by)

        charter.save_with_history(events)

        email_admin_re_charter(request, group, "Charter state changed to \"%s\"" % new_charter_state.name, change_description,'charter_state_edit_admin_needed')

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
                        group=group, type="changed_milestone", by=by,
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
                    group=group, type="changed_milestone", by=by,
                    desc="Added milestone \"%s\", due %s, from approved charter" % (m.desc, m.due),
                    milestone=m)

        for m in milestones_to_delete:
            save_milestone_in_history(m)
            m.state_id = "deleted"
            m.save()

            MilestoneGroupEvent.objects.create(
                group=group, type="changed_milestone", by=by,
                desc="Deleted milestone \"%s\", not present in approved charter" % m.desc,
                milestone=m)

        # send announcement
        send_mail_preformatted(request, announcement)

        return HttpResponseRedirect(charter.get_absolute_url())

    return render(request, 'doc/charter/approve.html',
                  dict(charter=charter,
                       announcement=escape(announcement)))


def charter_with_milestones_txt(request, name, rev):
    charter = get_object_or_404(Document, type="charter", name=name)

    revision_event = charter.latest_event(
        NewRevisionDocEvent, type="new_revision", rev=rev
    )
    if not revision_event:
        return HttpResponseNotFound("Revision %s not found in database" % rev)

    # read charter text
    c = find_history_active_at(charter, revision_event.time) or charter
    filename = Path(settings.CHARTER_PATH) / f"{c.name}-{rev}.txt"
    try:
        with filename.open() as f:
            charter_text = force_str(f.read(), errors="ignore")
    except IOError:
        charter_text = f"Error reading charter text {filename.name}"

    milestones = historic_milestones_for_charter(charter, rev)

    # wrap the output nicely
    wrapper = textwrap.TextWrapper(
        initial_indent="", subsequent_indent=" " * 11, width=80, break_long_words=False
    )
    for m in milestones:
        m.desc_filled = wrapper.fill(m.desc)

    return render(
        request,
        "doc/charter/charter_with_milestones.txt",
        dict(charter_text=charter_text, milestones=milestones),
        content_type="text/plain; charset=%s" % settings.DEFAULT_CHARSET,
    )
