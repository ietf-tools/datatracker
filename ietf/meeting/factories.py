# Copyright The IETF Trust 2016-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import factory
import random
import datetime

from django.core.files.base import ContentFile

from ietf.meeting.models import Meeting, Session, SchedulingEvent, Schedule, TimeSlot, SessionPresentation, FloorPlan, Room, SlideSubmission
from ietf.name.models import SessionStatusName
from ietf.group.factories import GroupFactory
from ietf.person.factories import PersonFactory

class MeetingFactory(factory.DjangoModelFactory):
    class Meta:
        model = Meeting

    type_id = factory.Iterator(['ietf','interim'])

    city = factory.Faker('city')
    country = factory.Faker('country_code')
    time_zone = factory.Faker('timezone')
    idsubmit_cutoff_day_offset_00 = 13
    idsubmit_cutoff_day_offset_01 = 13
    idsubmit_cutoff_time_utc = datetime.timedelta(0, 86399)
    idsubmit_cutoff_warning_days = datetime.timedelta(days=21)
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

    @factory.lazy_attribute
    def days(self):
        if self.type_id == 'ietf':
            return 7
        else:
            return 1

    @factory.lazy_attribute
    def date(self):
        if self.type_id == 'ietf':
            num = int(self.number)
            year = (num-2)//3+1985
            month = ((num-2)%3+1)*4-1
            day = random.randint(1,28)
            return datetime.date(year, month, day)
        else:
            return datetime.date(2010,1,1)+datetime.timedelta(days=random.randint(0,3652))


    @factory.post_generation
    def populate_schedule(obj, create, extracted, **kwargs): # pylint: disable=no-self-argument
        '''
        Create a default schedule, unless the factory is called
        with populate_agenda=False
        '''
        if extracted is None:
            extracted = True
        if create and extracted:
            for x in range(3):
                TimeSlotFactory(meeting=obj)
            obj.schedule = ScheduleFactory(meeting=obj)
            obj.save()

class SessionFactory(factory.DjangoModelFactory):
    class Meta:
        model = Session

    meeting = factory.SubFactory(MeetingFactory)
    type_id='regular'
    group = factory.SubFactory(GroupFactory)

    @factory.post_generation
    def status_id(obj, create, extracted, **kwargs):
        if create:
            if not extracted:
                extracted = 'sched'

            if extracted not in ['apprw', 'schedw']:
                # requested event
                SchedulingEvent.objects.create(
                    session=obj,
                    status=SessionStatusName.objects.get(slug='schedw'),
                    by=PersonFactory(),
                )

            # actual state event
            SchedulingEvent.objects.create(
                session=obj,
                status=SessionStatusName.objects.get(slug=extracted),
                by=PersonFactory(),
            )
                
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
            obj.timeslotassignments.create(timeslot=ts[random.randrange(len(ts))],schedule=obj.meeting.schedule)

class ScheduleFactory(factory.DjangoModelFactory):
    class Meta:
        model = Schedule

    meeting = factory.SubFactory(MeetingFactory)
    name = factory.Sequence(lambda n: 'schedule_%d'%n)
    owner = factory.SubFactory(PersonFactory)

class RoomFactory(factory.DjangoModelFactory):
    class Meta:
        model = Room

    meeting = factory.SubFactory(MeetingFactory)
    name = factory.Faker('name')


class TimeSlotFactory(factory.DjangoModelFactory):
    class Meta:
        model = TimeSlot

    meeting = factory.SubFactory(MeetingFactory)
    type_id = 'regular'

    @factory.post_generation
    def location(obj, create, extracted, **kwargs): # pylint: disable=no-self-argument
        if create:
            if extracted:
                obj.location = extracted
            else:
                obj.location = RoomFactory(meeting=obj.meeting)
            obj.save()
    
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

    name = factory.Sequence(lambda n: 'Venue Floor %d' % n)
    short = factory.Sequence(lambda n: '%d' % n)
    meeting = factory.SubFactory(MeetingFactory)
    order = factory.Sequence(lambda n: n)
    image = factory.LazyAttribute(
            lambda _: ContentFile(
                factory.django.ImageField()._make_data(
                    {'width': 1024, 'height': 768}
                ), 'floorplan.jpg'
            )
        )

class SlideSubmissionFactory(factory.DjangoModelFactory):
    class Meta:
        model = SlideSubmission

    session = factory.SubFactory(SessionFactory)
    title = factory.Faker('sentence')
    filename = factory.Sequence(lambda n: 'test_slide_%d'%n)
    submitter = factory.SubFactory(PersonFactory)

    make_file = factory.PostGeneration(
                    lambda obj, create, extracted, **kwargs: open(obj.staged_filepath(),'a').close()
                )
