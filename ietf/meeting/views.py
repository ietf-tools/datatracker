# Copyright The IETF Trust 2007, All Rights Reserved

#import models
import datetime
import os
import re
import tarfile

from tempfile import mkstemp

from django.shortcuts import render_to_response, get_object_or_404
from ietf.idtracker.models import IETFWG, IRTF, Area
from django.views.generic.list_detail import object_list
from django.http import HttpResponseRedirect, HttpResponse, Http404
from django.core.urlresolvers import reverse
from django.db.models import Q
from django.template import RequestContext
from django.template.loader import render_to_string
from django.conf import settings
from django.utils.decorators import decorator_from_middleware
from django.middleware.gzip import GZipMiddleware
from django.db.models import Count, Max
from ietf.idtracker.models import InternetDraft
from ietf.idrfc.idrfc_wrapper import IdWrapper
from ietf.utils.pipe import pipe

from ietf.proceedings.models import Meeting, MeetingTime, WgMeetingSession, MeetingVenue, IESGHistory, Proceeding, Switches, WgProceedingsActivities, SessionConflict


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
    if settings.USE_DB_REDESIGN_PROXY_CLASSES:
        queryset_list = []
        queryset_irtf = []
        queryset_interim = []   # currently ignored, have no way of handling interim here
        queryset_training = []
        for item in WgMeetingSession.objects.filter(meeting=meeting_num):
            if item.type_id in ("session", "plenary"):
                if item.session and item.session.group and item.session.group.type_id == "rg":
                    queryset_irtf.append(item)
                else:
                    queryset_list.append(item)
            else:
                if item.type_id == "other" and item.slides():
                    queryset_training.append(item)
        from redesign.doc.models import Document
        cache_version = Document.objects.filter(timeslot__meeting__number=meeting_num).aggregate(Max('time'))["time__max"]
    else:
        queryset_list = WgMeetingSession.objects.filter(Q(meeting=meeting_num, group_acronym_id__gte = -2, status__id=4), Q(irtf__isnull=True) | Q(irtf=0))
        queryset_irtf = WgMeetingSession.objects.filter(meeting=meeting_num, group_acronym_id__gte = -2, status__id=4, irtf__gt=0)
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
    return render_to_response("meeting/list.html",
                              {'meeting_num':meeting_num,'object_list': queryset_list, 'irtf_list':queryset_irtf, 'interim_list':queryset_interim, 'training_list':queryset_training, 'begin_date':begin_date, 'cut_off_date':cut_off_date, 'cor_cut_off_date':cor_cut_off_date,'sub_began':sub_began,'cache_version':cache_version},
                              context_instance=RequestContext(request))

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

def agenda_infoREDESIGN(num=None):
    try:
        if num != None:
            meeting = Meeting.objects.get(number=num)
        else:
            meeting = Meeting.objects.all().order_by('-date')[:1].get()
    except Meeting.DoesNotExist:
        raise Http404("No meeting information for meeting %s available" % num)

    # now go through the timeslots, only keeping those that are
    # sessions/plenary/training and don't occur at the same time
    timeslots = []
    time_seen = set()
    for t in MeetingTime.objects.filter(meeting=meeting, type__in=("session", "plenary", "other")).order_by("time").select_related():
        if not t.time in time_seen:
            time_seen.add(t.time)
            timeslots.append(t)

    update = Switches().from_object(meeting)
    venue = meeting.meeting_venue

    ads = []
    meeting_time = datetime.datetime.combine(meeting.date, datetime.time(0, 0, 0))
    from redesign.group.models import Group
    from ietf.utils.history import find_history_active_at
    for g in Group.objects.filter(type="area").order_by("acronym"):
        history = find_history_active_at(g, meeting_time)
        if history:
            if history.state_id == "active":
                ads.extend(IESGHistory().from_role(x, meeting_time) for x in history.rolehistory_set.filter(name="ad"))
        else:
            if g.state_id == "active":
                ads.extend(IESGHistory().from_role(x, meeting_time) for x in g.role_set.filter(name="ad"))
    
    from redesign.doc.models import Document
    plenary_agendas = Document.objects.filter(timeslot__meeting=meeting, timeslot__type="plenary", type="agenda").distinct()
    plenaryw_agenda = plenaryt_agenda = "The Plenary has not been scheduled"
    for agenda in plenary_agendas:
        # we use external_url at the moment, should probably regularize
        # the filenames to match the document name instead
        path = os.path.join(settings.AGENDA_PATH, meeting.number, "agenda", agenda.external_url)
        try:
            f = open(path)
            s = f.read()
            f.close()
        except IOError:
             s = "THE AGENDA HAS NOT BEEN UPLOADED YET"
        
        if "plenaryw" in agenda.name:
            plenaryw_agenda = s
        elif "plenaryt" in agenda.name:
            plenaryt_agenda = s
                               
    return timeslots, update, meeting, venue, ads, plenaryw_agenda, plenaryt_agenda

