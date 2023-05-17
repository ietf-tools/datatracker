# Copyright The IETF Trust 2016-2021, All Rights Reserved
# -*- coding: utf-8 -*-

import debug    # pyflakes:ignore
import factory

from ietf.iesg.models import TelechatAgendaItem, TelechatAgendaContent


class IESGMgmtItemFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = TelechatAgendaItem

    type = 3
    text = factory.Faker('paragraph', nb_sentences=3)
    title = factory.Faker('sentence', nb_words=3)


class TelechatAgendaContentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = TelechatAgendaContent

    text = factory.Faker('paragraph', nb_sentences=5)
