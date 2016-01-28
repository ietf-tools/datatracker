import factory

from ietf.group.models import Group

class GroupFactory(factory.DjangoModelFactory):
    class Meta:
        model = Group

    name = factory.Faker('sentence',nb_words=6)
    acronym = factory.Sequence(lambda n: 'acronym_%d' %n)
