# Copyright 2016 IETF Trust

#from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

import debug                            # pyflakes:ignore

from ietf.group.models import Role

class Command(BaseCommand):
    help = "Create apache permission stanzas for given roles."

    def add_arguments(self, parser):
        parser.add_argument('roles', nargs='+',
            help="One or more group:type:role specifications.  Use '*' as wildcard. Use group acronyms "
            "for groups and group type and role name slugs for type and role. "
            "Examples:  all ADs: *:*:ad,  core chairs: core:*:chair,  Directorate secretaries: *:dir:secr."
            )

    # --------------------------------------------------------------------

    def handle(self, *filenames, **options):
        self.verbosity = options['verbosity']
        self.errors = []

        for role_spec in options["roles"]:
            try:
                group, type, name = role_spec.split(':')
            except ValueError as e:
                raise CommandError(str(e))
            kwargs = {}
            if group != '*':
                kwargs['group__acronym'] = group
            if type != '*':
                kwargs['group__type__slug'] = type
            if name != '*':
                kwargs['name__slug'] = name
            if kwargs:
                seen = set()
                for role in Role.objects.filter(**kwargs).distinct():
                    if role.group.state_id in ['active', 'bof'] and role.person.user:
                        login = role.person.user.username.lower()
                        if not login in seen:
                            seen.add(login)
                            self.stdout.write("Require user %s\n" % login)
                
