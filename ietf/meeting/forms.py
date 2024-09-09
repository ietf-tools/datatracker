# Copyright The IETF Trust 2016-2023, All Rights Reserved
# -*- coding: utf-8 -*-


import io
import os
import datetime
import json
import re

from pathlib import Path

from django import forms
from django.conf import settings
from django.core import validators
from django.core.exceptions import ValidationError
from django.forms import BaseInlineFormSet
from django.utils.functional import cached_property

import debug                            # pyflakes:ignore

from ietf.doc.models import Document, State, NewRevisionDocEvent
from ietf.group.models import Group
from ietf.group.utils import groups_managed_by
from ietf.meeting.models import Session, Meeting, Schedule, countries, timezones, TimeSlot, Room
from ietf.meeting.helpers import get_next_interim_number, make_materials_directories
from ietf.meeting.helpers import is_interim_meeting_approved, get_next_agenda_name
from ietf.message.models import Message
from ietf.name.models import TimeSlotTypeName, SessionPurposeName
from ietf.person.models import Person
from ietf.utils.fields import (
    DatepickerDateField,
    DatepickerSplitDateTimeWidget,
    DurationField,
    ModelMultipleChoiceField,
    MultiEmailField,
)
from ietf.utils.validators import ( validate_file_size, validate_mime_type,
    validate_file_extension, validate_no_html_frame)

# need to insert empty option for use in ChoiceField
# countries.insert(0, ('', '-'*9 ))
countries.insert(0, ('', '-' * 9))
timezones.insert(0, ('', '-' * 9))

# -------------------------------------------------
# Helpers
# -------------------------------------------------


class GroupModelChoiceField(forms.ModelChoiceField):
    '''
    Custom ModelChoiceField, changes the label to a more readable format
    '''
    def label_from_instance(self, obj):
        return obj.acronym

class CustomDurationField(DurationField):
    """Custom DurationField to display as HH:MM (no seconds)"""
    widget = forms.TextInput(dict(placeholder='HH:MM'))
    def prepare_value(self, value):
        if isinstance(value, datetime.timedelta):
            return duration_string(value)
        return value

def duration_string(duration):
    '''Custom duration_string to return HH:MM (no seconds)'''
    days = duration.days
    seconds = duration.seconds

    minutes = seconds // 60
    hours = minutes // 60
    minutes = minutes % 60

    string = '{:02d}:{:02d}'.format(hours, minutes)
    if days:
        string = '{} '.format(days) + string

    return string


# -------------------------------------------------
# Forms
# -------------------------------------------------

class InterimSessionInlineFormSet(BaseInlineFormSet):
    def __init__(self, *args, **kwargs):
        super(InterimSessionInlineFormSet, self).__init__(*args, **kwargs)
        if 'data' in kwargs:
            self.meeting_type = kwargs['data']['meeting_type']

    def clean(self):
        '''Custom clean method to verify dates are consecutive for multi-day meetings'''
        super(InterimSessionInlineFormSet, self).clean()
        if self.meeting_type == 'multi-day':
            dates = []
            for form in self.forms:
                date = form.cleaned_data.get('date')
                if date:
                    dates.append(date)
            if len(dates) < 2:
                return
            dates.sort()
            last_date = dates[0]
            for date in dates[1:]:
                if date - last_date != datetime.timedelta(days=1):
                    raise forms.ValidationError('For Multi-Day meetings, days must be consecutive')
                last_date = date
            self.days = len(dates)
        return                          # formset doesn't have cleaned_data

