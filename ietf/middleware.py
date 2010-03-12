# Copyright The IETF Trust 2007, All Rights Reserved

from django.db import connection
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.http import HttpResponsePermanentRedirect
from ietf.utils import log
import re
import smtplib
import sys
import traceback

class SQLLogMiddleware(object):
    def process_response(self, request, response):
	for q in connection.queries:
	    if re.match('(update|insert)', q['sql'], re.IGNORECASE):
		log(q['sql'])
        return response

class SMTPExceptionMiddleware(object):
    def process_exception(self, request, exception):
	if isinstance(exception, smtplib.SMTPException):
	    type = sys.exc_info()[0]
	    value = sys.exc_info()[1]
	    # See if it's a non-smtplib exception that we faked
	    if type == smtplib.SMTPException and len(value.args) == 1 and isinstance(value.args[0], dict) and value.args[0].has_key('really'):
		orig = value.args[0]
		type = orig['really']
		tb = traceback.format_tb(orig['tb'])
		value = orig['value']
	    else:
		tb = traceback.format_tb(sys.exc_info()[2])
	    return render_to_response('email_failed.html', {'exception': type, 'args': value, 'traceback': "".join(tb)},
		context_instance=RequestContext(request))
	return None

class RedirectTrailingPeriod(object):
    def process_response(self, request, response):
	if response.status_code == 404 and request.path.endswith("."):
	    return HttpResponsePermanentRedirect(request.path.rstrip("."))
	return response
