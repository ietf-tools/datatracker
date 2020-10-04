# Copyright The IETF Trust 2016-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import io
import itertools
import json
import os
import datetime
import requests
import email.utils

from django.utils.http import is_safe_url
from simple_history.utils import update_change_reason

import debug    # pyflakes:ignore

from django.http import JsonResponse, Http404, HttpResponse, HttpResponseRedirect
from django.shortcuts import render, get_object_or_404, redirect
from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils.html import mark_safe # type:ignore
from django.core.exceptions import ValidationError
from django.template.loader import render_to_string, TemplateDoesNotExist
from django.urls import reverse as urlreverse

from ietf.doc.models import (Document, NewRevisionDocEvent, State, DocAlias,
                             LastCallDocEvent, ReviewRequestDocEvent, ReviewAssignmentDocEvent, DocumentAuthor)
from ietf.name.models import (ReviewRequestStateName, ReviewAssignmentStateName, ReviewResultName, 
                             ReviewTypeName)
from ietf.person.models import Person
from ietf.review.models import ReviewRequest, ReviewAssignment, ReviewWish
from ietf.group.models import Group
from ietf.ietfauth.utils import is_authorized_in_doc_stream, user_is_person, has_role
from ietf.message.models import Message
from ietf.message.utils import infer_message
from ietf.person.fields import PersonEmailChoiceField, SearchablePersonField
from ietf.review.policies import get_reviewer_queue_policy
from ietf.review.utils import (active_review_teams, assign_review_request_to_reviewer,
                               can_request_review_of_doc, can_manage_review_requests_for_team,
                               email_review_assignment_change, email_review_request_change,
                               close_review_request_states,
                               close_review_request)
from ietf.review import mailarch
from ietf.utils.fields import DatepickerDateField
from ietf.utils.text import strip_prefix, xslugify
from ietf.utils.textupload import get_cleaned_text_file_content
from ietf.utils.mail import send_mail_message
from ietf.mailtrigger.utils import gather_address_lists
from ietf.utils.fields import MultiEmailField
from ietf.utils.response import permission_denied

def clean_doc_revision(doc, rev):
    if rev:
        rev = rev.rjust(2, "0")

        if not NewRevisionDocEvent.objects.filter(doc=doc, rev=rev).exists():
            raise forms.ValidationError("Could not find revision \"{}\" of the document.".format(rev))

    return rev

class RequestReviewForm(forms.ModelForm):
    team = forms.ModelMultipleChoiceField(queryset=Group.objects.all(), widget=forms.CheckboxSelectMultiple)
    deadline = DatepickerDateField(date_format="yyyy-mm-dd", picker_settings={ "autoclose": "1", "start-date": "+0d" })

    class Meta:
        model = ReviewRequest
        fields = ('requested_by', 'type', 'deadline', 'requested_rev', 'comment') 

    def __init__(self, user, doc, *args, **kwargs):
        super(RequestReviewForm, self).__init__(*args, **kwargs)

        self.doc = doc

        f = self.fields["team"]
        f.queryset = active_review_teams()
        f.initial = [group.pk for group in f.queryset if can_manage_review_requests_for_team(user, group, allow_personnel_outside_team=False)]

        self.fields['type'].queryset = self.fields['type'].queryset.filter(used=True, reviewteamsettings__group__in=self.fields["team"].queryset).distinct()
        self.fields['type'].widget = forms.RadioSelect(choices=[t for t in self.fields['type'].choices if t[0]])

        self.fields["requested_rev"].label = "Document revision"

        if has_role(user, "Secretariat"):
            self.fields["requested_by"] = SearchablePersonField()
        else:
            self.fields["requested_by"].widget = forms.HiddenInput()
            self.fields["requested_by"].initial = user.person.pk

    def clean_deadline(self):
        v = self.cleaned_data.get('deadline')
        if v < datetime.date.today():
            raise forms.ValidationError("Select today or a date in the future.")
        return v

    def clean_requested_rev(self):
        return clean_doc_revision(self.doc, self.cleaned_data.get("requested_rev"))

    def clean(self):
        chosen_type = self.cleaned_data.get("type")
        chosen_teams = self.cleaned_data.get("team")

        if chosen_type and chosen_teams:
            for t in chosen_teams:
                if chosen_type not in t.reviewteamsettings.review_types.all():
                    self.add_error("type", "{} does not use the review type {}.".format(t.name, chosen_type.name))

        return self.cleaned_data

