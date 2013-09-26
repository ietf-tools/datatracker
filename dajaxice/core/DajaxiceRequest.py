#----------------------------------------------------------------------
# Copyright (c) 2009-2011 Benito Jorge Bastida
# All rights reserved.
#  Redistribution and use in source and binary forms, with or without
#  modification, are permitted provided that the following conditions are
#  met:
#
#    o Redistributions of source code must retain the above copyright
#      notice, this list of conditions, and the disclaimer that follows.
#
#    o Redistributions in binary form must reproduce the above copyright
#      notice, this list of conditions, and the following disclaimer in
#      the documentation and/or other materials provided with the
#      distribution.
#
#    o Neither the name of Digital Creations nor the names of its
#      contributors may be used to endorse or promote products derived
#      from this software without specific prior written permission.
#
#  THIS SOFTWARE IS PROVIDED BY DIGITAL CREATIONS AND CONTRIBUTORS *AS
#  IS* AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED
#  TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A
#  PARTICULAR PURPOSE ARE DISCLAIMED.  IN NO EVENT SHALL DIGITAL
#  CREATIONS OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
#  INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
#  BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS
#  OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
#  ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR
#  TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE
#  USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH
#  DAMAGE.
#----------------------------------------------------------------------

import os
import sys
import logging
import traceback

from django.conf import settings
from django.utils import simplejson
from django.http import HttpResponse

from dajaxice.core import dajaxice_functions
from dajaxice.exceptions import FunctionNotCallableError, DajaxiceImportError

log = logging.getLogger('dajaxice.DajaxiceRequest')

# Python 2.7 has an importlib with import_module.
# For older Pythons, Django's bundled copy provides it.
# For older Django's dajaxice reduced_import_module.
try:
    from importlib import import_module
except:
    try:
        from django.utils.importlib import import_module
    except:
        from dajaxice.utils import simple_import_module as import_module


def safe_dict(d):
    """
    Recursively clone json structure with UTF-8 dictionary keys
    http://www.gossamer-threads.com/lists/python/bugs/684379
    """
    if isinstance(d, dict):
        return dict([(k.encode('utf-8'), safe_dict(v)) for k, v in d.iteritems()])
    elif isinstance(d, list):
        return [safe_dict(x) for x in d]
    else:
        return d


class DajaxiceRequest(object):

    def __init__(self, request, call):
        call = call.rsplit('.', 1)
        self.app_name = call[0]
        self.method = call[1]
        self.request = request

        self.project_name = os.environ['DJANGO_SETTINGS_MODULE'].split('.')[0]
        self.module = "%s.ajax" % self.app_name
        self.full_name = "%s.%s" % (self.module, self.method)

    @staticmethod
    def get_js_functions():
        return dajaxice_functions.get_functions()

    @staticmethod
    def get_media_prefix():
        return getattr(settings, 'DAJAXICE_MEDIA_PREFIX', "dajaxice")

    @staticmethod
    def get_functions():
        return getattr(settings, 'DAJAXICE_FUNCTIONS', ())

    @staticmethod
    def get_debug():
        return getattr(settings, 'DAJAXICE_DEBUG', True)

    @staticmethod
    def get_notify_exceptions():
        return getattr(settings, 'DAJAXICE_NOTIFY_EXCEPTIONS', False)

    @staticmethod
    def get_cache_control():
        if settings.DEBUG:
            return 0
        return getattr(settings, 'DAJAXICE_CACHE_CONTROL', 5 * 24 * 60 * 60)

    @staticmethod
    def get_xmlhttprequest_js_import():
        return getattr(settings, 'DAJAXICE_XMLHTTPREQUEST_JS_IMPORT', True)

    @staticmethod
    def get_json2_js_import():
        return getattr(settings, 'DAJAXICE_JSON2_JS_IMPORT', True)

    @staticmethod
    def get_exception_message():
        return getattr(settings, 'DAJAXICE_EXCEPTION', u'DAJAXICE_EXCEPTION')

    @staticmethod
    def get_js_docstrings():
        return getattr(settings, 'DAJAXICE_JS_DOCSTRINGS', False)

    def _is_callable(self):
        """
        Return if the request function was registered.
        """
        return dajaxice_functions.is_callable(self.full_name)

    def _get_ajax_function(self):
        """
        Return a callable ajax function.
        This function should be imported according the Django version.
        """
        return self._modern_get_ajax_function()

    def _modern_get_ajax_function(self):
        """
        Return a callable ajax function.
        This function uses django.utils.importlib
        """
        self.module_import_name = "%s.%s" % (self.project_name, self.module)
        try:
            return self._modern_import()
        except:
            self.module_import_name = self.module
            return self._modern_import()

    def _modern_import(self):
        try:
            mod = import_module(self.module_import_name)
            return mod.__getattribute__(self.method)
        except:
            raise DajaxiceImportError()

    def process(self):
        """
        Process the dajax request calling the apropiate method.
        """
        if self._is_callable():
            log.debug('Function %s is callable' % self.full_name)

            argv = self.request.POST.get('argv')
            if argv != 'undefined':
                try:
                    argv = simplejson.loads(self.request.POST.get('argv'))
                    argv = safe_dict(argv)
                except Exception, e:
                    log.error('argv exception %s' % e)
                    argv = {}
            else:
                argv = {}

            log.debug('argv %s' % argv)

            try:
                thefunction = self._get_ajax_function()
                response = '%s' % thefunction(self.request, **argv)

            except Exception, e:
                trace = '\n'.join(traceback.format_exception(*sys.exc_info()))
                log.error(trace)
                response = '%s' % DajaxiceRequest.get_exception_message()

                if DajaxiceRequest.get_notify_exceptions():
                    self.notify_exception(self.request, sys.exc_info())

            log.info('response: %s' % response)
            return HttpResponse(response, mimetype="application/x-json")

        else:
            log.debug('Function %s is not callable' % self.full_name)
            raise FunctionNotCallableError(name=self.full_name)

    def notify_exception(self, request, exc_info):
        """
        Send Exception traceback to ADMINS
        Similar to BaseHandler.handle_uncaught_exception
        """
        from django.conf import settings
        from django.core.mail import mail_admins

        subject = 'Error (%s IP): %s' % ((request.META.get('REMOTE_ADDR') in settings.INTERNAL_IPS and 'internal' or 'EXTERNAL'), request.path)
        try:
            request_repr = repr(request)
        except:
            request_repr = "Request repr() unavailable"

        trace = '\n'.join(traceback.format_exception(*(exc_info or sys.exc_info())))
        message = "%s\n\n%s" % (trace, request_repr)
        mail_admins(subject, message, fail_silently=True)
