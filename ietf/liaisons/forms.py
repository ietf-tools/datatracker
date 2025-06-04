# Copyright The IETF Trust 2011-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import io
import operator
import os
from email.utils import parseaddr
from functools import reduce
from typing import Union, Optional  # pyflakes:ignore

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db.models import Q, QuerySet
from django.forms.utils import ErrorList
from django_stubs_ext import QuerySetAny

from ietf.doc.models import Document
from ietf.group.models import Group
from ietf.ietfauth.utils import has_role
from ietf.liaisons.fields import SearchableLiaisonStatementsField
from ietf.liaisons.models import (LiaisonStatement,
                                  LiaisonStatementEvent, LiaisonStatementAttachment, LiaisonStatementPurposeName)
from ietf.liaisons.utils import get_person_for_user, is_authorized_individual, OUTGOING_LIAISON_ROLES, \
    INCOMING_LIAISON_ROLES
from ietf.liaisons.widgets import ButtonWidget, ShowAttachmentsWidget
from ietf.name.models import DocRelationshipName
from ietf.person.models import Person
from ietf.utils.fields import DatepickerDateField, ModelMultipleChoiceField
from ietf.utils.timezone import date_today, datetime_from_date, DEADLINE_TZINFO

'''
NOTES:
Authorized individuals are people (in our Person table) who are authorized to send
messages on behalf of some other group - they have a formal role in the other group,
whereas the liaison manager has a formal role with the IETF (or more correctly,
with the IAB).
'''


# -------------------------------------------------
# Helper Functions
# -------------------------------------------------
def liaison_manager_sdos(person):
    return Group.objects.filter(type="sdo", state="active", role__person=person, role__name="liaiman").distinct()


def flatten_choices(choices):
    """Returns a flat choice list given one with option groups defined
    
    n.b., Django allows mixing grouped options and top-level options. This helper only supports
    the non-mixed case where every option is in an option group.
    """
    flat = []
    for optgroup, options in choices:
        flat.extend(options)
    return flat


def choices_from_group_queryset(groups: QuerySet[Group]):
    """Get choices list for internal IETF groups user is authorized to select
    
    Returns a grouped list of choices suitable for use with a ChoiceField. If user is None,
    includes all groups.
    """
    main = []
    areas = []
    wgs = []
    for g in groups.distinct().order_by("acronym"):
        if g.acronym in ("ietf", "iesg", "iab"):
            main.append((g.pk, f"The {g.acronym.upper()}"))
        elif g.type_id == "area":
            areas.append((g.pk, f"{g.acronym} - {g.name}"))
        elif g.type_id == "wg":
            wgs.append((g.pk, f"{g.acronym} - {g.name}"))
    choices = []
    if len(main) > 0:
        choices.append(("Main IETF Entities", main))
    if len(areas) > 0:
        choices.append(("IETF Areas", areas))
    if len(wgs) > 0:
        choices.append(("IETF Working Groups", wgs))
    return choices


def all_internal_groups():
    """Get a queryset of all IETF groups suitable for LS To/From assignment"""
    return Group.objects.filter(
        Q(acronym__in=("ietf", "iesg", "iab"))
        | Q(type="area", state="active")
        | Q(type="wg", state="active")
    ).distinct()


def internal_groups_for_person(person: Optional[Person]):
    """Get a queryset of IETF groups suitable for LS To/From assignment by person"""
    if person is None:
        return Group.objects.none()  # no person = no roles

    if has_role(
        person.user,
        (
            "Secretariat",
            "IETF Chair",
            "IAB Chair",
            "IAB Executive Director",
            "Liaison Manager",
            "Liaison Coordinator",
            "Authorized Individual",
        ),
    ):
        return all_internal_groups()
    # Interesting roles, as Group queries
    queries = [
        Q(role__person=person, role__name="chair", acronym="ietf"),
        Q(role__person=person, role__name__in=("chair", "execdir"), acronym="iab"),
        Q(role__person=person, role__name="ad", type="area", state="active"),
        Q(
            role__person=person,
            role__name__in=("chair", "secretary"),
            type="wg",
            state="active",
        ),
        Q(
            parent__role__person=person,
            parent__role__name="ad",
            type="wg",
            state="active",
        ),
    ]
    if has_role(person.user, "Area Director"):
        queries.append(Q(acronym__in=("ietf", "iesg")))  # AD can also choose these
    return Group.objects.filter(reduce(operator.or_, queries)).distinct()


