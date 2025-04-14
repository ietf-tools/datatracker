# Copyright The IETF Trust 2012-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import re

from django import forms
from django.db.models import Q

from ietf.community.models import SearchRule, EmailSubscription
from ietf.doc.fields import SearchableDocumentsField
from ietf.person.models import Person
from ietf.person.fields import SearchablePersonField


class AddDocumentsForm(forms.Form):
    documents = SearchableDocumentsField(
        label="Add Internet-Drafts to track", doc_type="draft"
    )


class SearchRuleTypeForm(forms.Form):
    rule_type = forms.ChoiceField(
        choices=[("", "--------------")] + SearchRule.RULE_TYPES
    )


class SearchRuleForm(forms.ModelForm):
    person = SearchablePersonField()

    class Meta:
        model = SearchRule
        fields = ("state", "group", "person", "text")

    def __init__(self, clist, rule_type, *args, **kwargs):
        kwargs["prefix"] = rule_type  # add prefix to avoid mixups in the Javascript
        super(SearchRuleForm, self).__init__(*args, **kwargs)

        def restrict_state(state_type, slug=None):
            if "state" not in self.fields:
                raise RuntimeError(
                    f"Rule type {rule_type} cannot include state filtering"
                )
            f = self.fields["state"]
            f.queryset = f.queryset.filter(used=True).filter(type=state_type)
            if slug:
                f.queryset = f.queryset.filter(slug=slug)
            if len(f.queryset) == 1:
                f.initial = f.queryset[0].pk
                f.widget = forms.HiddenInput()

        if rule_type.endswith("_rfc"):
            del self.fields["state"]  # rfc rules must not look at document states

        if rule_type in ["group", "group_rfc", "area", "area_rfc", "group_exp"]:
            if rule_type == "group_exp":
                restrict_state("draft", "expired")
            else:
                if not rule_type.endswith("_rfc"):
                    restrict_state("draft", "active")

            if rule_type.startswith("area"):
                self.fields["group"].label = "Area"
                self.fields["group"].queryset = (
                    self.fields["group"]
                    .queryset.filter(Q(type="area") | Q(acronym="irtf"))
                    .order_by("acronym")
                )
            else:
                self.fields["group"].queryset = (
                    self.fields["group"]
                    .queryset.filter(type__in=("wg", "rg", "ag", "rag", "program"))
                    .order_by("acronym")
                )

            del self.fields["person"]
            del self.fields["text"]

        elif rule_type.startswith("state_"):
            mapping = {
                "state_iab": "draft-stream-iab",
                "state_iana": "draft-iana-review",
                "state_iesg": "draft-iesg",
                "state_irtf": "draft-stream-irtf",
                "state_ise": "draft-stream-ise",
                "state_rfceditor": "draft-rfceditor",
                "state_ietf": "draft-stream-ietf",
            }
            restrict_state(mapping[rule_type])

            del self.fields["group"]
            del self.fields["person"]
            del self.fields["text"]

        elif rule_type in ["author", "author_rfc", "shepherd", "ad"]:
            if not rule_type.endswith("_rfc"):
                restrict_state("draft", "active")

            if rule_type.startswith("author"):
                self.fields["person"].label = "Author"
            elif rule_type.startswith("shepherd"):
                self.fields["person"].label = "Shepherd"
            elif rule_type.startswith("ad"):
                self.fields["person"].label = "Area Director"
                self.fields["person"] = forms.ModelChoiceField(
                    queryset=Person.objects.filter(
                        role__name__in=("ad", "pre-ad"), role__group__state="active"
                    )
                    .distinct()
                    .order_by("name")
                )

            del self.fields["group"]
            del self.fields["text"]

        elif rule_type == "name_contains":
            if not rule_type.endswith("_rfc"):
                restrict_state("draft", "active")

            del self.fields["person"]
            del self.fields["group"]

        if "group" in self.fields:
            self.fields["group"].queryset = (
                self.fields["group"].queryset.filter(state="active").order_by("acronym")
            )
            self.fields["group"].choices = [
                (g.pk, "%s - %s" % (g.acronym, g.name))
                for g in self.fields["group"].queryset
            ]

        for name, f in self.fields.items():
            f.required = True

    def clean_text(self):
        candidate_text = (
            self.cleaned_data["text"].strip().lower()
        )  # names are always lower case
        try:
            re.compile(candidate_text)
        except re.error as e:
            raise forms.ValidationError(str(e))
        return candidate_text


class SubscriptionForm(forms.ModelForm):
    def __init__(self, person, clist, *args, **kwargs):
        self.clist = clist

        super(SubscriptionForm, self).__init__(*args, **kwargs)

        self.fields["notify_on"].widget = forms.RadioSelect(
            choices=self.fields["notify_on"].choices
        )
        self.fields["email"].queryset = (
            self.fields["email"]
            .queryset.filter(person=person, active=True)
            .order_by("-primary")
        )
        self.fields["email"].widget = forms.RadioSelect(
            choices=[t for t in self.fields["email"].choices if t[0]]
        )

        if self.fields["email"].queryset:
            self.fields["email"].initial = self.fields["email"].queryset[0]

    def clean_email(self):
        self.cleaned_data["email"].address = (
            self.cleaned_data["email"].address.strip().lower()
        )
        return self.cleaned_data["email"]

    def clean(self):
        if EmailSubscription.objects.filter(
            community_list=self.clist,
            email=self.cleaned_data["email"],
            notify_on=self.cleaned_data["notify_on"],
        ).exists():
            raise forms.ValidationError("You already have a subscription like this.")

    class Meta:
        model = EmailSubscription
        fields = ("notify_on", "email")
