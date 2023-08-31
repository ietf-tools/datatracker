# Copyright The IETF Trust 2023, All Rights Reserved
# -*- coding: utf-8 -*-

import factory

from .models import (
    AppealArtifactTypeName,
)

class AppealArtifactTypeNameFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = AppealArtifactTypeName
        django_get_or_create = ("slug",)
