# Copyright The IETF Trust 2013-2019, All Rights Reserved
import datetime
import re

from django import forms

import debug                            # pyflakes:ignore

from ietf.group.models import Group
from ietf.meeting.models import Meeting, Room, TimeSlot, Session, SchedTimeSessAssignment
from ietf.name.models import TimeSlotTypeName
import ietf.utils.fields


# using Django week_day lookup values (Sunday=1)
SESSION_DAYS = ((2,'Monday'),
                (3,'Tuesday'),
                (4,'Wednesday'),
                (5,'Thursday'),
                (6,'Friday'))
        
SESSION_DURATION_RE = re.compile(r'^\d{2}:\d{2}')

#----------------------------------------------------------
# Helper Functions
#----------------------------------------------------------
def get_next_slot(slot):
    '''Takes a TimeSlot object and returns the next TimeSlot same day and same room, None if there
    aren't any.  You must check availability of the slot as we sometimes need to get the next
    slot whether it's available or not.  For use with combine option.
    '''
    same_day_slots = TimeSlot.objects.filter(meeting=slot.meeting,location=slot.location,time__day=slot.time.day).order_by('time')
    try:
        i = list(same_day_slots).index(slot)
        return same_day_slots[i+1]
    except IndexError:
        return None
    
def get_times(meeting,day):
    '''
    Takes a Meeting object and an integer representing the week day (sunday=1).  
    Returns a list of tuples for use in a ChoiceField.  The value is start_time, 
    The label is [start_time]-[end_time].
    '''
    # pick a random room
    rooms = Room.objects.filter(meeting=meeting,session_types='regular')
    if rooms:
        room = rooms[0]
    else:
        room = None
    slots = TimeSlot.objects.filter(meeting=meeting,time__week_day=day,location=room).order_by('time')
    choices = [ (t.time.strftime('%H%M'), '%s-%s' % (t.time.strftime('%H%M'), t.end_time().strftime('%H%M'))) for t in slots ]
    return choices

#----------------------------------------------------------
# Base Classes
#----------------------------------------------------------
class BaseMeetingRoomFormSet(forms.models.BaseInlineFormSet):
    def clean(self):
        '''Check that any rooms marked for deletion are not in use'''
        for form in self.deleted_forms:
            room = form.cleaned_data['id']
            schedtimesessassignments = SchedTimeSessAssignment.objects.filter(timeslot__location=room,
                                                                session__isnull=False)
            if schedtimesessassignments:
                raise forms.ValidationError('Cannot delete meeting room %s.  Already assigned to some session.' % room.name)
                
class TimeSlotModelChoiceField(forms.ModelChoiceField):
    '''
    Custom ModelChoiceField, changes the label to a more readable format
    '''
    def label_from_instance(self, obj):
        
        return "%s %s - %s" % (obj.time.strftime('%a %H:%M'),obj.name,obj.location)
        
class TimeChoiceField(forms.ChoiceField):
    '''
    We are modifying the time choice field with javascript so the value submitted may not have
    been in the initial select list.  Just override valid_value validaion.
    '''
    def valid_value(self, value):
        return True
        
#----------------------------------------------------------
# Forms
#----------------------------------------------------------
class MeetingSelectForm(forms.Form):
    meeting = forms.ChoiceField()

    def __init__(self,*args,**kwargs):
        choices = kwargs.pop('choices')
        super(MeetingSelectForm, self).__init__(*args,**kwargs)
        self.fields['meeting'].widget.choices = choices

class MeetingModelForm(forms.ModelForm):
    idsubmit_cutoff_time_utc     = ietf.utils.fields.DurationField()
    idsubmit_cutoff_warning_days = ietf.utils.fields.DurationField()
    class Meta:
        model = Meeting
        exclude = ('type', 'schedule', 'session_request_lock_message')
        

    def __init__(self,*args,**kwargs):
        super(MeetingModelForm, self).__init__(*args,**kwargs)
        if 'instance' in kwargs:
            for f in [ 'idsubmit_cutoff_warning_days', 'idsubmit_cutoff_time_utc', ]:
                self.fields[f].help_text = kwargs['instance']._meta.get_field(f).help_text

    def clean_number(self):
        number = self.cleaned_data['number']
        if not number.isdigit():
            raise forms.ValidationError('Meeting number must be an integer')
        return number
        
    def save(self, force_insert=False, force_update=False, commit=True):
        meeting = super(MeetingModelForm, self).save(commit=False)
        meeting.type_id = 'ietf'
        if commit:
            meeting.save()
        return meeting
        
