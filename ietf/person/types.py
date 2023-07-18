# Copyright The IETF Trust 2023, All Rights Reserved
import strawberry
from strawberry import auto
from typing import List
from . import models

@strawberry.django.filters.filter(models.Person)
class PersonFilter:
    name: auto

@strawberry.django.type(
    models.Person,
    # description='Person Object'
)
class Person:
    id: auto
    name: auto
    plain: auto
    ascii: auto
