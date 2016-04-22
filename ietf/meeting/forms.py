import datetime
import re

from django import forms
from django.core.validators import ValidationError
from django.forms.fields import Field
from django.utils.encoding import force_text
from django.utils import six

from ietf.group.models import Group
from ietf.ietfauth.utils import has_role
from ietf.meeting.models import Session, countries, timezones
from ietf.meeting.helpers import assign_interim_session
from ietf.utils.fields import DatepickerDateField

# need to insert empty option for use in ChoiceField
#countries.insert(0, ('', '-'*9 ))
countries.insert(0, ('', ''))
timezones.insert(0, ('', '-'*9 ))

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

    string = '{:02d}:{:02d}:{:02d}'.format(hours, minutes, seconds)
    if days:
        string = '{} '.format(days) + string
    if microseconds:
        string += '.{:06d}'.format(microseconds)

    return string

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

'''
class BaseSessionFormSet(BaseFormSet):
    def save_new_objects(self, commit=True):
        self.new_objects = []
        for form in self.extra_forms:
            if not form.has_changed():
                continue
            # If someone has marked an add form for deletion, don't save the
            # object.
            if self.can_delete and self._should_delete_form(form):
                continue
            self.new_objects.append(self.save_new(form, commit=commit))
            if not commit:
                self.saved_forms.append(form)
        return self.new_objects

    def save(self,commit=True):
        #return self.save_existing_objects(commit) + self.save_new_objects(commit)
        return self.save_new_objects(commit)
'''

# -------------------------------------------------
# Forms
# -------------------------------------------------

class InterimRequestForm(forms.Form):
    group = GroupModelChoiceField(queryset = Group.objects.filter(type__in=('wg','rg'),state='active').order_by('acronym'))
    in_person = forms.BooleanField(required=False)
    meeting_type = forms.ChoiceField(choices=(("single", "Single"), ("multi-day", "Multi-Day"), ('series','Series')), required=False, initial='single', widget=forms.RadioSelect)
    approved = forms.BooleanField(required=False)
    
    def __init__(self, request, *args, **kwargs):
        super(InterimRequestForm, self).__init__(*args, **kwargs)
        self.user = request.user
        self.person = self.user.person
        self.fields["group"].widget.attrs["class"] = "select2-field"
        self.set_group_options()

    def set_group_options(self):
        '''Set group options based on user accessing the form'''

        if has_role(self.user, "Secretariat"):
            return  # don't reduce group options
        if has_role(self.user, "Area Director"):
            queryset = Group.objects.filter(type="wg", state="active").order_by('acronym')
        elif has_role(self.user, "IRTF Chair"):
            queryset = Group.objects.filter(type="rg", state="active").order_by('acronym')
        elif has_role(self.user, "WG Chair"):
            queryset = Group.objects.filter(type="wg", state="active", role__person=self.person, role__name="chair").distinct().order_by('acronym')
        elif has_role(self.user, "RG Chair"):
            queryset = Group.objects.filter(type="rg", state="active", role__person=self.person, role__name="chair").distinct().order_by('acronym')
        self.fields['group'].queryset = queryset

        # if there's only one possibility make it the default
        if len(queryset) == 1:
            self.fields['group'].initial = queryset[0]

class InterimSessionForm(forms.Form):
    # unset: date,time,duration
    date = DatepickerDateField(date_format="yyyy-mm-dd", picker_settings={"autoclose": "1" }, label='Date', required=False)
    time = forms.TimeField(required=False)
    time_utc = forms.TimeField(required=False)
    duration = DurationField(required=False)
    end_time = forms.TimeField(required=False)
    end_time_utc = forms.TimeField(required=False)
    remote_instructions = forms.CharField(max_length=1024,required=False)
    agenda = forms.CharField(required=False,widget=forms.Textarea)
    agenda_note = forms.CharField(max_length=255,required=False)
    city = forms.CharField(max_length=255,required=False)
    country = forms.ChoiceField(choices=countries,required=False)
    timezone = forms.ChoiceField(choices=timezones)

    def __init__(self, *args, **kwargs):
        super(InterimSessionForm, self).__init__(*args, **kwargs)
        self.fields['timezone'].initial = 'UTC'
        
    def _save_agenda(self, text):
        pass

    def save(self, request, group, meeting, is_approved):
        person = request.user.person
        agenda = self.cleaned_data.get('agenda')
        agenda_note = self.cleaned_data.get('agenda_note')
        date = self.cleaned_data.get('date')
        time = self.cleaned_data.get('time')
        duration = self.cleaned_data.get('duration')
        remote_instructions = self.cleaned_data.get('remote_instructions')
        time = datetime.datetime.combine(date, time)
        if is_approved:
            status_id = 'scheda'
        else:
            status_id = 'apprw'
        session = Session.objects.create(meeting=meeting,
            group=group,
            requested_by=person,
            requested_duration=duration,
            status_id=status_id,
            type_id='session',
            remote_instructions=remote_instructions,
            agenda_note=agenda_note,)
        assign_interim_session(session,time)
       
        if agenda:
            self._save_agenda(agenda)