class InterimMeetingModelForm(forms.ModelForm):
    group = GroupModelChoiceField(
        queryset=Group.objects.with_meetings().filter(
            state__in=('active', 'proposed', 'bof')
        ).order_by('acronym'),
        required=False,
        empty_label="Click to select",
    )
    group.widget.attrs['data-max-entries'] = 1
    group.widget.attrs['data-minimum-input-length'] = 0
    in_person = forms.BooleanField(required=False)
    meeting_type = forms.ChoiceField(
        choices=(
            ("single", "Single"),
            ("multi-day", "Multi-Day"),
            ('series', 'Series')
        ),
        required=False,
        initial='single',
        widget=forms.RadioSelect,
        help_text='''
            Use <b>Multi-Day</b> for a single meeting that spans more than one contiguous
            workday. Do not use Multi-Day for a series of separate meetings (such as
            periodic interim calls). Use Series instead.
            Use <b>Series</b> for a series of separate meetings, such as periodic interim calls.
            Use Multi-Day for a single meeting that spans more than one contiguous
            workday.''',
    )
    approved = forms.BooleanField(required=False)
    city = forms.CharField(max_length=255, required=False)
    city.widget.attrs['placeholder'] = "City"
    country = forms.ChoiceField(choices=countries, required=False)
    country.widget.attrs['class'] = "select2-field"
    country.widget.attrs['data-max-entries'] = 1
    country.widget.attrs['data-placeholder'] = "Country"
    country.widget.attrs['data-minimum-input-length'] = 0
    time_zone = forms.ChoiceField(choices=timezones)
    time_zone.widget.attrs['class'] = "select2-field"
    time_zone.widget.attrs['data-max-entries'] = 1
    time_zone.widget.attrs['data-minimum-input-length'] = 0

    class Meta:
        model = Meeting
        fields = ('group', 'in_person', 'meeting_type', 'approved', 'city', 'country', 'time_zone')

    def __init__(self, request, *args, **kwargs):
        super(InterimMeetingModelForm, self).__init__(*args, **kwargs)
        self.user = request.user
        self.person = self.user.person
        self.is_edit = bool(self.instance.pk)
        self.fields['group'].widget.attrs['class'] = "select2-field"
        self.fields['time_zone'].initial = 'UTC'
        self.fields['approved'].initial = True
        self.set_group_options()
        if self.is_edit:
            self.fields['group'].initial = self.instance.session_set.first().group
            self.fields['group'].widget.attrs['disabled'] = True
            if self.instance.city or self.instance.country:
                self.fields['in_person'].initial = True
            if is_interim_meeting_approved(self.instance):
                self.fields['approved'].initial = True
            else:
                self.fields['approved'].initial = False
            self.fields['approved'].widget.attrs['disabled'] = True

    def clean(self):
        super(InterimMeetingModelForm, self).clean()
        cleaned_data = self.cleaned_data
        if not cleaned_data.get('group'):
            raise forms.ValidationError("You must select a group")

        return self.cleaned_data

    def is_virtual(self):
        if not self.is_bound or self.data.get('in_person'):
            return False
        else:
            return True

    def set_group_options(self):
        """Set group options based on user accessing the form"""
        queryset = groups_managed_by(
            self.user,
            Group.objects.with_meetings(),
        ).filter(
            state_id__in=['active', 'proposed', 'bof']
        ).order_by('acronym')
        self.fields['group'].queryset = queryset
        # if there's only one possibility make it the default
        if len(queryset) == 1:
            self.fields['group'].initial = queryset[0]

    def save(self, *args, **kwargs):
        '''Save must handle fields not included in the form: date,number,type_id'''
        date = kwargs.pop('date')
        group = self.cleaned_data.get('group')
        meeting = super(InterimMeetingModelForm, self).save(commit=False)
        if not meeting.type_id:
            meeting.type_id = 'interim'
        if not meeting.number:
            meeting.number = get_next_interim_number(group.acronym, date)
        meeting.date = date
        meeting.days = 1
        if kwargs.get('commit', True):
            # create schedule with meeting
            meeting.save()  # pre-save so we have meeting.pk for schedule
            if not meeting.schedule:
                meeting.schedule = Schedule.objects.create(
                    meeting=meeting,
                    owner=Person.objects.get(name='(System)'))
            meeting.save()  # save with schedule
            
            # create directories
            make_materials_directories(meeting)

        return meeting


