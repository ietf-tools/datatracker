# Copyright The IETF Trust 2018-2020, All Rights Reserved
# -*- coding: utf-8 -*-


from tqdm import tqdm

from django.conf import settings
from django.core.management.base import BaseCommand


import debug                            # pyflakes:ignore

from ietf.person.models import Person, Alias


class Command(BaseCommand):
    help = ("""
        Check for missing Alias records, and create missing record if requested.
        Check for certain bad Alias records, and fix if requested.
        Check for certain bad strings in Person names and fix if requested.
        """)

    def add_arguments(self, parser):
        parser.add_argument('-f', '--fix', action='store_true', default=False,
            help="Create missing aliases")

    def handle(self, *args, **options):
        verbosity = options['verbosity']
        fix = options['fix']
        system_names = ['(System)', 'IAB', 'IANA', ]
        missing = []
        badalias = []
        badname = []
        onename = []
        addrname = []
        if hasattr(settings, 'SERVER_MODE'):
            # Try to avoid sending mail during repair
            settings.SERVER_MODE = 'repair'
        for person in tqdm(Person.objects.all()):
            email = person.email()
            # Person names with junk
            if '<>' in person.name:
                name = person.name
                if fix:
                    person.name = name.replace('<>', '').strip()
                    person.save()
                badname.append((name, person.name, email))
            if '@' in person.name:
                # Can't fix this here, needs human intervention
                addrname.append((person.name, '-', email))
            #                    
            alias_names = { n for n in [ person.name, person.ascii, person.plain_name(), person.plain_ascii(), ] if n and (' ' in n and not '@' in n) }
            aliases = Alias.objects.filter(name__in=alias_names, person=person)
            # Aliases that look like email addresses
            for alias in aliases:
                if '@' in alias.name:
                    name = alias.name
                    aliases = aliases.exclude(pk=alias.pk)
                    if fix:
                        alias.delete()
                    badalias.append((name, '-', email))
            # Missing aliases
            if aliases.count() < len(alias_names):
                for name in alias_names - { a.name for a in aliases }:
                    if fix:
                        Alias.objects.create(person=person, name=name)
                    missing.append((name, person.name, email))
            if not ' ' in person.name and not person.name in system_names:
                name = person.name
                # Names using Chinese ideographs don't necessary have spaces
                if (all( 0x4E00 <= ord(c) <= 0x9FFF for c in name) or # Han
                    all( 0xAC00 <= ord(c) <= 0xD7AF for c in name) ): # HanGul
                        pass
                else:
                    onename.append((name, '-', email))
        
        action = "Fixed" if fix else "Found"
        #
        print("\n  %s %d bad names." % (action, len(badname)))
        if verbosity > 1:
            for n in badname:
                print(n)
        print("\n  %s %d missing aliases." % (action, len(missing)))
        if verbosity > 1:
            for n in missing:
                print(n)
        print("\n  %s %d bad aliases." % (action, len(badalias)))
        if verbosity > 1:
            for n in badalias:
                print(n)
        print("\n  Found %d names that could be email addresses." % (len(addrname)))
        if verbosity > 1:
            for n in addrname:
                print(n)
        else:
            print("  Use -v2 to list them.")
        print("\n  Found %d single-word names (names with no space)." % (len(onename), ))
        if verbosity > 1:
            for n in onename:
                print(n)
        else:
            print("  Use -v2 to list them.")
                        