# Copyright The IETF Trust 2017-2023, All Rights Reserved
# -*- coding: utf-8 -*-


# Stdlib imports
import re

import debug  # pyflakes:ignore

# Django imports
from django import forms
from django.utils.html import mark_safe  # type:ignore
from django.db.models import F
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.db.models import Q

# IETF imports
from ietf.group.models import Group, GroupHistory, GroupStateName, GroupFeatures
from ietf.name.models import ReviewTypeName, RoleName, ExtResourceName
from ietf.person.fields import SearchableEmailsField, PersonEmailChoiceField
from ietf.person.models import Email
from ietf.review.models import (
    ReviewerSettings,
    UnavailablePeriod,
    ReviewSecretarySettings,
)
from ietf.review.policies import get_reviewer_queue_policy
from ietf.review.utils import close_review_request_states
from ietf.utils import log
from ietf.utils.textupload import get_cleaned_text_file_content

# from ietf.utils.ordereddict import insert_after_in_ordered_dict
from ietf.utils.fields import DatepickerDateField, MultiEmailField
from ietf.utils.timezone import date_today
from ietf.utils.validators import validate_external_resource_value

# --- Constants --------------------------------------------------------

MAX_GROUP_DELEGATES = 3

# --- Forms ------------------------------------------------------------


class StatusUpdateForm(forms.Form):
    content = forms.CharField(
        widget=forms.Textarea,
        label="Status update",
        help_text="Enter the status update",
        required=False,
        strip=False,
    )
    txt = forms.FileField(
        label=".txt format", help_text="Or upload a .txt file", required=False
    )

    def clean_content(self):
        return self.cleaned_data["content"].replace("\r", "")

    def clean_txt(self):
        return get_cleaned_text_file_content(self.cleaned_data["txt"])

    def clean(self):
        if (
            self.cleaned_data["content"]
            and self.cleaned_data["content"].strip()
            and self.cleaned_data["txt"]
        ):
            raise forms.ValidationError("Cannot enter both text box and TXT file")
        elif (
            self.cleaned_data["content"]
            and not self.cleaned_data["content"].strip()
            and not self.cleaned_data["txt"]
        ):
            raise forms.ValidationError("NULL input is not a valid option")
        elif self.cleaned_data["txt"] and not self.cleaned_data["txt"].strip():
            raise forms.ValidationError("NULL TXT file input is not a valid option")


class ConcludeGroupForm(forms.Form):
    instructions = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 15}), required=True, strip=False
    )
    closing_note = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 5}),
        label="Closing note, for WG history (optional)",
        required=False,
        strip=False,
    )


