from django.http import QueryDict


def deserialize_form(data):
    """
    Create a new QueryDict from a serialized form.
    """
    return QueryDict(query_string=unicode(data).encode('utf-8'))
