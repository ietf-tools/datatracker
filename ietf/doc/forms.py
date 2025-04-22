# Copyright The IETF Trust 2013-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import datetime
import debug #pyflakes:ignore
from django import forms
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.validators import validate_email

from ietf.doc.fields import SearchableDocumentField, SearchableDocumentsField
from ietf.doc.models import RelatedDocument, DocExtResource
from ietf.iesg.models import TelechatDate
from ietf.iesg.utils import telechat_page_count
from ietf.person.fields import SearchablePersonField, SearchablePersonsField
from ietf.person.models import Email, Person

from ietf.name.models import ExtResourceName
from ietf.utils.timezone import date_today
from ietf.utils.validators import validate_external_resource_value

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
          if d - date_today() < datetime.timedelta(days=13):
              choice_display[d] += ' : WARNING - this may not leave enough time for directorate reviews!'
        self.fields['telechat_date'].choices = [("", "(not on agenda)")] + [(d, choice_display[d]) for d in dates]


class DocAuthorForm(forms.Form):
    person = SearchablePersonField()
    email = forms.ModelChoiceField(queryset=Email.objects.none(), required=False)
    affiliation = forms.CharField(max_length=100, required=False)
    country = forms.CharField(max_length=255, required=False)
    
    def __init__(self, *args, **kwargs):
        super(DocAuthorForm, self).__init__(*args, **kwargs)

        person = self.data.get(
            self.add_prefix('person'),
            self.get_initial_for_field(self.fields['person'], 'person')
        )
        if person:
            self.fields['email'].queryset = Email.objects.filter(person=person)

class DocAuthorChangeBasisForm(forms.Form):
    basis = forms.CharField(max_length=255, 
                            label='Reason for change', 
                            help_text='What is the source or reasoning for the changes to the author list?')
    
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
    notify = forms.CharField(
        widget=forms.Textarea,
        max_length=1023,
        help_text="List of email addresses to receive state notifications, separated by comma.",
        label="Notification list",
        required=False,
    )

    def clean_notify(self):
        # As long as the widget is a Textarea, users will separate addresses with newlines, whether that matches the instructions or not
        # We have been allowing nameaddrs for a long time (there are many Documents with namaddrs in their notify field)
        # python set doesn't preserve order, so in an attempt to mostly preserve the order of what was entered, we'll use
        # a dict (whose keys are guaranteed to be ordered) to cull out duplicates

        nameaddrs=dict()
        duplicate_addrspecs = set()
        bad_nameaddrs = []
        for nameaddr in self.cleaned_data["notify"].replace("\n", ",").split(","):
            stripped = nameaddr.strip()
            if stripped == "":
                continue
            if "<" in stripped:
                if stripped[-1] != ">":
                    bad_nameaddrs.append(nameaddr)
                    continue
                addrspec = stripped[stripped.find("<")+1:-1]
            else:
                addrspec = stripped
            try:
                validate_email(addrspec)
            except ValidationError:
                bad_nameaddrs.append(nameaddr)
            if addrspec in nameaddrs:
                duplicate_addrspecs.add(addrspec)
                continue
            else:
                nameaddrs[addrspec] = stripped
        error_messages = []
        if len(duplicate_addrspecs) != 0:
            error_messages.append(f'Duplicate addresses: {", ".join(duplicate_addrspecs)}')
        if len(bad_nameaddrs) != 0:
            error_messages.append(f'Invalid addresses: {", ".join(bad_nameaddrs)}')
        if len(error_messages) != 0:
            raise ValidationError(" and ".join(error_messages))
        return ", ".join(nameaddrs.values())

class ActionHoldersForm(forms.Form):
    action_holders = SearchablePersonsField(required=False)
    reason = forms.CharField(
        label='Reason for change',
        required=False,
        max_length=255,
        strip=True,
    )

IESG_APPROVED_STATE_LIST = ("ann", "rfcqueue", "pub")