class GroupForm(forms.Form):
    name = forms.CharField(max_length=80, label="Name", required=True)
    acronym = forms.CharField(max_length=40, label="Acronym", required=True)
    state = forms.ModelChoiceField(
        GroupStateName.objects.all(), label="State", required=True
    )
    # Note that __init__ will add role fields here

    parent = forms.ModelChoiceField(
        Group.objects.filter(state="active").order_by("name"),
        empty_label="(None)",
        required=False,
    )
    list_email = forms.CharField(max_length=64, required=False)
    list_subscribe = forms.CharField(max_length=255, required=False)
    list_archive = forms.CharField(max_length=255, required=False)
    description = forms.CharField(
        widget=forms.Textarea,
        required=False,
        help_text='Text that appears on the "about" page.',
    )
    urls = forms.CharField(
        widget=forms.Textarea,
        label="Additional URLs",
        help_text="Format: https://site/path (Optional description). Separate multiple entries with newline. Prefer HTTPS URLs where possible.",
        required=False,
    )
    resources = forms.CharField(
        widget=forms.Textarea,
        label="Additional Resources",
        help_text="Format: tag value (Optional description). Separate multiple entries with newline. Prefer HTTPS URLs where possible.",
        required=False,
    )
    closing_note = forms.CharField(
        widget=forms.Textarea, label="Closing note", required=False
    )

    def __init__(self, *args, **kwargs):
        self.group = kwargs.pop("group", None)
        self.group_type = kwargs.pop("group_type", False)
        if self.group:
            group_features = self.group.features
            self.used_roles = self.group.used_roles or group_features.default_used_roles
        else:
            group_features = GroupFeatures.objects.filter(
                type_id=self.group_type
            ).first()
            self.used_roles = group_features.default_used_roles

        log.assertion("group_features is not None")
        if group_features is not None:
            parent_types = group_features.parent_types.all()
            need_parent = group_features.need_parent
            default_parent = group_features.default_parent
        else:
            # This should not happen, but in the absence of constraints that ensure it
            # cannot, prevent the form from breaking if it does.
            self.used_roles = []
            parent_types = GroupFeatures.objects.none()
            need_parent = False
            default_parent = None

        if "field" in kwargs:
            field = kwargs["field"]
            del kwargs["field"]
            if field in self.used_roles:
                field = field + "_roles"
        else:
            field = None

        self.hide_parent = kwargs.pop("hide_parent", False)

        super(self.__class__, self).__init__(*args, **kwargs)

        if not group_features or group_features.has_chartering_process:
            self.fields.pop(
                "description"
            )  # do not show the description field for chartered groups

        for role_slug in self.used_roles:
            role_name = RoleName.objects.get(slug=role_slug)
            fieldname = "%s_roles" % role_slug
            field_args = {
                "label": role_name.name,
                "required": False,
                "only_users": True,
            }
            if fieldname == "delegate_roles":
                field_args["max_entries"] = MAX_GROUP_DELEGATES
                field_args["help_text"] = mark_safe(
                    "Chairs can delegate the authority to update the state of group documents - at most %s persons at a given time."
                    % MAX_GROUP_DELEGATES
                )
            if role_slug == "ad":
                field_args["extra_prefetch"] = Email.objects.filter(
                    Q(
                        role__name__in=("pre-ad", "ad"),
                        role__group__type="area",
                        role__group__state="active",
                    )
                ).distinct()
                field_args["disable_ajax"] = True  # only use the prefetched options
                field_args["min_search_length"] = (
                    0  # do not require typing to display options
                )
            self.fields[fieldname] = SearchableEmailsField(**field_args)
            self.fields[fieldname].initial = Email.objects.filter(
                person__role__name_id=role_slug,
                person__role__group=self.group,
                person__role__email__pk=F("pk"),
            ).distinct()

        self.adjusted_field_order = ["name", "acronym", "state"]
        for role_slug in self.used_roles:
            self.adjusted_field_order.append("%s_roles" % role_slug)
        self.order_fields(self.adjusted_field_order)

        if self.group_type == "rg":
            self.fields["state"].queryset = self.fields["state"].queryset.exclude(
                slug__in=("bof", "bof-conc")
            )

        if self.group:
            self.fields["acronym"].widget.attrs["readonly"] = ""

        # Sort out parent options
        if self.hide_parent:
            self.fields.pop("parent")
        else:
            self.fields["parent"].queryset = self.fields["parent"].queryset.filter(
                type__in=parent_types
            )
            if need_parent:
                self.fields["parent"].required = True
                self.fields["parent"].empty_label = None
            # if this is a new group, fill in the default parent, if any
            if self.group is None or (not hasattr(self.group, "pk")):
                self.fields["parent"].initial = (
                    self.fields["parent"]
                    .queryset.filter(acronym=default_parent)
                    .first()
                )
            # label the parent field as 'IETF Area' if appropriate, for consistency with past behavior
            if parent_types.count() == 1 and parent_types.first().pk == "area":
                self.fields["parent"].label = "IETF Area"

        if field:
            keys = list(self.fields.keys())
            for f in keys:
                if f != field and not (f == "closing_note" and field == "state"):
                    del self.fields[f]
        if "resources" in self.fields:
            info = (
                "Format: 'tag value (Optional description)'. "
                + "Separate multiple entries with newline. When the value is a URL, use https:// where possible.<br>"
                + "Valid tags: %s"
                % ", ".join(
                    [o.slug for o in ExtResourceName.objects.all().order_by("slug")]
                )
            )
            self.fields["resources"].help_text = mark_safe("<div>" + info + "</div>")

    def clean_acronym(self):
        # Changing the acronym of an already existing group will cause 404s all
        # over the place, loose history, and generally muck up a lot of
        # things, so we don't permit it
        if self.group:
            return self.group.acronym  # no change permitted

        acronym = self.cleaned_data["acronym"].strip().lower()

        if (
            self.group_type
            and GroupFeatures.objects.get(type=self.group_type).has_documents
        ):
            if not re.match(r"^[a-z][a-z0-9]+$", acronym):
                raise forms.ValidationError(
                    "Acronym is invalid, for groups that create documents, the acronym must be at least two characters and only contain lowercase letters and numbers starting with a letter."
                )
        else:
            if not re.match(r"^[a-z][a-z0-9-]*[a-z0-9]$", acronym):
                raise forms.ValidationError(
                    "Acronym is invalid, must be at least two characters and only contain lowercase letters and numbers starting with a letter. It may contain hyphens, but that is discouraged."
                )

        # be careful with acronyms, requiring confirmation to take existing or override historic
        existing = Group.objects.filter(acronym__iexact=acronym)
        if existing:
            existing = existing[0]

        confirmed = self.data.get("confirm_acronym", False)

        #         def insert_confirm_field(label, initial):
        #             # set required to false, we don't need it since we do the
        #             # validation of the field in here, and otherwise the
        #             # browser and Django may barf
        #             insert_after_in_ordered_dict(self.fields, "confirm_acronym", forms.BooleanField(label=label, required=False), after="acronym")
        #             # we can't set initial, it's ignored since the form is bound, instead mutate the data
        #             self.data = self.data.copy()
        #             self.data["confirm_acronym"] = initial

        if existing and existing.type_id == self.group_type:
            if existing.state_id == "bof":
                # insert_confirm_field(label="Turn BOF %s into proposed %s and start chartering it" % (existing.acronym, existing.type.name), initial=True)
                if confirmed:
                    return acronym
                else:
                    raise forms.ValidationError(
                        "Warning: Acronym used for an existing BOF (%s)."
                        % existing.acronym
                    )
            else:
                # insert_confirm_field(label="Set state of %s %s to proposed and start chartering it" % (existing.acronym, existing.type.name), initial=False)
                if confirmed:
                    return acronym
                else:
                    raise forms.ValidationError(
                        "Warning: Acronym used for an existing %s (%s, %s)."
                        % (
                            existing.type.name,
                            existing.acronym,
                            existing.state.name if existing.state else "unknown state",
                        )
                    )

        if existing:
            raise forms.ValidationError(
                "Acronym used for an existing group (%s)." % existing.acronym
            )

        old = GroupHistory.objects.filter(acronym__iexact=acronym)
        if old:
            # insert_confirm_field(label="Confirm reusing acronym %s" % old[0].acronym, initial=False)
            if confirmed:
                return acronym
            else:
                raise forms.ValidationError(
                    "Warning: Acronym used for a historic group."
                )

        return acronym

    def clean_urls(self):
        return [x.strip() for x in self.cleaned_data["urls"].splitlines() if x.strip()]

    def clean_resources(self):
        lines = [
            x.strip() for x in self.cleaned_data["resources"].splitlines() if x.strip()
        ]
        errors = []
        for l in lines:
            parts = l.split()
            if len(parts) == 1:
                errors.append(
                    "Too few fields: Expected at least tag and value: '%s'" % l
                )
            elif len(parts) >= 2:
                name_slug = parts[0]
                try:
                    name = ExtResourceName.objects.get(slug=name_slug)
                except ObjectDoesNotExist:
                    errors.append(
                        "Bad tag in '%s': Expected one of %s"
                        % (
                            l,
                            ", ".join([o.slug for o in ExtResourceName.objects.all()]),
                        )
                    )
                    continue
                value = parts[1]
                try:
                    validate_external_resource_value(name, value)
                except ValidationError as e:
                    e.message += " : " + value
                    errors.append(e)
        if errors:
            raise ValidationError(errors)
        return lines

    def clean_delegates(self):
        if len(self.cleaned_data["delegates"]) > MAX_GROUP_DELEGATES:
            raise forms.ValidationError(
                "At most %s delegates can be appointed at the same time, please remove %s delegates."
                % (
                    MAX_GROUP_DELEGATES,
                    len(self.cleaned_data["delegates"]) - MAX_GROUP_DELEGATES,
                )
            )
        return self.cleaned_data["delegates"]

    def clean_parent(self):
        p = self.cleaned_data["parent"]
        seen = set()
        if self.group:
            seen.add(self.group)
        while p != None and p not in seen:
            seen.add(p)
            p = p.parent
        if p is None:
            return self.cleaned_data["parent"]
        else:
            raise forms.ValidationError(
                "A group cannot be its own ancestor.  "
                "Found that the group '%s' would end up being the ancestor of (%s)"
                % (p.acronym, ", ".join([g.acronym for g in seen]))
            )

    def clean(self):
        cleaned_data = super(GroupForm, self).clean()
        state = cleaned_data.get("state", None)
        parent = cleaned_data.get("parent", None)
        if state and (
            state.slug
            in [
                "bof",
            ]
            and "parent" in self.fields
            and not parent
        ):
            raise forms.ValidationError(
                "You requested the creation of a BOF, but specified no parent area.  A parent is required when creating a bof."
            )
        return cleaned_data


