from django import forms
from django.db.models import Q

from ietf.group.models import Group
from ietf.meeting.models import Meeting, Room, TimeSlot, Session
from ietf.meeting.timedeltafield import TimedeltaFormField, TimedeltaWidget
from ietf.name.models import TimeSlotTypeName

import itertools
import re

DAYS_CHOICES = ((-1,'Saturday'),
                (0,'Sunday'),
                (1,'Monday'),
                (2,'Tuesday'),
                (3,'Wednesday'),
                (4,'Thursday'),
                (5,'Friday'))

"""
SESSION_CHOICES = list(SessionName.objects.values_list('session_name_id', 'session_name')) 
SESSION_CHOICES.insert(0,('0','-----------'))
#----------------------------------------------------------
# Helper Functions
#----------------------------------------------------------
"""
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
#----------------------------------------------------------
# Base Classes
#----------------------------------------------------------
class BaseMeetingRoomFormSet(forms.models.BaseInlineFormSet):
    def clean(self):
        '''Check that any rooms marked for deletion are not in use'''
        for form in self.deleted_forms:
            room = form.cleaned_data['id']
            sessions = Session.objects.filter(timeslot__location=room)
            if sessions:
                raise forms.ValidationError('Cannot delete meeting room %s.  Already assigned to some session.' % room.name)
                
class TimeSlotModelChoiceField(forms.ModelChoiceField):
    '''
    Custom ModelChoiceField, changes the label to a more readable format
    '''
    def label_from_instance(self, obj):
        
        return "%s %s - %s" % (obj.time.strftime('%a %H:%M'),obj.name,obj.location)
#----------------------------------------------------------
# Forms
#----------------------------------------------------------

class MeetingModelForm(forms.ModelForm):
    class Meta:
        model = Meeting
        exclude = ('type')
        
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

class MeetingTimeForm(forms.ModelForm):
    class Meta:
        model = TimeSlot
        fields = ('day_id', 'time_desc', 'session_name_id')
        
    def __init__(self, *args, **kwargs):
        super(MeetingTimeForm, self).__init__(*args, **kwargs)
        self.fields['day_id'].widget = forms.Select(choices=DAYS_CHOICES)
        self.fields['session_name_id'].widget = forms.Select(choices=SESSION_CHOICES)
    
    def clean_time_desc(self):
        time_desc = self.cleaned_data['time_desc']
        if time_desc and time_desc != '0':
            match = re.match(r'\d{4}-\d{4}', time_desc)
            if not match:
                raise forms.ValidationError('Time must be in the from NNNN-NNNN')
        return time_desc
        
class ExtraSessionForm(forms.Form):
    no_notify = forms.BooleanField(required=False, label="Do NOT notify this action")

class NewSessionForm(forms.Form):
    time = TimeSlotModelChoiceField(queryset=TimeSlot.objects,label='Day-Time-Room',required=False)
    session = forms.CharField(widget=forms.HiddenInput)
    note = forms.CharField(max_length=255, required=False, label='Special Note from Scheduler')
    combine = forms.BooleanField(required=False, label='Combine with next session')
    
    # setup the timeslot options based on meeting passed in
    def __init__(self,*args,**kwargs):
        meeting = kwargs.pop('meeting')
        super(NewSessionForm, self).__init__(*args,**kwargs)
        
        # attach session object to the form so we can use it in the template
        self.session_object = Session.objects.get(id=self.initial['session'])
        
        # if we are editing, timeslot queryset needs to include the timeslot the session was 
        # assigned to in order to initialize the form
        if self.initial['time']:
            queryset = TimeSlot.objects.filter(Q(meeting=meeting,type='session',session__isnull=True)|
                                               Q(session__id=self.initial['session']))
        else:
            queryset = TimeSlot.objects.filter(meeting=meeting,type='session',session__isnull=True)
        self.fields['time'].queryset = queryset.order_by('time')
    
    def clean_time(self):
        time = self.cleaned_data['time']
        if time:
            if not self.session_object.requested_duration <= time.duration:
                raise forms.ValidationError('The requested session length is longer than the duration of this timeslot')
        return time
        
    def clean(self):
        super(NewSessionForm, self).clean()
        if any(self.errors):
            return
        cleaned_data = self.cleaned_data
        time = cleaned_data['time']
        if cleaned_data['combine']:
            slot = get_next_slot(cleaned_data['time'])
            if not slot or slot.session != None:
                raise forms.ValidationError('There is no next session to combine')
        
        return cleaned_data

class RoomForm(forms.Form):
    location = forms.ModelChoiceField(queryset=Room.objects)
    group = forms.ModelChoiceField(queryset=Group.objects.filter(acronym__in=('edu','ietf','iepg','tools','iesg','iab','iaoc')),
        help_text='''Select a group to associate with this session.  For example:<br>
                     Tutorials = Education,<br>
                     Code Sprint = Tools Team,<br>
                     Technical Plenary = IAB,<br>
                     Administrative Plenary = IAOC or IESG''',empty_label=None)
    
    def __init__(self,*args,**kwargs):
        meeting = kwargs.pop('meeting')
        self.session = kwargs.pop('session')
        super(RoomForm, self).__init__(*args,**kwargs)
        self.fields['location'].queryset = Room.objects.filter(meeting=meeting)
    
    def clean_group(self):
        group = self.cleaned_data['group']
        if self.session.group != group and self.session.materials.all():
            raise forms.ValidationError("ERROR: can't change group after materials have been uploaded")
        return group
        
class TimeSlotForm(forms.Form):
    day = forms.ChoiceField(choices=DAYS_CHOICES)
    time = forms.TimeField()
    duration = TimedeltaFormField(widget=TimedeltaWidget(attrs={'inputs':['hours','minutes']}))
    name = forms.CharField()

class NonSessionForm(TimeSlotForm):
    # inherit TimeSlot and add Type field
    type = forms.ModelChoiceField(queryset=TimeSlotTypeName.objects.filter(slug__in=('other','reg','break')),empty_label=None)
    show_location = forms.BooleanField(required=False)
