# Copyright The IETF Trust 2018-2026, All Rights Reserved
import datetime
import factory
from faker import Faker

from django.utils import timezone

from ietf.ipr.models import (
    IprDisclosureBase, HolderIprDisclosure, ThirdPartyIprDisclosure, NonDocSpecificIprDisclosure,
    GenericIprDisclosure, IprDocRel, RelatedIpr, IprEvent
)

_fake = Faker()


def _fake_name(max_length):
    """Fake a name acceptable to ietf.ipr.forms.validate_name

    The limits are those of the edit form, not of the model: patent_info is an
    unbounded TextField, but the edit form parses it back into bounded, validated
    fields. Retries rather than truncating, so the result is still a plausible name.
    """
    for _ in range(100):
        name = _fake.name()
        if (
            len(name) <= max_length
            and " " in name
            and sum(c.isalpha() for c in name) >= 3
        ):
            return name
    raise RuntimeError(f"Unable to fake a name of at most {max_length:d} characters")


def _fake_patent_title():
    """Fake a patent title acceptable to ietf.ipr.forms.validate_title"""
    for _ in range(100):
        title = _fake.sentence(nb_words=8)
        if (
            len(title) <= 255
            and title.count(" ") >= 2
            and sum(c.isalpha() for c in title) >= 15
        ):
            return title
    raise RuntimeError("Unable to fake a patent title")


def _fake_patent_info():
    # Values must not contain newlines - text_to_dict() parses this back as RFC2822
    # headers and returns {} for anything it cannot parse.
    return "Date: {}\nNotes: {}\nTitle: {}\nNumber: {}\nInventor: {}\n".format(
        (timezone.now() - datetime.timedelta(days=365)).strftime("%Y-%m-%d"),
        _fake.paragraph(),
        _fake_patent_title(),
        "US9999999",
        _fake_name(63),
    )

class IprDisclosureBaseFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = IprDisclosureBase
        skip_postgeneration_save = True

    by = factory.SubFactory('ietf.person.factories.PersonFactory')
    compliant = True
    holder_legal_name = factory.LazyFunction(lambda: _fake_name(255))
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
                IprDocRel.objects.create(disclosure=self,document=doc)

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
    patent_info = factory.LazyFunction(_fake_patent_info)


class ThirdPartyIprDisclosureFactory(IprDisclosureBaseFactory):
    class Meta:
        model = ThirdPartyIprDisclosure

    ietfer_name = factory.Faker('name')
    ietfer_contact_email = factory.Faker('email')
    patent_info = factory.LazyFunction(_fake_patent_info)


class NonDocSpecificIprDisclosureFactory(IprDisclosureBaseFactory):
    class Meta:
        model = NonDocSpecificIprDisclosure

    holder_contact_email = factory.Faker('email')
    holder_contact_name = factory.Faker('name')
    patent_info = factory.LazyFunction(_fake_patent_info)

class GenericIprDisclosureFactory(IprDisclosureBaseFactory):
    class Meta:
        model = GenericIprDisclosure

    holder_contact_email = factory.Faker('email')
    holder_contact_name = factory.Faker('name')
    
class IprEventFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = IprEvent

    type_id = 'submitted'
    by = factory.SubFactory('ietf.person.factories.PersonFactory')
    disclosure = factory.SubFactory(IprDisclosureBaseFactory)
    desc = factory.Faker('sentence')

class IprDocRelFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = IprDocRel

    disclosure = factory.SubFactory(HolderIprDisclosureFactory)
    document = factory.SubFactory("ietf.doc.factories.IndividualDraftFactory")
    revisions = "00"
    sections = ""
