# Copyright The IETF Trust 2015-2022, All Rights Reserved
import datetime
import debug # pyflakes:ignore
import factory

from typing import List    # pyflakes:ignore

from django.utils import timezone

from ietf.group.models import (
    Appeal,
    AppealArtifact,
    Group,
    GroupEvent,
    GroupMilestone,
    GroupHistory,
    Role,
    RoleHistory
)   
from ietf.review.factories import ReviewTeamSettingsFactory
from ietf.utils.timezone import date_today


class GroupFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Group
        django_get_or_create = ('acronym',)
        skip_postgeneration_save = True

    name = factory.Faker('text', max_nb_chars=80)
    acronym = factory.Sequence(lambda n: 'acronym%d' %n)
    state_id = 'active'
    type_id = 'wg'
    list_email = factory.LazyAttribute(lambda a: '%s@ietf.org'% a.acronym)
    uses_milestone_dates = True
    used_roles = [] # type: List[str]

    @factory.lazy_attribute
    def parent(self):
        if self.type_id in ['wg','ag']:
            return GroupFactory(type_id='area')
        elif self.type_id in ['rg','rag']:
            return GroupFactory(acronym='irtf', type_id='irtf')
        else:
            return None

class ReviewTeamFactory(GroupFactory):

    type_id = 'review'

    @factory.post_generation
    def settings(obj, create, extracted, **kwargs):
        ReviewTeamSettingsFactory.create(group=obj,**kwargs)

class RoleFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Role

    group = factory.SubFactory(GroupFactory)
    person = factory.SubFactory('ietf.person.factories.PersonFactory')
    email = factory.LazyAttribute(lambda obj: obj.person.email())

class GroupEventFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = GroupEvent

    group = factory.SubFactory(GroupFactory)
    by = factory.SubFactory('ietf.person.factories.PersonFactory')
    type = 'comment'
    desc = factory.Faker('paragraph')

class BaseGroupMilestoneFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = GroupMilestone

    group = factory.SubFactory(GroupFactory)
    state_id = 'active'
    desc = factory.Faker('sentence')

class DatedGroupMilestoneFactory(BaseGroupMilestoneFactory):
    group = factory.SubFactory(GroupFactory, uses_milestone_dates=True)
    due = date_today() + datetime.timedelta(days=180)

class DatelessGroupMilestoneFactory(BaseGroupMilestoneFactory):
    group = factory.SubFactory(GroupFactory, uses_milestone_dates=False)
    order = factory.Sequence(lambda n: n)

class GroupHistoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model=GroupHistory
        skip_postgeneration_save = True

    time = lambda: timezone.now()
    group = factory.SubFactory(GroupFactory, state_id='active')

    name = factory.LazyAttribute(lambda obj: obj.group.name)
    state_id = factory.LazyAttribute(lambda obj: obj.group.state_id)
    type_id = factory.LazyAttribute(lambda obj: obj.group.type_id)
    parent = factory.LazyAttribute(lambda obj: obj.group.parent)
    uses_milestone_dates = factory.LazyAttribute(lambda obj: obj.group.uses_milestone_dates)
    used_roles = factory.LazyAttribute(lambda obj: obj.group.used_roles)
    description = factory.LazyAttribute(lambda obj: obj.group.description)
    list_email = factory.LazyAttribute(lambda obj: '%s@ietf.org'% obj.group.acronym) #TODO : move this to GroupFactory
    list_subscribe = factory.LazyAttribute(lambda obj: obj.group.list_subscribe)
    list_archive = factory.LazyAttribute(lambda obj: obj.group.list_archive)
    comments = factory.LazyAttribute(lambda obj: obj.group.comments)
    meeting_seen_as_area = factory.LazyAttribute(lambda obj: obj.group.meeting_seen_as_area)
    acronym = factory.LazyAttribute(lambda obj: obj.group.acronym)

    @factory.post_generation
    def unused_states(obj, create, extracted, **kwargs):
        if create:
            if extracted:
                obj.unused_states.set(extracted)
            else:
                obj.unused_states.set(obj.group.unused_states.all())
    @factory.post_generation
    def unused_tags(obj, create, extracted, **kwargs):
        if create:
            if extracted:
                obj.unused_tags.set(extracted)
            else:
                obj.unused_tags.set(obj.group.unused_states.all())            

class RoleHistoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model=RoleHistory

    group = factory.SubFactory(GroupHistoryFactory)
    person = factory.SubFactory('ietf.person.factories.PersonFactory')
    email = factory.LazyAttribute(lambda obj: obj.person.email())

class AppealFactory(factory.django.DjangoModelFactory):
    class Meta:
        model=Appeal
    
    name=factory.Faker("sentence")
    group=factory.SubFactory(GroupFactory, acronym="iab")

class AppealArtifactFactory(factory.django.DjangoModelFactory):
    class Meta:
        model=AppealArtifact
        skip_postgeneration_save = True
    
    appeal = factory.SubFactory(AppealFactory)
    artifact_type = factory.SubFactory("ietf.name.factories.AppealArtifactTypeNameFactory", slug="appeal")
    content_type = "text/markdown;charset=utf-8"
    # Needs newer factory_boy
    # bits = factory.Transformer(
    #     "Some example **Markdown**",
    #     lambda o: memoryview(o.encode("utf-8") if isinstance(o,str) else o)
    # )
    #
    # Usage: a = AppealArtifactFactory(set_bits__using="foo bar") or
    #        a = AppealArtifactFactory(set_bits__using=b"foo bar")
    @factory.post_generation
    def set_bits(obj, create, extracted, **kwargs):
        if not create:
            return
        using = kwargs.pop("using","Some example **Markdown**")
        if isinstance(using, str):
            using = using.encode("utf-8")
        obj.bits = memoryview(using)
        obj.save()

