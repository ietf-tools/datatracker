# Create your views here.
import models
from django.shortcuts import render_to_response as render
import django.newforms as forms
from django.utils.html import escape, linebreaks
import ietf.utils
from ietf.proceedings.models import Meeting, MeetingTime, WgMeetingSession, SessionName, NonSession, MeetingVenue
from django.views.generic.list_detail import object_list

def default(request):
    """Default page, with links to sub-pages"""
    return render("meeting/list.html", {})

def showlist(request):
    """Display a list of existing disclosures"""
    return list(request, 'meeting/list.html')


def list(request, template):
    """ Get A List of All Meetings That are in the system """  
    meetings  = Meeting.objects.all()
    
    return render(template,
        {
            'meetings' : meetings.order_by(* ['-start_date', ] ),
        } )

# Details views

def show_html_materials(request, meeting_num=None):
	return render("meeting/list.html",{})

def show_html_agenda(request, meeting_num=None):
    meeting_info=Meeting.objects.filter(meeting_num=meeting_num)[0]
    nonsession_info=NonSession.objects.filter(meeting=meeting_num)[0]
    meetingvenue_info=MeetingVenue.objects.filter(meeting_num=meeting_num)[0]
    queryset_list=MeetingTime.objects.filter(meeting=meeting_num).exclude(day_id=0).order_by("day_id","time_desc") 
    #queryset_list=WgMeetingSession.objects.filter(meeting_num=meeting_num, group_acronym_id > -3) 
    queryset_list_sun=WgMeetingSession.objects.filter(meeting=meeting_num, sched_time_id1__day_id=0).order_by('sched_time_id1__time_desc')
    return object_list(request,queryset=queryset_list, template_name='meeting/agenda.html',allow_empty=True, extra_context={'qs_sun':queryset_list_sun, 'meeting_info':meeting_info, 'meeting_num':meeting_num, 'nonsession_info':nonsession_info, 'meetingvenue_info':meetingvenue_info})

def show(request):
    return 0