if settings.USE_DB_REDESIGN_PROXY_CLASSES:
    agenda_info = agenda_infoREDESIGN

@decorator_from_middleware(GZipMiddleware)
def html_agenda(request, num=None):
    timeslots, update, meeting, venue, ads, plenaryw_agenda, plenaryt_agenda = agenda_info(num)

    groups_meeting = [];
    for slot in timeslots:
        for session in slot.sessions():
            groups_meeting.append(session.acronym())
    groups_meeting = set(groups_meeting);

    wgs = IETFWG.objects.filter(status=IETFWG.ACTIVE).filter(group_acronym__acronym__in = groups_meeting).order_by('group_acronym__acronym')
    rgs = IRTF.objects.all().filter(acronym__in = groups_meeting).order_by('acronym')
    areas = Area.objects.filter(status=Area.ACTIVE).order_by('area_acronym__acronym')

    if  settings.SERVER_MODE != 'production' and '_testiphone' in request.REQUEST:
        user_agent = "iPhone"
    elif 'user_agent' in request.REQUEST:
        user_agent = request.REQUEST['user_agent']
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
                "plenaryw_agenda":plenaryw_agenda, "plenaryt_agenda":plenaryt_agenda, 
                "wg_list" : wgs, "rg_list" : rgs, "area_list" : areas},
            context_instance=RequestContext(request))


def text_agenda(request, num=None):
    timeslots, update, meeting, venue, ads, plenaryw_agenda, plenaryt_agenda = agenda_info(num)
    plenaryw_agenda = "   "+plenaryw_agenda.strip().replace("\n", "\n   ")
    plenaryt_agenda = "   "+plenaryt_agenda.strip().replace("\n", "\n   ")
    return HttpResponse(render_to_string("meeting/agenda.txt",
        {"timeslots":timeslots, "update":update, "meeting":meeting, "venue":venue, "ads":ads,
            "plenaryw_agenda":plenaryw_agenda, "plenaryt_agenda":plenaryt_agenda, },
        RequestContext(request)), mimetype="text/plain")
    
def session_agenda(request, num, session, ext=None):
    if ext:
        extensions = [ ext.lstrip(".") ]
    else:
        extensions = ["html", "htm", "txt", "HTML", "HTM", "TXT", ]
    for wg in [session, session.upper(), session.lower()]:
        for e in extensions:
            path = settings.AGENDA_PATH_PATTERN % {"meeting":num, "wg":wg, "ext":e}
            if os.path.exists(path):
                file = open(path)
                text = file.read()
                file.close()
                if e.lower() == "txt":
                    return HttpResponse(text, mimetype="text/plain")
                elif e.lower() == "pdf":
                    return HttpResponse(text, mimetype="application/pdf")
                else:
                    return HttpResponse(text)
    if ext:
        raise Http404("No %s agenda for the %s session of IETF %s is available" % (ext, session, num))
    else:
        raise Http404("No agenda for the %s session of IETF %s is available" % (session, num))