def external_groups_for_person(person):
    """Get a queryset of external groups suitable for LS To/From assignment by person"""
    filter_expr = Q(pk__in=[])  # start with no groups
    # These roles can add all external sdo groups
    if has_role(person.user, set(INCOMING_LIAISON_ROLES + OUTGOING_LIAISON_ROLES) - {"Liaison Manager", "Authorized Individual"}):
        filter_expr |= Q(type="sdo")
    else:
        # The person cannot add all external sdo groups; add any for which they are Liaison Manager
        filter_expr |= Q(type="sdo", role__person=person, role__name__in=["auth", "liaiman"])
    return Group.objects.filter(state="active").filter(filter_expr).distinct().order_by("name")


def liaison_form_factory(request, type=None, **kwargs):
    """Returns appropriate Liaison entry form"""
    user = request.user
    if kwargs.get('instance',None):
        return EditLiaisonForm(user, **kwargs)
    elif type == 'incoming':
        return IncomingLiaisonForm(user, **kwargs)
    elif type == 'outgoing':
        return OutgoingLiaisonForm(user, **kwargs)
    return None

def validate_emails(value):
    '''Custom validator for emails'''
    value = value.strip()           # strip whitespace
    if '\r\n' in value:             # cc_contacts has newlines
        value = value.replace('\r\n',',')
    value = value.rstrip(',')       # strip trailing comma
    emails = value.split(',')
    for email in emails:
        name, addr = parseaddr(email)
        try:
            validate_email(addr)
        except ValidationError:
            raise forms.ValidationError('Invalid email address: %s' % addr)
        try:
            addr.encode('ascii')
        except UnicodeEncodeError as e:
            raise forms.ValidationError('Invalid email address: %s (check character %d)' % (addr,e.start))

# -------------------------------------------------
# Form Classes
# -------------------------------------------------
class AddCommentForm(forms.Form):
    comment = forms.CharField(required=True, widget=forms.Textarea, strip=False)
    private = forms.BooleanField(label="Private comment", required=False,help_text="If this box is checked the comment will not appear in the statement's public history view.")

# class RadioRenderer(RadioFieldRenderer):
#     def render(self):
#         output = []
#         for widget in self:
#             output.append(format_html(force_str(widget)))
#         return mark_safe('\n'.join(output))


class SearchLiaisonForm(forms.Form):
    '''Expects initial keyword argument queryset which then gets filtered based on form data'''
    text = forms.CharField(required=False)
