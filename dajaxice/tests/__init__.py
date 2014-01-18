from django.test import TestCase

from django.conf import settings

from dajaxice.core import DajaxiceConfig
from dajaxice.core.Dajaxice import DajaxiceModule, DajaxiceFunction, Dajaxice
from dajaxice.exceptions import FunctionNotCallableError


class DajaxiceModuleTest(TestCase):

    def setUp(self):
        self.module = DajaxiceModule()

    def test_constructor(self):
        self.assertEqual(self.module.functions, {})
        self.assertEqual(self.module.submodules, {})

    def test_add_function(self):
        function = lambda x: x

        self.module.add('test', function)
        self.assertEqual(self.module.functions, {'test': function})
        self.assertEqual(self.module.submodules, {})

        self.module.add('foo.bar', function)
        self.assertEqual(self.module.functions, {'test': function})
        self.assertEqual(self.module.submodules.keys(), ['foo'])
        self.assertEqual(self.module.submodules['foo'].functions, {'bar': function})


class DajaxiceFunctionTest(TestCase):

    def test_constructor(self):

        class CalledEception(Exception):
            pass

        def callback():
            raise CalledEception

        function = DajaxiceFunction(callback, 'foo', 'POST')

        self.assertEqual(function.function, callback)
        self.assertEqual(function.name, 'foo')
        self.assertEqual(function.method, 'POST')
        self.assertRaises(CalledEception, function.call)


class DajaxiceTest(TestCase):

    def setUp(self):
        self.dajaxice = Dajaxice()
        self.function = lambda x: x

    def test_constructor(self):
        self.assertEqual(self.dajaxice._registry, {})

    def test_register(self):
        self.dajaxice.register(self.function, 'foo')
        self.assertTrue('foo' in self.dajaxice._registry)
        self.assertEqual(type(self.dajaxice._registry['foo']), DajaxiceFunction)

        def bar_function():
            return

        self.dajaxice.register(bar_function)
        self.assertTrue('dajaxice.tests.bar_function' in self.dajaxice._registry)
        self.assertEqual(type(self.dajaxice._registry['dajaxice.tests.bar_function']), DajaxiceFunction)

    def test__is_callable(self):
        self.dajaxice.register(self.function, 'foo')
        self.dajaxice.register(self.function, 'bar', method='GET')

        self.assertTrue(self.dajaxice.is_callable('foo', 'POST'))
        self.assertTrue(self.dajaxice.is_callable('bar', 'GET'))
        self.assertFalse(self.dajaxice.is_callable('foo', 'GET'))
        self.assertFalse(self.dajaxice.is_callable('bar', 'POST'))
        self.assertFalse(self.dajaxice.is_callable('test', 'POST'))
        self.assertFalse(self.dajaxice.is_callable('test', 'GET'))

    def test_clean_method(self):
        self.assertEqual(self.dajaxice.clean_method('post'), 'POST')
        self.assertEqual(self.dajaxice.clean_method('get'), 'GET')
        self.assertEqual(self.dajaxice.clean_method('POST'), 'POST')
        self.assertEqual(self.dajaxice.clean_method('GET'), 'GET')
        self.assertEqual(self.dajaxice.clean_method('other'), 'POST')

    def test_modules(self):
        self.dajaxice.register(self.function, 'foo')
        self.dajaxice.register(self.function, 'bar')

        self.assertEqual(type(self.dajaxice.modules), DajaxiceModule)
        self.assertEqual(self.dajaxice.modules.functions.keys(), ['foo', 'bar'])


class DajaxiceConfigTest(TestCase):

    def setUp(self):
        self.config = DajaxiceConfig()

    def test_defaults(self):
        self.assertTrue(self.config.DAJAXICE_XMLHTTPREQUEST_JS_IMPORT)
        self.assertTrue(self.config.DAJAXICE_JSON2_JS_IMPORT)
        self.assertEqual(self.config.DAJAXICE_EXCEPTION, 'DAJAXICE_EXCEPTION')
        self.assertEqual(self.config.DAJAXICE_MEDIA_PREFIX, 'dajaxice')

        dajaxice_url = r'^%s/' % self.config.DAJAXICE_MEDIA_PREFIX
        self.assertEqual(self.config.dajaxice_url, dajaxice_url)

        self.assertEqual(type(self.config.modules), DajaxiceModule)


class DjangoIntegrationTest(TestCase):

    urls = 'dajaxice.tests.urls'

    def setUp(self):
        settings.INSTALLED_APPS += ('dajaxice.tests',)

    def test_calling_not_registered_function(self):
        self.failUnlessRaises(FunctionNotCallableError, self.client.post, '/dajaxice/dajaxice.tests.this_function_not_exist/')

    def test_calling_registered_function(self):
        response = self.client.post('/dajaxice/dajaxice.tests.test_foo/')

        self.failUnlessEqual(response.status_code, 200)
        self.failUnlessEqual(response.content, '{"foo": "bar"}')

    def test_calling_registered_function_with_params(self):

        response = self.client.post('/dajaxice/dajaxice.tests.test_foo_with_params/', {'argv': '{"param1":"value1"}'})

        self.failUnlessEqual(response.status_code, 200)
        self.failUnlessEqual(response.content, '{"param1": "value1"}')

    def test_bad_function(self):

        response = self.client.post('/dajaxice/dajaxice.tests.test_ajax_exception/')
        self.failUnlessEqual(response.status_code, 200)
        self.failUnlessEqual(response.content, "DAJAXICE_EXCEPTION")

    def test_get_register(self):

        response = self.client.get('/dajaxice/dajaxice.tests.test_get_register/')

        self.failUnlessEqual(response.status_code, 200)
        self.failUnlessEqual(response.content, '{"foo": "user"}')

    def test_get_custom_name_register(self):

        response = self.client.get('/dajaxice/get_user_data/')

        self.failUnlessEqual(response.status_code, 200)
        self.failUnlessEqual(response.content, '{"bar": "user"}')

    def test_multi_register(self):

        response = self.client.get('/dajaxice/get_multi/')
        self.failUnlessEqual(response.status_code, 200)
        self.failUnlessEqual(response.content, '{"foo": "multi"}')

        response = self.client.post('/dajaxice/post_multi/')
        self.failUnlessEqual(response.status_code, 200)
        self.failUnlessEqual(response.content, '{"foo": "multi"}')