def convert_to_pdf(doc_name):
    import subprocess
    inpath = os.path.join(settings.IDSUBMIT_REPOSITORY_PATH, doc_name + ".txt")
    outpath = os.path.join(settings.INTERNET_DRAFT_PDF_PATH, doc_name + ".pdf")

    try:
        infile = open(inpath, "r")
    except Exception, e:
        return

    t,tempname = mkstemp()
    tempfile = open(tempname, "w")

    pageend = 0;
    newpage = 0;
    formfeed = 0;
    for line in infile:
        line = re.sub("\r","",line)
        line = re.sub("[ \t]+$","",line)
        if re.search("\[?[Pp]age [0-9ivx]+\]?[ \t]*$",line):
            pageend=1
            tempfile.write(line)
            continue
        if re.search("^[ \t]*\f",line):
            formfeed=1
            tempfile.write(line)
            continue
        if re.search("^ *INTERNET.DRAFT.+[0-9]+ *$",line) or re.search("^ *Internet.Draft.+[0-9]+ *$",line) or re.search("^draft-[-a-z0-9_.]+.*[0-9][0-9][0-9][0-9]$",line) or re.search("^RFC.+[0-9]+$",line):
            newpage=1
        if re.search("^[ \t]*$",line) and pageend and not newpage:
            continue
        if pageend and newpage and not formfeed:
            tempfile.write("\f")
        pageend=0
        formfeed=0
        newpage=0
        tempfile.write(line)

    infile.close()
    tempfile.close()
    t,psname = mkstemp()
    pipe("enscript --margins 76::76: -B -q -p "+psname + " " +tempname)
    os.unlink(tempname)
    pipe("ps2pdf "+psname+" "+outpath)
    os.unlink(psname)


def session_draft_list(num, session):
    extensions = ["html", "htm", "txt", "HTML", "HTM", "TXT", ]
    result = []
    found = False
    for wg in [session, session.upper(), session.lower()]:
        for e in extensions:
            path = settings.AGENDA_PATH_PATTERN % {"meeting":num, "wg":wg, "ext":e}
            if os.path.exists(path):
                file = open(path)
                agenda = file.read()
                file.close()
                found = True
                break
        if found:
           break
    else:
      raise Http404("No agenda for the %s session of IETF %s is available" % (session, num))
    
    drafts = set(re.findall('(draft-[-a-z0-9]*)',agenda))

    for draft in drafts:
        try:
            if (re.search('-[0-9]{2}$',draft)):
                doc_name = draft
            else:
                id = InternetDraft.objects.get(filename=draft)
                doc = IdWrapper(id)
                doc_name = draft + "-" + id.revision
            result.append(doc_name)
        except InternetDraft.DoesNotExist:
            pass
    return sorted(list(set(result)))


def session_draft_tarfile(request, num, session):
    drafts = session_draft_list(num, session);

    response = HttpResponse(mimetype='application/octet-stream')
    response['Content-Disposition'] = 'attachment; filename=%s-drafts.tgz'%(session)
    tarstream = tarfile.open('','w:gz',response)
    mfh, mfn = mkstemp()
    manifest = open(mfn, "w")

    for doc_name in drafts:
        pdf_path = os.path.join(settings.INTERNET_DRAFT_PDF_PATH, doc_name + ".pdf")

        if (not os.path.exists(pdf_path)):
            convert_to_pdf(doc_name)

        if os.path.exists(pdf_path):
            try:
                tarstream.add(pdf_path, str(doc_name + ".pdf"))
                manifest.write("Included:  "+pdf_path+"\n")
            except Exception, e:
                manifest.write(("Failed (%s): "%e)+pdf_path+"\n")
        else:
            manifest.write("Not found: "+pdf_path+"\n")

    manifest.close()
    tarstream.add(mfn, "manifest.txt")
    tarstream.close()
    os.unlink(mfn)
    return response    

def pdf_pages(file):
    try:
        infile = open(file, "r")
    except Exception, e:
        return 0
    for line in infile:
        m = re.match('\] /Count ([0-9]+)',line)
        if m:
            return int(m.group(1))
    return 0


def session_draft_pdf(request, num, session):
    drafts = session_draft_list(num, session);
    curr_page = 1
    pmh, pmn = mkstemp()
    pdfmarks = open(pmn, "w")
    pdf_list = ""

    for draft in drafts:
        pdf_path = os.path.join(settings.INTERNET_DRAFT_PDF_PATH, draft + ".pdf")
        if (not os.path.exists(pdf_path)):
            convert_to_pdf(draft)

        if (os.path.exists(pdf_path)):
            pages = pdf_pages(pdf_path)
            pdfmarks.write("[/Page "+str(curr_page)+" /View [/XYZ 0 792 1.0] /Title (" + draft + ") /OUT pdfmark\n")
            pdf_list = pdf_list + " " + pdf_path
            curr_page = curr_page + pages

    pdfmarks.close()
    pdfh, pdfn = mkstemp()
    pipe("gs -dBATCH -dNOPAUSE -q -sDEVICE=pdfwrite -sOutputFile=" + pdfn + " " + pdf_list + " " + pmn)

    pdf = open(pdfn,"r")
    pdf_contents = pdf.read()
    pdf.close()

    os.unlink(pmn)
    os.unlink(pdfn)
    return HttpResponse(pdf_contents, mimetype="application/pdf")

