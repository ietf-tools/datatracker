# Copyright The IETF Trust 2023, All Rights Reserved
# -*- coding: utf-8 -*-


import factory

from django.db.models import Max

from .models import (
    ActionHolder,
    Assignment,
    Capability,
    Cluster,
    FinalApproval,
    RfcAuthor,
    RfcToBe,
    RpcAuthorComment,
    RpcPerson,
    RpcRole,
    UnusableRfcNumber,
)


class RpcPersonFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = RpcPerson

    person = factory.SubFactory("ietf.person.factories.PersonFactory")

    @factory.post_generation
    def can_hold_role(self, create, extracted, **kwargs):
        if not create or not extracted:
            return
        for item in extracted:
            if isinstance(item, str):
                self.can_hold_role.add(RpcRoleFactory(slug=item, **kwargs))
            elif isinstance(item, RpcRole):
                self.can_hold_role.add(item)
            else:
                raise Exception(f"Cannot add {item} to can_hold_role")

    @factory.post_generation
    def capable_of(self, create, extracted, **kwargs):
        if not create or not extracted:
            return
        for item in extracted:
            if isinstance(item, str):
                self.capable_of.add(CapabilityFactory(slug=item, **kwargs))
            elif isinstance(item, Capability):
                self.capable_of.add(item)
            else:
                raise Exception(f"Cannot add {item} to can_hold_role")


class RpcRoleFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = RpcRole
        django_get_or_create = ("slug",)

    slug = factory.Faker("word")
    name = factory.Faker("sentence")
    desc = factory.Faker("sentence")


class CapabilityFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Capability
        django_get_or_create = ("slug",)

    slug = factory.Faker("word")
    name = factory.Faker("sentence")
    desc = factory.Faker("sentence")


class RfcToBeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = RfcToBe

    draft = factory.SubFactory("ietf.doc.factories.WgDraftFactory")
    rfc_number = factory.Sequence(lambda n: n + 1000)
    submitted_format = factory.SubFactory("ietf.name.factories.SourceFormatNameFactory", slug="xml-v3")
    submitted_std_level = factory.SubFactory("ietf.name.factories.StdLevelNameFactory", slug="ps")
    submitted_boilerplate = factory.SubFactory("ietf.name.factories.TlpBoilerplateChoiceNameFactory",slug="trust200902")
    submitted_stream = factory.SubFactory("ietf.name.factories.StreamNameFactory",slug="ietf")
    intended_std_level = factory.LazyAttribute(lambda o: o.submitted_std_level)
    intended_boilerplate = factory.LazyAttribute(
        lambda o: o.submitted_boilerplate
    )
    intended_stream = factory.LazyAttribute(lambda o: o.submitted_stream)


class AprilFirstRfcToBeFactory(RfcToBeFactory):
    is_april_first_rfc = True
    draft = None


class ActionHolderFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ActionHolder

    person = factory.SubFactory("ietf.person.factories.PersonFactory")
    comment = factory.Faker("sentence")


class RpcAuthorCommentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = RpcAuthorComment

    person = factory.SubFactory("ietf.person.factories.PersonFactory")
    comment = factory.Faker("sentence")
    by = factory.SubFactory("ietf.person.factories.PersonFactory")


class ClusterFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Cluster

    number = factory.LazyFunction(
        lambda: Cluster.objects.aggregate(Max("number"))["number__max"] or 1
    )


class UnusableRfcNumberFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = UnusableRfcNumber

    number = factory.LazyFunction(
        lambda: UnusableRfcNumber.objects.aggregate(Max("number"))["number__max"] or 1
    )
    comment = factory.Faker("sentence")


class AssignmentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Assignment

    rfc_to_be = factory.SubFactory(RfcToBeFactory)
    person = factory.SubFactory(RpcPersonFactory)


class RfcAuthorFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = RfcAuthor

    person = factory.SubFactory("ietf.person.factories.PersonFactory")
    rfc_to_be = factory.SubFactory(RfcToBeFactory)


class FinalApprovalFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = FinalApproval

    rfc_to_be = factory.SubFactory(RfcToBeFactory)
    approver = factory.SubFactory("ietf.person.factories.PersonFactory")
