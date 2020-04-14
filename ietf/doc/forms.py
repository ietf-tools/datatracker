# Copyright The IETF Trust 2013-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import datetime
import debug #pyflakes:ignore
from django import forms

from ietf.doc.fields import SearchableDocAliasesField, SearchableDocAliasField
from ietf.doc.models import RelatedDocument
from ietf.iesg.models import TelechatDate
from ietf.iesg.utils import telechat_page_count

class TelechatForm(forms.Form):
    telechat_date = forms.TypedChoiceField(coerce=lambda x: datetime.datetime.strptime(x, '%Y-%m-%d').date(), empty_value=None, required=False, help_text="Page counts are the current page counts for the telechat, before this telechat date edit is made.")
    returning_item = forms.BooleanField(required=False)

    def __init__(self, *args, **kwargs):
        super(self.__class__, self).__init__(*args, **kwargs)

        dates = [d.date for d in TelechatDate.objects.active().order_by('date')]
        init = kwargs['initial'].get("telechat_date")
        if init and init not in dates:
            dates.insert(0, init)

        self.page_count = {}
        choice_display = {}
        for d in dates:
          self.page_count[d] = telechat_page_count(date=d).for_approval
          choice_display[d] = '%s (%s pages)' % (d.strftime("%Y-%m-%d"),self.page_count[d])
          if d-datetime.date.today() < datetime.timedelta(days=13):
              choice_display[d] += ' : WARNING - this may not leave enough time for directorate reviews!'
        self.fields['telechat_date'].choices = [("", "(not on agenda)")] + [(d, choice_display[d]) for d in dates]

from ietf.person.models import Person

class AdForm(forms.Form):
    ad = forms.ModelChoiceField(Person.objects.filter(role__name="ad", role__group__state="active", role__group__type='area').order_by('name'),
                                label="Shepherding AD", empty_label="(None)", required=True)

    def __init__(self, *args, **kwargs):
        super(self.__class__, self).__init__(*args, **kwargs)

        # if previous AD is now ex-AD, append that person to the list
        ad_pk = self.initial.get('ad')
        choices = self.fields['ad'].choices
        if ad_pk and ad_pk not in [pk for pk, name in choices]:
            self.fields['ad'].choices = list(choices) + [("", "-------"), (ad_pk, Person.objects.get(pk=ad_pk).plain_name())]

class NotifyForm(forms.Form):
    notify = forms.CharField(max_length=255, help_text="List of email addresses to receive state notifications, separated by comma.", label="Notification list", required=False)

    def clean_notify(self):
        addrspecs = [x.strip() for x in self.cleaned_data["notify"].split(',')]
        return ', '.join(addrspecs)

IESG_APPROVED_STATE_LIST = ("ann", "rfcqueue", "pub")

class AddDownrefForm(forms.Form):
    rfc = SearchableDocAliasField(
                label="Referenced RFC",
                help_text="The RFC that is approved for downref",
                required=True)
    drafts = SearchableDocAliasesField(
                label="Internet-Drafts that makes the reference",
                help_text="The drafts that approve the downref in their Last Call",
                required=True)

    def clean_rfc(self):
        if 'rfc' not in self.cleaned_data:
            raise forms.ValidationError("Please provide a referenced RFC and a referencing Internet-Draft")

        rfc = self.cleaned_data['rfc']
        if not rfc.document.is_rfc():
            raise forms.ValidationError("Cannot find the RFC: " + rfc.name)
        return rfc

    def clean_drafts(self):
        if 'drafts' not in self.cleaned_data:
            raise forms.ValidationError("Please provide a referenced RFC and a referencing Internet-Draft")

        v_err_names = []
        drafts = self.cleaned_data['drafts']
        for da in drafts:
            state = da.document.get_state("draft-iesg")
            if not state or state.slug not in IESG_APPROVED_STATE_LIST:
                v_err_names.append(da.name)
        if v_err_names:
            raise forms.ValidationError("Draft is not yet approved: " + ", ".join(v_err_names))
        return drafts

    def clean(self):
        if 'rfc' not in self.cleaned_data or 'drafts' not in self.cleaned_data:
            raise forms.ValidationError("Please provide a referenced RFC and a referencing Internet-Draft")

        v_err_pairs = []
        rfc = self.cleaned_data['rfc']
        drafts = self.cleaned_data['drafts']
        for da in drafts:
            if RelatedDocument.objects.filter(source=da.document, target=rfc, relationship_id='downref-approval'):
                v_err_pairs.append(da.name + " --> RFC " + rfc.document.rfc_number())
        if v_err_pairs:
            raise forms.ValidationError("Downref is already in the registry: " + ", ".join(v_err_pairs))

        if 'save_downref_anyway' not in self.data:
        # this check is skipped if the save_downref_anyway button is used
            v_err_refnorm = ""
            for da in drafts:
                if not RelatedDocument.objects.filter(source=da.document, target=rfc, relationship_id='refnorm'):
                    if v_err_refnorm:
                        v_err_refnorm = v_err_refnorm + " or " + da.name
                    else:
                        v_err_refnorm = da.name
            if v_err_refnorm:
                v_err_refnorm_prefix = "There does not seem to be a normative reference to RFC " + rfc.document.rfc_number() + " by "
                raise forms.ValidationError(v_err_refnorm_prefix  + v_err_refnorm)
