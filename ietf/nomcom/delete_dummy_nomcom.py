#!/usr/bin/python

# script for generating a dummy nomcom to use when developing nomcom related code

# boiler plate
import os, sys
import django
import socket


basedir = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../..'))
sys.path.insert(0, basedir)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ietf.settings")

django.setup()

from ietf.group.models import Group
from ietf.person.models import User

if socket.gethostname().split('.')[0] in ['core3', 'ietfa', 'ietfb', 'ietfc', ]:
    raise EnvironmentError("Refusing to run tests on production server")

Group.objects.filter(acronym='nomcom7437').delete()
User.objects.filter(username__in=['dummychair','dummymember','dummycandidate']).delete()
