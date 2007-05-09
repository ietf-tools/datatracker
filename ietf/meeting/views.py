# Create your views here.
import models
from django.shortcuts import render_to_response as render
import django.newforms as forms
from django.utils.html import escape, linebreaks
import ietf.utils
from ietf.proceedings import models

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
	#a=models.MeetingTime.objects.all().filter(meeting=68,day_id=0)
	#print a
	session = models.WgMeetingSession.objects.all()

# There has to be a better way to do this, than the way i'm doing it here.. 
# I'm copying the formula from the cgi script.. 
	sessions = session.filter(meeting=meeting_num)
# First we get the non sessions lines 98 - 100 from the cgi..
#	non_sessions = models.NonSession.objects.filter(meeting_num=meeting_num)
	cbreak_time = models.NonSession.objects.filter(
					meeting_num=meeting_num).filter(non_session_ref=2)[0]
	break_time = models.NonSession.objects.filter(
					meeting_num=meeting_num).filter(non_session_ref=3)[0]
	fbreak_time = models.NonSession.objects.filter(
					meeting_num=meeting_num).filter(non_session_ref=6)[0]
	abreak_time1 = models.NonSession.objects.filter(
						meeting_num=meeting_num).filter(non_session_ref=6)[0]
	abreak_time2 = models.NonSession.objects.filter(
						meeting_num=meeting_num).filter(non_session_ref=6)[0]
	reg_time = models.NonSession.objects.filter(meeting_num=meeting_num).filter(non_session_ref=1)

	meeting = models.Meeting.objects.filter(meeting_num=meeting_num)[0]

	return render("meeting/agenda.html",
	{
		"all_sessions": sessions,
		"meeting_num": meeting_num,
		"meeting": meeting,
		"cbreak_time": cbreak_time,
		"break_time": break_time,
		"fbreak_time": fbreak_time

	} )


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
