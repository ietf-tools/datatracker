import factory
import random
import datetime

from django.core.files.base import ContentFile

from ietf.meeting.models import Meeting, Session, Schedule, TimeSlot, SessionPresentation, FloorPlan
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
                so_far = max([int(x.number) for x in Meeting.objects.filter(type='ietf')])
                return '%02d'%(so_far+1)
            else:
                return '%02d'%(n+80)
        else:
            return 'interim-%d-%s-%02d'%(self.date.year,GroupFactory().acronym,n)

    @factory.post_generation
    def populate_agenda(obj, create, extracted, **kwargs): # pylint: disable=no-self-argument
        '''
        Create a default agenda, unless the factory is called
        with populate_agenda=False
        '''
        if extracted is None:
            extracted = True
        if create and extracted:
            for x in range(3):
                TimeSlotFactory(meeting=obj)
            obj.agenda = ScheduleFactory(meeting=obj)
            obj.save()


class SessionFactory(factory.DjangoModelFactory):
    class Meta:
        model = Session

    meeting = factory.SubFactory(MeetingFactory)
    type_id='session'
    group = factory.SubFactory(GroupFactory)
    requested_by = factory.SubFactory(PersonFactory) 
    status_id='sched'

    @factory.post_generation
    def add_to_schedule(obj, create, extracted, **kwargs): # pylint: disable=no-self-argument
        '''
        Put this session in a timeslot unless the factory is called
        with add_to_schedule=False
        '''
        if extracted is None:
            extracted = True
        if create and extracted:
            ts = obj.meeting.timeslot_set.all()
            obj.timeslotassignments.create(timeslot=ts[random.randrange(len(ts))],schedule=obj.meeting.agenda)

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

class FloorPlanFactory(factory.DjangoModelFactory):
    class Meta:
        model = FloorPlan

    name = factory.Sequence(lambda n: u'Venue Floor %d' % n)
    meeting = factory.SubFactory(MeetingFactory)
    order = factory.Sequence(lambda n: n)
    image = factory.LazyAttribute(
            lambda _: ContentFile(
                factory.django.ImageField()._make_data(
                    {'width': 1024, 'height': 768}
                ), 'floorplan.jpg'
            )
        )
        
