# Copyright The IETF Trust 2018, All Rights Reserved
# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function

import factory
import random

from ietf.mailinglists.models import List

class ListFactory(factory.DjangoModelFactory):
    class Meta:
        model = List

    name = factory.Faker('word')
    description = factory.Faker('sentence', nb_words=10)
    advertised = factory.LazyAttribute(lambda obj: random.randint(0, 1))

    