#    scope = forms.ChoiceField(choices=(("all", "All text fields"), ("title", "Title field")), required=False, initial='title')
    source = forms.CharField(required=False)
    destination = forms.CharField(required=False)
    start_date = DatepickerDateField(date_format="yyyy-mm-dd", picker_settings={"autoclose": "1" }, label='Start date', required=False)
    end_date = DatepickerDateField(date_format="yyyy-mm-dd", picker_settings={"autoclose": "1" }, label='End date', required=False)

    def __init__(self, *args, **kwargs):
        self.queryset = kwargs.pop('queryset')
        super(SearchLiaisonForm, self).__init__(*args, **kwargs)

    def get_results(self):
        results = self.queryset
        if self.is_bound:
            query = self.cleaned_data.get('text')
            if query:
                q = (Q(title__icontains=query) |
                    Q(from_contact__icontains=query) |
                    Q(to_contacts__icontains=query) |
                    Q(other_identifiers__icontains=query) |
                    Q(body__icontains=query) |
                    Q(attachments__title__icontains=query,liaisonstatementattachment__removed=False) |
                    Q(technical_contacts__icontains=query) | 
                    Q(action_holder_contacts__icontains=query) |
                    Q(cc_contacts=query) |
                    Q(response_contacts__icontains=query))
                results = results.filter(q)

            source = self.cleaned_data.get('source')
            if source:
                source_list = source.split(',')
                if len(source_list) > 1:
                    results = results.filter(Q(from_groups__acronym__in=source_list))
                else:
                    results = results.filter(Q(from_groups__name__icontains=source) | Q(from_groups__acronym__iexact=source))

            destination = self.cleaned_data.get('destination')
            if destination:
                destination_list = destination.split(',')
                if len(destination_list) > 1:
                    results = results.filter(Q(to_groups__acronym__in=destination_list))
                else:
                    results = results.filter(Q(to_groups__name__icontains=destination) | Q(to_groups__acronym__iexact=destination))

            start_date = self.cleaned_data.get('start_date')
            end_date = self.cleaned_data.get('end_date')
            events = None
            if start_date:
                events = LiaisonStatementEvent.objects.filter(
                    type='posted',
                    time__gte=datetime_from_date(start_date, DEADLINE_TZINFO),
                )
                if end_date:
                    events = events.filter(time__lte=datetime_from_date(end_date, DEADLINE_TZINFO))
            elif end_date:
                events = LiaisonStatementEvent.objects.filter(type='posted', time__lte=end_date)
            if events:
                results = results.filter(liaisonstatementevent__in=events)

        results = results.distinct().order_by('title')
        return results


class CustomModelMultipleChoiceField(ModelMultipleChoiceField):
    '''If value is a QuerySet, return it as is (for use in widget.render)'''
    def prepare_value(self, value):
        if isinstance(value, QuerySetAny):
            return value
        if (hasattr(value, '__iter__') and
                not isinstance(value, str) and
                not hasattr(value, '_meta')):
            return [super(CustomModelMultipleChoiceField, self).prepare_value(v) for v in value]
        return super(CustomModelMultipleChoiceField, self).prepare_value(value)


class LiaisonModelForm(forms.ModelForm):
    '''Specify fields which require a custom widget or that are not part of the model.
    '''
    from_groups = ModelMultipleChoiceField(queryset=Group.objects.all(),label='Groups',required=False)
    to_contacts = forms.CharField(label="Contacts", widget=forms.Textarea(attrs={'rows':'3', }), strip=False)
    to_groups = ModelMultipleChoiceField(queryset=Group.objects,label='Groups',required=False)
    deadline = DatepickerDateField(date_format="yyyy-mm-dd", picker_settings={"autoclose": "1" }, label='Deadline', required=True)
    related_to = SearchableLiaisonStatementsField(label='Related Liaison Statement', required=False)
    submitted_date = DatepickerDateField(date_format="yyyy-mm-dd", picker_settings={"autoclose": "1" }, label='Submission date', required=True, initial=lambda: date_today(DEADLINE_TZINFO))
    attachments = CustomModelMultipleChoiceField(queryset=Document.objects,label='Attachments', widget=ShowAttachmentsWidget, required=False)
    attach_title = forms.CharField(label='Title', required=False)
    attach_file = forms.FileField(label='File', required=False)
    attach_button = forms.CharField(label='',
                                    widget=ButtonWidget(label='Attach', show_on='id_attachments',
                                                        require=['id_attach_title', 'id_attach_file'],
                                                        required_label='title and file'),
                                    required=False)
    class Meta:
        model = LiaisonStatement
        exclude = ('attachments','state','from_name','to_name')

    def __init__(self, user, *args, **kwargs):
        super(LiaisonModelForm, self).__init__(*args, **kwargs)
        self.user = user
        self.edit = False
        self.person = get_person_for_user(user)
        self.is_new = not self.instance.pk

        self.fields["from_groups"].widget.attrs["class"] = "select2-field"
        self.fields["from_groups"].widget.attrs["data-minimum-input-length"] = 0
        self.fields["from_groups"].widget.attrs["data-placeholder"] = "Type in name to search for group"
        self.fields["to_groups"].widget.attrs["class"] = "select2-field"
        self.fields["to_groups"].widget.attrs["data-minimum-input-length"] = 0
        self.fields["to_groups"].widget.attrs["data-placeholder"] = "Type in name to search for group"
        self.fields["to_contacts"].label = 'Contacts'
        self.fields["other_identifiers"].widget.attrs["rows"] = 2

        # add email validators
        for field in ['to_contacts','technical_contacts','action_holder_contacts','cc_contacts']:
            if field in self.fields:
                self.fields[field].validators.append(validate_emails)

        self.set_from_fields()
        self.set_to_fields()

    def clean_from_groups(self):
        from_groups = self.cleaned_data.get('from_groups')
        if not from_groups:
            raise forms.ValidationError('You must specify a From Group')
        return from_groups
        
    def clean_to_groups(self):
        to_groups = self.cleaned_data.get('to_groups')
        if not to_groups:
            raise forms.ValidationError('You must specify a To Group')
        return to_groups
        
