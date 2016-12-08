import datetime, os, email.utils

import debug    # pyflakes:ignore

from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django import forms
from django.contrib.auth.decorators import login_required
from django.utils.html import mark_safe
from django.core.exceptions import ValidationError
from django.template.loader import render_to_string
from django.core.urlresolvers import reverse as urlreverse

from ietf.doc.models import (Document, NewRevisionDocEvent, State, DocAlias,
                             LastCallDocEvent, ReviewRequestDocEvent)
from ietf.name.models import ReviewRequestStateName, ReviewResultName, DocTypeName
from ietf.review.models import ReviewRequest, TypeUsedInReviewTeam
from ietf.group.models import Group
from ietf.person.fields import PersonEmailChoiceField, SearchablePersonField
from ietf.ietfauth.utils import is_authorized_in_doc_stream, user_is_person, has_role
from ietf.review.utils import (active_review_teams, assign_review_request_to_reviewer,
                               can_request_review_of_doc, can_manage_review_requests_for_team,
                               email_review_request_change, make_new_review_request_from_existing,
                               close_review_request_states, close_review_request,
                               setup_reviewer_field)
from ietf.review import mailarch
from ietf.utils.fields import DatepickerDateField
from ietf.utils.text import strip_prefix, xslugify
from ietf.utils.textupload import get_cleaned_text_file_content
from ietf.utils.mail import send_mail
from ietf.mailtrigger.utils import gather_address_lists
from ietf.utils.fields import MultiEmailField

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
        fields = ('requested_by', 'type', 'deadline', 'requested_rev')

    def __init__(self, user, doc, *args, **kwargs):
        super(RequestReviewForm, self).__init__(*args, **kwargs)

        self.doc = doc

        f = self.fields["team"]
        f.queryset = active_review_teams()
        f.initial = [group.pk for group in f.queryset if can_manage_review_requests_for_team(user, group, allow_personnel_outside_team=False)]

        self.fields['type'].queryset = self.fields['type'].queryset.filter(used=True, typeusedinreviewteam__team__in=self.fields["team"].queryset).distinct()
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
                if not TypeUsedInReviewTeam.objects.filter(type=chosen_type, team=t).exists():
                    self.add_error("type", "{} does not use the review type {}.".format(t.name, chosen_type.name))

        return self.cleaned_data

@login_required
def request_review(request, name):
    doc = get_object_or_404(Document, name=name)

    if not can_request_review_of_doc(request.user, doc):
        return HttpResponseForbidden("You do not have permission to perform this action")

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
                review_req.doc = doc
                review_req.state = ReviewRequestStateName.objects.get(slug="requested", used=True)
                review_req.team = team
                review_req.save()

                ReviewRequestDocEvent.objects.create(
                    type="requested_review",
                    doc=doc,
                    by=request.user.person,
                    desc="Requested {} review by {}".format(review_req.type.name, review_req.team.acronym.upper()),
                    time=review_req.time,
                    review_request=review_req,
                    state=None,
                )

            return redirect('doc_view', name=doc.name)

    else:
        if lc_ends:
            review_type = "lc"
        elif scheduled_for_telechat:
            review_type = "telechat"
        else:
            review_type = "early"

        form = RequestReviewForm(request.user, doc, initial={ "type": review_type })

    return render(request, 'doc/review/request_review.html', {
        'doc': doc,
        'form': form,
        'lc_ends': lc_ends,
        'lc_ends_days': (lc_ends - now).days if lc_ends else None,
        'scheduled_for_telechat': scheduled_for_telechat,
        'scheduled_for_telechat_days': (scheduled_for_telechat - now.date()).days if scheduled_for_telechat else None,
    })

