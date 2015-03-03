import os
import sys
import json

from django.test import Client
from django.conf import settings
from django.utils.importlib import import_module
from django.db import models

from tastypie.test import ResourceTestCase

import debug                            # pyflakes:ignore

OMITTED_APPS = (
    'ietf.secr.meetings',
    'ietf.secr.proceedings',
    'ietf.ipr',
)

class TastypieApiTestCase(ResourceTestCase):
    def __init__(self, *args, **kwargs):
        self.apps = {}
        for app_name in settings.INSTALLED_APPS:
            if app_name.startswith('ietf') and not app_name in OMITTED_APPS:
                app = import_module(app_name)
                name = app_name.split('.',1)[-1]
                models_path = os.path.join(os.path.dirname(app.__file__), "models.py")
                if os.path.exists(models_path):
                    self.apps[name] = app
        super(ResourceTestCase, self).__init__(*args, **kwargs)

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

    def test_all_model_resources_exist(self):
        client = Client(Accept='application/json')
        r = client.get("/api/v1")
        top = json.loads(r.content)
        for name in self.apps:
            app = self.apps[name]
            self.assertEqual("/api/v1/%s/"%name, top[name]["list_endpoint"])
            r = client.get(top[name]["list_endpoint"])
            self.assertValidJSONResponse(r)
            app_resources = json.loads(r.content)
            model_list = models.get_models(app.models)
            for model in model_list:
                if not model._meta.model_name in app_resources.keys():
                    #print("There doesn't seem to be any resource for model %s.models.%s"%(app.__name__,model.__name__,))
                    self.assertIn(model._meta.model_name, app_resources.keys(),
                        "There doesn't seem to be any API resource for model %s.models.%s"%(app.__name__,model.__name__,))

