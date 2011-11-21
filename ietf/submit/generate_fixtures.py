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
        f = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures/%s.xml" % name), 'w')
        f.write(serialize("xml", qs, indent=4))
        f.close()
    except:
        from django.db import connection
        from pprint import pprint
        pprint(connection.queries)
        raise

# pick all name models directly out of the module
names = []

from ietf.submit.models import IdSubmissionStatus

output("idsubmissionstatus", IdSubmissionStatus.objects.all())