@login_required
def request_review(request, name):
    doc = get_object_or_404(Document, name=name)

    if not can_request_review_of_doc(request.user, doc):
        permission_denied(request, "You do not have permission to perform this action")

    now = datetime.datetime.now()

    lc_ends = None
    e = doc.latest_event(LastCallDocEvent, type="sent_last_call")
    if e and e.expires >= now:
        lc_ends = e.expires

    scheduled_for_telechat = doc.telechat_date()

    if request.method == "POST":
        form = RequestReviewForm(request.user, doc, request.POST)

        if form.is_valid():
            teams = form.cleaned_data["team"]
            for team in teams:
                review_req = form.save(commit=False)
                review_req.id = None
                review_req.doc = doc
                review_req.state = ReviewRequestStateName.objects.get(slug="requested", used=True)
                review_req.team = team
                review_req.save()

                descr = "Requested {} review by {}".format(review_req.type.name,
                                                           review_req.team.acronym.upper())
                update_change_reason(review_req, descr)
                ReviewRequestDocEvent.objects.create(
                    type="requested_review",
                    doc=doc,
                    rev=doc.rev,
                    by=request.user.person,
                    desc=descr,
                    time=review_req.time,
                    review_request=review_req,
                    state=None,
                )

                subject = "%s %s Review requested: %s" % (review_req.team.acronym, review_req.type.name, doc.name)

                msg = subject

                if review_req.comment:
                    msg += "\n\n"+review_req.comment

                email_review_request_change(request, review_req, subject, msg, by=request.user.person, notify_secretary=True, notify_reviewer=False, notify_requested_by=True)

            return redirect('ietf.doc.views_doc.document_main', name=doc.name)

    else:
        if lc_ends:
            review_type = "lc"
            deadline = lc_ends.date().isoformat()
        elif scheduled_for_telechat:
            review_type = "telechat"
            deadline = doc.telechat_date()-datetime.timedelta(days=2)
        else:
            review_type = "early"
            deadline = None

        form = RequestReviewForm(request.user, doc, 
                                 initial={ "type": review_type,
                                           "requested_by": request.user.person,
                                           "deadline": deadline,
                                         })

    return render(request, 'doc/review/request_review.html', {
        'doc': doc,
        'form': form,
        'lc_ends': lc_ends,
        'lc_ends_days': (lc_ends - now).days if lc_ends else None,
        'scheduled_for_telechat': scheduled_for_telechat,
        'scheduled_for_telechat_days': (scheduled_for_telechat - now.date()).days if scheduled_for_telechat else None,
    })

@login_required
def review_request_forced_login(request, name, request_id):
    return redirect(urlreverse("ietf.doc.views_review.review_request", kwargs={ "name": name, "request_id": request_id }))


def review_request(request, name, request_id):
    doc = get_object_or_404(Document, name=name)
    review_req = get_object_or_404(ReviewRequest, pk=request_id)
    if review_req.doc != doc:
        raise Http404('The indicated ReviewRequest is not a request for the indicated document')

    can_manage_request = can_manage_review_requests_for_team(request.user, review_req.team)

    can_close_request = (review_req.state_id in ["requested", "assigned"]
                         and (is_authorized_in_doc_stream(request.user, doc)
                              or can_manage_request))

    can_assign_reviewer = (review_req.state_id in ["requested", "assigned"]
                           and can_manage_request)

    can_edit_comment = can_request_review_of_doc(request.user, doc)
    
    can_edit_deadline = can_edit_comment

    assignments = review_req.reviewassignment_set.all()
    for assignment in assignments:
        assignment.is_reviewer = user_is_person(request.user, assignment.reviewer.person)

        assignment.can_accept_reviewer_assignment = (assignment.state_id == "assigned"
                                                     and (assignment.is_reviewer or can_manage_request))

        assignment.can_reject_reviewer_assignment = (assignment.state_id in ["assigned", "accepted"]
                                                     and (assignment.is_reviewer or can_manage_request))

        assignment.can_complete_review = (assignment.state_id in ["assigned", "accepted", "overtaken", "no-response", "part-completed", "completed"]
                                          and (assignment.is_reviewer or can_manage_request))

    # This implementation means if a reviewer accepts one assignment for a review_request, he accepts all assigned to him (for that request)
    # This problematic - it's a bug (probably) for the same person to have more than one assignment for the same request.
    # It is, however unintuitive, and acceptance should be refactored to be something that works on assignments, not requests
    if request.method == "POST" and request.POST.get("action") == "accept":
        for assignment in assignments:
            if assignment.can_accept_reviewer_assignment:
                assignment.state = ReviewAssignmentStateName.objects.get(slug="accepted")
                assignment.save()
                update_change_reason(assignment, 'Assignment for {} accepted'.format(assignment.reviewer.person))
        return redirect(review_request, name=review_req.doc.name, request_id=review_req.pk)

    wg_chairs = None
    if review_req.doc.group:
        wg_chairs = [role.person for role in review_req.doc.group.role_set.filter(name__slug='chair')]

    history = list(review_req.history.all()) 
    history += itertools.chain(*[list(r.history.all()) for r in review_req.reviewassignment_set.all()])
    history.sort(key=lambda h: h.history_date, reverse=True)
    
    return render(request, 'doc/review/review_request.html', {
        'doc': doc,
        'review_req': review_req,
        'can_close_request': can_close_request,
        'can_assign_reviewer': can_assign_reviewer,
        'can_edit_comment': can_edit_comment,
        'can_edit_deadline': can_edit_deadline,
        'assignments': assignments,
        'wg_chairs': wg_chairs,
        'history': history,
    })


class CloseReviewRequestForm(forms.Form):
    close_reason = forms.ModelChoiceField(queryset=close_review_request_states(), widget=forms.RadioSelect, empty_label=None)
    close_comment = forms.CharField(label='Comment (optional)', max_length=255, required=False)

    def __init__(self, can_manage_request, *args, **kwargs):
        super(CloseReviewRequestForm, self).__init__(*args, **kwargs)

        if not can_manage_request:
            self.fields["close_reason"].queryset = self.fields["close_reason"].queryset.filter(slug__in=["withdrawn"])

        if len(self.fields["close_reason"].queryset) == 1:
            self.fields["close_reason"].initial = self.fields["close_reason"].queryset.first().pk
            self.fields["close_reason"].widget = forms.HiddenInput()


