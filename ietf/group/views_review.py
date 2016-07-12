from django.shortcuts import render, redirect
from django.http import Http404, HttpResponseForbidden
from django.contrib.auth.decorators import login_required
from django import forms

from ietf.review.models import ReviewRequest
from ietf.review.utils import (can_manage_review_requests_for_team, close_review_request_states,
                               extract_revision_ordered_review_requests_for_documents,
                               assign_review_request_to_reviewer,
                               close_review_request,
                               setup_reviewer_field,
#                               make_new_review_request_from_existing,
                               suggested_review_requests_for_team)
from ietf.group.utils import get_group_or_404
from ietf.person.fields import PersonEmailChoiceField


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
    ).prefetch_related("reviewer", "type", "state").order_by("time", "id"))

    review_requests += suggested_review_requests_for_team(group)

    document_requests = extract_revision_ordered_review_requests_for_documents(
        ReviewRequest.objects.filter(state__in=("part-completed", "completed")).prefetch_related("result"),
        set(r.doc_id for r in review_requests),
    )

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

        req.form = ManageReviewRequestForm(req, request.POST if request.method == "POST" else None)

    if request.method == "POST":
        form_results = []
        for req in review_requests:
            form_results.append(req.form.is_valid())

        if all(form_results):
            for review_req in review_requests:
                action = review_req.form.cleaned_data.get("action")
                if action == "assign":
                    assign_review_request_to_reviewer(request, review_req, review_req.form.cleaned_data["reviewer"])
                elif action == "close":
                    close_review_request(request, review_req, review_req.form.cleaned_data["close"])


            kwargs = { "acronym": group.acronym }
            if group_type:
                kwargs["group_type"] = group_type
            import ietf.group.views
            return redirect(ietf.group.views.review_requests, **kwargs)


    return render(request, 'group/manage_review_requests.html', {
        'group': group,
        'review_requests': review_requests,
    })

