# Copyright The IETF Trust 2023, All Rights Reserved
# -*- coding: utf-8 -*-


import factory

from .models import (
    ActionHolder,
    Capability,
    RpcAuthorComment,
    RpcPerson,
    RpcRole,
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
