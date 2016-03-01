import datetime

from django import forms
from ietf.group.models import Group
from ietf.ietfauth.utils import has_role
from ietf.meeting.models import Meeting, Schedule, TimeSlot, Session, SchedTimeSessAssignment, countries, timezones

# need to insert empty option for use in ChoiceField
countries.insert(0, ('', '-'*9 ))
timezones.insert(0, ('', '-'*9 ))

class GroupModelChoiceField(forms.ModelChoiceField):
    '''
    Custom ModelChoiceField, changes the label to a more readable format
    '''
    def label_from_instance(self, obj):
        return obj.acronym

class InterimRequestForm(forms.Form):
    group = GroupModelChoiceField(queryset = Group.objects.filter(type__in=('wg','rg'),state='active').order_by('acronym'))
    date = forms.DateField()
    face_to_face = forms.BooleanField(required=False)
    city = forms.CharField(max_length=255,required=False)
    country = forms.ChoiceField(choices=countries,required=False)
    timezone = forms.ChoiceField(choices=timezones)
    remote_instructions = forms.CharField(max_length=1024)
    agenda = forms.CharField(widget=forms.Textarea)
    agenda_note = forms.CharField(widget=forms.Textarea)

    def __init__(self, request, *args, **kwargs):
        super(InterimRequestForm, self).__init__(*args, **kwargs)
        self.user = request.user
        self.person = self.user.person

        self.set_group_options()

    def _save_agenda(self, text):
        pass

    def save(self):
        agenda = self.cleaned_data.get('agenda')
        agenda_note = self.cleaned_data.get('agenda_note')
        date = self.cleaned_data.get('date')
        group = self.cleaned_data.get('group')
        city = self.cleaned_data.get('city')
        country = self.cleaned_data.get('country')
        timezone = self.cleaned_data.get('timezone')
        remote_instructions = self.cleaned_data.get('remote_instructions')
        sequence = Meeting.objects.filter(number__startswith='interim-%s-%s' % (date.year,group.acronym)).count() + 1
        number = 'interim-%s-%s-%s' % (date.year,group.acronym,sequence)
        meeting = Meeting.objects.create(number=number,type_id='interim',date=date,city=city,
            country=country,agenda_note=agenda_note,time_zone=timezone)
        schedule = Schedule.objects.create(meeting=meeting, owner=self.person, visible=True, public=True)
        slot = TimeSlot.objects.create(meeting=meeting, type_id="session", duration=30 * 60,
            time=datetime.datetime.combine(datetime.date.today(), datetime.time(9, 30)))
        session = Session.objects.create(meeting=meeting,
            group=group,
            requested_by=self.person,
            status_id='apprw',
            type_id='session',
            remote_instructions=remote_instructions)
        SchedTimeSessAssignment.objects.create(timeslot=slot, session=session, schedule=schedule)

        if agenda:
            self._save_agenda(agenda)

        return meeting

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

        self.fields['group'].queryset = queryset