def review_request(request, name, request_id):
    doc = get_object_or_404(Document, name=name)
    review_req = get_object_or_404(ReviewRequest, pk=request_id)

    is_reviewer = review_req.reviewer and user_is_person(request.user, review_req.reviewer.person)
    can_manage_request = can_manage_review_requests_for_team(request.user, review_req.team)

    can_close_request = (review_req.state_id in ["requested", "accepted"]
                         and (is_authorized_in_doc_stream(request.user, doc)
                              or can_manage_request))

    can_assign_reviewer = (review_req.state_id in ["requested", "accepted"]
                           and can_manage_request)

    can_accept_reviewer_assignment = (review_req.state_id == "requested"
                                      and review_req.reviewer
                                      and (is_reviewer or can_manage_request))

    can_reject_reviewer_assignment = (review_req.state_id in ["requested", "accepted"]
                                      and review_req.reviewer
                                      and (is_reviewer or can_manage_request))

    can_complete_review = (review_req.state_id in ["requested", "accepted", "overtaken", "no-response", "part-completed", "completed"]
                           and review_req.reviewer
                           and (is_reviewer or can_manage_request))

    if request.method == "POST" and request.POST.get("action") == "accept" and can_accept_reviewer_assignment:
        review_req.state = ReviewRequestStateName.objects.get(slug="accepted")
        review_req.save()

        return redirect(review_request, name=review_req.doc.name, request_id=review_req.pk)

    return render(request, 'doc/review/review_request.html', {
        'doc': doc,
        'review_req': review_req,
        'can_close_request': can_close_request,
        'can_reject_reviewer_assignment': can_reject_reviewer_assignment,
        'can_assign_reviewer': can_assign_reviewer,
        'can_accept_reviewer_assignment': can_accept_reviewer_assignment,
        'can_complete_review': can_complete_review,
    })


class CloseReviewRequestForm(forms.Form):
    close_reason = forms.ModelChoiceField(queryset=close_review_request_states(), widget=forms.RadioSelect, empty_label=None)

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
    review_req = get_object_or_404(ReviewRequest, pk=request_id, state__in=["requested", "accepted"])

    can_request = is_authorized_in_doc_stream(request.user, doc)
    can_manage_request = can_manage_review_requests_for_team(request.user, review_req.team)

    if not (can_request or can_manage_request):
        return HttpResponseForbidden("You do not have permission to perform this action")

    if request.method == "POST":
        form = CloseReviewRequestForm(can_manage_request, request.POST)
        if form.is_valid():
            close_review_request(request, review_req, form.cleaned_data["close_reason"])

        return redirect(review_request, name=review_req.doc.name, request_id=review_req.pk)
    else:
        form = CloseReviewRequestForm(can_manage_request)

    return render(request, 'doc/review/close_request.html', {
        'doc': doc,
        'review_req': review_req,
        'form': form,
    })


class AssignReviewerForm(forms.Form):
    reviewer = PersonEmailChoiceField(empty_label="(None)", required=False)

    def __init__(self, review_req, *args, **kwargs):
        super(AssignReviewerForm, self).__init__(*args, **kwargs)
        setup_reviewer_field(self.fields["reviewer"], review_req)


@login_required
def assign_reviewer(request, name, request_id):
    doc = get_object_or_404(Document, name=name)
    review_req = get_object_or_404(ReviewRequest, pk=request_id, state__in=["requested", "accepted"])

    if not can_manage_review_requests_for_team(request.user, review_req.team):
        return HttpResponseForbidden("You do not have permission to perform this action")

    if request.method == "POST" and request.POST.get("action") == "assign":
        form = AssignReviewerForm(review_req, request.POST)
        if form.is_valid():
            reviewer = form.cleaned_data["reviewer"]
            assign_review_request_to_reviewer(request, review_req, reviewer)

            return redirect(review_request, name=review_req.doc.name, request_id=review_req.pk)
    else:
        form = AssignReviewerForm(review_req)

    return render(request, 'doc/review/assign_reviewer.html', {
        'doc': doc,
        'review_req': review_req,
        'form': form,
    })

class RejectReviewerAssignmentForm(forms.Form):
    message_to_secretary = forms.CharField(widget=forms.Textarea, required=False, help_text="Optional explanation of rejection, will be emailed to team secretary if filled in")

