import datetime

from django.http import HttpResponseForbidden
from django.shortcuts import render, get_object_or_404, redirect
from django import forms
from django.contrib.auth.decorators import login_required

from ietf.doc.models import Document, NewRevisionDocEvent, DocEvent
from ietf.ietfauth.utils import is_authorized_in_doc_stream, user_is_person
from ietf.name.models import ReviewRequestStateName
from ietf.group.models import Role
from ietf.review.models import ReviewRequest
from ietf.review.utils import active_review_teams, assign_review_request_to_reviewer
from ietf.review.utils import can_request_review_of_doc, can_manage_review_requests_for_team
from ietf.utils.fields import DatepickerDateField

class RequestReviewForm(forms.ModelForm):
    deadline_date = DatepickerDateField(date_format="yyyy-mm-dd", picker_settings={ "autoclose": "1", "start-date": "+0d" })
    deadline_time = forms.TimeField(widget=forms.TextInput(attrs={ 'placeholder': "HH:MM" }), help_text="If time is not specified, end of day is assumed", required=False)

    class Meta:
        model = ReviewRequest
        fields = ('type', 'team', 'deadline', 'requested_rev')

    def __init__(self, user, doc, *args, **kwargs):
        super(RequestReviewForm, self).__init__(*args, **kwargs)

        self.doc = doc

        self.fields['type'].widget = forms.RadioSelect(choices=[t for t in self.fields['type'].choices if t[0]])

        f = self.fields["team"]
        f.queryset = active_review_teams()
        if not is_authorized_in_doc_stream(user, doc): # user is a reviewer
            f.queryset = f.queryset.filter(role__name="reviewer", role__person__user=user)
        if len(f.queryset) < 6:
            f.widget = forms.RadioSelect(choices=[t for t in f.choices if t[0]])

        self.fields["deadline"].required = False
        self.fields["requested_rev"].label = "Document revision"

    def clean_deadline_date(self):
        v = self.cleaned_data.get('deadline_date')
        if v < datetime.date.today():
            raise forms.ValidationError("Select a future date.")
        return v

    def clean_requested_rev(self):
        rev = self.cleaned_data.get("requested_rev")
        if rev:
            rev = rev.rjust(2, "0")

            if not NewRevisionDocEvent.objects.filter(doc=self.doc, rev=rev).exists():
                raise forms.ValidationError("Could not find revision '{}' of the document.".format(rev))

        return rev

    def clean(self):
        deadline_date = self.cleaned_data.get('deadline_date')
        deadline_time = self.cleaned_data.get('deadline_time', None)

        if deadline_date:
            if deadline_time is None:
                deadline_time = datetime.time(23, 59, 59)

            self.cleaned_data["deadline"] = datetime.datetime.combine(deadline_date, deadline_time)

        return self.cleaned_data

@login_required
def request_review(request, name):
    doc = get_object_or_404(Document, name=name)

    if not can_request_review_of_doc(request.user, doc):
        return HttpResponseForbidden("You do not have permission to perform this action")

    if request.method == "POST":
        form = RequestReviewForm(request.user, doc, request.POST)

        if form.is_valid():
            review_req = form.save(commit=False)
            review_req.doc = doc
            review_req.state = ReviewRequestStateName.objects.get(slug="requested", used=True)
            review_req.save()

            DocEvent.objects.create(
                type="requested_review",
                doc=doc,
                by=request.user.person,
                desc="Requested {} review by {}".format(review_req.type.name, review_req.team.acronym.upper()),
                time=review_req.time,
            )

            return redirect('doc_view', name=doc.name)

    else:
        form = RequestReviewForm(request.user, doc)

    return render(request, 'doc/review/request_review.html', {
        'doc': doc,
        'form': form,
    })

def review_request(request, name, request_id):
    doc = get_object_or_404(Document, name=name)
    review_req = get_object_or_404(ReviewRequest, pk=request_id)

    is_reviewer = review_req.reviewer and user_is_person(request.user, review_req.reviewer.person)
    can_manage_req = can_manage_review_requests_for_team(request.user, review_req.team)

    can_withdraw_request = (review_req.state_id in ["requested", "accepted"]
                            and is_authorized_in_doc_stream(request.user, doc))

    can_assign_reviewer = (review_req.state_id in ["requested", "accepted"]
                           and is_authorized_in_doc_stream(request.user, doc))

    can_reject_reviewer_assignment = (review_req.state_id in ["requested", "accepted"]
                                      and review_req.reviewer_id is not None
                                      and (is_reviewer or can_manage_req))

    return render(request, 'doc/review/review_request.html', {
        'doc': doc,
        'review_req': review_req,
        'can_withdraw_request': can_withdraw_request,
        'can_reject_reviewer_assignment': can_reject_reviewer_assignment,
        'can_assign_reviewer': can_assign_reviewer,
    })