# Note to future person: This is the wrong place to fix the new lines
# in cc_contacts and to_contacts. Those belong in the save function.
# Or at least somewhere other than here.
    def clean_cc_contacts(self):
        '''Return a comma separated list of addresses'''
        cc_contacts = self.cleaned_data.get('cc_contacts')
        cc_contacts = cc_contacts.replace('\r\n',',')
        cc_contacts = cc_contacts.rstrip(',')
        return cc_contacts
## to_contacts can also have new lines
    def clean_to_contacts(self):
        '''Return a comma separated list of addresses'''
        to_contacts = self.cleaned_data.get('to_contacts')
        to_contacts = to_contacts.replace('\r\n',',')
        to_contacts = to_contacts.rstrip(',')
        return to_contacts

    def clean(self):
        if not self.cleaned_data.get('body', None) and not self.has_attachments():
            self._errors['body'] = ErrorList(['You must provide a body or attachment files'])
            self._errors['attachments'] = ErrorList(['You must provide a body or attachment files'])

        # if purpose=response there must be a related statement
        purpose = LiaisonStatementPurposeName.objects.get(slug='response')
        if self.cleaned_data.get('purpose') == purpose and not self.cleaned_data.get('related_to'):
            self._errors['related_to'] = ErrorList(['You must provide a related statement when purpose is In Response'])
        return self.cleaned_data

    def full_clean(self):
        self.set_required_fields()
        super(LiaisonModelForm, self).full_clean()
        self.reset_required_fields()

    def has_attachments(self):
        for key in list(self.files.keys()):
            if key.startswith('attach_file_') and key.replace('file', 'title') in list(self.data.keys()):
                return True
        return False

    def is_approved(self):
        assert NotImplemented

    def save(self, *args, **kwargs):
        super(LiaisonModelForm, self).save(*args,**kwargs)

        # set state for new statements
        if self.is_new:
            self.instance.change_state(state_id='pending',person=self.person)
            if self.is_approved():
                self.instance.change_state(state_id='posted',person=self.person)
        else:
            # create modified event
            LiaisonStatementEvent.objects.create(
                type_id='modified',
                by=self.person,
                statement=self.instance,
                desc='Statement Modified'
            )

        self.save_related_liaisons()
        self.save_attachments()
        self.save_tags()

        return self.instance

    def save_attachments(self):
        '''Saves new attachments.
        Files come in with keys like "attach_file_N" where N is index of attachments
        displayed in the form.  The attachment title is in the corresponding
        request.POST[attach_title_N]
        '''
        written = self.instance.attachments.all().count()
        for key in list(self.files.keys()):
            title_key = key.replace('file', 'title')
            attachment_title = self.data.get(title_key)
            if not key.startswith('attach_file_') or not title_key in list(self.data.keys()):
                continue
            attached_file = self.files.get(key)
            extension=attached_file.name.rsplit('.', 1)
            if len(extension) > 1:
                extension = '.' + extension[1]
            else:
                extension = ''
            written += 1
            name = self.instance.name() + ("-attachment-%s" % written)
            attach, created = Document.objects.get_or_create(
                name = name,
                defaults=dict(
                    title = attachment_title,
                    type_id = "liai-att",
                    uploaded_filename = name + extension, 
                    )
                )
            LiaisonStatementAttachment.objects.create(statement=self.instance,document=attach)
            attach_file = io.open(os.path.join(settings.LIAISON_ATTACH_PATH, attach.name + extension), 'wb')
            attach_file.write(attached_file.read())
            attach_file.close()
            attached_file.seek(0)
            attach.store_file(attach.uploaded_filename, attached_file)

            if not self.is_new:
                # create modified event
                LiaisonStatementEvent.objects.create(
                    type_id='modified',
                    by=self.person,
                    statement=self.instance,
                    desc='Added attachment: {}'.format(attachment_title)
                )

    def save_related_liaisons(self):
        rel = DocRelationshipName.objects.get(slug='refold')
        new_related = self.cleaned_data.get('related_to', [])
        # add new ones
        for stmt in new_related:
            self.instance.source_of_set.get_or_create(target=stmt,relationship=rel)
        # delete removed ones
        for related in self.instance.source_of_set.all():
            if related.target not in new_related:
                related.delete()

    def save_tags(self):
        '''Create tags as needed'''
        if self.instance.deadline and not self.instance.tags.filter(slug='taken'):
            self.instance.tags.add('required')

    def set_from_fields(self):
        assert NotImplemented

    def set_required_fields(self):
        purpose = self.data.get('purpose', None)
        if purpose in ['action', 'comment']:
            self.fields['deadline'].required = True
        else:
            self.fields['deadline'].required = False

    def reset_required_fields(self):
        self.fields['deadline'].required = True

    def set_to_fields(self):
        assert NotImplemented

