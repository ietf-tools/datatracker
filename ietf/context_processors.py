# Copyright The IETF Trust 2007, All Rights Reserved

from django.conf import settings
from ietf import __date__, __rev__, __version__, __patch__, __id__

def server_mode(request):
    return {'server_mode': settings.SERVER_MODE}

def rfcdiff_base_url(request):
    return {'rfcdiff_base_url': settings.RFCDIFF_BASE_URL}
    
def revision_info(request):
    return {'revision_time': __date__[7:32], 'revision_date': __date__[7:17], 'revision_num': __rev__[6:-2], "revision_id": __id__[5:-2], "version_num": __version__+__patch__ }

def debug_mark_queries_from_view(request):
    "Marks the queries which has occurred so far as coming from a view."
    context_extras = {}
    if settings.DEBUG and request.META.get('REMOTE_ADDR') in settings.INTERNAL_IPS:
        from django.db import connection
        for query in connection.queries:
            query['where'] = 'V'           # V is for 'view'
    return context_extras
    
