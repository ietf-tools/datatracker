from django.shortcuts import render, redirect
from django.http import Http404, HttpResponseForbidden
from django.contrib.auth.decorators import login_required
from django import forms
from django.template.loader import render_to_string

from ietf.review.models import ReviewRequest
from ietf.review.utils import (can_manage_review_requests_for_team, close_review_request_states,
                               extract_revision_ordered_review_requests_for_documents,
                               assign_review_request_to_reviewer,
                               close_review_request,
                               setup_reviewer_field,
                               suggested_review_requests_for_team)
from ietf.group.utils import get_group_or_404
from ietf.person.fields import PersonEmailChoiceField
from ietf.utils.mail import send_mail_text


class ManageReviewRequestForm(forms.Form):
    ACTIONS = [
        ("assign", "Assign"),
        ("close", "Close"),
    ]

    action = forms.ChoiceField(choices=ACTIONS, widget=forms.HiddenInput, required=False)
    close = forms.ModelChoiceField(queryset=close_review_request_states(), required=False)
    reviewer = PersonEmailChoiceField(empty_label="(None)", required=False, label_with="person")

    def __init__(self, review_req, *args, **kwargs):
        if not "prefix" in kwargs:
            if review_req.pk is None:
                kwargs["prefix"] = "r{}-{}".format(review_req.type_id, review_req.doc_id)
            else:
                kwargs["prefix"] = "r{}".format(review_req.pk)

        super(ManageReviewRequestForm, self).__init__(*args, **kwargs)

        close_initial = None
        if review_req.pk is None:
            if review_req.latest_reqs:
                close_initial = "no-review-version"
            else:
                close_initial = "no-review-document"
        elif review_req.reviewer:
            close_initial = "no-response"
        else:
            close_initial = "overtaken"

        if close_initial:
            self.fields["close"].initial = close_initial

        if review_req.pk is None:
            self.fields["close"].queryset = self.fields["close"].queryset.filter(slug__in=["noreviewversion", "noreviewdocument"])

        self.fields["close"].widget.attrs["class"] = "form-control input-sm"

        setup_reviewer_field(self.fields["reviewer"], review_req)
        self.fields["reviewer"].widget.attrs["class"] = "form-control input-sm"

        if self.is_bound:
            if self.data.get("action") == "close":
                self.fields["close"].required = True


