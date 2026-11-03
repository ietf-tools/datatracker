# Copyright The IETF Trust 2013-2019, All Rights Reserved

def get_session(timeslot, schedule=None):
    '''
    Helper function to get the session given a timeslot, assume Official schedule if one isn't
    provided.  Replaces "timeslot.session"
    '''
    # todo, doesn't account for shared timeslot
    if not schedule:
        schedule = timeslot.meeting.schedule
    qs = timeslot.sessions.filter(timeslotassignments__schedule__in=[schedule, schedule.base if schedule else None])  #.exclude(states__slug='deleted')
    if qs:
        return qs[0]
    else:
        return None
    
def get_timeslot(session, schedule=None):
    '''
    Helper function to get the timeslot associated with a session.  Created for Agenda Tool
    db schema changes.  Use this function in place of session.timeslot_set.all()[0].  Don't specify
    schedule to use the meeting "official" schedule.
    '''
    if not schedule:
        schedule = session.meeting.schedule
    ss = session.timeslotassignments.filter(schedule__in=[schedule, schedule.base if schedule else None])
    if ss:
        return ss[0].timeslot
    else:
        return None

