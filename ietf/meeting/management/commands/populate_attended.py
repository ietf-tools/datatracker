# Copyright The IETF Trust 2022, All Rights Reserved

import debug # pyflakes: ignore

from tqdm import tqdm

from django.core.management.base import BaseCommand

from ietf.meeting.models import Session
from ietf.meeting.utils import sort_sessions
from ietf.person.models import Person, Email

import json

class Command(BaseCommand):

    help = 'Populates the meeting Attended table based on bluesheets and registration information'

    def add_arguments(self, parser):
        parser.add_argument('filename', nargs='+', type=str)

    def handle(self, *args, **options):

        issues = []
        session_cache = dict()
        skipped = 0
        for filename in options['filename']:
            records = json.loads(open(filename,'r').read())
            for record in tqdm(records):
                user = record['sub']
                session_acronym = record['group']
                meeting_number = record['meeting']
                email = record['email']
                # In the expected dumps from MeetEcho, if there was only one session for group foo, it would just be named 'foo'.
                # If there were _three_, we would see 'foo' for the first, 'foo_2' for the second, and 'foo_3' for the third.
                # order below is the index into what is returned from sort_sessions -- 0 is the first session for a group at that meeting.
                # There is brutal fixup below for older meetings where we had special arrangements where meetecho reported the non-existant
                # group of 'plenary', mapping it into the appropriate 'ietf' group session.
                # A bug in the export scripts at MeetEcho trimmed the '-t' from 'model-t'.
                order = 0
                if session_acronym in ['anrw_test', 'demoanrw', 'hostspeaker']:
                    skipped = skipped + 1
                    continue
                if session_acronym=='model':
                    session_acronym='model-t'
                if '_' in session_acronym:
                    session_acronym, order = session_acronym.split('_')
                    order = int(order)-1
                if session_acronym == 'plenary':
                    session_acronym = 'ietf'
                    if meeting_number == '111':
                        order = 4
                    elif meeting_number == '110':
                        order = 3
                    elif meeting_number == '109':
                        order = 6
                    elif meeting_number == '108':
                        order = 13
                if not (meeting_number, session_acronym) in session_cache:
                    session_cache[(meeting_number, session_acronym)] = sort_sessions([s for s in Session.objects.filter(meeting__number=meeting_number,group__acronym=session_acronym) if s.official_timeslotassignment()])
                sessions = session_cache[(meeting_number, session_acronym)]
                try:
                    session = sessions[order]
                except IndexError:
                    issues.append(('session not found',record))
                    continue
                person = None
                email = Email.objects.filter(address=email).first()
                if email:
                    person = email.person
                else:
                    person = Person.objects.filter(user__pk=user).first()
                if not person:
                    issues.append(('person not found',record))
                    continue
                obj, created = session.attended_set.get_or_create(person=person)
        for issue in issues:
            print(issue)
        print(f'{len(issues)} issues encountered')
        print(f'{skipped} records intentionally skipped')
