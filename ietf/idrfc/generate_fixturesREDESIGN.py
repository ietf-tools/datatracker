#!/usr/bin/python

# boiler plate
import os, sys

one_dir_up = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../'))

sys.path.insert(0, one_dir_up)

from django.core.management import setup_environ
import settings
setup_environ(settings)

# script
from django.core.serializers import serialize
from django.db.models import Q 

def output(name, qs):
    try:
        f = open(os.path.join(settings.BASE_DIR, "idrfc/fixtures/%s.xml" % name), 'w')
        f.write(serialize("xml", qs, indent=4))
        f.close()
    except:
        from django.db import connection
        from pprint import pprint
        pprint(connection.queries)
        raise

# pick all name models directly out of the module
names = []

import name.models
for n in dir(name.models):
    if n[:1].upper() == n[:1] and n.endswith("Name"):
        model = getattr(name.models, n)
        if not model._meta.abstract:
            names.extend(model.objects.all())
            
output("names", names)        