class InterimSessionModelForm(forms.ModelForm):
    date = DatepickerDateField(date_format="yyyy-mm-dd", picker_settings={"autoclose": "1"}, label='Date', required=False)
    time = forms.TimeField(widget=forms.TimeInput(format='%H:%M'), required=True, help_text="Start time in meeting time zone")
    time.widget.attrs['placeholder'] = "HH:MM"
    requested_duration = CustomDurationField(required=True)
    end_time = forms.TimeField(required=False, help_text="End time in meeting time zone")
    end_time.widget.attrs['placeholder'] = "HH:MM"
    remote_participation = forms.ChoiceField(choices=(), required=False)
    remote_instructions = forms.CharField(
        max_length=1024,
        required=False,
        help_text='''
            For virtual interims, a conference link <b>should be provided in the original request</b> in all but the most unusual circumstances.
            Otherwise, "Remote participation is not supported" or "Remote participation information will be obtained at the time of approval" are acceptable values.
            See <a href="https://www.ietf.org/forms/wg-webex-account-request/">here</a> for more on remote participation support.
        ''',
    )
    agenda = forms.CharField(required=False, widget=forms.Textarea, strip=False)
    agenda.widget.attrs['placeholder'] = "Paste agenda here"
    agenda_note = forms.CharField(max_length=255, required=False, label=" Additional information")

    class Meta:
        model = Session
        fields = ('date', 'time', 'requested_duration', 'end_time',
                  'remote_instructions', 'agenda', 'agenda_note')

    def __init__(self, *args, **kwargs):
        if 'user' in kwargs:
            self.user = kwargs.pop('user')
        if 'group' in kwargs:
            self.group = kwargs.pop('group')
        if 'requires_approval' in kwargs:
            self.requires_approval = kwargs.pop('requires_approval')
        super(InterimSessionModelForm, self).__init__(*args, **kwargs)
        self.is_edit = bool(self.instance.pk)
        # setup fields that aren't intrinsic to the Session object
        if self.is_edit:
            self.initial['date'] = self.instance.official_timeslotassignment().timeslot.local_start_time().date()
            self.initial['time'] = self.instance.official_timeslotassignment().timeslot.local_start_time().time()
            if self.instance.agenda():
                doc = self.instance.agenda()
                content = doc.text_or_error()
                self.initial['agenda'] = content

        # set up remote participation choices
        choices = []
        if hasattr(settings, 'MEETECHO_API_CONFIG'):
            choices.append(('meetecho', 'Automatically create Meetecho conference'))
        choices.append(('manual', 'Manually specify remote instructions...'))
        self.fields['remote_participation'].choices = choices
        # put remote_participation ahead of remote_instructions
        field_order = [field for field in self.fields if field != 'remote_participation']
        field_order.insert(field_order.index('remote_instructions'), 'remote_participation')
        self.order_fields(field_order)

    def clean_date(self):
        '''Date field validator.  We can't use required on the input because
        it is a datepicker widget'''
        date = self.cleaned_data.get('date')
        if not date:
            raise forms.ValidationError('Required field')
        return date

    def clean_requested_duration(self):
        min_minutes = settings.INTERIM_SESSION_MINIMUM_MINUTES
        max_minutes = settings.INTERIM_SESSION_MAXIMUM_MINUTES
        duration = self.cleaned_data.get('requested_duration')
        if not duration or duration < datetime.timedelta(minutes=min_minutes) or duration > datetime.timedelta(minutes=max_minutes):
            raise forms.ValidationError('Provide a duration, %s-%smin.' % (min_minutes, max_minutes))
        return duration

    def clean(self):
        if self.cleaned_data.get('remote_participation', None) == 'meetecho':
            self.cleaned_data['remote_instructions'] = ''  # blank this out if we're creating a Meetecho conference
        elif not self.cleaned_data['remote_instructions']:
            self.add_error('remote_instructions', 'This field is required')
        return self.cleaned_data

    # Override to ignore the non-model 'remote_participation' field when computing has_changed()
    @cached_property
    def changed_data(self):
        data = super().changed_data
        if 'remote_participation' in data:
            data.remove('remote_participation')
        return data

    def save(self, *args, **kwargs):
        """NOTE: as the baseform of an inlineformset self.save(commit=True)
        never gets called"""
        session = super(InterimSessionModelForm, self).save(commit=False)
        session.group = self.group
        session.type_id = 'regular'
        session.purpose_id = 'regular'
        if kwargs.get('commit', True) is True:
            super(InterimSessionModelForm, self).save(commit=True)
        return session

    def save_agenda(self):
        if self.instance.agenda():
            doc = self.instance.agenda()
            doc.rev = str(int(doc.rev) + 1).zfill(2)
            doc.uploaded_filename = doc.filename_with_rev()
            e = NewRevisionDocEvent.objects.create(
                type='new_revision',
                by=self.user.person,
                doc=doc,
                rev=doc.rev,
                desc='New revision available')
            doc.save_with_history([e])
        else:
            filename = get_next_agenda_name(meeting=self.instance.meeting)
            doc = Document.objects.create(
                type_id='agenda',
                group=self.group,
                name=filename,
                rev='00',
                # FIXME: if these are always computed, they shouldn't be in uploaded_filename - just compute them when needed
                # FIXME: What about agendas in html or markdown format?
                uploaded_filename='{}-00.txt'.format(filename))
            doc.set_state(State.objects.get(type__slug=doc.type.slug, slug='active'))
            self.instance.presentations.create(document=doc, rev=doc.rev)
            NewRevisionDocEvent.objects.create(
                type='new_revision',
                by=self.user.person,
                doc=doc,
                rev=doc.rev,
                desc='New revision available')
        # write file
        path = os.path.join(self.instance.meeting.get_materials_path(), 'agenda', doc.filename_with_rev())
        directory = os.path.dirname(path)
        if not os.path.exists(directory):
            os.makedirs(directory)
        with io.open(path, "w", encoding='utf-8') as file:
            file.write(self.cleaned_data['agenda'])


class InterimAnnounceForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ('to', 'cc', 'frm', 'subject', 'body')

    def __init__(self, *args, **kwargs):
        super(InterimAnnounceForm, self).__init__(*args, **kwargs)
        self.fields['frm'].label='From'
        self.fields['frm'].widget.attrs['readonly'] = True
        self.fields['to'].widget.attrs['readonly'] = True

    def save(self, *args, **kwargs):
        user = kwargs.pop('user')
        message = super(InterimAnnounceForm, self).save(commit=False)
        message.by = user.person
        message.save()

        return message


class InterimCancelForm(forms.Form):
    group = forms.CharField(max_length=255, required=False)
    date = forms.DateField(required=False)
    # max_length must match Session.agenda_note
    comments = forms.CharField(max_length=512, required=False, widget=forms.Textarea(attrs={'placeholder': 'enter optional comments here'}), strip=False)

    def __init__(self, *args, **kwargs):
        super(InterimCancelForm, self).__init__(*args, **kwargs)
        self.fields['group'].widget.attrs['disabled'] = True
        self.fields['date'].widget.attrs['disabled'] = True

class FileUploadForm(forms.Form):
    """Base class for FileUploadForms

    Abstract base class - subclasses must fill in the doc_type value with
    the type of document they handle.
    """
    file = forms.FileField(label='File to upload')

    doc_type = ''  # subclasses must set this

    def __init__(self, *args, **kwargs):
        assert self.doc_type in settings.MEETING_VALID_UPLOAD_EXTENSIONS
        self.extensions = settings.MEETING_VALID_UPLOAD_EXTENSIONS[self.doc_type]
        self.mime_types = settings.MEETING_VALID_UPLOAD_MIME_TYPES[self.doc_type]
        super(FileUploadForm, self).__init__(*args, **kwargs)
        label = '%s file to upload.  ' % (self.doc_type.capitalize(), )
        if self.doc_type == "slides":
            label += 'Did you remember to put in slide numbers? '
        if self.mime_types:
            label += 'Note that you can only upload files with these formats: %s.' % (', '.join(self.mime_types, ))
        self.fields['file'].label=label

    def clean_file(self):
        file = self.cleaned_data['file']
        validate_file_size(file)
        ext = validate_file_extension(file, self.extensions)

        # override the Content-Type if needed
        if file.content_type in 'application/octet-stream':
            content_type_map = settings.MEETING_APPLICATION_OCTET_STREAM_OVERRIDES
            filename = Path(file.name)
            if filename.suffix in content_type_map:
                file.content_type = content_type_map[filename.suffix]
                self.cleaned_data['file'] = file

        mime_type, encoding = validate_mime_type(file, self.mime_types)
        if not hasattr(self, 'file_encoding'):
            self.file_encoding = {}
        self.file_encoding[file.name] = encoding or None
        if self.mime_types:
            if not file.content_type in settings.MEETING_VALID_UPLOAD_MIME_FOR_OBSERVED_MIME[mime_type]:
                raise ValidationError('Upload Content-Type (%s) is different from the observed mime-type (%s)' % (file.content_type, mime_type))
            # We just validated that file.content_type is safe to accept despite being identified
            # as a different MIME type by the validator. Check extension based on file.content_type
            # because that better reflects the intention of the upload client.
            if file.content_type in settings.MEETING_VALID_MIME_TYPE_EXTENSIONS:
                if not ext in settings.MEETING_VALID_MIME_TYPE_EXTENSIONS[file.content_type]:
                    raise ValidationError('Upload Content-Type (%s) does not match the extension (%s)' % (file.content_type, ext))
        if (file.content_type in ['text/html', ]
                or ext in settings.MEETING_VALID_MIME_TYPE_EXTENSIONS.get('text/html', [])):
            # We'll do html sanitization later, but for frames, we fail here,
            # as the sanitized version will most likely be useless.
            validate_no_html_frame(file)
        return file