class StreamEditForm(forms.Form):
    delegates = SearchableEmailsField(required=False, only_users=True)


# ----------------------------------------------------------------------


class ManageReviewRequestForm(forms.Form):
    ACTIONS = [
        ("assign", "Assign"),
        ("close", "Close"),
    ]

    action = forms.ChoiceField(
        choices=ACTIONS, widget=forms.HiddenInput, required=False
    )
    close = forms.ModelChoiceField(
        queryset=close_review_request_states(), required=False
    )
    close_comment = forms.CharField(
        max_length=255, required=False, label="Closing comment"
    )
    reviewer = PersonEmailChoiceField(
        empty_label="(None)",
        required=False,
        label_with="person",
        label="Assign reviewer",
    )
    review_type = forms.ModelChoiceField(
        queryset=ReviewTypeName.objects.filter(slug__in=["telechat", "lc"]),
        required=True,
        label="Review type",
    )
    add_skip = forms.BooleanField(required=False, label="Skip next time")

    def __init__(self, review_req, *args, **kwargs):
        if not "prefix" in kwargs:
            if review_req.pk is None:
                kwargs["prefix"] = "r{}-{}".format(
                    review_req.type_id, review_req.doc.name
                )
            else:
                kwargs["prefix"] = "r{}".format(review_req.pk)

        super(ManageReviewRequestForm, self).__init__(*args, **kwargs)

        if review_req.pk is None:
            self.fields["close"].queryset = self.fields["close"].queryset.filter(
                slug__in=["no-review-version", "no-review-document"]
            )

        close_initial = None
        if review_req.pk is None:
            close_initial = "no-review-version"
        else:
            close_initial = "overtaken"

        if close_initial:
            self.fields["close"].initial = close_initial

        get_reviewer_queue_policy(review_req.team).setup_reviewer_field(
            self.fields["reviewer"], review_req
        )

        if not getattr(review_req, "in_lc_and_telechat", False):
            del self.fields["review_type"]

        if self.is_bound:
            if self.data.get("action") == "close":
                self.fields["close"].required = True


