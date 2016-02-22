import datetime

from ietf.meeting.models import Session
from ietf.group.utils import can_manage_materials

def group_sessions(sessions):

    def sort_key(session):
        if session.meeting.type.slug=='ietf':
            official_sessions = session.timeslotassignments.filter(schedule=session.meeting.agenda)
            if official_sessions:
                return official_sessions.first().timeslot.time
            elif session.meeting.date:
                return datetime.datetime.combine(session.meeting.date,datetime.datetime.min.time())
            else:
                return session.requested
        else:
            # TODO: use timeslots for interims once they have them
            return datetime.datetime.combine(session.meeting.date,datetime.datetime.min.time())

    for s in sessions:
        s.time=sort_key(s)

    sessions = sorted(sessions,key=lambda s:s.time,reverse=True)

    today = datetime.date.today()
    future = []
    in_progress = []
    past = []
    for s in sessions:
        if s.meeting.date > today:
            future.append(s)
        elif s.meeting.end_date() >= today:
            in_progress.append(s)
        else:
            past.append(s)

    return future, in_progress, past

def get_upcoming_manageable_sessions(user):
    """  Find all the sessions for meetings that haven't ended that the user could affect """

    # Consider adding an argument that has some Qs to append to the queryset
    # to allow filtering to a particular group, etc. if we start seeing a lot of code
    # that calls this function and then immediately starts whittling down the returned list

    # Note the days=15 - this allows this function to find meetings in progress that last up to two weeks.
    # This notion of searching by end-of-meeting is also present in Document.future_presentations.
    # It would be nice to make it easier to use querysets to talk about meeting endings wthout a heuristic like this one

    candidate_sessions = Session.objects.exclude(status__in=['canceled','disappr','notmeet','deleted']).filter(meeting__date__gte=datetime.date.today()-datetime.timedelta(days=15))
    refined_candidates = [ sess for sess in candidate_sessions if sess.meeting.end_date()>=datetime.date.today()]

    return [ sess for sess in refined_candidates if can_manage_materials(user, sess.group) ]

def sort_sessions(sessions):

    # Python sorts are stable since version 2,2, so this series results in a list sorted first
    # by the meeting 'number', then by session's group acronym, then by scheduled time
    # (or the time of the session request if the session isn't scheduled).

    def time_sort_key(session):
        official_sessions = session.timeslotassignments.filter(schedule=session.meeting.agenda)
        if official_sessions:
            return official_sessions.first().timeslot.time
        else:
            return session.requested

    time_sorted = sorted(sessions,key=time_sort_key)
    acronym_sorted = sorted(time_sorted,key=lambda x: x.group.acronym)
    meeting_sorted = sorted(acronym_sorted,key=lambda x: x.meeting.number)

    return meeting_sorted
