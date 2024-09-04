# Copyright The IETF Trust 2018-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import factory

from ietf.mailinglists.models import NonWgMailingList

class NonWgMailingListFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = NonWgMailingList

    name = factory.Sequence(lambda n: "list-name-%s" % n)
    domain = factory.Sequence(lambda n: "domain-%s.org" % n)
    description = factory.Faker('sentence', nb_words=10)

    
