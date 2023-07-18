# Copyright The IETF Trust 2023, All Rights Reserved

from typing import List
import strawberry

from ietf.person.types import Person, PersonFilter

@strawberry.type
class Query:
    personById: Person = strawberry.django.field()
    persons: List[Person] = strawberry.django.field(pagination=True, filters=PersonFilter)

schema = strawberry.Schema(
    Query
)
