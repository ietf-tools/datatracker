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
import unittest

from django.test import TestCase
from django.conf import settings

from dajaxice.exceptions import FunctionNotCallableError, DajaxiceImportError
from dajaxice.core import DajaxiceRequest
from dajaxice.core.Dajaxice import Dajaxice, DajaxiceModule, DajaxiceFunction
from dajaxice.core import dajaxice_functions


class DjangoIntegrationTest(TestCase):

    urls = 'dajaxice.tests.urls'

    def setUp(self):
        settings.DAJAXICE_MEDIA_PREFIX = "dajaxice"
        settings.DAJAXICE_DEBUG = False
        settings.INSTALLED_APPS += ('dajaxice.tests', 'dajaxice.tests.submodules',)
        os.environ['DJANGO_SETTINGS_MODULE'] = 'dajaxice'

    def test_calling_not_registered_function(self):
        self.failUnlessRaises(FunctionNotCallableError, self.client.post, '/dajaxice/dajaxice.tests.this_function_not_exist/', {'callback': 'my_callback'})

    def test_calling_registered_function(self):
        response = self.client.post('/dajaxice/dajaxice.tests.test_foo/', {'callback': 'my_callback'})

        self.failUnlessEqual(response.status_code, 200)
        self.failUnlessEqual(response.content, 'my_callback()')

    def test_calling_registered_function_with_params(self):

        response = self.client.post('/dajaxice/dajaxice.tests.test_foo_with_params/', {'callback': 'my_callback', 'argv': '{"param1":"value1"}'})

        self.failUnlessEqual(response.status_code, 200)
        self.failUnlessEqual(response.content, 'my_callback("value1")')

    def test_bad_function(self):

        response = self.client.post('/dajaxice/dajaxice.tests.test_ajax_exception/', {'callback': 'my_callback'})
        self.failUnlessEqual(response.status_code, 200)
        self.failUnlessEqual(response.content, "my_callback('DAJAXICE_EXCEPTION')")

    def test_is_callable(self):

        dr = DajaxiceRequest(None, 'dajaxice.tests.test_registered_function')
        self.failUnless(dr._is_callable())

        dr = DajaxiceRequest(None, 'dajaxice.tests.test_ajax_not_registered')
        self.failIf(dr._is_callable())

    def test_get_js_functions(self):

        js_functions = DajaxiceRequest.get_js_functions()

        functions = [DajaxiceFunction('test_registered_function', 'dajaxice.tests.ajax.test_registered_function'),
                     DajaxiceFunction('test_string', 'dajaxice.tests.ajax.test_string'),
                     DajaxiceFunction('test_ajax_exception', 'dajaxice.tests.ajax.test_ajax_exception'),
                     DajaxiceFunction('test_foo', 'dajaxice.tests.ajax.test_foo'),
                     DajaxiceFunction('test_foo_with_params', 'dajaxice.tests.ajax.test_foo_with_params'),
                     DajaxiceFunction('test_submodule_registered_function', 'dajaxice.tests.submodules.ajax.test_submodule_registered_function')]

        callables = [f.path for f in functions]

        self.failUnlessEqual(len(js_functions), 1)
        self.failUnlessEqual(dajaxice_functions._callable, callables)

        sub = js_functions[0]
        self.failUnlessEqual(len(sub.sub_modules), 1)
        self.failUnlessEqual(len(sub.functions), 0)
        self.failUnlessEqual(sub.name, 'dajaxice')

        sub = js_functions[0].sub_modules[0]
        self.failUnlessEqual(len(sub.sub_modules), 1)
        self.failUnlessEqual(len(sub.functions), 5)
        self.failUnlessEqual(sub.functions, functions[:-1])
        self.failUnlessEqual(sub.name, 'tests')

        sub = js_functions[0].sub_modules[0].sub_modules[0]
        self.failUnlessEqual(len(sub.sub_modules), 0)
        self.failUnlessEqual(len(sub.functions), 1)
        self.failUnlessEqual(sub.functions, functions[-1:])
        self.failUnlessEqual(sub.name, 'submodules')

    def test_get_ajax_function(self):

        # Test modern Import with a real ajax function
        dr = DajaxiceRequest(None, 'dajaxice.tests.test_foo')
        function = dr._modern_get_ajax_function()
        self.failUnless(hasattr(function, '__call__'))

        # Test modern Import without a real ajax function
        dr = DajaxiceRequest(None, 'dajaxice.tests.test_foo2')
        self.failUnlessRaises(DajaxiceImportError, dr._modern_get_ajax_function)


class DajaxiceFunctionTest(unittest.TestCase):

    def setUp(self):
        self.function = DajaxiceFunction('my_function', 'module.submodule.foo.ajax')

    def test_constructor(self):
        self.failUnlessEqual(self.function.name, 'my_function')
        self.failUnlessEqual(self.function.path, 'module.submodule.foo.ajax')

    def test_get_callable_path(self):
        self.failUnlessEqual(self.function.get_callable_path(), 'module.submodule.foo.my_function')


class DajaxiceModuleTest(unittest.TestCase):

    def setUp(self):
        self.module = DajaxiceModule('module.submodule.foo.ajax'.split('.'))

    def test_constructor(self):
        self.failUnlessEqual(self.module.functions, [])
        self.failUnlessEqual(self.module.name, 'module')

        self.failUnlessEqual(len(self.module.sub_modules), 1)

    def test_add_function(self):
        function = DajaxiceFunction('my_function', 'module.submodule.foo.ajax')
        self.failUnlessEqual(len(self.module.functions), 0)
        self.module.add_function(function)
        self.failUnlessEqual(len(self.module.functions), 1)

    def test_has_sub_modules(self):
        self.failUnlessEqual(self.module.has_sub_modules(), True)

    def test_exist_submodule(self):
        self.failUnlessEqual(self.module.exist_submodule('submodule'), 0)
        self.assertFalse(self.module.exist_submodule('other'))
        self.module.add_submodule('other.foo'.split('.'))
        self.failUnlessEqual(self.module.exist_submodule('other'), 1)

    def test_add_submodule(self):
        self.failUnlessEqual(len(self.module.sub_modules), 1)
        self.module.add_submodule('other.foo'.split('.'))
        self.failUnlessEqual(len(self.module.sub_modules), 2)
        self.assertTrue(type(self.module.sub_modules[1]), DajaxiceModule)