class IncomingLiaisonForm(LiaisonModelForm):
    def clean(self):
        if 'send' in list(self.data.keys()) and self.get_post_only():
            raise forms.ValidationError('As an IETF Liaison Manager you can not send incoming liaison statements, you only can post them')
        return super(IncomingLiaisonForm, self).clean()

    def is_approved(self):
        '''Incoming Liaison Statements do not required approval'''
        return True

    def get_post_only(self):
        from_groups = self.cleaned_data.get("from_groups")
        if (
            has_role(self.user, "Secretariat")
            or has_role(self.user, "Liaison Coordinator")
            or is_authorized_individual(self.user, from_groups)
        ):
            return False
        return True

    def set_from_fields(self):
        """Configure from "From" fields based on user roles"""
        qs = external_groups_for_person(self.person)
        self.fields["from_groups"].queryset = qs
        self.fields["from_groups"].widget.submitter = str(self.person)
        # if there's only one possibility make it the default
        if len(qs) == 1:
            self.fields['from_groups'].initial = qs

        # Note that the IAB chair currently doesn't get to work with incoming liaison statements
        if not (
            has_role(self.user, "Secretariat")
            or has_role(self.user, "Liaison Coordinator")
        ):
            self.fields["from_contact"].initial = (
                self.person.role_set.filter(group=qs[0]).first().email.formatted_email()
            )
            self.fields["from_contact"].widget.attrs["disabled"] = True

    def set_to_fields(self):
        '''Set to_groups and to_contacts options and initial value based on user
        accessing the form.  For incoming Liaisons, to_groups choices is the full set.
        '''
        self.fields['to_groups'].choices = choices_from_group_queryset(all_internal_groups())


