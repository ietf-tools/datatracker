"""
Runs the automatic placement code (simulated annealing of glass)
for a given meeting number, using a schedule given by the schedule database ID.

for help on this file:
https://docs.djangoproject.com/en/dev/howto/custom-management-commands/

"""

from django.core.management.base import BaseCommand
from optparse import make_option
#import cProfile, pstats, io
import sys
from ietf.meeting.models import Schedule, Meeting

class Command(BaseCommand):
    args = '<meeting> <schedulename>'
    help = 'perform automatic placement'
    stderr = sys.stderr
    stdout = sys.stdout

    verbose = False
    profile = False
    permit_movement = False
    maxstep = 20000
    seed    = None
    recordsteps = False

    option_list = BaseCommand.option_list + (
        make_option('--profile',
            action='store_true',
            dest='profile',
            default=False,
            help='Enable verbose mode'),
       make_option('--recordsteps',
            action='store_true',
            dest='recordsteps',
            default=False,
            help='Enable recording progress to table'),
        make_option('--verbose',
            action='count',
            dest='verbose',
            default=False,
            help='Enable verbose mode'),
        make_option('--maxstep',
                    action="store", type="int",
                    dest='maxstep',
                    default=20000,
                    help='Maximum number of steps'),
        make_option('--seed',
                    action="store", type="int",
                    dest='seed',
                    default=None,
                    help='Seed to use for calculation'),
        )

    def handle(self, *labels, **options):
        self.verbose  = options.get('verbose', 1)

        meetingname = labels[0]
        schedname   = labels[1]
        targetname  = None
        if labels[2] is not None:
            targetname = labels[2]

        seed    = options.get('seed', None)
        maxstep = options.get('maxstep', 20000)
        verbose = options.get('verbose', False)
        profile = options.get('profile', False)
        recordsteps = options.get('recordsteps', False)

        from ietf.meeting.helpers import get_meeting
        try:
            meeting = get_meeting(meetingname)
        except Meeting.DoesNotExist:
            print "No such meeting: %s" % (meetingname)
            return

        try:
            schedule = meeting.schedule_set.get(name = schedname)
        except Schedule.DoesNotExist:
            print "No such schedule: %s in meeting: %s" % (schedname, meeting)
            return

        if targetname is not None:
            try:
                targetsched = meeting.schedule_set.get(name=targetname)
            except Schedule.DoesNotExist:
                print "Creating new schedule %s" % (targetname)
                targetsched = Schedule(meeting = meeting,
                                       owner   = schedule.owner,
                                       name = targetname)
                targetsched.save()
        else:
            targetsched = schedule

        print "Saving results to %s" % (targetsched.name)

        from ietf.meeting.placement import CurrentScheduleState
        css = CurrentScheduleState(schedule, seed)
        css.recordsteps = recordsteps
        css.verbose     = verbose

        if profile:
            import cProfile
            cProfile.runctx('css.do_placement(maxstep, targetsched)',
                            vars(),
                            vars(),
                            'placestats.pyprof')

            import pstats
            p = pstats.Stats('placestats.pyprof')
            p.strip_dirs().sort_stats(-1).print_stats()
        else:
            css.do_placement(maxstep, targetsched)



