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

import httplib
import urllib

from django.core.management.base import BaseCommand
from django.template.loader import render_to_string
from optparse import make_option

from dajaxice.core import DajaxiceRequest
from dajaxice.core import dajaxice_autodiscover
dajaxice_autodiscover()


class Command(BaseCommand):
    help = "Generate dajaxice.core.js file to import it as static file"
    args = "[--compile]"
    option_list = BaseCommand.option_list + (
        make_option('--compile', default='no', dest='compile', help='Compile output using Google closure-compiler'),
    )

    requires_model_validation = False

    def handle(self, *app_labels, **options):
        compile_output = options.get('compile', 'yes')
        data = {'dajaxice_js_functions': DajaxiceRequest.get_js_functions(),
            'DAJAXICE_URL_PREFIX': DajaxiceRequest.get_media_prefix(),
            'DAJAXICE_XMLHTTPREQUEST_JS_IMPORT': DajaxiceRequest.get_xmlhttprequest_js_import(),
            'DAJAXICE_JSON2_JS_IMPORT': DajaxiceRequest.get_json2_js_import(),
            'DAJAXICE_EXCEPTION': DajaxiceRequest.get_exception_message()}

        js = render_to_string('dajaxice/dajaxice.core.js', data)
        if compile_output.lower() == "closure":
            print self.complie_js_with_closure(js)
        else:
            print js

    def complie_js_with_closure(self, js):
        params = urllib.urlencode([
            ('js_code', js),
            ('compilation_level', 'ADVANCED_OPTIMIZATIONS'),
            ('output_format', 'text'),
            ('output_info', 'compiled_code'),
        ])
        # Always use the following value for the Content-type header.
        headers = {"Content-type": "application/x-www-form-urlencoded"}
        conn = httplib.HTTPConnection('closure-compiler.appspot.com')
        conn.request('POST', '/compile', params, headers)
        response = conn.getresponse()
        data = response.read()
        conn.close()
        return data
