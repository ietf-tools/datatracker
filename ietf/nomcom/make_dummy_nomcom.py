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

from ietf.nomcom.factories import nomcom_kwargs_for_year, NomComFactory, NomineePositionFactory, key
from ietf.person.factories import EmailFactory

if socket.gethostname().split('.')[0] in ['core3', 'ietfa', 'ietfb', 'ietfc', ]:
    raise EnvironmentError("Refusing to run tests on production server")

nc = NomComFactory.create(**nomcom_kwargs_for_year(year=7437,
                                                  populate_personnel=False,
                                                  populate_positions=False))

e = EmailFactory(person__name=u'Dummy Chair',address=u'dummychair@example.com',person__user__username=u'dummychair',person__default_emails=False)
e.person.user.set_password('password')
e.person.user.save()
nc.group.role_set.create(name_id=u'chair',person=e.person,email=e)

e = EmailFactory(person__name=u'Dummy Member',address=u'dummymember@example.com',person__user__username=u'dummymember',person__default_emails=False)
e.person.user.set_password('password')
e.person.user.save()
nc.group.role_set.create(name_id=u'member',person=e.person,email=e)


e = EmailFactory(person__name=u'Dummy Candidate',address=u'dummycandidate@example.com',person__user__username=u'dummycandidate',person__default_emails=False)
e.person.user.set_password('password')
e.person.user.save()
NomineePositionFactory(nominee__nomcom=nc, nominee__person=e.person,
                       position__nomcom=nc, position__name=u'Dummy Area Director',
                      )

print key
print "Nomcom 7437 created. The private key can also be found at any time in ietf/nomcom/factories.py. Note that it is NOT a secure key."
