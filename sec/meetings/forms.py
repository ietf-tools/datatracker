from django import forms
#from sec.proceedings.models import SessionName, Proceeding
#from sec.core.models import Acronym, MeetingRoom, MeetingTime, WgMeetingSession, TIME_ZONE_CHOICES
#from models import *

from ietf.meeting.models import Meeting, Room, TimeSlot, Session
import re

DAYS_CHOICES = ((0,'Monday'),
                (1,'Tuesday'),
                (2,'Wednesday'),
                (3,'Thursday'),
                (4,'Friday'),
                (5,'Saturday'),
                (6,'Sunday'))

"""
SESSION_CHOICES = list(SessionName.objects.values_list('session_name_id', 'session_name')) 
SESSION_CHOICES.insert(0,('0','-----------'))
#----------------------------------------------------------
# Helper Functions
#----------------------------------------------------------
"""
def get_next_slot(slot_id):
    '''Takes a Time object ID and returns the next time slot on the same day.
    Returns None if there is no later slot.  For use with combine option.
    '''
    # TODO is this correct?
    slot = TimeSlot.objects.get(id=slot_id)
    all_slots = TimeSlot.objects.filter(meeting=slot.meeting,time__startswith=slot.time.date()).order_by('time')
    try:
        i = list(all_slots).index(slot)
        return all_slots[i+1]
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
                
class BaseMeetingTimeFormSet(forms.models.BaseInlineFormSet):
    def clean(self):
        '''Check that any times marked for deletion aren't in use'''
        for form in self.deleted_forms:
            # returns the MeetingTime object
            meeting_time = form.cleaned_data['id']
            # returns the MeetingTime object id
            #id = form._raw_value('id')
            rawqs = WgMeetingSession.objects.raw('SELECT * FROM wg_meeting_sessions where sched_time_id1=%s or sched_time_id2=%s or sched_time_id3=%s' % (meeting_time.id, meeting_time.id, meeting_time.id))
            if len(list(rawqs)):
                raise forms.ValidationError('Cannot delete meeting time slot %s.  Already assigned to some session.' % meeting_time)
#----------------------------------------------------------
# Forms
#----------------------------------------------------------

class MeetingModelForm(forms.ModelForm):
    class Meta:
        model = Meeting
        exclude = ('type')
        
    def clean_number(self):
        number = self.cleaned_data['number']
        # this is now handled by model unique=True
        #if not self.instance.pk or 'number' in self.changed_data:
        #    if Meeting.objects.filter(number=number):
        #        raise forms.ValidationError('Meeting number %s is already in use.' % number)
        if not number.isdigit():
            raise forms.ValidationError('Meeting number must be an integer')
        return number
        
    def save(self, force_insert=False, force_update=False, commit=True):
        meeting = super(MeetingModelForm, self).save(commit=False)
        meeting.type_id = 'ietf'
        if commit:
            meeting.save()
        return meeting
        
class AddTutorialForm(forms.ModelForm):
    pass
        
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
    note = forms.CharField(max_length=255, required=False, label='Special Note from Scheduler')
    no_notify = forms.BooleanField(required=False, label="Do NOT notify this action")
    
    def __init__(self,*args,**kwargs):
        super(ExtraSessionForm, self).__init__(*args,**kwargs)
        self.fields['note'].widget.attrs['size'] = 40

class NewSessionForm(forms.Form):
    '''Time and Room choices will default to current meeting.  If we need otherwise
    pass to init like GroupSelectForm
    '''
    time = forms.ChoiceField(label='Day and Time')
    room = forms.ModelChoiceField(queryset=Room.objects)
    combine = forms.BooleanField(required=False, label='Combine with next session')
    
    # setup the room and time options based on meeting passed in
    def __init__(self,*args,**kwargs):
        meeting = kwargs.pop('meeting')
        self.meeting = meeting
        super(NewSessionForm, self).__init__(*args,**kwargs)
        all_times = TimeSlot.objects.filter(meeting=meeting).order_by('id')
        time_tuples = [(str(x.id), str(x)) for x in all_times]
        #time_choices = sorted(time_tuples, key=lambda time_tuples: time_tuples[1])
        self.fields['time'].choices = time_tuples
        self.fields['room'].queryset = Room.objects.filter(meeting=meeting).order_by('name')
        
    def clean(self):
        super(NewSessionForm, self).clean()
        if any(self.errors):
            return
        cleaned_data = self.cleaned_data
        room = cleaned_data['room']
        time = cleaned_data['time']
        if cleaned_data['combine']:
            slot = get_next_slot(cleaned_data['time'])
            if not slot:
                raise forms.ValidationError('There is no next session to combine')
        
        '''
        # TODO needs to exclude itself from query
        # error if session conflicts
        sessions = WgMeetingSession.objects.filter(meeting=self.meeting,sched_room_id1=room,sched_time_id1=time)
        if sessions:
            raise forms.ValidationError('The %s group has already scheduled this room during this time' % (sessions[0].group))
        sessions = WgMeetingSession.objects.filter(meeting=self.meeting,sched_room_id2=room,sched_time_id2=time)
        if sessions:
            raise forms.ValidationError('The %s group has already scheduled this room during this time' % (sessions[0].group))
        sessions = WgMeetingSession.objects.filter(meeting=self.meeting,sched_room_id3=room,sched_time_id3=time)
        if sessions:
            raise forms.ValidationError('The %s group has already scheduled this room during this time' % (sessions[0].group))
        
        '''
        return cleaned_data
"""
class NonSessionForm(forms.ModelForm):
    class Meta:
        model = NonSession
        
    def __init__(self, *args, **kwargs):
        super(NonSessionForm, self).__init__(*args, **kwargs)
        self.fields['time_desc'].label = '%s %s' % (self.instance.non_session_ref,
                                                    self.instance.day())
    
    def clean_time_desc(self):
        time_desc = self.cleaned_data['time_desc']
        if time_desc and time_desc != '0':
            match = re.match(r'\d{4}-\d{4}', time_desc)
            if not match:
                raise forms.ValidationError('Time must be in the from NNNN-NNNN')
        return time_desc
        
"""   
class TimeSlotForm(forms.Form):
    day = forms.ChoiceField(choices=DAYS_CHOICES)
    time = forms.IntegerField()
    
class TimeSlotModelForm(forms.ModelForm):
    class Meta:
        model = TimeSlot
        exclude = ('location','show_location','session','modified')