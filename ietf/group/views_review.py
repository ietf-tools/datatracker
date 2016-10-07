import datetime, math
from collections import defaultdict

from django.shortcuts import render, redirect, get_object_or_404
from django.http import Http404, HttpResponseForbidden, HttpResponseRedirect
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse as urlreverse
from django import forms
from django.template.loader import render_to_string

from ietf.review.models import ReviewRequest, ReviewerSettings, UnavailablePeriod
from ietf.review.utils import (can_manage_review_requests_for_team, close_review_request_states,
                               extract_revision_ordered_review_requests_for_documents_and_replaced,
                               assign_review_request_to_reviewer,
                               close_review_request,
                               setup_reviewer_field,
                               suggested_review_requests_for_team,
                               unavailable_periods_to_list,
                               current_unavailable_periods_for_reviewers,
                               email_reviewer_availability_change,
                               reviewer_rotation_list,
                               extract_review_request_data)
from ietf.group.models import Role
from ietf.group.utils import get_group_or_404, construct_group_menu_context
from ietf.person.fields import PersonEmailChoiceField
from ietf.name.models import ReviewRequestStateName
from ietf.utils.mail import send_mail_text
from ietf.utils.fields import DatepickerDateField
from ietf.ietfauth.utils import user_is_person


def review_requests(request, acronym, group_type=None):
    group = get_group_or_404(acronym, group_type)
    if not group.features.has_reviews:
        raise Http404

    open_review_requests = list(ReviewRequest.objects.filter(
        team=group, state__in=("requested", "accepted")
    ).prefetch_related("reviewer", "type", "state").order_by("-time", "-id"))

    unavailable_periods = current_unavailable_periods_for_reviewers(group)
    for review_req in open_review_requests:
        if review_req.reviewer:
            review_req.reviewer_unavailable = any(p.availability == "unavailable"
                                                  for p in unavailable_periods.get(review_req.reviewer.person_id, []))

    open_review_requests = suggested_review_requests_for_team(group) + open_review_requests

    today = datetime.date.today()
    for r in open_review_requests:
        r.due = max(0, (today - r.deadline).days)

    closed_review_requests = ReviewRequest.objects.filter(
        team=group,
    ).exclude(
        state__in=("requested", "accepted")
    ).prefetch_related("reviewer", "type", "state", "doc").order_by("-time", "-id")

    since_choices = [
        (None, "1 month"),
        ("3m", "3 months"),
        ("6m", "6 months"),
        ("1y", "1 year"),
        ("2y", "2 years"),
        ("all", "All"),
    ]
    since = request.GET.get("since", None)
    if since not in [key for key, label in since_choices]:
        since = None

    if since != "all":
        date_limit = {
            None: datetime.timedelta(days=31),
            "3m": datetime.timedelta(days=31 * 3),
            "6m": datetime.timedelta(days=180),
            "1y": datetime.timedelta(days=365),
            "2y": datetime.timedelta(days=2 * 365),
        }[since]

        closed_review_requests = closed_review_requests.filter(time__gte=datetime.date.today() - date_limit)

    return render(request, 'group/review_requests.html',
                  construct_group_menu_context(request, group, "review requests", group_type, {
                      "open_review_requests": open_review_requests,
                      "closed_review_requests": closed_review_requests,
                      "since_choices": since_choices,
                      "since": since,
                      "can_manage_review_requests": can_manage_review_requests_for_team(request.user, group)
                  }))

