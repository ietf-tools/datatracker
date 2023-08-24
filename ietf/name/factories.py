# Copyright The IETF Trust 2023, All Rights Reserved
# -*- coding: utf-8 -*-

import factory

from .models import (
    SourceFormatName,
    StdLevelName,
    StreamName,
    TlpBoilerplateChoiceName,
)

class SourceFormatNameFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SourceFormatName
        django_get_or_create = ("slug",)

class StdLevelNameFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = StdLevelName
        django_get_or_create = ("slug",)

class TlpBoilerplateChoiceNameFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = TlpBoilerplateChoiceName
        django_get_or_create = ("slug",)

class StreamNameFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = StreamName
        django_get_or_create = ("slug",)
