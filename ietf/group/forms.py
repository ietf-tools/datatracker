# Copyright The IETF Trust 2007, All Rights Reserved
from __future__ import unicode_literals, print_function

# Stdlib imports
import re

# Django imports
from django import forms
from django.utils.html import mark_safe

# IETF imports
from ietf.group.models import Group, GroupHistory, GroupStateName
from ietf.person.fields import SearchableEmailsField, PersonEmailChoiceField
from ietf.person.models import Person
from ietf.review.models import ReviewerSettings, UnavailablePeriod, ReviewSecretarySettings
from ietf.review.utils import close_review_request_states, setup_reviewer_field
from ietf.utils.textupload import get_cleaned_text_file_content
from ietf.utils.text import strip_suffix
from ietf.utils.ordereddict import insert_after_in_ordered_dict
from ietf.utils.fields import DatepickerDateField, MultiEmailField

# --- Constants --------------------------------------------------------

MAX_GROUP_DELEGATES = 3

# --- Utility Functions ------------------------------------------------

def roles_for_group_type(group_type):
    roles = ["chair", "secr", "techadv", "delegate", ]
    if group_type == "dir":
        roles.append("reviewer")
    return roles

# --- Forms ------------------------------------------------------------

class StatusUpdateForm(forms.Form):
    content = forms.CharField(widget=forms.Textarea, label='Status update', help_text = 'Edit the status update', required=False, strip=False)
    txt = forms.FileField(label='.txt format', help_text='Or upload a .txt file', required=False)

    def clean_content(self):
        return self.cleaned_data['content'].replace('\r','')

    def clean_txt(self):
        return get_cleaned_text_file_content(self.cleaned_data["txt"])


class ConcludeGroupForm(forms.Form):
    instructions = forms.CharField(widget=forms.Textarea(attrs={'rows': 30}), required=True, strip=False)

class GroupForm(forms.Form):
    name = forms.CharField(max_length=80, label="Name", required=True)
    acronym = forms.CharField(max_length=40, label="Acronym", required=True)
    state = forms.ModelChoiceField(GroupStateName.objects.all(), label="State", required=True)

    # roles
    chair_roles = SearchableEmailsField(label="Chairs", required=False, only_users=True)
    secr_roles = SearchableEmailsField(label="Secretaries", required=False, only_users=True)
    techadv_roles = SearchableEmailsField(label="Technical Advisors", required=False, only_users=True)
    delegate_roles = SearchableEmailsField(label="Delegates", required=False, only_users=True, max_entries=MAX_GROUP_DELEGATES,
                                      help_text=mark_safe("Chairs can delegate the authority to update the state of group documents - at most %s persons at a given time." % MAX_GROUP_DELEGATES))
    reviewer_roles = SearchableEmailsField(label="Reviewers", required=False, only_users=True)
    ad = forms.ModelChoiceField(Person.objects.filter(role__name="ad", role__group__state="active", role__group__type='area').order_by('name'), label="Shepherding AD", empty_label="(None)", required=False)

    parent = forms.ModelChoiceField(Group.objects.filter(state="active").order_by('name'), empty_label="(None)", required=False)
    list_email = forms.CharField(max_length=64, required=False)
    list_subscribe = forms.CharField(max_length=255, required=False)
    list_archive = forms.CharField(max_length=255, required=False)
    urls = forms.CharField(widget=forms.Textarea, label="Additional URLs", help_text="Format: https://site/path (Optional description). Separate multiple entries with newline. Prefer HTTPS URLs where possible.", required=False)

    def __init__(self, *args, **kwargs):
        self.group = kwargs.pop('group', None)
        self.group_type = kwargs.pop('group_type', False)
        if "field" in kwargs:
            field = kwargs["field"]
            del kwargs["field"]
            if field in roles_for_group_type(self.group_type):
                field = field + "_roles"
        else:
            field = None

        super(self.__class__, self).__init__(*args, **kwargs)

        if self.group_type == "rg":
            self.fields["state"].queryset = self.fields["state"].queryset.exclude(slug__in=("bof", "bof-conc"))

        # if previous AD is now ex-AD, append that person to the list
        ad_pk = self.initial.get('ad')
        choices = self.fields['ad'].choices
        if ad_pk and ad_pk not in [pk for pk, name in choices]:
            self.fields['ad'].choices = list(choices) + [("", "-------"), (ad_pk, Person.objects.get(pk=ad_pk).plain_name())]

        if self.group:
            self.fields['acronym'].widget.attrs['readonly'] = ""

        if self.group_type == "rg":
            self.fields['ad'].widget = forms.HiddenInput()
            self.fields['parent'].queryset = self.fields['parent'].queryset.filter(acronym="irtf")
            self.fields['parent'].initial = self.fields['parent'].queryset.first()
            self.fields['parent'].widget = forms.HiddenInput()
        else:
            self.fields['parent'].queryset = self.fields['parent'].queryset.filter(type="area")
            self.fields['parent'].label = "IETF Area"

        role_fields_to_remove = (set(strip_suffix(attr, "_roles") for attr in self.fields if attr.endswith("_roles"))
                                 - set(roles_for_group_type(self.group_type)))
        for r in role_fields_to_remove:
            del self.fields[r + "_roles"]
        if field:
            for f in self.fields:
                if f != field:
                    del self.fields[f]

    def clean_acronym(self):
        # Changing the acronym of an already existing group will cause 404s all
        # over the place, loose history, and generally muck up a lot of
        # things, so we don't permit it
        if self.group:
            return self.group.acronym # no change permitted

        acronym = self.cleaned_data['acronym'].strip().lower()

        if not re.match(r'^[a-z][a-z0-9]+$', acronym):
            raise forms.ValidationError("Acronym is invalid, must be at least two characters and only contain lowercase letters and numbers starting with a letter.")

        # be careful with acronyms, requiring confirmation to take existing or override historic
        existing = Group.objects.filter(acronym__iexact=acronym)
        if existing:
            existing = existing[0]

        confirmed = self.data.get("confirm_acronym", False)

        def insert_confirm_field(label, initial):
            # set required to false, we don't need it since we do the
            # validation of the field in here, and otherwise the
            # browser and Django may barf
            insert_after_in_ordered_dict(self.fields, "confirm_acronym", forms.BooleanField(label=label, required=False), after="acronym")
            # we can't set initial, it's ignored since the form is bound, instead mutate the data
            self.data = self.data.copy()
            self.data["confirm_acronym"] = initial

        if existing and existing.type_id == self.group_type:
            if existing.state_id == "bof":
                insert_confirm_field(label="Turn BoF %s into proposed %s and start chartering it" % (existing.acronym, existing.type.name), initial=True)
                if confirmed:
                    return acronym
                else:
                    raise forms.ValidationError("Warning: Acronym used for an existing BoF (%s)." % existing.name)
            else:
                insert_confirm_field(label="Set state of %s %s to proposed and start chartering it" % (existing.acronym, existing.type.name), initial=False)
                if confirmed:
                    return acronym
                else:
                    raise forms.ValidationError("Warning: Acronym used for an existing %s (%s, %s)." % (existing.type.name, existing.name, existing.state.name if existing.state else "unknown state"))

        if existing:
            raise forms.ValidationError("Acronym used for an existing group (%s)." % existing.name)

        old = GroupHistory.objects.filter(acronym__iexact=acronym, type__in=("wg", "rg"))
        if old:
            insert_confirm_field(label="Confirm reusing acronym %s" % old[0].acronym, initial=False)
            if confirmed:
                return acronym
            else:
                raise forms.ValidationError("Warning: Acronym used for a historic group.")

        return acronym

    def clean_urls(self):
        return [x.strip() for x in self.cleaned_data["urls"].splitlines() if x.strip()]

    def clean_delegates(self):
        if len(self.cleaned_data["delegates"]) > MAX_GROUP_DELEGATES:
            raise forms.ValidationError("At most %s delegates can be appointed at the same time, please remove %s delegates." % (
                    MAX_GROUP_DELEGATES, len(self.cleaned_data["delegates"]) - MAX_GROUP_DELEGATES))
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
            raise forms.ValidationError("A group cannot be its own ancestor.  "
                "Found that the group '%s' would end up being the ancestor of (%s)" % (p.acronym, ', '.join([g.acronym for g in seen])))
        
    def clean(self):
        cleaned_data = super(GroupForm, self).clean()
        state = cleaned_data.get('state', None)
        parent = cleaned_data.get('parent', None)
        if state and (state.slug in ['bof', ] and not parent):
            raise forms.ValidationError("You requested the creation of a BoF, but specified no parent area.  A parent is required when creating a bof.")
        return cleaned_data


