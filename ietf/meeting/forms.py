import datetime
import os
import re
import codecs

from django import forms
from django.core.validators import ValidationError
from django.forms.fields import Field
from django.utils.encoding import force_text
from django.utils import six

from ietf.doc.models import Document, DocAlias, State, NewRevisionDocEvent
from ietf.doc.utils import get_document_content
from ietf.group.models import Group
from ietf.ietfauth.utils import has_role
from ietf.meeting.models import Session, Meeting, Schedule, countries, timezones
from ietf.meeting.helpers import get_next_interim_number, make_materials_directories
from ietf.meeting.helpers import is_meeting_approved, get_next_agenda_name
from ietf.message.models import Message
from ietf.person.models import Person
from ietf.utils.fields import DatepickerDateField

# need to insert empty option for use in ChoiceField
# countries.insert(0, ('', '-'*9 ))
countries.insert(0, ('', ''))
timezones.insert(0, ('', '-' * 9))

# -------------------------------------------------
# DurationField from Django 1.8
# -------------------------------------------------


def duration_string(duration):
    days = duration.days
    seconds = duration.seconds
    microseconds = duration.microseconds

    minutes = seconds // 60
    seconds = seconds % 60

    hours = minutes // 60
    minutes = minutes % 60

    # string = '{:02d}:{:02d}:{:02d}'.format(hours, minutes, seconds)
    string = '{:02d}:{:02d}'.format(hours, minutes)
    if days:
        string = '{} '.format(days) + string
    if microseconds:
        string += '.{:06d}'.format(microseconds)

    return string

custom_duration_re = re.compile(
    r'^(?P<hours>\d+):(?P<minutes>\d+)$'
)

standard_duration_re = re.compile(
    r'^'
    r'(?:(?P<days>-?\d+) (days?, )?)?'
    r'((?:(?P<hours>\d+):)(?=\d+:\d+))?'
    r'(?:(?P<minutes>\d+):)?'
    r'(?P<seconds>\d+)'
    r'(?:\.(?P<microseconds>\d{1,6})\d{0,6})?'
    r'$'
)

# Support the sections of ISO 8601 date representation that are accepted by
# timedelta
iso8601_duration_re = re.compile(
    r'^P'
    r'(?:(?P<days>\d+(.\d+)?)D)?'
    r'(?:T'
    r'(?:(?P<hours>\d+(.\d+)?)H)?'
    r'(?:(?P<minutes>\d+(.\d+)?)M)?'
    r'(?:(?P<seconds>\d+(.\d+)?)S)?'
    r')?'
    r'$'
)


def parse_duration(value):
    """Parses a duration string and returns a datetime.timedelta.

    The preferred format for durations in Django is '%d %H:%M:%S.%f'.

    Also supports ISO 8601 representation.
    """
    match = custom_duration_re.match(value)
    if not match:
        match = standard_duration_re.match(value)
    if not match:
        match = iso8601_duration_re.match(value)
    if match:
        kw = match.groupdict()
        if kw.get('microseconds'):
            kw['microseconds'] = kw['microseconds'].ljust(6, '0')
        kw = {k: float(v) for k, v in six.iteritems(kw) if v is not None}
        return datetime.timedelta(**kw)


class DurationField(Field):
    default_error_messages = {
        'invalid': 'Enter a valid duration.',
    }

    def prepare_value(self, value):
        if isinstance(value, datetime.timedelta):
            return duration_string(value)
        return value

    def to_python(self, value):
        if value in self.empty_values:
            return None
        if isinstance(value, datetime.timedelta):
            return value
        value = parse_duration(force_text(value))
        if value is None:
            raise ValidationError(self.error_messages['invalid'], code='invalid')
        return value


# -------------------------------------------------
# Helpers
# -------------------------------------------------


class GroupModelChoiceField(forms.ModelChoiceField):
    '''
    Custom ModelChoiceField, changes the label to a more readable format
    '''
    def label_from_instance(self, obj):
        return obj.acronym

# -------------------------------------------------
# Forms
# -------------------------------------------------