class UploadBlueSheetForm(FileUploadForm):
    doc_type = 'bluesheets'


class ApplyToAllFileUploadForm(FileUploadForm):
    """FileUploadField that adds an apply_to_all checkbox

    Checkbox can be disabled by passing show_apply_to_all_checkbox=False to the constructor.
    This entirely removes the field from the form.
    """
    # Note: subclasses must set doc_type for FileUploadForm
    apply_to_all = forms.BooleanField(label='Apply to all group sessions at this meeting',initial=True,required=False)

    def __init__(self, show_apply_to_all_checkbox, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not show_apply_to_all_checkbox:
            self.fields.pop('apply_to_all')
        else:
            self.order_fields(
                sorted(
                    self.fields.keys(),
                    key=lambda f: 'zzzzzz' if f == 'apply_to_all' else f
                )
            )

class UploadMinutesForm(ApplyToAllFileUploadForm):
    doc_type = 'minutes'

class UploadNarrativeMinutesForm(ApplyToAllFileUploadForm):
    doc_type = 'narrativeminutes'


class UploadAgendaForm(ApplyToAllFileUploadForm):
    doc_type = 'agenda'


class UploadSlidesForm(ApplyToAllFileUploadForm):
    doc_type = 'slides'
    title = forms.CharField(max_length=255)
    approved = forms.BooleanField(label='Auto-approve', initial=True, required=False)

    def __init__(self, session, show_apply_to_all_checkbox, can_manage, *args, **kwargs):
        super().__init__(show_apply_to_all_checkbox, *args, **kwargs)
        if not can_manage:
            self.fields.pop('approved')
        self.session = session

    def clean_title(self):
        title = self.cleaned_data['title']
        # The current tables only handles Unicode BMP:
        if ord(max(title)) > 0xffff:
            raise forms.ValidationError("The title contains characters outside the Unicode BMP, which is not currently supported")
        if self.session.meeting.type_id=='interim':
            if re.search(r'-\d{2}$', title):
                raise forms.ValidationError("Interim slides currently may not have a title that ends with something that looks like a revision number (-nn)")
        return title


class ImportMinutesForm(forms.Form):
    markdown_text = forms.CharField(strip=False, widget=forms.HiddenInput)


class RequestMinutesForm(forms.Form):
    to = MultiEmailField()
    cc = MultiEmailField(required=False)
    subject = forms.CharField()
    body = forms.CharField(widget=forms.Textarea,strip=False)


class SwapDaysForm(forms.Form):
    source_day = forms.DateField(required=True)
    target_day = forms.DateField(required=True)


class CsvModelPkInput(forms.TextInput):
    """Text input that expects a CSV list of PKs of a model instances"""
    def format_value(self, value):
        """Convert value to contents of input text widget

        Value is a list of pks, or None
        """
        return '' if value is None else ','.join(str(v) for v in value)

    def value_from_datadict(self, data, files, name):
        """Convert data back to list of PKs"""
        value = super(CsvModelPkInput, self).value_from_datadict(data, files, name)
        return value.split(',')


class SwapTimeslotsForm(forms.Form):
    """Timeslot swap form

    Interface uses timeslot instances rather than time/duration to simplify handling in
    the JavaScript. This might make more sense with a DateTimeField and DurationField for
    origin/target. Instead, grabs time and duration from a TimeSlot.

    This is not likely to be practical as a rendered form. Current use is to validate
    data from an ad hoc form. In an ideal world, this would be refactored to use a complex
    custom widget, but unless it proves to be reused that would be a poor investment of time.
    """
    origin_timeslot = forms.ModelChoiceField(
        required=True,
        queryset=TimeSlot.objects.none(),  # default to none, fill in when we have a meeting
        widget=forms.TextInput,
    )
    target_timeslot = forms.ModelChoiceField(
        required=True,
        queryset=TimeSlot.objects.none(),  # default to none, fill in when we have a meeting
        widget=forms.TextInput,
    )
    rooms = ModelMultipleChoiceField(
        required=True,
        queryset=Room.objects.none(),  # default to none, fill in when we have a meeting
        widget=CsvModelPkInput,
    )

    def __init__(self, meeting, *args, **kwargs):
        super(SwapTimeslotsForm, self).__init__(*args, **kwargs)
        self.meeting = meeting
        self.fields['origin_timeslot'].queryset = meeting.timeslot_set.all()
        self.fields['target_timeslot'].queryset = meeting.timeslot_set.all()
        self.fields['rooms'].queryset = meeting.room_set.all()


class TimeSlotDurationField(CustomDurationField):
    """Duration field for TimeSlot edit / create forms"""
    default_validators=[
        validators.MinValueValidator(datetime.timedelta(seconds=0)),
        validators.MaxValueValidator(datetime.timedelta(hours=12)),
    ]

    def __init__(self, **kwargs):
        kwargs.setdefault('help_text', 'Duration of timeslot in hours and minutes')
        super().__init__(**kwargs)


class TimeSlotEditForm(forms.ModelForm):
    class Meta:
        model = TimeSlot
        fields = ('name', 'type', 'time', 'duration', 'show_location', 'location')
        field_classes = dict(
            time=forms.SplitDateTimeField,
            duration=TimeSlotDurationField
        )
        widgets = dict(
            time=DatepickerSplitDateTimeWidget,
        )

    def __init__(self, *args, **kwargs):
        super(TimeSlotEditForm, self).__init__(*args, **kwargs)
        self.fields['location'].queryset = self.instance.meeting.room_set.all()


class TimeSlotCreateForm(forms.Form):
    name = forms.CharField(max_length=255)
    type = forms.ModelChoiceField(queryset=TimeSlotTypeName.objects.all(), initial='regular')
    days = forms.TypedMultipleChoiceField(
        label='Meeting days',
        widget=forms.CheckboxSelectMultiple,
        coerce=lambda s: datetime.date.fromordinal(int(s)),
        empty_value=None,
        required=False
    )
    other_date = DatepickerDateField(
        required=False,
        help_text='Optional date outside the official meeting dates',
        date_format="yyyy-mm-dd",
        picker_settings={"autoclose": "1"},
    )

    time = forms.TimeField(
        help_text='Time to create timeslot on each selected date',
        widget=forms.TimeInput(dict(placeholder='HH:MM'))
    )
    duration = TimeSlotDurationField()
    show_location = forms.BooleanField(required=False, initial=True)
    locations = ModelMultipleChoiceField(
        queryset=Room.objects.none(),
        widget=forms.CheckboxSelectMultiple,
    )

    def __init__(self, meeting, *args, **kwargs):
        super(TimeSlotCreateForm, self).__init__(*args, **kwargs)

        meeting_days = [
            meeting.date + datetime.timedelta(days=n)
            for n in range(meeting.days)
        ]

        # Fill in dynamic field properties
        self.fields['days'].choices = self._day_choices(meeting_days)
        self.fields['other_date'].widget.attrs['data-date-default-view-date'] = meeting.date
        self.fields['other_date'].widget.attrs['data-date-dates-disabled'] = ','.join(
            d.isoformat() for d in meeting_days
        )
        self.fields['locations'].queryset = meeting.room_set.order_by('name')

    def clean_other_date(self):
        # Because other_date is not required, failed field validation does not automatically
        # invalidate the form. It should, otherwise a typo may be silently ignored.
        if self.data.get('other_date') and not self.cleaned_data.get('other_date'):
            raise ValidationError('Enter a valid date or leave field blank.')
        return self.cleaned_data.get('other_date', None)

    def clean(self):
        # Merge other_date and days fields
        try:
            other_date = self.cleaned_data.pop('other_date')
        except KeyError:
            other_date = None

        self.cleaned_data['days'] = self.cleaned_data.get('days') or []
        if other_date is not None:
            self.cleaned_data['days'].append(other_date)
        if len(self.cleaned_data['days']) == 0:
            self.add_error('days', ValidationError('Please select a day or specify a date'))

    @staticmethod
    def _day_choices(days):
        """Generates an iterable of value, label pairs for a choice field

        Uses toordinal() to represent dates - would prefer to use isoformat(),
        but fromisoformat() is not available in python 3.6..
        """
        choices = [
            (str(day.toordinal()), day.strftime('%A ({})'.format(day.isoformat())))
            for day in days
        ]
        return choices


class DurationChoiceField(forms.ChoiceField):
    def __init__(self, durations=None, *args, **kwargs):
        if durations is None:
            durations = (3600, 5400, 7200)
        super().__init__(
            choices=self._make_choices(durations),
            *args, **kwargs,
        )

    def prepare_value(self, value):
        """Converts incoming value into string used for the option value"""
        if value:
            return str(int(value.total_seconds())) if isinstance(value, datetime.timedelta) else str(value)
        return ''

    def to_python(self, value):
        if value in self.empty_values or (isinstance(value, str) and not value.isnumeric()):
            return None  # treat non-numeric values as empty
        else:
            # noinspection PyTypeChecker
            return datetime.timedelta(seconds=round(float(value)))

    def valid_value(self, value):
        return super().valid_value(self.prepare_value(value))

    def _format_duration_choice(self, dur):
        seconds = int(dur.total_seconds()) if isinstance(dur, datetime.timedelta) else int(dur)
        hours = int(seconds / 3600)
        minutes = round((seconds - 3600 * hours) / 60)
        hr_str = '{} hour{}'.format(hours, '' if hours == 1 else 's')
        min_str = '{} minute{}'.format(minutes, '' if minutes == 1 else 's')
        if hours > 0 and minutes > 0:
            time_str = ' '.join((hr_str, min_str))
        elif hours > 0:
            time_str = hr_str
        else:
            time_str = min_str
        return (str(seconds), time_str)

    def _make_choices(self, durations):
        return (
            ('','--Please select'),
            *[self._format_duration_choice(dur) for dur in durations])

    def _set_durations(self, durations):
        self.choices = self._make_choices(durations)

    durations = property(None, _set_durations)


class SessionDetailsForm(forms.ModelForm):
    requested_duration = DurationChoiceField()

    def __init__(self, group, *args, **kwargs):
        session_purposes = group.features.session_purposes
        # Default to the first allowed session_purposes. Do not do this if we have an instance,
        # though, because ModelForm will override instance data with initial data if it gets both.
        # When we have an instance we want to keep its value.
        if 'instance' not in kwargs:
            kwargs.setdefault('initial', {})
            kwargs['initial'].setdefault(
                'purpose',
                session_purposes[0] if len(session_purposes) > 0 else None,
            )
            kwargs['initial'].setdefault('has_onsite_tool', group.features.acts_like_wg)
        super().__init__(*args, **kwargs)

        self.fields['type'].widget.attrs.update({
            'data-allowed-options': json.dumps({
                purpose.slug: list(purpose.timeslot_types)
                for purpose in SessionPurposeName.objects.all()
            }),
        })
        self.fields['purpose'].queryset = SessionPurposeName.objects.filter(pk__in=session_purposes)
        if not group.features.acts_like_wg:
            self.fields['requested_duration'].durations = [datetime.timedelta(minutes=m) for m in range(30, 241, 30)]

    class Meta:
        model = Session
        fields = (
            'purpose', 'name', 'short', 'type', 'requested_duration',
            'on_agenda', 'agenda_note', 'has_onsite_tool', 'chat_room', 'remote_instructions',
            'attendees', 'comments',
        )
        labels = {'requested_duration': 'Length'}

    def clean(self):
        super().clean()
        # Fill in on_agenda. If this is a new instance or we have changed its purpose, then use
        # the on_agenda value for the purpose. Otherwise, keep the value of an existing instance (if any)
        # or leave it blank.
        if 'purpose' in self.cleaned_data and (
                self.instance.pk is None or (self.instance.purpose != self.cleaned_data['purpose'])
        ):
            self.cleaned_data['on_agenda'] = self.cleaned_data['purpose'].on_agenda
        elif self.instance.pk is not None:
            self.cleaned_data['on_agenda'] = self.instance.on_agenda
        return self.cleaned_data

    class Media:
        js = ('ietf/js/session_details_form.js',)


class SessionEditForm(SessionDetailsForm):
    """Form to edit an existing session"""
    def __init__(self, instance, *args, **kwargs):
        kw_group = kwargs.pop('group', None)
        if kw_group is not None and kw_group != instance.group:
            raise ValueError('Session group does not match group keyword')
        super().__init__(instance=instance, group=instance.group, *args, **kwargs)


class SessionCancelForm(forms.Form):
    confirmed = forms.BooleanField(
        label='Cancel session?',
        help_text='Confirm that you want to cancel this session.',
    )


class SessionDetailsInlineFormSet(forms.BaseInlineFormSet):
    def __init__(self, group, meeting, queryset=None, *args, **kwargs):
        self._meeting = meeting

        # Restrict sessions to the meeting and group. The instance
        # property handles one of these for free.
        kwargs['instance'] = group
        if queryset is None:
            queryset = Session._default_manager
        if self._meeting.pk is not None:
            queryset = queryset.filter(meeting=self._meeting)
        else:
            queryset = queryset.none()
        kwargs['queryset'] = queryset.not_deleted()

        kwargs.setdefault('form_kwargs', {})
        kwargs['form_kwargs'].update({'group': group})

        super().__init__(*args, **kwargs)

    def save_new(self, form, commit=True):
        form.instance.meeting = self._meeting
        return super().save_new(form, commit)

    @property
    def forms_to_keep(self):
        """Get the not-deleted forms"""
        return [f for f in self.forms if f not in self.deleted_forms]

def sessiondetailsformset_factory(min_num=1, max_num=3):
    return forms.inlineformset_factory(
        Group,
        Session,
        formset=SessionDetailsInlineFormSet,
        form=SessionDetailsForm,
        can_delete=True,
        can_order=False,
        min_num=min_num,
        max_num=max_num,
        extra=max_num,  # only creates up to max_num total
    )