@login_required
def close_request(request, name, request_id):
    doc = get_object_or_404(Document, name=name)
    review_req = get_object_or_404(ReviewRequest, pk=request_id, state__in=["requested", "assigned"])

    can_request = is_authorized_in_doc_stream(request.user, doc)
    can_manage_request = can_manage_review_requests_for_team(request.user, review_req.team)

    if not (can_request or can_manage_request):
        permission_denied(request, "You do not have permission to perform this action")

    if request.method == "POST":
        form = CloseReviewRequestForm(can_manage_request, request.POST)
        if form.is_valid():
            close_review_request(request, review_req,form.cleaned_data["close_reason"],
                                 form.cleaned_data["close_comment"])

        return redirect(review_request, name=review_req.doc.name, request_id=review_req.pk)
    else:
        form = CloseReviewRequestForm(can_manage_request)

    return render(request, 'doc/review/close_request.html', {
        'doc': doc,
        'review_req': review_req,
        'assignments': review_req.reviewassignment_set.all(),
        'form': form,
    })


class AssignReviewerForm(forms.Form):
    reviewer = PersonEmailChoiceField(label="Assign Additional Reviewer", empty_label="(None)")
    add_skip = forms.BooleanField(label='Skip next time', required=False)

    def __init__(self, review_req, *args, **kwargs):
        super(AssignReviewerForm, self).__init__(*args, **kwargs)
        get_reviewer_queue_policy(review_req.team).setup_reviewer_field(self.fields["reviewer"], review_req)


@login_required
def assign_reviewer(request, name, request_id):
    doc = get_object_or_404(Document, name=name)
    review_req = get_object_or_404(ReviewRequest, pk=request_id, state__in=["requested", "assigned"])

    if not can_manage_review_requests_for_team(request.user, review_req.team):
        permission_denied(request, "You do not have permission to perform this action")

    if request.method == "POST" and request.POST.get("action") == "assign":
        form = AssignReviewerForm(review_req, request.POST)
        if form.is_valid():
            reviewer = form.cleaned_data["reviewer"]
            add_skip = form.cleaned_data["add_skip"]
            assign_review_request_to_reviewer(request, review_req, reviewer, add_skip)

            return redirect(review_request, name=review_req.doc.name, request_id=review_req.pk)
    else:
        form = AssignReviewerForm(review_req)

    return render(request, 'doc/review/assign_reviewer.html', {
        'doc': doc,
        'review_req': review_req,
        'assignments': review_req.reviewassignment_set.all(),
        'form': form,
    })

class RejectReviewerAssignmentForm(forms.Form):
    message_to_secretary = forms.CharField(widget=forms.Textarea, required=False, help_text="Optional explanation of rejection, will be emailed to team secretary if filled in", strip=False)

@login_required
def reject_reviewer_assignment(request, name, assignment_id):
    doc = get_object_or_404(Document, name=name)
    review_assignment = get_object_or_404(ReviewAssignment, pk=assignment_id, state__in=["assigned", "accepted"])
    review_request_past_deadline = review_assignment.review_request.deadline < datetime.date.today()

    if not review_assignment.reviewer:
        return redirect(review_request, name=review_assignment.review_request.doc.name, request_id=review_assignment.review_request.pk)

    is_reviewer = user_is_person(request.user, review_assignment.reviewer.person)
    can_manage_request = can_manage_review_requests_for_team(request.user, review_assignment.review_request.team)

    if not (is_reviewer or can_manage_request):
        permission_denied(request, "You do not have permission to perform this action")

    if request.method == "POST" and request.POST.get("action") == "reject" and not review_request_past_deadline:
        form = RejectReviewerAssignmentForm(request.POST)
        if form.is_valid():
            # reject the assignment
            review_assignment.state = ReviewAssignmentStateName.objects.get(slug="rejected")
            review_assignment.completed_on = datetime.datetime.now()
            review_assignment.save()

            descr = "Assignment of request for {} review by {} to {} was rejected".format(
                review_assignment.review_request.type.name,
                review_assignment.review_request.team.acronym.upper(),
                review_assignment.reviewer.person
            )
            update_change_reason(review_assignment, descr)
            ReviewAssignmentDocEvent.objects.create(
                type="closed_review_assignment",
                doc=review_assignment.review_request.doc,
                rev=review_assignment.review_request.doc.rev,
                by=request.user.person,
                desc=descr,
                review_assignment=review_assignment,
                state=review_assignment.state,
            )

            policy = get_reviewer_queue_policy(review_assignment.review_request.team)
            policy.return_reviewer_to_rotation_top(review_assignment.reviewer.person)

            msg = render_to_string("review/reviewer_assignment_rejected.txt", {
                "by": request.user.person,
                "message_to_secretary": form.cleaned_data.get("message_to_secretary")
            })

            email_review_assignment_change(request, review_assignment, "Reviewer assignment rejected", msg, by=request.user.person, notify_secretary=True, notify_reviewer=True, notify_requested_by=False)

            return redirect(review_request, name=review_assignment.review_request.doc.name, request_id=review_assignment.review_request.pk)
    else:
        form = RejectReviewerAssignmentForm()

    return render(request, 'doc/review/reject_reviewer_assignment.html', {
        'doc': doc,
        'review_req': review_assignment.review_request,
        'assignments': review_assignment.review_request.reviewassignment_set.all(),
        'form': form,
        'review_request_past_deadline': review_request_past_deadline,
    })

