import os
import sys
import json

from django.test import Client
from django.conf import settings
from django.utils.importlib import import_module
from django.db import models

from tastypie.exceptions import BadRequest
from tastypie.test import ResourceTestCaseMixin

import debug                            # pyflakes:ignore

from ietf.utils.test_utils import TestCase

OMITTED_APPS = (
    'ietf.secr.meetings',
    'ietf.secr.proceedings',
    'ietf.ipr',
)

class TastypieApiTestCase(ResourceTestCaseMixin, TestCase):
    def __init__(self, *args, **kwargs):
        self.apps = {}
        for app_name in settings.INSTALLED_APPS:
            if app_name.startswith('ietf') and not app_name in OMITTED_APPS:
                app = import_module(app_name)
                name = app_name.split('.',1)[-1]
                models_path = os.path.join(os.path.dirname(app.__file__), "models.py")
                if os.path.exists(models_path):
                    self.apps[name] = app
        super(TastypieApiTestCase, self).__init__(*args, **kwargs)

    def test_api_top_level(self):
        client = Client(Accept='application/json')
        r = client.get("/api/v1/")
        self.assertValidJSONResponse(r)        
        resource_list = json.loads(r.content)

        for name in self.apps:
            if not name in self.apps:
                sys.stderr.write("Expected a REST API resource for %s, but didn't find one\n" % name)

        for name in self.apps:
            self.assertIn(name, resource_list,
                        "Expected a REST API resource for %s, but didn't find one" % name)

    def _assertCallbackReturnsSameJSON(self, api_url, json_dict):
        cbclient = Client(Accept='text/javascript')
        identity = lambda x: x      # pyflakes:ignore

        # To be able to eval JSON, we need to have three more symbols
        # They are used indirectly
        true = True                 # pyflakes:ignore
        false = False               # pyflakes:ignore
        null = None                 # pyflakes:ignore
        r = cbclient.get(api_url + '?callback=identity')
        code = compile(r.content, '<string>', 'eval')
        # Make sure it is just a call with the identity function
        self.assertTrue(len(code.co_names) == 1, "The callback API returned "
            "code which uses more symbols than just the given \'identity\' "
            "callback function: %s" % ', '.join(code.co_names))
        self.assertTrue(code.co_names[0] == 'identity', "The callback API "
            "returned code with a different symbol than the given "
            "\'identity\' callback function: %s" % code.co_names[0])
        # After all these checks, I think calling eval is "safe"
        # Fingers crossed!
        callback_dict = eval(code)
        self.assertEqual(callback_dict, json_dict, "The callback API returned "
            "a different dictionary than the json API")

    def test_all_model_resources_exist(self):
        client = Client(Accept='application/json')
        r = client.get("/api/v1")
        top = json.loads(r.content)
        self._assertCallbackReturnsSameJSON("/api/v1", top)
        for name in self.apps:
            app = self.apps[name]
            self.assertEqual("/api/v1/%s/"%name, top[name]["list_endpoint"])
            r = client.get(top[name]["list_endpoint"])
            self.assertValidJSONResponse(r)
            app_resources = json.loads(r.content)
            self._assertCallbackReturnsSameJSON("/api/v1/%s/"%name, app_resources)
            model_list = models.get_models(app.models)
            for model in model_list:
                if not model._meta.model_name in app_resources.keys():
                    #print("There doesn't seem to be any resource for model %s.models.%s"%(app.__name__,model.__name__,))
                    self.assertIn(model._meta.model_name, app_resources.keys(),
                        "There doesn't seem to be any API resource for model %s.models.%s"%(app.__name__,model.__name__,))

    def test_invalid_jsonp_callback_value(self):
        try:
            Client(Accept='text/javascript').get("/api/v1?callback=$.23")
        except BadRequest:
            return
        self.assertTrue(False,
            "The callback API accepted an invalid JSONP callback name")
