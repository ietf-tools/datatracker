# Copyright The IETF Trust 2016-2019, All Rights Reserved

import sys

#from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

import debug                            # pyflakes:ignore

from ietf.group.models import Role
from ietf.name.models import GroupTypeName, RoleName

class Command(BaseCommand):
    help = "Create apache permission stanzas for given roles."

    def add_arguments(self, parser):
        parser.add_argument('roles', nargs='*',
            help="One or more group:type:role specifications.  Use '*' as wildcard. Use group acronyms "
            "for groups and group type and role name slugs for type and role. "
            "Examples:  all ADs: *:*:ad,  core chairs: core:*:chair,  Directorate secretaries: *:dir:secr."
            )
        parser.add_argument('-l', '--list-slugs', action='store_true', default=False,
            help="List the group type and role slugs")

    # --------------------------------------------------------------------

    def handle(self, *filenames, **options):
        self.verbosity = options['verbosity']
        self.errors = []

        if options['list_slugs']:
            self.stdout.write("Group types:\n\n")
            for t in GroupTypeName.objects.all().order_by('slug'):
                self.stdout.write("   %-16s  %s\n" % (t.slug, t.name))
            self.stdout.write("\nRoles:\n\n")
            for r in RoleName.objects.all().order_by('slug'):
                self.stdout.write("   %-16s  %s\n" % (r.slug, r.name))
            sys.exit(0)

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
                        login = role.person.user.username
                        if not login in seen:
                            seen.add(login)
                            self.stdout.write("Require user %s\n" % login)
                
