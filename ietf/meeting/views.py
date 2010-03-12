# Copyright The IETF Trust 2007, All Rights Reserved

# Create your views here.
#import models
from django.shortcuts import render_to_response, get_object_or_404
from ietf.proceedings.models import Meeting, MeetingTime, WgMeetingSession, MeetingVenue, IESGHistory, Proceeding, Switches, WgProceedingsActivities
from django.views.generic.list_detail import object_list
from django.http import HttpResponseRedirect, HttpResponse, Http404
from django.core.urlresolvers import reverse
from django.db.models import Q
from django.template import RequestContext
from django.template.loader import render_to_string
from django.conf import settings
from django.utils.decorators import decorator_from_middleware
from django.middleware.gzip import GZipMiddleware
from django.db.models import Count
import datetime

@decorator_from_middleware(GZipMiddleware)
def show_html_materials(request, meeting_num=None):
    proceeding = get_object_or_404(Proceeding, meeting_num=meeting_num)
    begin_date = proceeding.sub_begin_date
    cut_off_date = proceeding.sub_cut_off_date
    cor_cut_off_date = proceeding.c_sub_cut_off_date
    now = datetime.date.today()
    if settings.SERVER_MODE != 'production' and '_testoverride' in request.REQUEST:
        pass
    elif now > cor_cut_off_date:
        return render_to_response("meeting/list_closed.html",{'meeting_num':meeting_num,'begin_date':begin_date, 'cut_off_date':cut_off_date, 'cor_cut_off_date':cor_cut_off_date}, context_instance=RequestContext(request))
    sub_began = 0
    if now > begin_date:
        sub_began = 1
    # List of WG sessions and Plenary sessions
    queryset_list = WgMeetingSession.objects.filter(Q(meeting=meeting_num, group_acronym_id__gte = -2, status_id=4), Q(irtf__isnull=True) | Q(irtf=0))
    queryset_irtf = WgMeetingSession.objects.filter(meeting=meeting_num, group_acronym_id__gte = -2, status_id=4, irtf__gt=0)
    queryset_interim = []
    queryset_training = []
    for item in list(WgMeetingSession.objects.filter(meeting=meeting_num)):
        if item.interim_meeting():
            item.interim=1
            queryset_interim.append(item)
        if item.group_acronym_id < -2:
            if item.slides():
                queryset_training.append(item)
    cache_version = WgProceedingsActivities.objects.aggregate(Count('id'))
    return object_list(request,queryset=queryset_list, template_name="meeting/list.html",allow_empty=True, extra_context={'meeting_num':meeting_num,'irtf_list':queryset_irtf, 'interim_list':queryset_interim, 'training_list':queryset_training, 'begin_date':begin_date, 'cut_off_date':cut_off_date, 'cor_cut_off_date':cor_cut_off_date,'sub_began':sub_began,'cache_version':cache_version})

def current_materials(request):
    meeting = Meeting.objects.order_by('-meeting_num')[0]
    return HttpResponseRedirect( reverse(show_html_materials, args=[meeting.meeting_num]) )

def get_plenary_agenda(meeting_num, id):
    try:
        plenary_agenda_file = settings.AGENDA_PATH + WgMeetingSession.objects.get(meeting=meeting_num,group_acronym_id=id).agenda_file()
        try:
            f = open(plenary_agenda_file)
            plenary_agenda = f.read()
            f.close()
            return plenary_agenda
        except IOError:
             return "THE AGENDA HAS NOT BEEN UPLOADED YET"
    except WgMeetingSession.DoesNotExist:
        return "The Plenary has not been scheduled"

def agenda_info(num=None):
    if num:
        meetings = [ num ]
    else:
        meetings =list(Meeting.objects.all())
        meetings.reverse()
        meetings = [ meeting.meeting_num for meeting in meetings ]
    for n in meetings:
        try:
            timeslots = MeetingTime.objects.select_related().filter(meeting=n).order_by("day_id", "time_desc")
            update = Switches.objects.get(id=1)
            meeting= Meeting.objects.get(meeting_num=n)
            venue  = MeetingVenue.objects.get(meeting_num=n)
            break
        except (MeetingTime.DoesNotExist, Switches.DoesNotExist, Meeting.DoesNotExist, MeetingVenue.DoesNotExist):
            continue
    else:
        raise Http404("No meeting information for meeting %s available" % num)
    ads = list(IESGHistory.objects.select_related().filter(meeting=n))
    if not ads:
        ads = list(IESGHistory.objects.select_related().filter(meeting=str(int(n)-1)))
    ads.sort(key=(lambda item: item.area.area_acronym.acronym))
    plenaryw_agenda = get_plenary_agenda(n, -1)
    plenaryt_agenda = get_plenary_agenda(n, -2)
    return timeslots, update, meeting, venue, ads, plenaryw_agenda, plenaryt_agenda

@decorator_from_middleware(GZipMiddleware)
def html_agenda(request, num=None):
    timeslots, update, meeting, venue, ads, plenaryw_agenda, plenaryt_agenda = agenda_info(num)
    if  settings.SERVER_MODE != 'production' and '_testiphone' in request.REQUEST:
        user_agent = "iPhone"
    elif 'HTTP_USER_AGENT' in request.META:
        user_agent = request.META["HTTP_USER_AGENT"]
    else:
        user_agent = ""
    #print user_agent
    if "iPhone" in user_agent:
        template = "meeting/m_agenda.html"
    else:
        template = "meeting/agenda.html"
    return render_to_response(template,
            {"timeslots":timeslots, "update":update, "meeting":meeting, "venue":venue, "ads":ads,
                "plenaryw_agenda":plenaryw_agenda, "plenaryt_agenda":plenaryt_agenda, },
            context_instance=RequestContext(request))

def text_agenda(request, num=None):
    timeslots, update, meeting, venue, ads, plenaryw_agenda, plenaryt_agenda = agenda_info(num)
    plenaryw_agenda = "   "+plenaryw_agenda.strip().replace("\n", "\n   ")
    plenaryt_agenda = "   "+plenaryt_agenda.strip().replace("\n", "\n   ")
    return HttpResponse(render_to_string("meeting/agenda.txt",
        {"timeslots":timeslots, "update":update, "meeting":meeting, "venue":venue, "ads":ads,
            "plenaryw_agenda":plenaryw_agenda, "plenaryt_agenda":plenaryt_agenda, },
        RequestContext(request)), mimetype="text/plain")
    
