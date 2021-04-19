# Copyright The IETF Trust 2020, All Rights Reserved
# -*- coding: utf-8 -*-


import debug    # pyflakes:ignore
import factory

from ietf.doc.factories import draft_name_generator
from ietf.name.models import ExtResourceName
from ietf.submit.models import Submission, SubmissionExtResource
from ietf.utils.accesstoken import generate_random_key


class SubmissionExtResourceFactory(factory.DjangoModelFactory):
    name = factory.Iterator(ExtResourceName.objects.all())
    value = factory.Faker('url')
    submission = factory.SubFactory('ietf.submit.factories.SubmissionFactory')

    class Meta:
        model = SubmissionExtResource

class SubmissionFactory(factory.DjangoModelFactory):
    state_id = 'uploaded'

    @factory.lazy_attribute_sequence
    def name(self, n):
        return draft_name_generator('draft', getattr(self, 'group', None), n)

    @factory.lazy_attribute
    def auth_key(self):
        return generate_random_key()

    class Meta:
        model = Submission
