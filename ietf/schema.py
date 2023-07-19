# Copyright The IETF Trust 2023, All Rights Reserved
from strawberry import Schema
from strawberry.tools import merge_types
from ietf.meeting.schema import Query as MeetingQuery
from ietf.person.schema import Query as PersonQuery
from ietf.name.schema import Query as NameQuery

queries = (MeetingQuery, PersonQuery, NameQuery)

Query = merge_types("Query", queries)
schema = Schema(query=Query)
