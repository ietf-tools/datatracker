#!/usr/bin/python

# boiler plate
import os, sys

ietf_path = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../ietf'))

sys.path.insert(0, ietf_path)

from django.core.management import setup_environ
import settings
setup_environ(settings)

# script
from django.core.serializers import serialize
from django.db.models import Q 

def output(name, qs):
    try:
        f = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures/%s.json" % name), 'w')
        f.write(serialize("json", qs, indent=1))
        f.close()
    except:
        from django.db import connection
        from pprint import pprint
        pprint(connection.queries)
        raise

# pick all name models directly out of the module
objects = []

import inspect
import ietf.name.models
for n in dir(ietf.name.models):
    symbol = getattr(ietf.name.models, n)
    if inspect.isclass(symbol) and issubclass(symbol, ietf.name.models.NameModel):
        if not symbol._meta.abstract:
            objects.extend(symbol.objects.all())


import ietf.doc.models # also pick some other name-like types while we're at it
objects += ietf.doc.models.StateType.objects.all()
objects += ietf.doc.models.State.objects.all()
objects += ietf.doc.models.BallotType.objects.all()

output("names", objects)