class AddDownrefForm(forms.Form):
    rfc = SearchableDocumentField(
                label="Referenced RFC",
                help_text="The RFC that is approved for downref",
                required=True,
                doc_type="rfc")
    drafts = SearchableDocumentsField(
                label="Internet-Drafts that makes the reference",
                help_text="The Internet-Drafts that approve the downref in their Last Call",
                required=True)

    def clean_rfc(self):
        if 'rfc' not in self.cleaned_data:
            raise forms.ValidationError("Please provide a referenced RFC and a referencing Internet-Draft")

        rfc = self.cleaned_data['rfc']
        if rfc.type_id != "rfc":
            raise forms.ValidationError("Cannot find the RFC: " + rfc.name)
        return rfc

    def clean_drafts(self):
        if 'drafts' not in self.cleaned_data:
            raise forms.ValidationError("Please provide a referenced RFC and a referencing Internet-Draft")

        v_err_names = []
        drafts = self.cleaned_data['drafts']
        for d in drafts:
            state = d.get_state("draft-iesg")
            if not state or state.slug not in IESG_APPROVED_STATE_LIST:
                v_err_names.append(d.name)
        if v_err_names:
            raise forms.ValidationError("Internet-Draft is not yet approved: " + ", ".join(v_err_names))
        return drafts

    def clean(self):
        if 'rfc' not in self.cleaned_data or 'drafts' not in self.cleaned_data:
            raise forms.ValidationError("Please provide a referenced RFC and a referencing Internet-Draft")

        v_err_pairs = []
        rfc = self.cleaned_data['rfc']
        drafts = self.cleaned_data['drafts']
        for d in drafts:
            if RelatedDocument.objects.filter(source=d, target=rfc, relationship_id='downref-approval'):
                v_err_pairs.append(f"{d.name} --> RFC {rfc.rfc_number}")
        if v_err_pairs:
            raise forms.ValidationError("Downref is already in the registry: " + ", ".join(v_err_pairs))

        if 'save_downref_anyway' not in self.data:
        # this check is skipped if the save_downref_anyway button is used
            v_err_refnorm = ""
            for d in drafts:
                if not RelatedDocument.objects.filter(source=d, target=rfc, relationship_id='refnorm'):
                    if v_err_refnorm:
                        v_err_refnorm = v_err_refnorm + " or " + d.name
                    else:
                        v_err_refnorm = d.name
            if v_err_refnorm:
                v_err_refnorm_prefix = f"There does not seem to be a normative reference to RFC {rfc.rfc_number} by "
                raise forms.ValidationError(v_err_refnorm_prefix  + v_err_refnorm)


class ExtResourceForm(forms.Form):
    resources = forms.CharField(widget=forms.Textarea, label="Additional Resources", required=False,
                                help_text=("Format: 'tag value (Optional description)'."
                                           " Separate multiple entries with newline. When the value is a URL, use https:// where possible.") )

    def __init__(self, *args, initial=None, extresource_model=None, **kwargs):
        self.extresource_model = extresource_model
        if initial:
            kwargs = kwargs.copy()
            resources = initial.get('resources')
            if resources is not None and not isinstance(resources, str):
                initial = initial.copy()
                # Convert objects to string representation
                initial['resources'] = self.format_resources(resources)
            kwargs['initial'] = initial
        super(ExtResourceForm, self).__init__(*args, **kwargs)

    @staticmethod
    def format_resources(resources, fs="\n"):
        # Might be better to shift to a formset instead of parsing these lines.
        return fs.join([r.to_form_entry_str() for r in resources])

    def clean_resources(self):
        """Clean the resources field

        The resources field is a newline-separated set of resource entries. Each entry
        should be "<tag> <value>" or "<tag> <value> (<display name>)" with any whitespace
        delimiting the components. This clean only validates that the tag and value are
        present and valid - tag must be a recognized ExtResourceName and value is
        validated using validate_external_resource_value(). Further interpretation of
        the resource is performed int he clean() method.
        """
        lines = [x.strip() for x in self.cleaned_data["resources"].splitlines() if x.strip()]
        errors = []
        for l in lines:
            parts = l.split()
            if len(parts) == 1:
                errors.append("Too few fields: Expected at least tag and value: '%s'" % l)
            elif len(parts) >= 2:
                name_slug = parts[0]
                try:
                    name = ExtResourceName.objects.get(slug=name_slug)
                except ObjectDoesNotExist:
                    errors.append("Bad tag in '%s': Expected one of %s" % (l, ', '.join([ o.slug for o in ExtResourceName.objects.all() ])))
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

    def clean(self):
        """Clean operations after all other fields are cleaned by clean_<field> methods

        Converts resource strings into ExtResource model instances.
        """
        cleaned_data = super(ExtResourceForm, self).clean()
        cleaned_resources = []
        cls = self.extresource_model or DocExtResource
        for crs in cleaned_data.get('resources', []):
            cleaned_resources.append(
                cls.from_form_entry_str(crs)
            )
        cleaned_data['resources'] = cleaned_resources

    @staticmethod
    def valid_resource_tags():
        return ExtResourceName.objects.all().order_by('slug').values_list('slug', flat=True)

class InvestigateForm(forms.Form):
    name_fragment = forms.CharField(
        label="File name or fragment to investigate",
        required=True,
        help_text=(
            "Enter a filename such as draft-ietf-some-draft-00.txt or a fragment like draft-ietf-some-draft using at least 8 characters. The search will also work for files that are not necessarily drafts."
        ),
        min_length=8,
    )
    task_id = forms.CharField(required=False, widget=forms.HiddenInput)

    def clean_name_fragment(self):
        disallowed_characters = ["%", "/", "\\", "*"]
        name_fragment = self.cleaned_data["name_fragment"]
        # Manual inspection of the directories at the time of this writing shows
        # looking for files with less than 8 characters in the name is not useful
        # Requiring this will help protect against the secretariat unintentionally
        # matching every draft.
        if any(c in name_fragment for c in disallowed_characters):
            raise ValidationError(f"The following characters are disallowed: {', '.join(disallowed_characters)}")
        return name_fragment