def week_view(request, num=None):
    timeslots, update, meeting, venue, ads, plenaryw_agenda, plenaryt_agenda = agenda_info(num)
    wgs = IETFWG.objects.filter(status=IETFWG.ACTIVE).order_by('group_acronym__acronym')
    rgs = IRTF.objects.all().order_by('acronym')
    areas = Area.objects.filter(status=Area.ACTIVE).order_by('area_acronym__acronym')
    conflicts = SessionConflict.objects.filter(meeting_num=meeting.meeting_num)
    template = "meeting/week-view.html"
    return render_to_response(template,
            {"timeslots":timeslots, "update":update, "meeting":meeting, 
             "venue":venue, "ads":ads, "plenaryw_agenda":plenaryw_agenda,
             "plenaryt_agenda":plenaryt_agenda, "wg_list" : wgs, 
             "rg_list" : rgs, "area_list" : areas, "conflicts":conflicts},
             context_instance=RequestContext(request))

def ical_agenda(request, num=None):
    timeslots, update, meeting, venue, ads, plenaryw_agenda, plenaryt_agenda = agenda_info(num)
    wgs = IETFWG.objects.filter(status=IETFWG.ACTIVE).order_by('group_acronym__acronym')
    rgs = IRTF.objects.all().order_by('acronym')
    areas = Area.objects.filter(status=Area.ACTIVE).order_by('area_acronym__acronym')
    q = request.META.get('QUERY_STRING','') or ""
    filter = q.lower().split(',');
    include = set(filter)
    now = datetime.datetime.utcnow()

    for slot in timeslots:
        for session in slot.sessions():
            if session.area() == '' or session.area().find('plenary') > 0 or (session.area().lower() in include):
                filter.append(session.acronym())

    return HttpResponse(render_to_string("meeting/agendaREDESIGN.ics" if settings.USE_DB_REDESIGN_PROXY_CLASSES else "meeting/agenda.ics",
        {"filter":set(filter), "timeslots":timeslots, "update":update, "meeting":meeting, "venue":venue, "ads":ads,
            "plenaryw_agenda":plenaryw_agenda, "plenaryt_agenda":plenaryt_agenda, 
            "now":now},
        RequestContext(request)), mimetype="text/calendar")

def csv_agenda(request, num=None):
    timeslots, update, meeting, venue, ads, plenaryw_agenda, plenaryt_agenda = agenda_info(num)
    wgs = IETFWG.objects.filter(status=IETFWG.ACTIVE).order_by('group_acronym__acronym')
    rgs = IRTF.objects.all().order_by('acronym')
    areas = Area.objects.filter(status=Area.ACTIVE).order_by('area_acronym__acronym')

    return HttpResponse(render_to_string("meeting/agenda.csv",
        {"timeslots":timeslots, "update":update, "meeting":meeting, "venue":venue, "ads":ads,
         "plenaryw_agenda":plenaryw_agenda, "plenaryt_agenda":plenaryt_agenda, },
        RequestContext(request)), mimetype="text/csv")

def meeting_requests(request, num=None) :
    timeslots, update, meeting, venue, ads, plenaryw_agenda, plenaryt_agenda = agenda_info(num)
    sessions = WgMeetingSession.objects.filter(meeting=meeting)

    wgs = IETFWG.objects.filter(status=IETFWG.ACTIVE).order_by("group_acronym__acronym");
    rgs = IRTF.objects.all().order_by('acronym')
    areas = Area.objects.filter(status=Area.ACTIVE).order_by('area_acronym__acronym')
    return render_to_response("meeting/requests.html",
        {"sessions": sessions, "timeslots":timeslots, "update":update, "meeting":meeting, "venue":venue, "ads":ads, "wgs":wgs,
         "plenaryw_agenda":plenaryw_agenda, "plenaryt_agenda":plenaryt_agenda, "areas":areas},
        context_instance=RequestContext(request))

def conflict_digraph(request, num=None) :
    timeslots, update, meeting, venue, ads, plenaryw_agenda, plenaryt_agenda = agenda_info(num)
    sessions = WgMeetingSession.objects.filter(meeting=meeting)
    return render_to_response("meeting/digraph.html",
        {"sessions":sessions},
        context_instance=RequestContext(request), mimetype="text/plain")
