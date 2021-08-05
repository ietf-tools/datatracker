import factory

from ietf.group.factories import GroupFactory
from ietf.liaisons.models import LiaisonStatement, LiaisonStatementEvent, LiaisonStatementAttachment

class LiaisonStatementFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = LiaisonStatement

    title = factory.Faker('sentence')
    from_contact = factory.SubFactory('ietf.person.factories.EmailFactory')
    purpose_id = 'comment'
    body = factory.Faker('paragraph')
    state_id = 'posted'

    @factory.post_generation
    def from_groups(obj, create, extracted, **kwargs):
        if create:
            if extracted:
                obj.from_groups.set(extracted)
            else:
                obj.from_groups.add(GroupFactory(type_id='sdo'))

    @factory.post_generation
    def to_groups(obj, create, extracted, **kwargs):
        if create:
            if extracted:
                obj.to_groups.set(extracted)
            else:
                obj.to_groups.add(GroupFactory(type_id='wg'))


class LiaisonStatementEventFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = LiaisonStatementEvent

    type_id = 'posted'
    by = factory.SubFactory('ietf.person.factories.PersonFactory')
    statement = factory.SubFactory(LiaisonStatementFactory)
    desc = factory.Faker('sentence')


class LiaisonStatementAttachmentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = LiaisonStatementAttachment

    statement = factory.SubFactory(LiaisonStatementFactory)
    document = factory.SubFactory('ietf.doc.factories.BaseDocumentFactory',
        type_id='liai-att',
        # TODO: Make name more convenient (the default now is to try to generate a draftname)
    )
