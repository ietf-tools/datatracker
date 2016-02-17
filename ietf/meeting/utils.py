import datetime

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
