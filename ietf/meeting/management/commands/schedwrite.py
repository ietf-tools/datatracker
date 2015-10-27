from django.core.management.base import BaseCommand, CommandError
from django.core import serializers
from optparse import make_option


class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
        make_option('--format', default='json', dest='format',
            help='Specifies the output serialization format for fixtures.'),
        make_option('--indent', default=None, dest='indent', type='int',
            help='Specifies the indent level to use when pretty-printing output'),
    #    make_option('--schedulename', action='store',  dest='schedulename', default=False,
    #        help='Tells Django to stop running the test suite after first failed test.')
    )
    help = 'Saves the scheduled information for a named schedule in JSON format'
    args = 'meetingname [owner] schedname'

    def handle(self, *labels, **options):

        meetingname = labels[0]
        schedname   = labels[1]

        from ietf.meeting.helpers import get_meeting,get_schedule

        format = options.get('format','json')
        indent = options.get('indent', 2)
        meeting = get_meeting(meetingname)
        schedule = get_schedule(meeting, schedname)

        assignments = schedule.assignments.all()

        # cribbed from django/core/management/commands/dumpdata.py
        # Check that the serialization format exists; this is a shortcut to
        # avoid collating all the objects and _then_ failing.
        if format not in serializers.get_public_serializer_formats():
            raise CommandError("Unknown serialization format: %s" % format)

        return serializers.serialize(format, assignments, indent=indent,
                                     use_natural_keys=True)


