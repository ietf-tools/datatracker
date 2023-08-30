# Copyright The IETF Trust 2017-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import socket

from django.core.management.base import BaseCommand

import debug                            # pyflakes:ignore

from ietf.nomcom.factories import nomcom_kwargs_for_year, NomComFactory, NomineePositionFactory, key
from ietf.person.factories import EmailFactory
from ietf.group.models import Group
from ietf.person.models import Person, User

class Command(BaseCommand):
    help = ("Create (or delete) a nomcom for test and development purposes.")

    def add_arguments(self, parser):
        parser.add_argument('--delete', dest='delete', action='store_true', help='Delete the test and development nomcom')

    def handle(self, *args, **options):
        if socket.gethostname().split('.')[0] in ['core3', 'ietfa', 'ietfb', 'ietfc', ]:
            raise EnvironmentError("Refusing to create a test nomcom on a production server")

        opt_delete = options.get('delete', False)
        if opt_delete:
            if Group.objects.filter(acronym='nomcom7437').exists():
                Group.objects.filter(acronym='nomcom7437').delete()
                users_to_delete = ['testchair','testmember','testcandidate']
                Person.objects.filter(user__username__in=users_to_delete).delete()
                User.objects.filter(username__in=users_to_delete).delete()
                self.stdout.write("Deleted test group 'nomcom7437' and its related objects.")
            else:
                self.stderr.write("test nomcom 'nomcom7437' does not exist; nothing to do.\n")
        else:
            if Group.objects.filter(acronym='nomcom7437').exists():
                self.stderr.write("test nomcom 'nomcom7437' already exists; nothing to do.\n")
            else:
                nc = NomComFactory.create(**nomcom_kwargs_for_year(year=7437,
                                                                  populate_personnel=False,
                                                                  populate_positions=False))

                e = EmailFactory(person__name='Test Chair', address='testchair@example.com', person__user__username='testchair', person__default_emails=False, origin='testchair')
                e.person.user.set_password('password')
                e.person.user.save()
                nc.group.role_set.create(name_id='chair',person=e.person,email=e)

                e = EmailFactory(person__name='Test Member', address='testmember@example.com', person__user__username='testmember', person__default_emails=False, origin='testmember')
                e.person.user.set_password('password')
                e.person.user.save()
                nc.group.role_set.create(name_id='member',person=e.person,email=e)


                e = EmailFactory(person__name='Test Candidate', address='testcandidate@example.com', person__user__username='testcandidate', person__default_emails=False, origin='testcandidate')
                e.person.user.set_password('password')
                e.person.user.save()
                NomineePositionFactory(nominee__nomcom=nc, nominee__person=e.person,
                                       position__nomcom=nc, position__name='Test Area Director', position__is_iesg_position=True,
                                      )

                self.stdout.write("%s\n" % key.decode())
                self.stdout.write("Nomcom 7437 created. The private key can also be found at any time\nin ietf/nomcom/factories.py. Note that it is NOT a secure key.\n")