@login_required
def withdraw_reviewer_assignment(request, name, assignment_id):
    get_object_or_404(Document, name=name)
    review_assignment = get_object_or_404(ReviewAssignment, pk=assignment_id, state__in=["assigned", "accepted"])

    can_manage_request = can_manage_review_requests_for_team(request.user, review_assignment.review_request.team)
    if not can_manage_request:
        permission_denied(request, "You do not have permission to perform this action")

    if request.method == "POST" and request.POST.get("action") == "withdraw":
        review_assignment.state_id = 'withdrawn'
        review_assignment.save()

        descr = "Assignment of request for {} review by {} to {} was withdrawn".format(
            review_assignment.review_request.type.name,
            review_assignment.review_request.team.acronym.upper(),
            review_assignment.reviewer.person, )
        update_change_reason(review_assignment, descr)
        ReviewAssignmentDocEvent.objects.create(
            type="closed_review_assignment",
            doc=review_assignment.review_request.doc,
            rev=review_assignment.review_request.doc.rev,
            by=request.user.person,
            desc=descr,
            review_assignment=review_assignment,
            state=review_assignment.state,
        )            

        policy = get_reviewer_queue_policy(review_assignment.review_request.team)
        policy.return_reviewer_to_rotation_top(review_assignment.reviewer.person)
        
        msg = "Review assignment withdrawn by %s"%request.user.person

        email_review_assignment_change(request, review_assignment, "Reviewer assignment withdrawn", msg, by=request.user.person, notify_secretary=True, notify_reviewer=True, notify_requested_by=False)

        return redirect(review_request, name=review_assignment.review_request.doc.name, request_id=review_assignment.review_request.pk)

    return render(request, 'doc/review/withdraw_reviewer_assignment.html', {
        'assignment': review_assignment,
    })    

@login_required
def mark_reviewer_assignment_no_response(request, name, assignment_id):
    get_object_or_404(Document, name=name)
    review_assignment = get_object_or_404(ReviewAssignment, pk=assignment_id, state__in=["assigned", "accepted"])

    can_manage_request = can_manage_review_requests_for_team(request.user, review_assignment.review_request.team)
    if not can_manage_request:
        permission_denied(request, "You do not have permission to perform this action")

    if request.method == "POST" and request.POST.get("action") == "noresponse":
        review_assignment.state_id = 'no-response'
        review_assignment.save()

        descr = "Assignment of request for {} review by {} to {} was marked no-response".format(
            review_assignment.review_request.type.name,
            review_assignment.review_request.team.acronym.upper(),
            review_assignment.reviewer.person)
        update_change_reason(review_assignment, descr)
        ReviewAssignmentDocEvent.objects.create(
            type="closed_review_assignment",
            doc=review_assignment.review_request.doc,
            rev=review_assignment.review_request.doc.rev,
            by=request.user.person,
            desc=descr,
            review_assignment=review_assignment,
            state=review_assignment.state,
        )            

        msg = "Review assignment marked 'No Response' by %s"%request.user.person

        email_review_assignment_change(request, review_assignment, "Reviewer assignment marked no-response", msg, by=request.user.person, notify_secretary=True, notify_reviewer=True, notify_requested_by=False)

        return redirect(review_request, name=review_assignment.review_request.doc.name, request_id=review_assignment.review_request.pk)

    return render(request, 'doc/review/mark_reviewer_assignment_no_response.html', {
        'assignment': review_assignment,
    })    


class SubmitUnsolicitedReviewTeamChoiceForm(forms.Form):
    team = forms.ModelChoiceField(queryset=Group.objects.filter(reviewteamsettings__isnull=False), widget=forms.RadioSelect, empty_label=None)
    
    def __init__(self, user, *args, **kwargs):
        super(SubmitUnsolicitedReviewTeamChoiceForm, self).__init__(*args, **kwargs)
        self.fields['team'].queryset = self.fields['team'].queryset.filter(role__person__user=user, role__name='secr')
        

@login_required()
def submit_unsolicited_review_choose_team(request, name):
    """
    If a user is submitting an unsolicited review, and is allowed to do this for more
    than one team, they are routed through this small view to pick a team.
    This is needed as the complete review form needs to be specific for a team.
    This view only produces a redirect, so it's open for any user.
    """
    doc = get_object_or_404(Document, name=name)
    if request.method == "POST":
        form = SubmitUnsolicitedReviewTeamChoiceForm(request.user, request.POST)
        if form.is_valid():
            return redirect("ietf.doc.views_review.complete_review",
                            name=doc.name, acronym=form.cleaned_data['team'].acronym)
    else:
        form = SubmitUnsolicitedReviewTeamChoiceForm(user=request.user)
    return render(request, 'doc/review/submit_unsolicited_review.html', {
        'doc': doc,
        'form': form,
    })

