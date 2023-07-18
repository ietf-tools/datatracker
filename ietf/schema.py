# Copyright The IETF Trust 2023, All Rights Reserved
from strawberry import Schema
from strawberry.tools import merge_types
from ietf.meeting.schema import Query as MeetingQuery
from ietf.person.schema import Query as PersonQuery

queries = (MeetingQuery, PersonQuery)

Query = merge_types("Query", queries)
schema = Schema(query=Query)