@login_required
def reject_reviewer_assignment(request, name, request_id):
    doc = get_object_or_404(Document, name=name)
    review_req = get_object_or_404(ReviewRequest, pk=request_id, state__in=["requested", "accepted"])

    if not review_req.reviewer:
        return redirect(review_request, name=review_req.doc.name, request_id=review_req.pk)

    is_reviewer = user_is_person(request.user, review_req.reviewer.person)
    can_manage_request = can_manage_review_requests_for_team(request.user, review_req.team)

    if not (is_reviewer or can_manage_request):
        return HttpResponseForbidden("You do not have permission to perform this action")

    if request.method == "POST" and request.POST.get("action") == "reject":
        form = RejectReviewerAssignmentForm(request.POST)
        if form.is_valid():
            # reject the request
            review_req.state = ReviewRequestStateName.objects.get(slug="rejected")
            review_req.save()

            ReviewRequestDocEvent.objects.create(
                type="closed_review_request",
                doc=review_req.doc,
                by=request.user.person,
                desc="Assignment of request for {} review by {} to {} was rejected".format(
                    review_req.type.name,
                    review_req.team.acronym.upper(),
                    review_req.reviewer.person,
                ),
                review_request=review_req,
                state=review_req.state,
            )

            # make a new unassigned review request
            new_review_req = make_new_review_request_from_existing(review_req)
            new_review_req.save()

            msg = render_to_string("review/reviewer_assignment_rejected.txt", {
                "by": request.user.person,
                "message_to_secretary": form.cleaned_data.get("message_to_secretary")
            })

            email_review_request_change(request, review_req, "Reviewer assignment rejected", msg, by=request.user.person, notify_secretary=True, notify_reviewer=True, notify_requested_by=False)

            return redirect(review_request, name=new_review_req.doc.name, request_id=new_review_req.pk)
    else:
        form = RejectReviewerAssignmentForm()

    return render(request, 'doc/review/reject_reviewer_assignment.html', {
        'doc': doc,
        'review_req': review_req,
        'form': form,
    })

class CompleteReviewForm(forms.Form):
    state = forms.ModelChoiceField(queryset=ReviewRequestStateName.objects.filter(slug__in=("completed", "part-completed")).order_by("-order"), widget=forms.RadioSelect, initial="completed")
    reviewed_rev = forms.CharField(label="Reviewed revision", max_length=4)
    result = forms.ModelChoiceField(queryset=ReviewResultName.objects.filter(used=True), widget=forms.RadioSelect, empty_label=None)
    ACTIONS = [
        ("enter", "Enter review content (automatically posts to {mailing_list})"),
        ("upload", "Upload review content in text file (automatically posts to {mailing_list})"),
        ("link", "Link to review message already sent to {mailing_list}"),
    ]
    review_submission = forms.ChoiceField(choices=ACTIONS, widget=forms.RadioSelect)

    review_url = forms.URLField(label="Link to message", required=False)
    review_file = forms.FileField(label="Text file to upload", required=False)
    review_content = forms.CharField(widget=forms.Textarea, required=False)
    completion_date = DatepickerDateField(date_format="yyyy-mm-dd", picker_settings={ "autoclose": "1" }, initial=datetime.date.today, help_text="Date of announcement of the results of this review")
    completion_time = forms.TimeField(widget=forms.HiddenInput, initial=datetime.time.min)
    cc = MultiEmailField(required=False, help_text="Email addresses to send to in addition to the review team list")

    def __init__(self, review_req, *args, **kwargs):
        self.review_req = review_req

        super(CompleteReviewForm, self).__init__(*args, **kwargs)

        doc = self.review_req.doc

        known_revisions = NewRevisionDocEvent.objects.filter(doc=doc).order_by("time", "id").values_list("rev", flat=True)

        revising_review = review_req.state_id not in ["requested", "accepted"]

        if not revising_review:
            self.fields["state"].choices = [
                (slug, "{} - extra reviewer is to be assigned".format(label)) if slug == "part-completed" else (slug, label)
                for slug, label in self.fields["state"].choices
            ]

        self.fields["reviewed_rev"].help_text = mark_safe(
            " ".join("<a class=\"rev label label-default\">{}</a>".format(r)
                     for r in known_revisions))

        self.fields["result"].queryset = self.fields["result"].queryset.filter(resultusedinreviewteam__team=review_req.team)

        def format_submission_choice(label):
            if revising_review:
                label = label.replace(" (automatically posts to {mailing_list})", "")

            return label.format(mailing_list=review_req.team.list_email or "[error: team has no mailing list set]")

        self.fields["review_submission"].choices = [ (k, format_submission_choice(label)) for k, label in self.fields["review_submission"].choices]

        if revising_review:
            del self.fields["cc"]
        else:
            del self.fields["completion_date"]
            del self.fields["completion_time"]

    def clean_reviewed_rev(self):
        return clean_doc_revision(self.review_req.doc, self.cleaned_data.get("reviewed_rev"))

    def clean_review_content(self):
        return self.cleaned_data["review_content"].replace("\r", "")

    def clean_review_file(self):
        return get_cleaned_text_file_content(self.cleaned_data["review_file"])

    def clean(self):
        if "@" in self.review_req.reviewer.person.ascii:
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
            require_field("review_content")