class CompleteReviewForm(forms.Form):
    state = forms.ModelChoiceField(queryset=ReviewAssignmentStateName.objects.filter(slug__in=("completed", "part-completed")).order_by("-order"), widget=forms.RadioSelect, initial="completed")
    reviewed_rev = forms.CharField(label="Reviewed revision", max_length=4)
    result = forms.ModelChoiceField(queryset=ReviewResultName.objects.filter(used=True), widget=forms.RadioSelect, empty_label=None)
    review_type = forms.ModelChoiceField(queryset=ReviewTypeName.objects.filter(used=True), widget=forms.RadioSelect, empty_label=None)
    reviewer = forms.ModelChoiceField(queryset=Person.objects.all(), widget=forms.Select)

    ACTIONS = [
        ("enter", "Enter review content (automatically posts to {mailing_list})"),
        ("upload", "Upload review content in text file (automatically posts to {mailing_list})"),
        ("link", "Link to review message already sent to {mailing_list}"),
    ]
    review_submission = forms.ChoiceField(choices=ACTIONS, widget=forms.RadioSelect)

    review_url = forms.URLField(label="Link to message", required=False)
    review_file = forms.FileField(label="Text file to upload", required=False)
    review_content = forms.CharField(widget=forms.Textarea, required=False, strip=False)
    completion_date = DatepickerDateField(date_format="yyyy-mm-dd", picker_settings={ "autoclose": "1" }, initial=datetime.date.today, help_text="Date of announcement of the results of this review")
    completion_time = forms.TimeField(widget=forms.HiddenInput, initial=datetime.time.min)
    cc = MultiEmailField(required=False, help_text="Email addresses to send to in addition to the review team list")
    email_ad = forms.BooleanField(label="Send extra email to the responsible AD suggesting early attention", required=False)

    def __init__(self, assignment, doc, team, is_reviewer, *args, **kwargs):
        self.assignment = assignment
        self.doc = doc

        super(CompleteReviewForm, self).__init__(*args, **kwargs)

        known_revisions = NewRevisionDocEvent.objects.filter(doc=doc).order_by("time", "id").values_list("rev", "time", flat=False)

        revising_review = assignment.state_id not in ["assigned", "accepted"] if assignment else False

        if not is_reviewer:
            new_field_order = ['review_submission', 'review_url', 'review_file', 'review_content']
            new_field_order += [f for f in self.fields.keys() if f not in new_field_order]
            self.order_fields(new_field_order)

        if not revising_review:
            self.fields["state"].choices = [
                (slug, "{} - extra reviewer is to be assigned".format(label)) if slug == "part-completed" else (slug, label)
                for slug, label in self.fields["state"].choices
            ]

        if 'initial' in kwargs and assignment:
            reviewed_rev_class = []
            for r in known_revisions:
                last_version = r[0]
                if r[1] < assignment.review_request.time:
                    kwargs["initial"]["reviewed_rev"] = r[0]
                    reviewed_rev_class.append('reviewer-doc-past')
                else:
                    reviewed_rev_class.append('reviewer-doc-ok')

            # After this the ones in future are marked with green, but we
            # want also to mark the oldest one before the review was assigned
            # so shift list one step.
            reviewed_rev_class.pop(0)
            reviewed_rev_class.append('reviewer-doc-ok')

            # If it is users own review, then default to latest version
            if is_reviewer:
                kwargs["initial"]["reviewed_rev"] = last_version

            self.fields["reviewed_rev"].help_text = mark_safe(
                " ".join("<a class=\"rev label label-default {0}\" title=\"{2:%Y-%m-%d}\">{1}</a>".format(reviewed_rev_class[i], *r)
                         for i, r in enumerate(known_revisions)))
        else:
            self.fields["reviewed_rev"].help_text = mark_safe(
                " ".join("<a class=\"rev label label-default {0}\" title=\"{2:%Y-%m-%d}\">{1}</a>".format('', *r)
                         for i, r in enumerate(known_revisions)))

        self.fields["result"].queryset = self.fields["result"].queryset.filter(reviewteamsettings_review_results_set__group=team)

        def format_submission_choice(label):
            if revising_review:
                label = label.replace(" (automatically posts to {mailing_list})", "")

            return label.format(mailing_list=team.list_email or "[error: team has no mailing list set]")

        if assignment:
            del self.fields["review_type"]
            del self.fields["reviewer"]
        else:
            self.fields["review_type"].queryset = self.fields["review_type"].queryset.filter(
                reviewteamsettings__group=team)
            self.fields["reviewer"].queryset = self.fields["reviewer"].queryset.filter(role__name="reviewer", role__group=team)

        self.fields["review_submission"].choices = [ (k, format_submission_choice(label)) for k, label in self.fields["review_submission"].choices]
        
        if revising_review:
            del self.fields["cc"]
        elif is_reviewer:
            del self.fields["completion_date"]
            del self.fields["completion_time"]

    def clean_reviewed_rev(self):
        return clean_doc_revision(self.doc, self.cleaned_data.get("reviewed_rev"))

    def clean_review_content(self):
        return self.cleaned_data["review_content"].replace("\r", "")

    def clean_review_file(self):
        return get_cleaned_text_file_content(self.cleaned_data["review_file"])

    def clean_review_url(self):
        url = self.cleaned_data['review_url']
        #scheme, netloc, path, parameters, query, fragment = urlparse(url)
        if url:
            r = requests.get(url)
            if r.status_code != 200:
                raise forms.ValidationError("Trying to retrieve the URL resulted in status code %s: %s.  Please provide an URL that can be retrieved." % (r.status_code, r.reason))
        return url

    def clean(self):
        if self.assignment and "@" in self.assignment.reviewer.person.ascii:
            raise forms.ValidationError("Reviewer name must be filled in (the ASCII version is currently \"{}\" - since it contains an @ sign the name is probably still the original email address).".format(self.review_req.reviewer.person.ascii))

        def require_field(f):
            if not self.cleaned_data.get(f):
                self.add_error(f, ValidationError("You must fill in this field."))

        submission_method = self.cleaned_data.get("review_submission")
        if submission_method == "enter":
            require_field("review_content")
        elif submission_method == "upload":
            require_field("review_file")
        elif submission_method == "link":
            require_field("review_url")

