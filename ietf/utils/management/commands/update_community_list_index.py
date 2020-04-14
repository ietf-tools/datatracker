# Copyright The IETF Trust 2019-2020, All Rights Reserved
# -*- coding: utf-8 -*-

from tqdm import tqdm

from django.core.management.base import BaseCommand

import debug                            # pyflakes:ignore

from ietf.community.models import SearchRule
from ietf.community.utils import reset_name_contains_index_for_rule

class Command(BaseCommand):
    help = ("""
        Update the index tables for stored regex-based document search rules.
        """)

    def add_arguments(self, parser):
        parser.add_argument('-n', '--dry-run', action='store_true', default=False,
            help="Just show what would have been done")
         

    def handle(self, *args, **options):
        verbosity = options.get('verbosity', 1)
        for rule in tqdm(SearchRule.objects.filter(rule_type='name_contains'), disable=(verbosity!=1)):
            count1 = rule.name_contains_index.count()
            if not options['dry_run']:
                reset_name_contains_index_for_rule(rule)
            count2 = rule.name_contains_index.count()
            if int(options['verbosity']) > 1:
                group = rule.group or rule.community_list.group
                person  = rule.person
                if not person and not group:
                    try:
                        person = rule.community_list.user.person
                    except:
                        pass
                name = ((group and group.acronym) or (person and person.email_address())) or '?'
                self.stdout.write("%-24s %-24s  %3d -->%3d\n" % (name[:24], rule.text[:24], count1, count2 ))
            