class MeetingRoomForm(forms.ModelForm):
    class Meta:
        model = Room
        exclude = ['resources']

class TimeSlotForm(forms.Form):
    day = forms.ChoiceField()
    time = forms.TimeField()
    duration = ietf.utils.fields.DurationField()
    name = forms.CharField(help_text='Name that appears on the agenda')
    
    def __init__(self,*args,**kwargs):
        if 'meeting' in kwargs:
            self.meeting = kwargs.pop('meeting')
        super(TimeSlotForm, self).__init__(*args,**kwargs)
        self.fields["time"].widget.attrs["placeholder"] = "HH:MM"
        self.fields["duration"].widget.attrs["placeholder"] = "HH:MM"
        self.fields["day"].choices = self.get_day_choices()

    def clean_duration(self):
        '''Limit to HH:MM format'''
        duration = self.data['duration']
        if not SESSION_DURATION_RE.match(duration):
            raise forms.ValidationError('{} value has an invalid format. It must be in HH:MM format'.format(duration))
        return self.cleaned_data['duration']

    def get_day_choices(self):
        '''Get day choices for form based on meeting duration'''
        choices = []
        start = self.meeting.date 
        for n in range(self.meeting.days):
            date = start + datetime.timedelta(days=n)
            choices.append((n, date.strftime("%a %b %d")))
        return choices


class MiscSessionForm(TimeSlotForm):
    short = forms.CharField(max_length=32,label='Short Name',help_text='Enter an abbreviated session name (used for material file names)',required=False)
    type = forms.ModelChoiceField(queryset=TimeSlotTypeName.objects.filter(used=True).exclude(slug__in=('regular',)),empty_label=None)
    group = forms.ModelChoiceField(
        queryset=Group.objects.filter(type__in=['ietf','team'],state='active'),
        help_text='''Select a group to associate with this session.  For example:<br>
                     Tutorials = Education,<br>
                     Code Sprint = Tools Team,<br>
                     Plenary = IETF''',
        required=False)
    location = forms.ModelChoiceField(queryset=Room.objects, required=False)
    show_location = forms.BooleanField(required=False)

    def __init__(self,*args,**kwargs):
        if 'meeting' in kwargs:
            self.meeting = kwargs.pop('meeting')
        if 'session' in kwargs:
            self.session = kwargs.pop('session')
        super(MiscSessionForm, self).__init__(*args,**kwargs)
        self.fields['location'].queryset = Room.objects.filter(meeting=self.meeting)

    def clean(self):
        super(MiscSessionForm, self).clean()
        if any(self.errors):
            return
        cleaned_data = self.cleaned_data
        group = cleaned_data['group']
        type = cleaned_data['type']
        short = cleaned_data['short']
        if type.slug in ('other','plenary','lead') and not group:
            raise forms.ValidationError('ERROR: a group selection is required')
        if type.slug in ('other','plenary','lead') and not short:
            raise forms.ValidationError('ERROR: a short name is required')
            
        return cleaned_data
    
    def clean_group(self):
        group = self.cleaned_data['group']
        if hasattr(self, 'session') and self.session.group != group and self.session.materials.all():
            raise forms.ValidationError("ERROR: can't change group after materials have been uploaded")
        return group

class UploadBlueSheetForm(forms.Form):
    file = forms.FileField(help_text='example: bluesheets-84-ancp-01.pdf')
    
    def clean_file(self):
        file = self.cleaned_data['file']
        if not re.match(r'bluesheets-\d+',file.name):
            raise forms.ValidationError('Incorrect filename format')
        return file

class RegularSessionEditForm(forms.ModelForm):
    class Meta:
        model = Session
        fields = ['agenda_note']

