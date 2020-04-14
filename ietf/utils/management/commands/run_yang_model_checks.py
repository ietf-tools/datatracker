# Copyright The IETF Trust 2017-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import json

from textwrap import dedent

from django.core.management.base import BaseCommand

import debug                            # pyflakes:ignore

from ietf.doc.models import Document, State, DocAlias
from ietf.submit.models import Submission, SubmissionCheck
from ietf.submit.checkers import DraftYangChecker


class Command(BaseCommand):
    """
    Run yang model checks on active drafts.

    Repeats the yang checks in ietf/submit/checkers.py for active drafts, in
    order to catch changes in status due to new modules becoming available in
    the module directories.

    """

    help = dedent(__doc__).strip()
            
    def add_arguments(self, parser):
        parser.add_argument('draftnames', nargs="*", help="drafts to check, or none to check all active yang drafts")
        parser.add_argument('--clean',
            action='store_true', dest='clean', default=False,
            help='Remove the current directory content before writing new models.')


    def check_yang(self, checker, draft, force=False):
        if self.verbosity > 1:
            self.stdout.write("Checking %s-%s" % (draft.name, draft.rev))
        elif self.verbosity > 0:
            self.stderr.write('.', ending='')
        submission = Submission.objects.filter(name=draft.name, rev=draft.rev).order_by('-id').first()
        if submission or force:
            check = submission.checks.filter(checker=checker.name).order_by('-id').first()
            if check or force:
                result = checker.check_file_txt(draft.get_file_name())
                passed, message, errors, warnings, items = result
                if self.verbosity > 2:
                    self.stdout.write("  Errors: %s\n"
                                      "  Warnings: %s\n"
                                      "  Message:\n%s\n" % (errors, warnings, message))
                items = json.loads(json.dumps(items))
                new_res = (passed, errors, warnings, message)
                old_res = (check.passed, check.errors, check.warnings, check.message) if check else ()
                if new_res != old_res:
                    if self.verbosity > 1:
                        self.stdout.write("  Saving new yang checker results for %s-%s" % (draft.name, draft.rev))
                    SubmissionCheck.objects.create(submission=submission, checker=checker.name, passed=passed,
                                                message=message, errors=errors, warnings=warnings, items=items,
                                                symbol=checker.symbol)
        else:
            self.stderr.write("Error: did not find any submission object for %s-%s" % (draft.name, draft.rev))

    def handle(self, *filenames, **options):
        """
        """

        self.verbosity = int(options.get('verbosity'))
        drafts = options.get('draftnames')

        active_state = State.objects.get(type="draft", slug="active")

        checker = DraftYangChecker()
        if drafts:
            for name in drafts:
                parts = name.rsplit('-',1)
                if len(parts)==2 and len(parts[1])==2 and parts[1].isdigit():
                    name = parts[0]
                draft = DocAlias.objects.get(name=name).document
                self.check_yang(checker, draft, force=True)
        else:
            for draft in Document.objects.filter(states=active_state, type_id='draft'):
                self.check_yang(checker, draft)
