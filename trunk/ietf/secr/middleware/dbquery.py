#import logging

from django.db import connection
from django.utils.log import getLogger

logger = getLogger(__name__)
#logger.setLevel(logging.DEBUG)
#logger.addHandler(logging.FileHandler(settings.SECR_LOG_FILE))

class QueryCountDebugMiddleware(object):
    """
    This middleware will log the number of queries run
    and the total time taken for each request (with a
    status code of 200). It does not currently support
    multi-db setups.
    """
    def process_response(self, request, response):
        #assert False, request.path
        logger.debug('called middleware. %s:%s' % (request.path,len(connection.queries)))
        if response.status_code == 200:
            total_time = 0
            #for query in connection.queries:
            #    query_time = query.get('time')
            #    if query_time is None:
                    # django-debug-toolbar monkeypatches the connection
                    # cursor wrapper and adds extra information in each
                    # item in connection.queries. The query time is stored
                    # under the key "duration" rather than "time" and is
                    # in milliseconds, not seconds.
            #        query_time = query.get('duration', 0) / 1000
            #    total_time += float(query_time)
            logger.debug('%s: %s queries run, total %s seconds' % (request.path,len(connection.queries), total_time))
        return response