class StreamEditForm(forms.Form):
    delegates = SearchableEmailsField(required=False, only_users=True)


# ----------------------------------------------------------------------

class ManageReviewRequestForm(forms.Form):
    ACTIONS = [
        ("assign", "Assign"),
        ("close", "Close"),
    ]

    action = forms.ChoiceField(choices=ACTIONS, widget=forms.HiddenInput, required=False)
    close = forms.ModelChoiceField(queryset=close_review_request_states(), required=False)
    reviewer = PersonEmailChoiceField(empty_label="(None)", required=False, label_with="person")
    add_skip = forms.BooleanField(required=False)

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


class EmailOpenAssignmentsForm(forms.Form):
    frm = forms.CharField(label="From", widget=forms.EmailInput(attrs={"readonly":True}))
    to = MultiEmailField()
    cc = MultiEmailField(required=False)
    reply_to = MultiEmailField(required=False)
    subject = forms.CharField()
    body = forms.CharField(widget=forms.Textarea, strip=False)


class ReviewerSettingsForm(forms.ModelForm):
    class Meta:
        model = ReviewerSettings
        fields = ['min_interval', 'filter_re', 'skip_next', 'remind_days_before_deadline','expertise']

    def __init__(self, *args, **kwargs):
       exclude_fields = kwargs.pop('exclude_fields', [])
       super(ReviewerSettingsForm, self).__init__(*args, **kwargs)
       for field_name in exclude_fields:
            self.fields.pop(field_name)

    def clean_skip_next(self):
        skip_next = self.cleaned_data.get('skip_next')
        if skip_next < 0:
            raise forms.ValidationError("Skip next must not be negative")
        return skip_next


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

        self.fields["end_date"] = DatepickerDateField(date_format="yyyy-mm-dd", picker_settings={"autoclose": "1", "start-date": start_date.isoformat() if start_date else "" })

        self.start_date = start_date

    def clean_end_date(self):
        end = self.cleaned_data["end_date"]
        if self.start_date and end < self.start_date:
            raise forms.ValidationError("End date must be equal to or come after start date.")
        return end


class ReviewSecretarySettingsForm(forms.ModelForm):
    class Meta:
        model = ReviewSecretarySettings
        fields = ['remind_days_before_deadline']


