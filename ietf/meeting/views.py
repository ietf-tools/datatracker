# Copyright The IETF Trust 2007, All Rights Reserved

# Create your views here.
#import models
from django.shortcuts import render_to_response as render, get_object_or_404
from ietf.proceedings.models import Meeting, MeetingTime, WgMeetingSession, NonSession, MeetingVenue, IESGHistory, Proceeding, Switches
from django.views.generic.list_detail import object_list
from django.http import HttpResponsePermanentRedirect, Http404
from  django.db.models import Q
import datetime

def show_html_materials(request, meeting_num=None):
    proceeding = get_object_or_404(Proceeding, meeting_num=meeting_num)
    begin_date = proceeding.sub_begin_date
    cut_off_date = proceeding.sub_cut_off_date
    cor_cut_off_date = proceeding.c_sub_cut_off_date
    now = datetime.date.today()
    if now > cor_cut_off_date:
        return render("meeting/list_closed.html",{'meeting_num':meeting_num,'begin_date':begin_date, 'cut_off_date':cut_off_date, 'cor_cut_off_date':cor_cut_off_date})
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
    return object_list(request,queryset=queryset_list, template_name="meeting/list.html",allow_empty=True, extra_context={'meeting_num':meeting_num,'irtf_list':queryset_irtf, 'interim_list':queryset_interim, 'training_list':queryset_training, 'begin_date':begin_date, 'cut_off_date':cut_off_date, 'cor_cut_off_date':cor_cut_off_date,'sub_began':sub_began})

def show_html_agenda(request, meeting_num=None, html_or_txt=None):
    if html_or_txt == 'txt':
        return HttpResponsePermanentRedirect('http://www.ietf.org/meetings/agenda_%d.txt' % int(meeting_num))
    queryset_list=MeetingTime.objects.filter(meeting=meeting_num,day_id__gt='0').order_by("day_id","time_desc")
    queryset_list_pre_session=MeetingTime.objects.filter(meeting=meeting_num,day_id__lte='0').order_by("day_id","time_desc")
    meeting_info=get_object_or_404(Meeting, meeting_num=meeting_num)
    nonsession_info=NonSession.objects.filter(meeting=meeting_num,day_id__gte='0').order_by("day_id")
    meetingvenue_info=get_object_or_404(MeetingVenue, meeting_num=meeting_num)
    last_update_info=get_object_or_404(Switches,id=1)
    try:
        plenaryt_agenda_file = "/home/master-site/proceedings/%s" % WgMeetingSession.objects.get(meeting=meeting_num,group_acronym_id=-2).agenda_file()
        try:
            f = open(plenaryt_agenda_file)
            plenaryt_agenda = f.read()
            f.close()
        except IOError:
             plenaryt_agenda = "THE AGENDA HAS NOT BEEN UPLOADED YET"
    except WgMeetingSession.DoesNotExist:
        plenaryt_agenda = "The Technical Plenary has not been scheduled"
    if html_or_txt == "html":
        template_file="meeting/agenda.html"
    elif html_or_txt == "txt":
        template_file="meeting/agenda.txt"
    else:
        raise Http404
    try:
        plenaryw_agenda_file = "/home/master-site/proceedings/%s" % WgMeetingSession.objects.get(meeting=meeting_num,group_acronym_id=-1).agenda_file()
        try:
            f = open(plenaryw_agenda_file)
            plenaryw_agenda = f.read()
            f.close()
        except IOError:
            plenaryw_agenda = "THE AGENDA HAS NOT BEEN UPLOADED YET"
    except WgMeetingSession.DoesNotExist:
        plenaryw_agenda = "THE IETF Operations and Administration Plenary has not been secheduled"
    # Due to a bug in Django@0.96 we can't use foreign key lookup in
    # order_by(), see http://code.djangoproject.com/ticket/2076.  Changeset
    # [133] is broken because it requires a patched Django to run.  Work
    # around this instead.  Later: FIXME (revert to the straightforward code
    # when this bug has been fixed in the Django release we're running.)
    queryset_list_ads = list(IESGHistory.objects.filter(meeting=meeting_num))
    queryset_list_ads.sort(key=(lambda item: item.area.area_acronym.acronym))
    return object_list(request,queryset=queryset_list, template_name=template_file,allow_empty=True, extra_context={'queryset_list_pre_session':queryset_list_pre_session, 'meeting_info':meeting_info, 'meeting_num':meeting_num, 'nonsession_info':nonsession_info, 'meetingvenue_info':meetingvenue_info, 'plenaryw_agenda':plenaryw_agenda, 'plenaryt_agenda':plenaryt_agenda, 'qs_ads':queryset_list_ads,'last_update_info':last_update_info})

