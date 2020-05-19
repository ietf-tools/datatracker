# Copyright The IETF Trust 2015-2020, All Rights Reserved
import datetime
import debug # pyflakes:ignore
import factory

from ietf.group.models import Group, Role, GroupEvent, GroupMilestone
from ietf.review.factories import ReviewTeamSettingsFactory

class GroupFactory(factory.DjangoModelFactory):
    class Meta:
        model = Group
        django_get_or_create = ('acronym',)

    name = factory.Faker('sentence',nb_words=6)
    acronym = factory.Sequence(lambda n: 'acronym%d' %n)
    state_id = 'active'
    type_id = 'wg'
    list_email = factory.LazyAttribute(lambda a: '%s@ietf.org'% a.acronym)
    uses_milestone_dates = True

    @factory.lazy_attribute
    def parent(self):
        if self.type_id in ['wg','ag']:
            return GroupFactory(type_id='area')
        elif self.type_id in ['rg']:
            return GroupFactory(acronym='irtf', type_id='irtf')
        else:
            return None

class ReviewTeamFactory(GroupFactory):

    type_id = 'review'

    @factory.post_generation
    def settings(obj, create, extracted, **kwargs):
        ReviewTeamSettingsFactory.create(group=obj,**kwargs)

class RoleFactory(factory.DjangoModelFactory):
    class Meta:
        model = Role

    group = factory.SubFactory(GroupFactory)
    person = factory.SubFactory('ietf.person.factories.PersonFactory')
    email = factory.LazyAttribute(lambda obj: obj.person.email())

class GroupEventFactory(factory.DjangoModelFactory):
    class Meta:
        model = GroupEvent

    group = factory.SubFactory(GroupFactory)
    by = factory.SubFactory('ietf.person.factories.PersonFactory')
    type = 'comment'
    desc = factory.Faker('paragraph')

class BaseGroupMilestoneFactory(factory.DjangoModelFactory):
    class Meta:
        model = GroupMilestone

    group = factory.SubFactory(GroupFactory)
    state_id = 'active'
    desc = factory.Faker('sentence')

class DatedGroupMilestoneFactory(BaseGroupMilestoneFactory):
    group = factory.SubFactory(GroupFactory, uses_milestone_dates=True)
    due = datetime.datetime.today()+datetime.timedelta(days=180)

class DatelessGroupMilestoneFactory(BaseGroupMilestoneFactory):
    group = factory.SubFactory(GroupFactory, uses_milestone_dates=False)
    order = factory.Sequence(lambda n: n)

