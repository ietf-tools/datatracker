import datetime
import json
import urllib2
import urlparse

from django.conf import settings
from django.template.loader import render_to_string

from ietf.dbtemplate.models import DBTemplate
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

def create_proceedings_templates(meeting):
    '''Create DBTemplates for meeting proceedings'''
    # Get meeting attendees from registration system
    url = urlparse.urljoin(settings.REGISTRATION_ATTENDEES_BASE_URL,meeting.number)
    try:
        attendees = json.load(urllib2.urlopen(url))
    except (ValueError, urllib2.HTTPError):
        attendees = []

    if attendees:
        attendees = sorted(attendees, key = lambda a: a['LastName'])
        content = render_to_string('meeting/proceedings_attendees_table.html', {
            'attendees':attendees})
        DBTemplate.objects.create(
            path='/meeting/proceedings/%s/attendees.html' % meeting.number,
            title='IETF %s Attendee List' % meeting.number,
            type_id='django',
            content=content)
    
    # Make copy of default IETF Overview template
    if not meeting.overview:
        template = DBTemplate.objects.get(path='/meeting/proceedings/defaults/overview.rst')
        template.id = None
        template.path = '/meeting/proceedings/%s/overview.rst' % (meeting.number)
        template.title = 'IETF %s Proceedings Overview' % (meeting.number)
        template.save()
        meeting.overview = template
        meeting.save()

def finalize(meeting):
    end_date = meeting.end_date()
    end_time = datetime.datetime.combine(end_date, datetime.datetime.min.time())+datetime.timedelta(days=1)
    for session in meeting.session_set.all():
        for sp in session.sessionpresentation_set.filter(document__type='draft',rev=None):
            rev_before_end = [e for e in sp.document.docevent_set.filter(newrevisiondocevent__isnull=False).order_by('-time') if e.time <= end_time ]
            if rev_before_end:
                sp.rev = rev_before_end[-1].newrevisiondocevent.rev
            else:
                sp.rev = '00'
            sp.save()
    
    create_proceedings_templates(meeting)
    meeting.proceedings_final = True
    meeting.save()
    return