def reviewer_overview(request, acronym, group_type=None):
    group = get_group_or_404(acronym, group_type)
    if not group.features.has_reviews:
        raise Http404

    can_manage = can_manage_review_requests_for_team(request.user, group)

    reviewers = reviewer_rotation_list(group)

    reviewer_settings = { s.person_id: s for s in ReviewerSettings.objects.filter(team=group) }
    unavailable_periods = defaultdict(list)
    for p in unavailable_periods_to_list().filter(team=group):
        unavailable_periods[p.person_id].append(p)
    reviewer_roles = { r.person_id: r for r in Role.objects.filter(group=group, name="reviewer").select_related("email") }

    today = datetime.date.today()

    all_req_data = extract_review_request_data(teams=[group], time_from=today - datetime.timedelta(days=365))
    review_state_by_slug = { n.slug: n for n in ReviewRequestStateName.objects.all() }

    for person in reviewers:
        person.settings = reviewer_settings.get(person.pk) or ReviewerSettings(team=group, person=person)
        person.settings_url = None
        person.role = reviewer_roles.get(person.pk)
        if person.role and (can_manage or user_is_person(request.user, person)):
            person.settings_url = urlreverse("ietf.group.views_review.change_reviewer_settings", kwargs={ "group_type": group_type, "acronym": group.acronym, "reviewer_email": person.role.email.address })
        person.unavailable_periods = unavailable_periods.get(person.pk, [])
        person.completely_unavailable = any(p.availability == "unavailable"
                                       and p.start_date <= today and (p.end_date is None or today <= p.end_date)
                                       for p in person.unavailable_periods)

        MAX_REQS = 5
        req_data = all_req_data.get((group.pk, person.pk), [])
        open_reqs = sum(1 for _, _, _, _, state, _, _, _, _, _ in req_data if state in ("requested", "accepted"))
        latest_reqs = []
        for req_pk, doc, req_time, state, deadline, result, late_days, request_to_assignment_days, assignment_to_closure_days, request_to_closure_days in req_data:
            # any open requests pushes the others out
            if ((state in ("requested", "accepted") and len(latest_reqs) < MAX_REQS) or (len(latest_reqs) + open_reqs < MAX_REQS)):
                if assignment_to_closure_days is not None:
                    assignment_to_closure_days = int(math.ceil(assignment_to_closure_days))
                latest_reqs.append((req_pk, doc, deadline, review_state_by_slug.get(state), assignment_to_closure_days))
        person.latest_reqs = latest_reqs

    return render(request, 'group/reviewer_overview.html',
                  construct_group_menu_context(request, group, "reviewers", group_type, {
                      "reviewers": reviewers,
                  }))

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

        if review_req.pk is None:
            self.fields["close"].queryset = self.fields["close"].queryset.filter(slug__in=["no-review-version", "no-review-document"])

        close_initial = None
        if review_req.pk is None:
            close_initial = "no-review-version"
        elif review_req.reviewer:
            close_initial = "no-response"
        else:
            close_initial = "overtaken"

        if close_initial:
            self.fields["close"].initial = close_initial

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

    unavailable_periods = current_unavailable_periods_for_reviewers(group)

    open_review_requests = list(ReviewRequest.objects.filter(
        team=group, state__in=("requested", "accepted")
    ).prefetch_related("reviewer", "type", "state").order_by("-time", "-id"))

    for review_req in open_review_requests:
        if review_req.reviewer:
            review_req.reviewer_unavailable = any(p.availability == "unavailable"
                                                  for p in unavailable_periods.get(review_req.reviewer.person_id, []))

    review_requests = suggested_review_requests_for_team(group) + open_review_requests

    document_requests = extract_revision_ordered_review_requests_for_documents_and_replaced(
        ReviewRequest.objects.filter(state__in=("part-completed", "completed"), team=group).prefetch_related("result"),
        set(r.doc_id for r in review_requests),
    )

    # we need a mutable query dict for resetting upon saving with
    # conflicts
    query_dict = request.POST.copy() if request.method == "POST" else None
    for req in review_requests:
        l = []
        # take all on the latest reviewed rev
        for r in document_requests.get(req.doc_id, []):
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
                import ietf.group.views_review
                return redirect(ietf.group.views_review.review_requests, **kwargs)

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
            "rotation_list": reviewer_rotation_list(group)[:10],
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


class ReviewerSettingsForm(forms.ModelForm):
    class Meta:
        model = ReviewerSettings
        fields = ['min_interval', 'filter_re', 'skip_next', 'remind_days_before_deadline']

class AddUnavailablePeriodForm(forms.ModelForm):
    class Meta:
        model = UnavailablePeriod
        fields = ['start_date', 'end_date', 'availability']

    def __init__(self, *args, **kwargs):
        super(AddUnavailablePeriodForm, self).__init__(*args, **kwargs)

        self.fields["start_date"] = DatepickerDateField(date_format="yyyy-mm-dd", picker_settings={"autoclose": "1" }, label=self.fields["start_date"].label, help_text=self.fields["start_date"].help_text, required=self.fields["start_date"].required)
        self.fields["end_date"] = DatepickerDateField(date_format="yyyy-mm-dd", picker_settings={"autoclose": "1" }, label=self.fields["end_date"].label, help_text=self.fields["end_date"].help_text, required=self.fields["end_date"].required)

        self.fields['availability'].widget = forms.RadioSelect(choices=UnavailablePeriod.LONG_AVAILABILITY_CHOICES)

    def clean(self):
        start = self.cleaned_data.get("start_date")
        end = self.cleaned_data.get("end_date")
        if start and end and start > end:
            self.add_error("start_date", "Start date must be before or equal to end date.")
        return self.cleaned_data

class EndUnavailablePeriodForm(forms.Form):
    def __init__(self, start_date, *args, **kwargs):
        super(EndUnavailablePeriodForm, self).__init__(*args, **kwargs)

        self.fields["end_date"] = DatepickerDateField(date_format="yyyy-mm-dd", picker_settings={"autoclose": "1", "start-date": start_date.isoformat() })

        self.start_date = start_date

    def clean_end_date(self):
        end = self.cleaned_data["end_date"]
        if end < self.start_date:
            raise forms.ValidationError("End date must be equal to or come after start date.")
        return end