@login_required
def manage_review_requests(request, acronym, group_type=None):
    group = get_group_or_404(acronym, group_type)
    if not group.features.has_reviews:
        raise Http404

    if not can_manage_review_requests_for_team(request.user, group):
        return HttpResponseForbidden("You do not have permission to perform this action")

    review_requests = list(ReviewRequest.objects.filter(
        team=group, state__in=("requested", "accepted")
    ).prefetch_related("reviewer", "type", "state").order_by("-time", "-id"))

    review_requests += suggested_review_requests_for_team(group)

    document_requests = extract_revision_ordered_review_requests_for_documents(
        ReviewRequest.objects.filter(state__in=("part-completed", "completed"), team=group).prefetch_related("result"),
        set(r.doc_id for r in review_requests),
    )

    # we need a mutable query dict
    query_dict = request.POST.copy() if request.method == "POST" else None
    for req in review_requests:
        l = []
        # take all on the latest reviewed rev
        for r in document_requests[req.doc_id]:
            if l and l[0].reviewed_rev:
                if r.doc_id == l[0].doc_id and r.reviewed_rev:
                    if int(r.reviewed_rev) > int(l[0].reviewed_rev):
                        l = [r]
                    elif int(r.reviewed_rev) == int(l[0].reviewed_rev):
                        l.append(r)
            else:
                l = [r]

        req.latest_reqs = l

        req.form = ManageReviewRequestForm(req, query_dict)

    saving = False
    newly_closed = newly_opened = newly_assigned = 0

    if request.method == "POST":
        form_action = request.POST.get("action", "")
        saving = form_action.startswith("save")

        # check for conflicts
        review_requests_dict = { unicode(r.pk): r for r in review_requests }
        posted_reqs = set(request.POST.getlist("reviewrequest", []))
        current_reqs = set(review_requests_dict.iterkeys())

        closed_reqs = posted_reqs - current_reqs
        newly_closed += len(closed_reqs)

        opened_reqs = current_reqs - posted_reqs
        newly_opened += len(opened_reqs)
        for r in opened_reqs:
            review_requests_dict[r].form.add_error(None, "New request.")

        for req in review_requests:
            existing_reviewer = request.POST.get(req.form.prefix + "-existing_reviewer")
            if existing_reviewer is None:
                continue

            if existing_reviewer != unicode(req.reviewer_id or ""):
                msg = "Assignment was changed."
                a = req.form["action"].value()
                if a == "assign":
                    msg += " Didn't assign reviewer."
                elif a == "close":
                    msg += " Didn't close request."
                req.form.add_error(None, msg)
                req.form.data[req.form.prefix + "-action"] = "" # cancel the action

                newly_assigned += 1

        form_results = []
        for req in review_requests:
            form_results.append(req.form.is_valid())

        if saving and all(form_results) and not (newly_closed > 0 or newly_opened > 0 or newly_assigned > 0):
            for review_req in review_requests:
                action = review_req.form.cleaned_data.get("action")
                if action == "assign":
                    assign_review_request_to_reviewer(request, review_req, review_req.form.cleaned_data["reviewer"])
                elif action == "close":
                    close_review_request(request, review_req, review_req.form.cleaned_data["close"])

            kwargs = { "acronym": group.acronym }
            if group_type:
                kwargs["group_type"] = group_type

            if form_action == "save-continue":
                return redirect(manage_review_requests, **kwargs)
            else:
                import ietf.group.views
                return redirect(ietf.group.views.review_requests, **kwargs)

    return render(request, 'group/manage_review_requests.html', {
        'group': group,
        'review_requests': review_requests,
        'newly_closed': newly_closed,
        'newly_opened': newly_opened,
        'newly_assigned': newly_assigned,
        'saving': saving,
    })

class EmailOpenAssignmentsForm(forms.Form):
    to = forms.EmailField(widget=forms.EmailInput(attrs={ "readonly": True }))
    subject = forms.CharField()
    body = forms.CharField(widget=forms.Textarea)

@login_required
def email_open_review_assignments(request, acronym, group_type=None):
    group = get_group_or_404(acronym, group_type)
    if not group.features.has_reviews:
        raise Http404

    if not can_manage_review_requests_for_team(request.user, group):
        return HttpResponseForbidden("You do not have permission to perform this action")

    review_requests = list(ReviewRequest.objects.filter(
        team=group,
        state__in=("requested", "accepted"),
    ).exclude(
        reviewer=None,
    ).prefetch_related("reviewer", "type", "state", "doc").distinct().order_by("deadline", "reviewer"))

    if request.method == "POST" and request.POST.get("action") == "email":
        form = EmailOpenAssignmentsForm(request.POST)
        if form.is_valid():
            send_mail_text(request, form.cleaned_data["to"], None, form.cleaned_data["subject"], form.cleaned_data["body"])

            kwargs = { "acronym": group.acronym }
            if group_type:
                kwargs["group_type"] = group_type

            return redirect(manage_review_requests, **kwargs)
    else:
        to = group.list_email
        subject = "Open review assignments in {}".format(group.acronym)
        body = render_to_string("group/email_open_review_assignments.txt", {
            "review_requests": review_requests,
        })

        form = EmailOpenAssignmentsForm(initial={
            "to": to,
            "subject": subject,
            "body": body,
        })

    return render(request, 'group/email_open_review_assignments.html', {
        'group': group,
        'review_requests': review_requests,
        'form': form,
    })

