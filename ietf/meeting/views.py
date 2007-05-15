# Create your views here.
import models
from django.shortcuts import render_to_response as render
import django.newforms as forms
from django.utils.html import escape, linebreaks
import ietf.utils
from ietf.proceedings import models
from django.views.generic.list_detail import object_list

def default(request):
    """Default page, with links to sub-pages"""
    return render("meeting/list.html", {})

def showlist(request):
    """Display a list of existing disclosures"""
    return list(request, 'meeting/list.html')


def list(request, template):
    """ Get A List of All Meetings That are in the system """  
    meetings  = models.Meeting.objects.all()
    
    return render(template,
        {
            'meetings' : meetings.order_by(* ['-start_date', ] ),
        } )

# Details views

def show_html_materials(request, meeting_num=None):
	return render("meeting/list.html",{})

def show_html_agenda(request, meeting_num=None):
    meeting_info=models.Meeting.objects.filter(meeting_num=meeting_num)[0]
    queryset_list=models.WgMeetingSession.objects.filter(meeting_num=meeting_num)
    queryset_list_sun=models.WgMeetingSession.objects.filter(meeting=meeting_num, sched_time_id1__day_id=0).select_related().order_by("meeting_times.time_id")
    return object_list(request,queryset=queryset_list, template_name='meeting/agenda.html',allow_empty=True, extra_context={'qs_sun':queryset_list_sun, 'meeting_info':meeting_info, 'meeting_num':meeting_num})

def show(request, meeting_num=None):
    """Show a specific IPR disclosure"""
    assert meeting_num != None
    meeting = models.Meeting.objects.filter(meeting_num=meeting_num)[0]
    meeting.p_notes = linebreaks(escape(meeting.p_notes))
    meeting.discloser_identify = linebreaks(escape(meeting.discloser_identify))
    meeting.comments = linebreaks(escape(meeting.comments))
    meeting.other_notes = linebreaks(escape(meeting.other_notes))
    opt = meeting.licensing_option
    meeting.licensing_option = dict(models.LICENSE_CHOICES)[meeting.licensing_option]
    meeting.selecttype = dict(models.SELECT_CHOICES)[meeting.selecttype]
    if meeting.selectowned:
        meeting.selectowned = dict(models.SELECT_CHOICES)[meeting.selectowned]
    return render("meeting/details.html",  {"meeting": meeting, "section_list": section_list})
