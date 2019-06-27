# Copyright The IETF Trust 2016-2019, All Rights Reserved
import datetime
import json
import urllib.request, urllib.error, urllib.parse

from django.conf import settings
from django.template.loader import render_to_string

import debug                            # pyflakes:ignore

from ietf.dbtemplate.models import DBTemplate
from ietf.meeting.models import Session, Meeting
from ietf.group.utils import can_manage_materials
from ietf.person.models import Email
from ietf.secr.proceedings.proc_utils import import_audio_files

def group_sessions(sessions):

    def sort_key(session):
        official_sessions = session.timeslotassignments.filter(schedule=session.meeting.agenda)
        if official_sessions:
            return official_sessions.first().timeslot.time
        elif session.meeting.date:
            return datetime.datetime.combine(session.meeting.date,datetime.datetime.min.time())
        else:
            return session.requested

    for s in sessions:
        s.time=sort_key(s)

    sessions = sorted(sessions,key=lambda s:s.time)

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

    # List future and in_progress meetings with ascending time, but past
    # meetings with descending time
    past.reverse()

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
    url = settings.STATS_REGISTRATION_ATTENDEES_JSON_URL.format(number=meeting.number)
    try:
        attendees = json.load(urllib.request.urlopen(url))
    except (ValueError, urllib.error.HTTPError):
        attendees = []

    if attendees:
        attendees = sorted(attendees, key = lambda a: a['LastName'])
        content = render_to_string('meeting/proceedings_attendees_table.html', {
            'attendees':attendees})
        try:
            template = DBTemplate.objects.get(path='/meeting/proceedings/%s/attendees.html' % (meeting.number, ))
            template.title='IETF %s Attendee List' % meeting.number
            template.type_id='django'
            template.content=content
            template.save()
        except DBTemplate.DoesNotExist:
            DBTemplate.objects.create(
                path='/meeting/proceedings/%s/attendees.html' % (meeting.number, ),
                title='IETF %s Attendee List' % meeting.number,
                type_id='django',
                content=content)    
    # Make copy of default IETF Overview template
    if not meeting.overview:
        path = '/meeting/proceedings/%s/overview.rst' % (meeting.number, )
        try:
            template = DBTemplate.objects.get(path=path)
        except DBTemplate.DoesNotExist:
            template = DBTemplate.objects.get(path='/meeting/proceedings/defaults/overview.rst')
            template.id = None
            template.path = path
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
    
    import_audio_files(meeting)
    create_proceedings_templates(meeting)
    meeting.proceedings_final = True
    meeting.save()
    return

def attended_ietf_meetings(person):
    return Meeting.objects.filter(type='ietf',meetingregistration__email__in=Email.objects.filter(person=person).values_list('address',flat=True))

def attended_in_last_five_ietf_meetings(person, date=datetime.datetime.today()):
    previous_five = Meeting.objects.filter(type='ietf',date__lte=date).order_by('-date')[:5]
    attended = attended_ietf_meetings(person)
    return set(previous_five).intersection(attended)

def is_nomcom_eligible(person, date=datetime.date.today()):
    attended = attended_in_last_five_ietf_meetings(person, date)
    is_iesg = person.role_set.filter(group__type_id='area',group__state='active',name_id='ad').exists()
    is_iab = person.role_set.filter(group__acronym='iab',name_id__in=['member','chair']).exists()
    is_iaoc = person.role_set.filter(group__acronym='iaoc',name_id__in=['member','chair']).exists()
    return len(attended)>=3 and not (is_iesg or is_iab or is_iaoc)
