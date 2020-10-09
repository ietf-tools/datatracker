# Copyright The IETF Trust 2016-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import io
import os
import datetime

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.forms import BaseInlineFormSet

import debug                            # pyflakes:ignore

from ietf.doc.models import Document, DocAlias, State, NewRevisionDocEvent
from ietf.group.models import Group, GroupFeatures
from ietf.ietfauth.utils import has_role
from ietf.meeting.models import Session, Meeting, Schedule, countries, timezones
from ietf.meeting.helpers import get_next_interim_number, make_materials_directories
from ietf.meeting.helpers import is_interim_meeting_approved, get_next_agenda_name
from ietf.message.models import Message
from ietf.person.models import Person
from ietf.utils.fields import DatepickerDateField, DurationField, MultiEmailField
from ietf.utils.validators import ( validate_file_size, validate_mime_type,
    validate_file_extension, validate_no_html_frame)

# need to insert empty option for use in ChoiceField
# countries.insert(0, ('', '-'*9 ))
countries.insert(0, ('', ''))
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
    '''Custom DurationField to display as HH:MM (no seconds)'''
    def prepare_value(self, value):
        if isinstance(value, datetime.timedelta):
            return duration_string(value)
        return value

def duration_string(duration):
    '''Custom duration_string to return HH:MM (no seconds)'''
    days = duration.days
    seconds = duration.seconds
    microseconds = duration.microseconds

    minutes = seconds // 60
    seconds = seconds % 60

    hours = minutes // 60
    minutes = minutes % 60

    string = '{:02d}:{:02d}'.format(hours, minutes)
    if days:
        string = '{} '.format(days) + string
    if microseconds:
        string += '.{:06d}'.format(microseconds)

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
    group = GroupModelChoiceField(queryset=Group.objects.filter(type_id__in=GroupFeatures.objects.filter(has_meetings=True).values_list('type_id',flat=True), state__in=('active', 'proposed', 'bof')).order_by('acronym'), required=False)
    in_person = forms.BooleanField(required=False)
    meeting_type = forms.ChoiceField(choices=(
        ("single", "Single"),
        ("multi-day", "Multi-Day"),
        ('series', 'Series')), required=False, initial='single', widget=forms.RadioSelect)
    approved = forms.BooleanField(required=False)
    city = forms.CharField(max_length=255, required=False)
    country = forms.ChoiceField(choices=countries, required=False)
    time_zone = forms.ChoiceField(choices=timezones)

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
        '''Set group options based on user accessing the form'''
        if has_role(self.user, "Secretariat"):
            return  # don't reduce group options
        q_objects = Q()
        if has_role(self.user, "Area Director"):
            q_objects.add(Q(type__in=["wg", "ag"], state__in=("active", "proposed", "bof")), Q.OR)
        if has_role(self.user, "IRTF Chair"):
            q_objects.add(Q(type__in=["rg", "rag"], state__in=("active", "proposed")), Q.OR)
        if has_role(self.user, "WG Chair"):
            q_objects.add(Q(type="wg", state__in=("active", "proposed", "bof"), role__person=self.person, role__name="chair"), Q.OR)
        if has_role(self.user, "RG Chair"):
            q_objects.add(Q(type="rg", state__in=("active", "proposed"), role__person=self.person, role__name="chair"), Q.OR)
        if has_role(self.user, "Program Lead") or has_role(self.user, "Program Chair"):
            q_objects.add(Q(type="program", state__in=("active", "proposed"), role__person=self.person, role__name__in=["chair", "lead"]), Q.OR)
        
        queryset = Group.objects.filter(q_objects).distinct().order_by('acronym')
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
    time = forms.TimeField(widget=forms.TimeInput(format='%H:%M'), required=True)
    requested_duration = CustomDurationField(required=True)
    end_time = forms.TimeField(required=False)
    remote_instructions = forms.CharField(max_length=1024, required=True)
    agenda = forms.CharField(required=False, widget=forms.Textarea, strip=False)
    agenda_note = forms.CharField(max_length=255, required=False)

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
            self.initial['date'] = self.instance.official_timeslotassignment().timeslot.time
            self.initial['time'] = self.instance.official_timeslotassignment().timeslot.time
            if self.instance.agenda():
                doc = self.instance.agenda()
                content = doc.text_or_error()
                self.initial['agenda'] = content
                

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

    def save(self, *args, **kwargs):
        """NOTE: as the baseform of an inlineformset self.save(commit=True)
        never gets called"""
        session = super(InterimSessionModelForm, self).save(commit=False)
        session.group = self.group
        session.type_id = 'regular'
        if kwargs.get('commit', True) is True:
            super(InterimSessionModelForm, self).save(commit=True)
        return session

    def save_agenda(self):
        if self.instance.agenda():
            doc = self.instance.agenda()
            doc.rev = str(int(doc.rev) + 1).zfill(2)
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
            DocAlias.objects.create(name=doc.name).docs.add(doc)
            self.instance.sessionpresentation_set.create(document=doc, rev=doc.rev)
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
        fields = ('to', 'frm', 'cc', 'bcc', 'reply_to', 'subject', 'body')

    def save(self, *args, **kwargs):
        user = kwargs.pop('user')
        message = super(InterimAnnounceForm, self).save(commit=False)
        message.by = user.person
        message.save()

        return message


class InterimCancelForm(forms.Form):
    group = forms.CharField(max_length=255, required=False)
    date = forms.DateField(required=False)
    comments = forms.CharField(required=False, widget=forms.Textarea(attrs={'placeholder': 'enter optional comments here'}), strip=False)

    def __init__(self, *args, **kwargs):
        super(InterimCancelForm, self).__init__(*args, **kwargs)
        self.fields['group'].widget.attrs['disabled'] = True
        self.fields['date'].widget.attrs['disabled'] = True

class FileUploadForm(forms.Form):
    file = forms.FileField(label='File to upload')

    def __init__(self, *args, **kwargs):
        doc_type = kwargs.pop('doc_type')
        assert doc_type in settings.MEETING_VALID_UPLOAD_EXTENSIONS
        self.doc_type = doc_type
        self.extensions = settings.MEETING_VALID_UPLOAD_EXTENSIONS[doc_type]
        self.mime_types = settings.MEETING_VALID_UPLOAD_MIME_TYPES[doc_type]
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
        mime_type, encoding = validate_mime_type(file, self.mime_types)
        if not hasattr(self, 'file_encoding'):
            self.file_encoding = {}
        self.file_encoding[file.name] = encoding or None
        if self.mime_types:
            if not file.content_type in settings.MEETING_VALID_UPLOAD_MIME_FOR_OBSERVED_MIME[mime_type]:
                raise ValidationError('Upload Content-Type (%s) is different from the observed mime-type (%s)' % (file.content_type, mime_type))
            if mime_type in settings.MEETING_VALID_MIME_TYPE_EXTENSIONS:
                if not ext in settings.MEETING_VALID_MIME_TYPE_EXTENSIONS[mime_type]:
                    raise ValidationError('Upload Content-Type (%s) does not match the extension (%s)' % (file.content_type, ext))
        if mime_type in ['text/html', ] or ext in settings.MEETING_VALID_MIME_TYPE_EXTENSIONS['text/html']:
            # We'll do html sanitization later, but for frames, we fail here,
            # as the sanitized version will most likely be useless.
            validate_no_html_frame(file)
        return file

class RequestMinutesForm(forms.Form):
    to = MultiEmailField()
    cc = MultiEmailField(required=False)
    subject = forms.CharField()
    body = forms.CharField(widget=forms.Textarea,strip=False)
