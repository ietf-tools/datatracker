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

# using Django week_day lookup values (Sunday=1)
SESSION_DAYS = ((2,'Monday'),
                (3,'Tuesday'),
                (4,'Wednesday'),
                (5,'Thursday'),
                (6,'Friday'))
                
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
    Returns a list of tuples for use in a ChoiceField.  The value is a timeslot id, 
    The label is [start_time]-[end_time].
    '''
    # pick a random room
    rooms = Room.objects.filter(meeting=meeting)
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

class ExtraSessionForm(forms.Form):
    no_notify = forms.BooleanField(required=False, label="Do NOT notify this action")

class NewSessionForm(forms.Form):
    #time = TimeSlotModelChoiceField(queryset=TimeSlot.objects,label='Day-Time-Room',required=False)
    day = forms.ChoiceField(choices=SESSION_DAYS)
    time = forms.ChoiceField()
    room = forms.ModelChoiceField(queryset=Room.objects.none)
    session = forms.CharField(widget=forms.HiddenInput)
    note = forms.CharField(max_length=255, required=False, label='Special Note from Scheduler')
    combine = forms.BooleanField(required=False, label='Combine with next session')
    
    # setup the timeslot options based on meeting passed in
    def __init__(self,*args,**kwargs):
        meeting = kwargs.pop('meeting')
        super(NewSessionForm, self).__init__(*args,**kwargs)
        
        # attach session object to the form so we can use it in the template
        self.session_object = Session.objects.get(id=self.initial['session'])
        self.fields['room'].queryset = Room.objects.filter(meeting=meeting)
        self.fields['time'].choices = get_times(meeting,self.initial['day'])
        
    def clean_time(self):
        # skip the time validation because we're populating options from javascript
        return self.cleaned_data['time']
        
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

class NonSessionEditForm(forms.Form):
    name = forms.CharField(help_text='Name that appears on the agenda')
    short = forms.CharField(max_length=32,help_text='Enter an abbreviated session name (used for material file names)')
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
        super(NonSessionEditForm, self).__init__(*args,**kwargs)
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
    name = forms.CharField(help_text='Name that appears on the agenda')

class NonSessionForm(TimeSlotForm):
    # inherit TimeSlot and add extra fields
    short = forms.CharField(max_length=32,help_text='Enter an abbreviated session name (used for material file names)')
    type = forms.ModelChoiceField(queryset=TimeSlotTypeName.objects.filter(slug__in=('other','reg','break','plenary')),empty_label=None)
    show_location = forms.BooleanField(required=False)
