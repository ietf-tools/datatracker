# Create your views here.
import models
from django.shortcuts import render_to_response as render
import django.newforms as forms
from django.utils.html import escape, linebreaks
import ietf.utils
from ietf.proceedings.models import Meeting, MeetingTime, WgMeetingSession, SessionName, NonSession, MeetingVenue, IESGHistory
from django.views.generic.list_detail import object_list
from django.http import Http404
from  django.db.models import Q

def default(request):
    """Default page, with links to sub-pages"""
    return render("meeting/list.html", {})

def showlist(request):
    """Display a list of existing disclosures"""
    return meeting_list(request, 'meeting/list.html')


# don't hide Python's builtin list creation -- call this something else than 'list()'
def meeting_list(request, template):
    """ Get A List of All Meetings That are in the system """  
    meetings  = Meeting.objects.all()
    
    return render(template,
        {
            'meetings' : meetings.order_by(* ['-start_date', ] ),
        } )

# Details views

def show_html_materials(request, meeting_num=None):
    # List of WG sessions and Plenary sessions
    queryset_list = WgMeetingSession.objects.filter(Q(meeting=meeting_num, group_acronym_id__gte = -2, status_id=4), Q(irtf__isnull=True) | Q(irtf=0))
    return object_list(request,queryset=queryset_list, template_name="meeting/list.html",allow_empty=True, extra_context={'meeting_num':meeting_num})

def show_html_agenda(request, meeting_num=None, html_or_txt=None):
    try:
        queryset_list=MeetingTime.objects.filter(meeting=meeting_num).exclude(day_id=0).order_by("day_id","time_desc")
    except MeetingTime.DoesNotExist:
        raise Http404
    meeting_info=Meeting.objects.get(meeting_num=meeting_num)
    nonsession_info=NonSession.objects.filter(meeting=meeting_num,day_id__gte='0').order_by("day_id")
    try:
        meetingvenue_info=MeetingVenue.objects.get(meeting_num=meeting_num)
    except MeetingVenue.DoesNotExist:
        raise Http404
    plenaryt_agenda_file = "/home/master-site/proceedings/%s" % WgMeetingSession.objects.get(meeting=meeting_num,group_acronym_id=-2).agenda_file()
    try:
        f = open(plenaryt_agenda_file)
        plenaryt_agenda = f.read()
        f.close()
    except IOError:
        plenaryt_agenda = "THE AGENDA HAS NOT BEEN UPLOADED YET"
    if html_or_txt == "html":
        template_file="meeting/agenda.html"
    elif html_or_txt == "txt":
        template_file="meeting/agenda.txt"
    else:
        raise Http404
    plenaryw_agenda_file = "/home/master-site/proceedings/%s" % WgMeetingSession.objects.get(meeting=meeting_num,group_acronym_id=-1).agenda_file()
    try:
        f = open(plenaryw_agenda_file)
        plenaryw_agenda = f.read()
        f.close()
    except IOError:
        plenaryw_agenda = "THE AGENDA HAS NOT BEEN UPLOADED YET"
    # Due to a bug in Django@0.96 we can't use foreign key lookup in
    # order_by(), see http://code.djangoproject.com/ticket/2076.  Changeset
    # [133] is broken because it requires a patched Django to run.  Work
    # around this instead.  Later: FIXME (revert to the straightforward code
    # when this bug has been fixed in the Django release we're running.)
    ## queryset_list_sun=WgMeetingSession.objects.filter(meeting=meeting_num, sched_time_id1__day_id=0).order_by('sched_time_id1__time_desc')
    queryset_list_sun=list(WgMeetingSession.objects.filter(meeting=meeting_num, sched_time_id1__day_id=0))
    queryset_list_sun.sort(key=(lambda item: item.sched_time_id1.time_desc))
    queryset_list_ads = list(IESGHistory.objects.filter(meeting=meeting_num))
    queryset_list_ads.sort(key=(lambda item: item.area.area_acronym.acronym))
    return object_list(request,queryset=queryset_list, template_name=template_file,allow_empty=True, extra_context={'qs_sun':queryset_list_sun, 'meeting_info':meeting_info, 'meeting_num':meeting_num, 'nonsession_info':nonsession_info, 'meetingvenue_info':meetingvenue_info, 'plenaryw_agenda':plenaryw_agenda, 'plenaryt_agenda':plenaryt_agenda, 'qs_ads':queryset_list_ads})

def show(request):
    return 0