@login_required
def change_reviewer_settings(request, acronym, reviewer_email, group_type=None):
    group = get_group_or_404(acronym, group_type)
    if not group.features.has_reviews:
        raise Http404

    reviewer_role = get_object_or_404(Role, name="reviewer", group=group, email=reviewer_email)
    reviewer = reviewer_role.person

    if not (user_is_person(request.user, reviewer)
            or can_manage_review_requests_for_team(request.user, group)):
        return HttpResponseForbidden("You do not have permission to perform this action")

    settings = (ReviewerSettings.objects.filter(person=reviewer, team=group).first()
                or ReviewerSettings(person=reviewer, team=group))

    back_url = request.GET.get("next")
    if not back_url:
        import ietf.group.views_review
        back_url = urlreverse(ietf.group.views_review.reviewer_overview, kwargs={ "group_type": group.type_id, "acronym": group.acronym})

    # settings
    if request.method == "POST" and request.POST.get("action") == "change_settings":
        prev_min_interval = settings.get_min_interval_display()
        prev_skip_next = settings.skip_next
        settings_form = ReviewerSettingsForm(request.POST, instance=settings)
        if settings_form.is_valid():
            settings = settings_form.save()

            changes = []
            if settings.get_min_interval_display() != prev_min_interval:
                changes.append("Frequency changed to \"{}\" from \"{}\".".format(settings.get_min_interval_display(), prev_min_interval))
            if settings.skip_next != prev_skip_next:
                changes.append("Skip next assignments changed to {} from {}.".format(settings.skip_next, prev_skip_next))

            if changes:
                email_reviewer_availability_change(request, group, reviewer_role, "\n\n".join(changes), request.user.person)

            return HttpResponseRedirect(back_url)
    else:
        settings_form = ReviewerSettingsForm(instance=settings)

    # periods
    unavailable_periods = unavailable_periods_to_list().filter(person=reviewer, team=group)

    if request.method == "POST" and request.POST.get("action") == "add_period":
        period_form = AddUnavailablePeriodForm(request.POST)
        if period_form.is_valid():
            period = period_form.save(commit=False)
            period.team = group
            period.person = reviewer
            period.save()

            today = datetime.date.today()

            in_the_past = period.end_date and period.end_date < today

            if not in_the_past:
                msg = "Unavailable for review: {} - {} ({})".format(
                    period.start_date.isoformat(),
                    period.end_date.isoformat() if period.end_date else "indefinite",
                    period.get_availability_display(),
                )

                if period.availability == "unavailable":
                    # the secretary might need to reassign
                    # assignments, so mention the current ones

                    review_reqs = ReviewRequest.objects.filter(state__in=["requested", "accepted"], reviewer=reviewer_role.email, team=group)
                    msg += "\n\n"

                    if review_reqs:
                        msg += "{} is currently assigned to review:".format(reviewer_role.person)
                        for r in review_reqs:
                            msg += "\n\n"
                            msg += "{} (deadline: {})".format(r.doc_id, r.deadline.isoformat())
                    else:
                        msg += "{} does not have any assignments currently.".format(reviewer_role.person)

                email_reviewer_availability_change(request, group, reviewer_role, msg, request.user.person)

            return HttpResponseRedirect(request.get_full_path())
    else:
        period_form = AddUnavailablePeriodForm()

    if request.method == "POST" and request.POST.get("action") == "delete_period":
        period_id = request.POST.get("period_id")
        if period_id is not None:
            for period in unavailable_periods:
                if str(period.pk) == period_id:
                    period.delete()

                    today = datetime.date.today()

                    in_the_past = period.end_date and period.end_date < today

                    if not in_the_past:
                        msg = "Removed unavailable period: {} - {} ({})".format(
                            period.start_date.isoformat(),
                            period.end_date.isoformat() if period.end_date else "indefinite",
                            period.get_availability_display(),
                        )

                        email_reviewer_availability_change(request, group, reviewer_role, msg, request.user.person)

            return HttpResponseRedirect(request.get_full_path())

    for p in unavailable_periods:
        if not p.end_date:
            p.end_form = EndUnavailablePeriodForm(p.start_date, request.POST if request.method == "POST" and request.POST.get("action") == "end_period" else None)

    if request.method == "POST" and request.POST.get("action") == "end_period":
        period_id = request.POST.get("period_id")
        for period in unavailable_periods:
            if str(period.pk) == period_id:
                if not period.end_date and period.end_form.is_valid():
                    period.end_date = period.end_form.cleaned_data["end_date"]
                    period.save()

                    msg = "Set end date of unavailable period: {} - {} ({})".format(
                        period.start_date.isoformat(),
                        period.end_date.isoformat() if period.end_date else "indefinite",
                        period.get_availability_display(),
                    )

                    email_reviewer_availability_change(request, group, reviewer_role, msg, request.user.person)

                    return HttpResponseRedirect(request.get_full_path())


    return render(request, 'group/change_reviewer_settings.html', {
        'group': group,
        'reviewer_email': reviewer_email,
        'back_url': back_url,
        'settings_form': settings_form,
        'period_form': period_form,
        'unavailable_periods': unavailable_periods,
    })