@login_required
def complete_review(request, name, assignment_id=None, acronym=None):
    doc = get_object_or_404(Document, name=name)
    if assignment_id:
        assignment = get_object_or_404(ReviewAssignment, pk=assignment_id)
    
        revising_review = assignment.state_id not in ["assigned", "accepted"]
    
        is_reviewer = user_is_person(request.user, assignment.reviewer.person)
        can_manage_request = can_manage_review_requests_for_team(request.user, assignment.review_request.team)
    
        if not (is_reviewer or can_manage_request):
            permission_denied(request, "You do not have permission to perform this action")
    
        team = assignment.review_request.team
        team_acronym = assignment.review_request.team.acronym.lower()
        request_type = assignment.review_request.type
        reviewer = assignment.reviewer
        mailtrigger_slug = 'review_completed_{}_{}'.format(team_acronym, request_type.slug)
        # Description is only used if the mailtrigger does not exist yet.
        mailtrigger_desc = 'Recipients when a {} {} review is completed'.format(team_acronym, request_type)
        to, cc = gather_address_lists(
            mailtrigger_slug,
            create_from_slug_if_not_exists='review_completed',
            desc_if_not_exists=mailtrigger_desc,
            review_req=assignment.review_request
        )
    else:
        team = get_object_or_404(Group, acronym=acronym)
        if not can_manage_review_requests_for_team(request.user, team):
            permission_denied(request, "You do not have permission to perform this action")
        assignment = None
        is_reviewer = False
        revising_review = False
        request_type = None
        to, cc = [], []

    if request.method == "POST":
        form = CompleteReviewForm(assignment, doc, team, is_reviewer,
                                  request.POST, request.FILES)
        if form.is_valid():
            review_submission = form.cleaned_data['review_submission']
            if not assignment:
                request_type = form.cleaned_data['review_type']
                reviewer = form.cleaned_data['reviewer'].role_email('reviewer',group=team)

            if assignment and assignment.review:
                review = assignment.review
            else:
                # create review doc
                name_components = [
                    "review",
                    strip_prefix(doc.name, "draft-"),
                    form.cleaned_data["reviewed_rev"],
                    team.acronym, 
                    request_type.slug,
                    xslugify(reviewer.person.ascii_parts()[3]),
                    datetime.date.today().isoformat(),
                ]
                review_name = "-".join(c for c in name_components if c).lower()
                if not Document.objects.filter(name=review_name).exists():
                    review = Document.objects.create(name=review_name,type_id='review',group=team)
                    DocAlias.objects.create(name=review_name).docs.add(review)
                else:
                    messages.warning(message='Attempt to save review failed: review document already exists. This most likely occurred because the review was submitted twice in quick succession. If you intended to submit a new review, rather than update an existing one, things are probably OK. Please verify that the shown review is what you expected.')
                    return redirect("ietf.doc.views_doc.document_main", name=review_name)

            if not assignment:
                # If this is an unsolicited review, create a new request and assignment.
                # The assignment will be immediately closed after, sharing the usual
                # processes for regular assigned reviews.
                review_request = ReviewRequest.objects.create(
                    state_id='assigned',
                    type=form.cleaned_data['review_type'],
                    doc=doc,
                    team=team,
                    deadline=datetime.date.today(),
                    requested_by=Person.objects.get(user=request.user),
                    requested_rev=form.cleaned_data['reviewed_rev'],
                )
                assignment = ReviewAssignment.objects.create(
                    review_request=review_request,
                    state_id='assigned',
                    reviewer=form.cleaned_data['reviewer'].role_email('reviewer', group=team),
                    assigned_on=datetime.datetime.now(),
                    review = review,
                )

            review.rev = "00" if not review.rev else "{:02}".format(int(review.rev) + 1)
            review.title = "{} Review of {}-{}".format(assignment.review_request.type.name, assignment.review_request.doc.name, form.cleaned_data["reviewed_rev"])
            review.time = datetime.datetime.now()
            if review_submission == "link":
                review.external_url = form.cleaned_data['review_url']

            e = NewRevisionDocEvent.objects.create(
                type="new_revision",
                doc=review,
                by=request.user.person,
                rev=review.rev,
                desc='New revision available',
                time=review.time,
            )

            review.set_state(State.objects.get(type="review", slug="active"))

            review.save_with_history([e])

            # save file on disk
            if review_submission == "upload":
                content = form.cleaned_data['review_file']
            else:
                content = form.cleaned_data['review_content']

            filename = os.path.join(review.get_file_path(), '{}.txt'.format(review.name))
            with io.open(filename, 'w', encoding='utf-8') as destination:
                destination.write(content)

            completion_datetime = datetime.datetime.now()
            if "completion_date" in form.cleaned_data:
                completion_datetime = datetime.datetime.combine(form.cleaned_data["completion_date"], form.cleaned_data.get("completion_time") or datetime.time.min)

            # complete assignment
            assignment.state = form.cleaned_data["state"]
            assignment.reviewed_rev = form.cleaned_data["reviewed_rev"]
            assignment.result = form.cleaned_data["result"]
            assignment.review = review
            assignment.completed_on = completion_datetime
            assignment.save()

            need_to_email_review = review_submission != "link" and assignment.review_request.team.list_email and not revising_review

            submitted_on_different_date = completion_datetime.date() != datetime.date.today()
            desc = "Request for {} review by {} {}: {}. Reviewer: {}.".format(
                assignment.review_request.type.name,
                assignment.review_request.team.acronym.upper(),
                assignment.state.name,
                assignment.result.name,
                assignment.reviewer.person,
            )
            update_change_reason(assignment, desc)
            if need_to_email_review:
                desc += " " + "Sent review to list."
            if revising_review:
                desc += " Review has been revised by {}.".format(request.user.person)
            elif submitted_on_different_date:
                desc += " Submission of review completed at an earlier date."
            close_event = ReviewAssignmentDocEvent(type="closed_review_assignment", review_assignment=assignment)
            close_event.doc = assignment.review_request.doc
            close_event.rev = assignment.review_request.doc.rev
            close_event.by = request.user.person
            close_event.desc = desc
            close_event.state = assignment.state
            close_event.time = datetime.datetime.now()
            close_event.save()
            
            # If the completion date is different, record when the initial review was made too.
            if not revising_review and submitted_on_different_date:
                desc = "Request for {} review by {} {}: {}. Reviewer: {}.".format(
                    assignment.review_request.type.name,
                    assignment.review_request.team.acronym.upper(),
                    assignment.state.name,
                    assignment.result.name,
                    assignment.reviewer.person,
                )

                initial_close_event = ReviewAssignmentDocEvent(type="closed_review_assignment",
                                                               review_assignment=assignment)
                initial_close_event.doc = assignment.review_request.doc
                initial_close_event.rev = assignment.review_request.doc.rev
                initial_close_event.by = request.user.person
                initial_close_event.desc = desc
                initial_close_event.state = assignment.state
                initial_close_event.time = completion_datetime
                initial_close_event.save()

            if assignment.state_id == "part-completed" and not revising_review: 
                existing_assignments = ReviewAssignment.objects.filter(review_request__doc=assignment.review_request.doc, review_request__team=assignment.review_request.team, state__in=("assigned", "accepted", "completed"))

                subject = "Review of {}-{} completed partially".format(assignment.review_request.doc.name, assignment.reviewed_rev)

                msg = render_to_string("review/partially_completed_review.txt", {
                    "existing_assignments": existing_assignments,
                    "by": request.user.person,
                })

                email_review_assignment_change(request, assignment, subject, msg, request.user.person, notify_secretary=True, notify_reviewer=False, notify_requested_by=False)

            role = request.user.person.role_set.filter(group=assignment.review_request.team,name='reviewer').first()
            if role and role.email.active:
                author_email = role.email
                frm = role.formatted_email()
            else:
                author_email = request.user.person.email()
                frm =  request.user.person.formatted_email()
            author, created = DocumentAuthor.objects.get_or_create(document=review, email=author_email, person=request.user.person)

            if need_to_email_review:
                # email the review
                subject = "{} {} {} of {}-{}".format(assignment.review_request.team.acronym.capitalize(),assignment.review_request.type.name.lower(),"partial review" if assignment.state_id == "part-completed" else "review", assignment.review_request.doc.name, assignment.reviewed_rev)
                related_groups = [ assignment.review_request.team, ]
                if assignment.review_request.doc.group:
                    related_groups.append(assignment.review_request.doc.group)
                cc = form.cleaned_data["cc"]
                msg = Message.objects.create(
                        by=request.user.person,
                        subject=subject,
                        frm=frm,
                        to=", ".join(to),
                        cc=", ".join(cc),
                        body = render_to_string("review/completed_review.txt", {
                            "assignment": assignment,
                            "content": content,
                        }),
                    )
                msg.related_groups.add(*related_groups)
                msg.related_docs.add(assignment.review_request.doc)

                msg = send_mail_message(request, msg)

                list_name = mailarch.list_name_from_email(assignment.review_request.team.list_email)
                if list_name:
                    review.external_url = mailarch.construct_message_url(list_name, email.utils.unquote(msg["Message-ID"].strip()))
                    review.save_with_history([close_event])

            if form.cleaned_data['email_ad'] or assignment.result in assignment.review_request.team.reviewteamsettings.notify_ad_when.all(): 
                (to, cc) = gather_address_lists('review_notify_ad',review_req = assignment.review_request).as_strings() 
                msg_txt = render_to_string("review/notify_ad.txt", {
                    "to": to,
                    "cc": cc,
                    "assignment": assignment,
                    "settings": settings,
                    "explicit_request": form.cleaned_data['email_ad'],
                 })
                msg = infer_message(msg_txt)
                msg.by = request.user.person
                msg.save()
                send_mail_message(request, msg)

            return redirect("ietf.doc.views_doc.document_main", name=assignment.review.name)
    else:
        initial={
            "reviewed_rev": assignment.reviewed_rev if assignment else None,
            "result": assignment.result_id if assignment else None,
            "cc": ", ".join(cc),
        }

        try:
            initial['review_content'] = render_to_string('/group/%s/review/content_templates/%s.txt' % (assignment.review_request.team.acronym,
                                                                                                        request_type.slug), {'assignment':assignment, 'today':datetime.date.today()}) 
        except (TemplateDoesNotExist, AttributeError):
            pass

        form = CompleteReviewForm(assignment, doc, team, is_reviewer, initial=initial)

    mail_archive_query_urls = mailarch.construct_query_urls(doc, team)

    return render(request, 'doc/review/complete_review.html', {
        'doc': doc,
        'team': team,
        'assignment': assignment,
        'form': form,
        'mail_archive_query_urls': mail_archive_query_urls,
        'revising_review': revising_review,
        'review_to': to,
        'review_cc': cc,
        'is_reviewer': is_reviewer,
    })

