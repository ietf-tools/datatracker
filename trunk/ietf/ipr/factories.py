# Copyright The IETF Trust 2018-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import datetime
import factory


from ietf.ipr.models import (
    IprDisclosureBase, HolderIprDisclosure, ThirdPartyIprDisclosure, NonDocSpecificIprDisclosure,
    GenericIprDisclosure, IprDocRel, RelatedIpr, IprEvent
)

def _fake_patent_info():
    return "Date: %s\nNotes: %s\nTitle: %s\nNumber: %s\nInventor: %s\n" % (
        (datetime.datetime.today()-datetime.timedelta(days=365)).strftime("%Y-%m-%d"),
        factory.Faker('paragraph').generate({}),
        factory.Faker('sentence', nb_words=8).generate({}),
        'US9999999',
        factory.Faker('name').generate({}),
    )

class IprDisclosureBaseFactory(factory.DjangoModelFactory):
    class Meta:
        model = IprDisclosureBase

    by = factory.SubFactory('ietf.person.factories.PersonFactory')
    compliant = True
    holder_legal_name = factory.Faker('name')
    state_id='posted'
    submitter_name = factory.Faker('name')
    submitter_email = factory.Faker('email') 
    title = factory.Faker('sentence')
    
    @factory.post_generation
    def docs(self, create, extracted, **kwargs):
        if not create:
            return
        if extracted:
            for doc in extracted:
                IprDocRel.objects.create(disclosure=self,document=doc.docalias.first())

    @factory.post_generation
    def updates(self, create, extracted, **kwargs):
        if not create:
            return
        if extracted:
            for ipr in extracted:
                RelatedIpr.objects.create(source=self,target=ipr,relationship_id='updates')


class HolderIprDisclosureFactory(IprDisclosureBaseFactory):
    class Meta:
        model = HolderIprDisclosure

    holder_contact_email = factory.Faker('email')
    holder_contact_name = factory.Faker('name')
    licensing_id = 'reasonable'
    patent_info = _fake_patent_info()


class ThirdPartyIprDisclosureFactory(IprDisclosureBaseFactory):
    class Meta:
        model = ThirdPartyIprDisclosure

    ietfer_name = factory.Faker('name')
    ietfer_contact_email = factory.Faker('email')
    patent_info = _fake_patent_info()


class NonDocSpecificIprDisclosureFactory(IprDisclosureBaseFactory):
    class Meta:
        model = NonDocSpecificIprDisclosure

    holder_contact_email = factory.Faker('email')
    holder_contact_name = factory.Faker('name')
    patent_info = _fake_patent_info()

class GenericIprDisclosureFactory(IprDisclosureBaseFactory):
    class Meta:
        model = GenericIprDisclosure

    holder_contact_email = factory.Faker('email')
    holder_contact_name = factory.Faker('name')
    
class IprEventFactory(factory.DjangoModelFactory):
    class Meta:
        model = IprEvent

    type_id = 'submitted'
    by = factory.SubFactory('ietf.person.factories.PersonFactory')
    disclosure = factory.SubFactory(IprDisclosureBaseFactory)
    desc = factory.Faker('sentence')

