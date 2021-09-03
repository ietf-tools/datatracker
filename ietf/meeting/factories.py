# Copyright The IETF Trust 2016-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import factory
import random
import datetime

from django.core.files.base import ContentFile
from django.db.models import Q

from ietf.meeting.models import (Meeting, Session, SchedulingEvent, Schedule,
    TimeSlot, SessionPresentation, FloorPlan, Room, SlideSubmission, Constraint,
    MeetingHost, ProceedingsMaterial)
from ietf.name.models import ConstraintName, SessionStatusName, ProceedingsMaterialTypeName, TimerangeName
from ietf.doc.factories import ProceedingsMaterialDocFactory
from ietf.group.factories import GroupFactory
from ietf.person.factories import PersonFactory
from ietf.utils.text import xslugify


class MeetingFactory(factory.django.DjangoModelFactory):
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

    @factory.post_generation
    def group_conflicts(obj, create, extracted, **kwargs):  # pulint: disable=no-self-argument
        """Add conflict types

        Pass a list of ConflictNames as group_conflicts to specify which are enabled.
        """
        if extracted is None:
            extracted = [
                ConstraintName.objects.get(slug=s) for s in [
                'chair_conflict', 'tech_overlap', 'key_participant'
                ]]
        if create:
            for cn in extracted:
                obj.group_conflict_types.add(
                    cn if isinstance(cn, ConstraintName) else ConstraintName.objects.get(slug=cn)
                )


class SessionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Session

    meeting = factory.SubFactory(MeetingFactory)
    type_id='regular'
    group = factory.SubFactory(GroupFactory)
    requested_duration = datetime.timedelta(hours=1)

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

class ScheduleFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Schedule

    meeting = factory.SubFactory(MeetingFactory)
    name = factory.Sequence(lambda n: 'schedule_%d'%n)
    owner = factory.SubFactory(PersonFactory)

class RoomFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Room

    meeting = factory.SubFactory(MeetingFactory)
    name = factory.Faker('name')

    @factory.post_generation
    def session_types(obj, create, extracted, **kwargs): # pylint: disable=no-self-argument
        """Prep session types m2m relationship for room, defaulting to 'regular'"""
        if create:
            session_types = extracted if extracted is not None else ['regular']
            for st in session_types:
                obj.session_types.add(st)


class TimeSlotFactory(factory.django.DjangoModelFactory):
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

class SessionPresentationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SessionPresentation

    session = factory.SubFactory(SessionFactory)
    document = factory.SubFactory('ietf.doc.factories.DocumentFactory')
    @factory.lazy_attribute
    def rev(self):
        return self.document.rev

class FloorPlanFactory(factory.django.DjangoModelFactory):
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

class SlideSubmissionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SlideSubmission

    session = factory.SubFactory(SessionFactory)
    title = factory.Faker('sentence')
    filename = factory.Sequence(lambda n: 'test_slide_%d'%n)
    submitter = factory.SubFactory(PersonFactory)

    make_file = factory.PostGeneration(
                    lambda obj, create, extracted, **kwargs: open(obj.staged_filepath(),'a').close()
                )

class ConstraintFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Constraint

    meeting = factory.SubFactory(MeetingFactory)
    source = factory.SubFactory(GroupFactory)
    target = factory.SubFactory(GroupFactory)
    person = factory.SubFactory(PersonFactory)
    time_relation = factory.Iterator(Constraint.TIME_RELATION_CHOICES)

    @factory.lazy_attribute
    def name(obj):
        constraint_list = list(ConstraintName.objects.filter(
              Q(slug__in=['bethere','timerange','time_relation','wg_adjacent'])
            | Q(meeting=obj.meeting)
        ))
        return random.choice(constraint_list)

    @factory.post_generation
    def timeranges(self, create, extracted, **kwargs):
        if create:
            if extracted:
                for tr in TimerangeName.objects.filter(slug__in=extracted):
                    self.timeranges.add(tr)

class MeetingHostFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = MeetingHost

    meeting = factory.SubFactory(MeetingFactory, type_id='ietf')
    name = factory.Faker('company')
    logo = factory.django.ImageField()  # generates an image


def _pmf_doc_name(doc):
    """Helper to generate document name for a ProceedingsMaterialFactory LazyAttribute"""
    return 'proceedings-{number}-{slug}'.format(
        number=doc.factory_parent.meeting.number,
        slug=xslugify(doc.factory_parent.type.slug).replace("_", "-")[:128]
    )

class ProceedingsMaterialFactory(factory.django.DjangoModelFactory):
    """Create a ProceedingsMaterial for testing

    Note: if you want to specify a type, use type=ProceedingsMaterialTypeName.objects.get(slug='slug')
    rather than the type_id='slug' shortcut. The latter will advance the Iterator used to generate
    types. This value is then used by the document SubFactory to set the document's title. This will
    not match the type of material created.
    """
    class Meta:
        model = ProceedingsMaterial

    meeting = factory.SubFactory(MeetingFactory, type_id='ietf')
    type = factory.Iterator(ProceedingsMaterialTypeName.objects.filter(used=True))
    # The SelfAttribute atnd LazyAttribute allow the document to be a SubFactory instead
    # of a generic LazyAttribute. This allows other attributes on the document to be
    # specified as document__external_url, etc.
    document = factory.SubFactory(
        ProceedingsMaterialDocFactory,
        type_id='procmaterials',
        title=factory.SelfAttribute('..type.name'),
        name=factory.LazyAttribute(_pmf_doc_name),
        uploaded_filename=factory.LazyAttribute(
            lambda doc: f'{_pmf_doc_name(doc)}-{doc.rev}.pdf'
        ))