def search_mail_archive(request, name, acronym=None, assignment_id=None):
    if assignment_id:
        assignment = get_object_or_404(ReviewAssignment, pk=assignment_id)
        team = assignment.review_request.team
    else:
        assignment = None
        team = get_object_or_404(Group, acronym=acronym)
    doc = get_object_or_404(Document, name=name)

    is_reviewer = assignment and user_is_person(request.user, assignment.reviewer.person)
    can_manage_request = can_manage_review_requests_for_team(request.user, team)

    if not (is_reviewer or can_manage_request):
        permission_denied(request, "You do not have permission to perform this action")

    res = mailarch.construct_query_urls(doc, team, query=request.GET.get("query"))
    if not res:
        return JsonResponse({ "error": "Couldn't do lookup in mail archive - don't know where to look"})

    MAX_RESULTS = 30

    try:
        res["messages"] = mailarch.retrieve_messages(res["query_data_url"])[:MAX_RESULTS]
        for message in res["messages"]:
            try:
                revision_guess = message["subject"].split(name)[1].split('-')[1]
                message["revision_guess"] = revision_guess if revision_guess.isnumeric() else None
            except IndexError:
                pass
    except KeyError as e:
        res["error"] = "No results found (%s)" % str(e)
    except Exception as e:
        res["error"] = "Retrieval from mail archive failed: %s" % str(e)
        # raise # useful when debugging

    return JsonResponse(res)