class InterimMeetingModelForm(forms.ModelForm):
    group = GroupModelChoiceField(queryset=Group.objects.filter(type__in=('wg', 'rg'), state__in=('active', 'proposed', 'bof')).order_by('acronym'), required=False)
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
            if is_meeting_approved(self.instance):
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

    def set_group_options(self):
        '''Set group options based on user accessing the form'''
        if has_role(self.user, "Secretariat"):
            return  # don't reduce group options
        if has_role(self.user, "Area Director"):
            queryset = Group.objects.filter(type="wg", state__in=("active", "proposed", "bof")).order_by('acronym')
        elif has_role(self.user, "IRTF Chair"):
            queryset = Group.objects.filter(type="rg", state__in=("active", "proposed")).order_by('acronym')
        elif has_role(self.user, "WG Chair"):
            queryset = Group.objects.filter(type="wg", state__in=("active", "proposed", "bof"), role__person=self.person, role__name="chair").distinct().order_by('acronym')
        elif has_role(self.user, "RG Chair"):
            queryset = Group.objects.filter(type="rg", state__in=("active", "proposed"), role__person=self.person, role__name="chair").distinct().order_by('acronym')
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
        if kwargs.get('commit', True):
            # create schedule with meeting
            meeting.save()  # pre-save so we have meeting.pk for schedule
            if not meeting.agenda:
                meeting.agenda = Schedule.objects.create(
                    meeting=meeting,
                    owner=Person.objects.get(name='(System)'))
            meeting.save()  # save with agenda
            
            # create directories
            make_materials_directories(meeting)

        return meeting


class InterimSessionModelForm(forms.ModelForm):
    date = DatepickerDateField(date_format="yyyy-mm-dd", picker_settings={"autoclose": "1"}, label='Date', required=False)
    time = forms.TimeField(widget=forms.TimeInput(format='%H:%M'), required=True)
    requested_duration = DurationField(required=True)
    end_time = forms.TimeField(required=False)
    remote_instructions = forms.CharField(max_length=1024, required=True)
    agenda = forms.CharField(required=False, widget=forms.Textarea)
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
        if 'is_approved' in kwargs:
            self.is_approved = kwargs.pop('is_approved')
        super(InterimSessionModelForm, self).__init__(*args, **kwargs)
        self.is_edit = bool(self.instance.pk)
        # setup fields that aren't intrinsic to the Session object
        if self.is_edit:
            self.initial['date'] = self.instance.official_timeslotassignment().timeslot.time
            self.initial['time'] = self.instance.official_timeslotassignment().timeslot.time
            if self.instance.agenda():
                doc = self.instance.agenda()
                path = os.path.join(doc.get_file_path(), doc.filename_with_rev())
                self.initial['agenda'] = get_document_content(os.path.basename(path), path, markup=False)

    def clean_date(self):
        '''Date field validator.  We can't use required on the input because
        it is a datepicker widget'''
        date = self.cleaned_data.get('date')
        if not date:
            raise forms.ValidationError('Required field')
        return date

    def save(self, *args, **kwargs):
        """NOTE: as the baseform of an inlineformset self.save(commit=True)
        never gets called"""
        session = super(InterimSessionModelForm, self).save(commit=kwargs.get('commit', True))
        if self.is_approved:
            session.status_id = 'scheda'
        else:
            session.status_id = 'apprw'
        session.group = self.group
        session.type_id = 'session'
        if not self.instance.pk:
            session.requested_by = self.user.person

        return session

    def save_agenda(self):
        if self.instance.agenda():
            doc = self.instance.agenda()
            doc.rev = str(int(doc.rev) + 1).zfill(2)
            doc.save()
        else:
            filename = get_next_agenda_name(meeting=self.instance.meeting)
            doc = Document.objects.create(
                type_id='agenda',
                group=self.group,
                name=filename,
                rev='00',
                external_url='{}-00.txt'.format(filename))
            doc.set_state(State.objects.get(type=doc.type, slug='active'))
            DocAlias.objects.create(name=doc.name, document=doc)
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
        with codecs.open(path, "w", encoding='utf-8') as file:
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
    comments = forms.CharField(required=False, widget=forms.Textarea(attrs={'placeholder': 'enter optional comments here'}))

    def __init__(self, *args, **kwargs):
        super(InterimCancelForm, self).__init__(*args, **kwargs)
        self.fields['group'].widget.attrs['disabled'] = True
        self.fields['date'].widget.attrs['disabled'] = True