def withdraw_request(request, name, request_id):
    doc = get_object_or_404(Document, name=name)
    review_req = get_object_or_404(ReviewRequest, pk=request_id, state__in=["requested", "accepted"])

    if not is_authorized_in_doc_stream(request.user, doc):
        return HttpResponseForbidden("You do not have permission to perform this action")

    if request.method == "POST" and request.POST.get("action") == "withdraw":
        review_req.state = ReviewRequestStateName.objects.get(slug="withdrawn")
        review_req.save()

        DocEvent.objects.create(
            type="changed_review_request",
            doc=doc,
            by=request.user.person,
            desc="Withdrew request for {} review by {}".format(review_req.type.name, review_req.team.acronym.upper()),
        )

        if review_req.state_id != "requested":
            # FIXME: handle this case - by emailing?
            pass

        return redirect(review_request, name=review_req.doc.name, request_id=review_req.pk)

    return render(request, 'doc/review/withdraw_request.html', {
        'doc': doc,
        'review_req': review_req,
    })

class PersonEmailLabeledRoleModelChoiceField(forms.ModelChoiceField):
    def __init__(self, *args, **kwargs):
        if not "queryset" in kwargs:
            kwargs["queryset"] = Role.objects.select_related("person", "email")
        super(PersonEmailLabeledRoleModelChoiceField, self).__init__(*args, **kwargs)

    def label_from_instance(self, role):
        return u"{} <{}>".format(role.person.name, role.email.address)

class AssignReviewerForm(forms.Form):
    reviewer = PersonEmailLabeledRoleModelChoiceField(widget=forms.RadioSelect, empty_label="(None)", required=False)

    def __init__(self, review_req, *args, **kwargs):
        super(AssignReviewerForm, self).__init__(*args, **kwargs)
        f = self.fields["reviewer"]
        f.queryset = f.queryset.filter(name="reviewer", group=review_req.team)
        if review_req.reviewer:
            f.initial = review_req.reviewer_id

def assign_reviewer(request, name, request_id):
    doc = get_object_or_404(Document, name=name)
    review_req = get_object_or_404(ReviewRequest, pk=request_id, state__in=["requested", "accepted"])

    can_manage_req = can_manage_review_requests_for_team(request.user, review_req.team)

    if not can_manage_req:
        return HttpResponseForbidden("You do not have permission to perform this action")

    if request.method == "POST" and request.POST.get("action") == "assign":
        form = AssignReviewerForm(review_req, request.POST)
        if form.is_valid():
            reviewer = form.cleaned_data["reviewer"]
            assign_review_request_to_reviewer(review_req, reviewer, request.user.person)

            return redirect(review_request, name=review_req.doc.name, request_id=review_req.pk)
    else:
        form = AssignReviewerForm(review_req)

    return render(request, 'doc/review/assign_reviewer.html', {
        'doc': doc,
        'review_req': review_req,
        'form': form,
    })

class RejectReviewerAssignmentForm(forms.Form):
    message_to_secretary = forms.CharField(widget=forms.Textarea, required=False, help_text="Optional explanation of rejection, will be emailed to team secretary")

def reject_reviewer_assignment(request, name, request_id):
    doc = get_object_or_404(Document, name=name)
    review_req = get_object_or_404(ReviewRequest, pk=request_id, state__in=["requested", "accepted"])

    if not review_req.reviewer:
        return redirect(review_request, name=review_req.doc.name, request_id=review_req.pk)

    is_reviewer = user_is_person(request.user, review_req.reviewer.person)
    can_manage_req = can_manage_review_requests_for_team(request.user, review_req.team)

    if not (is_reviewer or can_manage_req):
        return HttpResponseForbidden("You do not have permission to perform this action")

    if request.method == "POST" and request.POST.get("action") == "reject":
        # reject the request
        review_req.state = ReviewRequestStateName.objects.get(slug="rejected")
        review_req.save()

        DocEvent.objects.create(
            type="changed_review_request",
            doc=review_req.doc,
            by=request.user.person,
            desc="Assignment of request for {} review by {} to {} was rejected".format(
                review_req.type.name,
                review_req.team.acronym.upper(),
                review_req.reviewer.person,
            ),
        )
        
        # make a new unassigned review request
        new_review_req = ReviewRequest.objects.create(
            time=review_req.time,
            type=review_req.type,
            doc=review_req.doc,
            team=review_req.team,
            deadline=review_req.deadline,
            requested_rev=review_req.requested_rev,
            state=ReviewRequestStateName.objects.get(slug="requested"),
        )

        return redirect(review_request, name=new_review_req.doc.name, request_id=new_review_req.pk)

    return render(request, 'doc/review/reject_reviewer_assignment.html', {
        'doc': doc,
        'review_req': review_req,
    })