class EditReviewRequestCommentForm(forms.ModelForm):
    comment = forms.CharField(widget=forms.Textarea, strip=False)
    class Meta:
        fields = ['comment',]
        model = ReviewRequest

def edit_comment(request, name, request_id):
    review_req = get_object_or_404(ReviewRequest, pk=request_id)
    if not can_request_review_of_doc(request.user, review_req.doc):
        permission_denied(request, "You do not have permission to perform this action")

    if request.method == "POST":
        form = EditReviewRequestCommentForm(request.POST, instance=review_req)
        if form.is_valid():
            form.save()
            return redirect(review_request, name=review_req.doc.name, request_id=review_req.pk)
    else: 
        form = EditReviewRequestCommentForm(instance=review_req) 

    return render(request, 'doc/review/edit_request_comment.html', {
        'review_req': review_req,
        'form' : form,
    })

class EditReviewRequestDeadlineForm(forms.ModelForm):
    deadline = DatepickerDateField(date_format="yyyy-mm-dd", picker_settings={ "autoclose": "1", "start-date": "+0d" })
    class Meta:
        fields = ['deadline',]
        model = ReviewRequest

    def clean_deadline(self):
        v = self.cleaned_data.get('deadline')
        if v < datetime.date.today():
            raise forms.ValidationError("Select today or a date in the future.")
        return v


def edit_deadline(request, name, request_id):
    review_req = get_object_or_404(ReviewRequest, pk=request_id)
    if not can_request_review_of_doc(request.user, review_req.doc):
        permission_denied(request, "You do not have permission to perform this action")

    old_deadline = review_req.deadline

    if request.method == "POST":
        form = EditReviewRequestDeadlineForm(request.POST, instance=review_req)
        if form.is_valid():
            if form.cleaned_data['deadline'] != old_deadline:
                form.save()
                subject = "Deadline changed: {} {} review of {}-{}".format(review_req.team.acronym.capitalize(),review_req.type.name.lower(), review_req.doc.name, review_req.requested_rev)
                msg = render_to_string("review/deadline_changed.txt", {
                    "review_req": review_req,
                    "old_deadline": old_deadline,
                    "by": request.user.person,
                })
                email_review_request_change(request, review_req, subject, msg, request.user.person, notify_secretary=True, notify_reviewer=True, notify_requested_by=True)

            return redirect(review_request, name=review_req.doc.name, request_id=review_req.pk)
    else: 
        form = EditReviewRequestDeadlineForm(instance=review_req) 

    return render(request, 'doc/review/edit_request_deadline.html', {
        'review_req': review_req,
        'form' : form,
    })


class ReviewWishAddForm(forms.Form):
    team = forms.ModelChoiceField(queryset=Group.objects.filter(reviewteamsettings__isnull=False),
                                  widget=forms.RadioSelect, empty_label=None, required=True)

    def __init__(self, user, doc, *args, **kwargs):
        super(ReviewWishAddForm, self).__init__(*args, **kwargs)
        self.person = get_object_or_404(Person, user=user)
        self.doc = doc
        self.fields['team'].queryset = self.fields['team'].queryset.filter(role__person=self.person,
                                                                           role__name='reviewer')
        if len(self.fields['team'].queryset) == 1:
            self.team = self.fields['team'].queryset.get()
            del self.fields['team']
            
    def save(self):
        team = self.team if hasattr(self, 'team') else self.cleaned_data['team']
        ReviewWish.objects.get_or_create(person=self.person, team=team, doc=self.doc)

@login_required
def review_wish_add(request, name):
    doc = get_object_or_404(Document, docalias__name=name)

    if request.method == "POST":
        form = ReviewWishAddForm(request.user, doc, request.POST)
        if form.is_valid():
            form.save()
            return _generate_ajax_or_redirect_response(request, doc)
    else:
        form = ReviewWishAddForm(request.user, doc)
        
    return render(request, "doc/review/review_wish_add.html", {
        "doc": doc,
        "form": form,
    })

@login_required
def review_wishes_remove(request, name):
    doc = get_object_or_404(Document, docalias__name=name)
    person = get_object_or_404(Person, user=request.user)

    if request.method == "POST":
        ReviewWish.objects.filter(person=person, doc=doc).delete()
        return _generate_ajax_or_redirect_response(request, doc)

    return render(request, "doc/review/review_wishes_remove.html", {
        "name": doc.name,
    })


def _generate_ajax_or_redirect_response(request, doc):
    redirect_url = request.GET.get('next')
    url_is_safe = is_safe_url(url=redirect_url, allowed_hosts=request.get_host(),
                              require_https=request.is_secure())
    if request.is_ajax():
        return HttpResponse(json.dumps({'success': True}), content_type='application/json')
    elif url_is_safe:
        return HttpResponseRedirect(redirect_url)
    else:
        return HttpResponseRedirect(doc.get_absolute_url())
