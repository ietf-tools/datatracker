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

from django.shortcuts import render_to_response
from django.views.decorators.cache import cache_control

from dajaxice.core import DajaxiceRequest


def dajaxice_request(request, call):
    """
    dajaxice_request
    Uses DajaxRequest to handle dajax request.
    Return the apropiate json according app_name and method.
    """
    return DajaxiceRequest(request, call).process()


@cache_control(max_age=DajaxiceRequest.get_cache_control())
def js_core(request):
    """
    Return the dajax JS code according settings.DAJAXICE_FUNCTIONS
    registered functions.
    """
    data = {'dajaxice_js_functions': DajaxiceRequest.get_js_functions(),
            'DAJAXICE_URL_PREFIX': DajaxiceRequest.get_media_prefix(),
            'DAJAXICE_XMLHTTPREQUEST_JS_IMPORT': DajaxiceRequest.get_xmlhttprequest_js_import(),
            'DAJAXICE_JSON2_JS_IMPORT': DajaxiceRequest.get_json2_js_import(),
            'DAJAXICE_EXCEPTION': DajaxiceRequest.get_exception_message(),
            'DAJAXICE_JS_DOCSTRINGS': DajaxiceRequest.get_js_docstrings()}

    return render_to_response('dajaxice/dajaxice.core.js', data, mimetype="text/javascript")
