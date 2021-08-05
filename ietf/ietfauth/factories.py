# Copyright The IETF Trust 2020, All Rights Reserved

import debug                            # pyflakes:ignore
import factory

from hashlib import sha224
from random import randint
from uuid import uuid4

from oidc_provider.models import Client as OidClientRecord, ResponseType

from ietf.person.factories import UserFactory, PersonFactory

class OidClientRecordFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = OidClientRecord

    name = factory.Faker('company')
    owner = factory.SubFactory(UserFactory)
    client_type = 'confidential'
    client_id = str(randint(1, 999999)).zfill(6)

    @factory.lazy_attribute
    def client_secret(self):
        if self.client_type == 'confidential':
            secret = sha224(uuid4().hex.encode()).hexdigest()
        else:
            secret = ''
        return secret

    @factory.post_generation
    def response_types(self, create, extracted, **kwargs):
        if not create:
            # Simple build, do nothing.
            return

        if not extracted:
            extracted = ['code', ]

        # A list of groups were passed in, use them
        for value in extracted:
            type, _ = ResponseType.objects.get_or_create(value=value)
            self.response_types.add(type)

    @factory.post_generation
    def person(self, create, extracted, **kwargs):
        if not create:
            # Simple build, do nothing.
            return

        user = self.owner
        if extracted:
            extracted.user = user
            extracted.save()
        else:
            PersonFactory(name='%s %s' % (user.first_name, user.last_name), user=user)