class EmailOpenAssignmentsForm(forms.Form):
    frm = forms.CharField(
        label="From", widget=forms.EmailInput(attrs={"readonly": True})
    )
    to = MultiEmailField()
    cc = MultiEmailField(required=False)
    reply_to = MultiEmailField(required=False)
    subject = forms.CharField()
    body = forms.CharField(widget=forms.Textarea, strip=False)


class ReviewerSettingsForm(forms.ModelForm):
    class Meta:
        model = ReviewerSettings
        fields = [
            "min_interval",
            "filter_re",
            "skip_next",
            "remind_days_before_deadline",
            "remind_days_open_reviews",
            "request_assignment_next",
            "expertise",
        ]

    def __init__(self, *args, **kwargs):
        exclude_fields = kwargs.pop("exclude_fields", [])
        super(ReviewerSettingsForm, self).__init__(*args, **kwargs)
        for field_name in exclude_fields:
            self.fields.pop(field_name)

    def clean_skip_next(self):
        skip_next = self.cleaned_data.get("skip_next")
        if skip_next < 0:
            raise forms.ValidationError("Skip next must not be negative")
        return skip_next


class AddUnavailablePeriodForm(forms.ModelForm):
    class Meta:
        model = UnavailablePeriod
        fields = ["start_date", "end_date", "availability", "reason"]

    def __init__(self, *args, **kwargs):
        super(AddUnavailablePeriodForm, self).__init__(*args, **kwargs)

        self.fields["start_date"] = DatepickerDateField(
            date_format="yyyy-mm-dd",
            picker_settings={"autoclose": "1"},
            label=self.fields["start_date"].label,
            help_text=self.fields["start_date"].help_text,
            required=self.fields["start_date"].required,
            initial=date_today(),
        )
        self.fields["end_date"] = DatepickerDateField(
            date_format="yyyy-mm-dd",
            picker_settings={"autoclose": "1"},
            label=self.fields["end_date"].label,
            help_text=self.fields["end_date"].help_text,
            required=self.fields["end_date"].required,
        )

        self.fields["availability"].widget = forms.RadioSelect(
            choices=UnavailablePeriod.LONG_AVAILABILITY_CHOICES
        )

    def clean(self):
        start = self.cleaned_data.get("start_date")
        end = self.cleaned_data.get("end_date")
        if start and end and start > end:
            self.add_error(
                "start_date", "Start date must be before or equal to end date."
            )
        return self.cleaned_data


class EndUnavailablePeriodForm(forms.Form):
    def __init__(self, start_date, *args, **kwargs):
        super(EndUnavailablePeriodForm, self).__init__(*args, **kwargs)

        self.fields["end_date"] = DatepickerDateField(
            date_format="yyyy-mm-dd",
            picker_settings={
                "autoclose": "1",
                "start-date": start_date.isoformat() if start_date else "",
            },
        )

        self.start_date = start_date

    def clean_end_date(self):
        end = self.cleaned_data["end_date"]
        if self.start_date and end < self.start_date:
            raise forms.ValidationError(
                "End date must be equal to or come after start date."
            )
        return end


class ReviewSecretarySettingsForm(forms.ModelForm):
    class Meta:
        model = ReviewSecretarySettings
        fields = [
            "remind_days_before_deadline",
            "max_items_to_show_in_reviewer_list",
            "days_to_show_in_reviewer_list",
        ]
