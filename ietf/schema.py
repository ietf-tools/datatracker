import graphene

import ietf.meeting.schema

class Query(
    ietf.meeting.schema.Query,
    graphene.ObjectType
):
    pass

schema = graphene.Schema(query=Query)