class OutgoingLiaisonForm(LiaisonModelForm):
    approved = forms.BooleanField(label="Obtained prior approval", required=False)

    class Meta:
        model = LiaisonStatement
        exclude = ('attachments','state','from_name','to_name','action_holder_contacts')

    def is_approved(self):
        return self.cleaned_data['approved']

    def set_from_fields(self):
        """Configure from "From" fields based on user roles"""
        self.set_from_groups_field()
        self.set_from_contact_field()

    def set_from_groups_field(self):
        """Configure the from_groups field based on roles"""
        grouped_choices = choices_from_group_queryset(internal_groups_for_person(self.person))
        flat_choices = flatten_choices(grouped_choices)
        if len(flat_choices) == 1:
            self.fields["from_groups"].choices = flat_choices
            self.fields["from_groups"].initial = [flat_choices[0][0]]
        else:
            self.fields["from_groups"].choices = grouped_choices

    def set_from_contact_field(self):
        """Configure the from_contact field based on user roles"""
        # Secretariat can set this to any valid address but gets no default
        if has_role(self.user, "Secretariat"):
            return
        elif has_role(self.user, ["IAB Chair", "Liaison Coordinator"]):
            self.fields["from_contact"].initial = "IAB Chair <iab-chair@iab.org>"
            return
        elif has_role(self.user, "IETF Chair"):
            self.fields["from_contact"].initial = "IETF Chair <chair@ietf.org>"
            return
        # ... others have it set to the correct value and cannot change it
        self.fields['from_contact'].disabled = True
        # Set up the querysets we might use - only evaluated as needed
        liaison_manager_role = self.person.role_set.filter(name="liaiman", group__state="active")
        chair_or_ad_role = self.person.role_set.filter(
                    name__in=("ad", "chair"), group__state="active"
                )  
        if liaison_manager_role.exists():
            from_contact_email = liaison_manager_role.first().email
        elif chair_or_ad_role.exists():
            from_contact_email = chair_or_ad_role.first().email
        else:
            from_contact_email = self.person.email()
        self.fields['from_contact'].initial = from_contact_email.formatted_email()

    def set_to_fields(self):
        """Configure the "To" fields based on user roles"""
        qs = external_groups_for_person(self.person)
        self.fields['to_groups'].queryset = qs 

        # set initial
        if has_role(self.user, "Liaison Manager"):
            self.fields['to_groups'].initial = [
                qs.filter(role__person=self.person, role__name="liaiman").first()
            ]


class EditLiaisonForm(LiaisonModelForm):
    def __init__(self, *args, **kwargs):
        super(EditLiaisonForm, self).__init__(*args, **kwargs)
        self.edit = True
        self.fields['attachments'].initial = self.instance.liaisonstatementattachment_set.exclude(removed=True)
        self.fields['related_to'].initial = [ x.target for x in self.instance.source_of_set.all() ]
        self.fields['submitted_date'].initial = self.instance.submitted

    def save(self, *args, **kwargs):
        super(EditLiaisonForm, self).save(*args,**kwargs)
        if self.has_changed() and 'submitted_date' in self.changed_data:
            event = self.instance.liaisonstatementevent_set.filter(type='submitted').first()
            event.time = datetime_from_date(self.cleaned_data.get('submitted_date'), DEADLINE_TZINFO)
            event.save()

        return self.instance

    def set_from_fields(self):
        """Configure from "From" fields based on user roles"""
        if self.instance.is_outgoing():
            self.fields['from_groups'].choices = choices_from_group_queryset(internal_groups_for_person(self.person))
        else:
            self.fields["from_groups"].queryset = external_groups_for_person(self.person)
            if not has_role(self.user, "Secretariat"):
                self.fields['from_contact'].widget.attrs['disabled'] = True

    def set_to_fields(self):
        """Configure the "To" fields based on user roles"""
        if self.instance.is_outgoing():
            self.fields['to_groups'].queryset = external_groups_for_person(self.person)
        else:
            self.fields['to_groups'].choices = choices_from_group_queryset(all_internal_groups())


class EditAttachmentForm(forms.Form):
    title = forms.CharField(max_length=255)
