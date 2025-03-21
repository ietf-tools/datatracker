# Copyright The IETF Trust 2025, All Rights Reserved
import factory

from .models import Blob


class BlobFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Blob

    name = factory.Faker("file_path")
    bucket = factory.Faker("word")
    content = factory.Faker("binary", length=32)  # careful, default length is 1e6
