import factory
import random
import datetime

from django.db.models import Max

from ietf.meeting.models import Meeting, Session, Schedule, TimeSlot, SessionPresentation
from ietf.group.factories import GroupFactory
from ietf.person.factories import PersonFactory

class MeetingFactory(factory.DjangoModelFactory):
    class Meta:
        model = Meeting

    type_id = factory.Iterator(['ietf','interim'])
    date = datetime.date(2010,1,1)+datetime.timedelta(days=random.randint(0,3652))
    city = factory.Faker('city')
    country = factory.Faker('country_code')
    time_zone = factory.Faker('timezone')
    idsubmit_cutoff_day_offset_00 = 13
    idsubmit_cutoff_day_offset_01 = 13
    idsubmit_cutoff_time_utc = datetime.timedelta(0, 86399)
    idsubmit_cutoff_warning_days = 21 
    venue_name = factory.Faker('sentence')
    venue_addr = factory.Faker('address')
    break_area = factory.Faker('sentence')
    reg_area = factory.Faker('sentence')

    @factory.lazy_attribute_sequence
    def number(self,n):
        if self.type_id == 'ietf':
            if Meeting.objects.filter(type='ietf').exists():
                return '%02d'%(int(Meeting.objects.filter(type='ietf').aggregate(Max('number'))['number__max'])+1)
            else:
                return '%02d'%(n+80)
        else:
            return 'interim-%d-%s-%02d'%(self.date.year,GroupFactory().acronym,n)

    @factory.post_generation
    def populate_agenda(self, create, extracted, **kwargs):
        '''
        Create a default agenda, unless the factory is called
        with populate_agenda=False
        '''
        if extracted is None:
            extracted = True
        if create and extracted:
            for x in range(3):
                TimeSlotFactory(meeting=self)
            self.agenda = ScheduleFactory(meeting=self)
            self.save()


class SessionFactory(factory.DjangoModelFactory):
    class Meta:
        model = Session

    meeting = factory.SubFactory(MeetingFactory)
    type_id='session'
    group = factory.SubFactory(GroupFactory)
    requested_by = factory.SubFactory(PersonFactory) 
    status_id='sched'

    @factory.post_generation
    def add_to_schedule(self, create, extracted, **kwargs):
        '''
        Put this session in a timeslot unless the factory is called
        with add_to_schedule=False
        '''
        if extracted is None:
            extracted = True
        if create and extracted:
            ts = self.meeting.timeslot_set.all()
            self.timeslotassignments.create(timeslot=ts[random.randrange(len(ts))],schedule=self.meeting.agenda)

class ScheduleFactory(factory.DjangoModelFactory):
    class Meta:
        model = Schedule

    meeting = factory.SubFactory(MeetingFactory)
    name = factory.Sequence(lambda n: 'schedule_%d'%n)
    owner = factory.SubFactory(PersonFactory)

class TimeSlotFactory(factory.DjangoModelFactory):
    class Meta:
        model = TimeSlot

    meeting = factory.SubFactory(MeetingFactory)
    type_id = 'session'
    
    @factory.lazy_attribute
    def time(self):
        return datetime.datetime.combine(self.meeting.date,datetime.time(11,0))

    @factory.lazy_attribute
    def duration(self):
        return datetime.timedelta(minutes=30+random.randrange(9)*15)

class SessionPresentationFactory(factory.DjangoModelFactory):
    class Meta:
        model = SessionPresentation

    session = factory.SubFactory(SessionFactory)
    document = factory.SubFactory('ietf.doc.factories.DocumentFactory')
    @factory.lazy_attribute
    def rev(self):
        return self.document.rev