@login_required
def complete_review(request, name, request_id):
    doc = get_object_or_404(Document, name=name)
    review_req = get_object_or_404(ReviewRequest, pk=request_id)

    revising_review = review_req.state_id not in ["requested", "accepted"]

    if not review_req.reviewer:
        return redirect(review_request, name=review_req.doc.name, request_id=review_req.pk)

    is_reviewer = user_is_person(request.user, review_req.reviewer.person)
    can_manage_request = can_manage_review_requests_for_team(request.user, review_req.team)

    if not (is_reviewer or can_manage_request):
        return HttpResponseForbidden("You do not have permission to perform this action")

    (to, cc) = gather_address_lists('review_completed',review_req = review_req)

    if request.method == "POST":
        form = CompleteReviewForm(review_req, request.POST, request.FILES)
        if form.is_valid():
            review_submission = form.cleaned_data['review_submission']

            review = review_req.review
            if not review:
                # create review doc
                for i in range(1, 100):
                    name_components = [
                        "review",
                        strip_prefix(review_req.doc.name, "draft-"),
                        form.cleaned_data["reviewed_rev"],
                        review_req.team.acronym,
                        review_req.type.slug,
                        xslugify(review_req.reviewer.person.ascii_parts()[3]),
                        datetime.date.today().isoformat(),
                    ]
                    if i > 1:
                        name_components.append(str(i))

                    name = "-".join(c for c in name_components if c).lower()
                    if not Document.objects.filter(name=name).exists():
                        review = Document.objects.create(name=name)
                        DocAlias.objects.create(document=review, name=review.name)
                        break

                review.type = DocTypeName.objects.get(slug="review")
                review.group = review_req.team

            review.rev = "00" if not review.rev else "{:02}".format(int(review.rev) + 1)
            review.title = "{} Review of {}-{}".format(review_req.type.name, review_req.doc.name, form.cleaned_data["reviewed_rev"])
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
                encoded_content = form.cleaned_data['review_file']
            else:
                encoded_content = form.cleaned_data['review_content'].encode("utf-8")

            filename = os.path.join(review.get_file_path(), '{}.txt'.format(review.name, review.rev))
            with open(filename, 'wb') as destination:
                destination.write(encoded_content)

            # close review request
            review_req.state = form.cleaned_data["state"]
            review_req.reviewed_rev = form.cleaned_data["reviewed_rev"]
            review_req.result = form.cleaned_data["result"]
            review_req.review = review
            review_req.save()

            need_to_email_review = review_submission != "link" and review_req.team.list_email and not revising_review

            desc = "Request for {} review by {} {}: {}. Reviewer: {}.".format(
                review_req.type.name,
                review_req.team.acronym.upper(),
                review_req.state.name,
                review_req.result.name,
                review_req.reviewer.person,
            )
            if need_to_email_review:
                desc += " " + "Sent review to list."

            completion_datetime = datetime.datetime.now()
            if "completion_date" in form.cleaned_data:
                completion_datetime = datetime.datetime.combine(form.cleaned_data["completion_date"], form.cleaned_data.get("completion_time") or datetime.time.min)

            close_event = ReviewRequestDocEvent.objects.filter(type="closed_review_request", review_request=review_req).first()
            if not close_event:
                close_event = ReviewRequestDocEvent(type="closed_review_request", review_request=review_req)

            close_event.doc = review_req.doc
            close_event.by = request.user.person
            close_event.desc = desc
            close_event.state = review_req.state
            close_event.time = completion_datetime
            close_event.save()

            if review_req.state_id == "part-completed" and not revising_review:
                existing_open_reqs = ReviewRequest.objects.filter(doc=review_req.doc, team=review_req.team, state__in=("requested", "accepted"))

                new_review_req_url = new_review_req = None
                if not existing_open_reqs:
                    new_review_req = make_new_review_request_from_existing(review_req)
                    new_review_req.save()

                    new_review_req_url = urlreverse("ietf.doc.views_review.review_request", kwargs={ "name": new_review_req.doc.name, "request_id": new_review_req.pk })
                    new_review_req_url = request.build_absolute_uri(new_review_req_url)

                subject = "Review of {}-{} completed partially".format(review_req.doc.name, review_req.reviewed_rev)

                msg = render_to_string("review/partially_completed_review.txt", {
                    "new_review_req_url": new_review_req_url,
                    "existing_open_reqs": existing_open_reqs,
                    "by": request.user.person,
                })

                email_review_request_change(request, review_req, subject, msg, request.user.person, notify_secretary=True, notify_reviewer=False, notify_requested_by=False)

            if need_to_email_review:
                # email the review
                subject = "{} of {}-{}".format("Partial review" if review_req.state_id == "part-completed" else "Review", review_req.doc.name, review_req.reviewed_rev)
                msg = send_mail(request, to, 
                                (request.user.person.plain_name(),request.user.person.email_address()),
                                subject,
                                "review/completed_review.txt", {
                                    "review_req": review_req,
                                    "content": encoded_content.decode("utf-8"),
                                },
                                cc=form.cleaned_data["cc"])

                list_name = mailarch.list_name_from_email(review_req.team.list_email)
                if list_name:
                    review.external_url = mailarch.construct_message_url(list_name, email.utils.unquote(msg["Message-ID"]))
                    review.save_with_history([close_event])

            return redirect("doc_view", name=review_req.review.name)
    else:
        form = CompleteReviewForm(review_req, initial={
            "reviewed_rev": review_req.reviewed_rev,
            "result": review_req.result_id,
            "cc": ", ".join(cc),
        })

    mail_archive_query_urls = mailarch.construct_query_urls(review_req)

    return render(request, 'doc/review/complete_review.html', {
        'doc': doc,
        'review_req': review_req,
        'form': form,
        'mail_archive_query_urls': mail_archive_query_urls,
        'revising_review': revising_review,
    })

def search_mail_archive(request, name, request_id):
    #doc = get_object_or_404(Document, name=name)
    review_req = get_object_or_404(ReviewRequest, pk=request_id)

    is_reviewer = user_is_person(request.user, review_req.reviewer.person)
    can_manage_request = can_manage_review_requests_for_team(request.user, review_req.team)

    if not (is_reviewer or can_manage_request):
        return HttpResponseForbidden("You do not have permission to perform this action")

    res = mailarch.construct_query_urls(review_req, query=request.GET.get("query"))
    if not res:
        return JsonResponse({ "error": "Couldn't do lookup in mail archive - don't know where to look"})

    MAX_RESULTS = 30

    try:
        res["messages"] = mailarch.retrieve_messages(res["query_data_url"])[:MAX_RESULTS]
    except Exception as e:
        res["error"] = "Retrieval from mail archive failed: {}".format(unicode(e))
        # raise # useful when debugging

    return JsonResponse(res)

