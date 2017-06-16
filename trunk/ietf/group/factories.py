import factory

from ietf.group.models import Group, Role, GroupEvent

class GroupFactory(factory.DjangoModelFactory):
    class Meta:
        model = Group

    name = factory.Faker('sentence',nb_words=6)
    acronym = factory.Sequence(lambda n: 'acronym%d' %n)

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
