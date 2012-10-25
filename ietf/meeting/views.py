# Copyright The IETF Trust 2007, All Rights Reserved

#import models
import datetime
import os
import re
import tarfile

from tempfile import mkstemp

from django.shortcuts import render_to_response, get_object_or_404
from ietf.idtracker.models import IETFWG, IRTF, Area
from django.http import HttpResponseRedirect, HttpResponse, Http404
from django.core.urlresolvers import reverse
from django.db.models import Q
from django.template import RequestContext
from django.template.loader import render_to_string
from django.conf import settings
from django.utils.decorators import decorator_from_middleware
from django.middleware.gzip import GZipMiddleware
from django.db.models import Max

import debug

from ietf.idtracker.models import InternetDraft
from ietf.utils.pipe import pipe
from ietf.utils.history import find_history_active_at
from ietf.doc.models import Document, State

# Old model -- needs to be removed
from ietf.proceedings.models import Meeting as OldMeeting, MeetingTime, WgMeetingSession, MeetingVenue, IESGHistory, Proceeding, Switches

# New models
from ietf.meeting.models import Meeting, TimeSlot, Session
from ietf.group.models import Group


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
    sessions  = Session.objects.filter(meeting__number=meeting_num, timeslot__isnull=False)
    plenaries = sessions.filter(name__icontains='plenary')
    ietf      = sessions.filter(group__parent__type__slug = 'area').exclude(group__acronym='edu')
    irtf      = sessions.filter(group__parent__acronym = 'irtf')
    training  = sessions.filter(group__acronym='edu')

    cache_version = Document.objects.filter(session__meeting__number=meeting_num).aggregate(Max('time'))["time__max"]
    #
    return render_to_response("meeting/list.html",
                              {'meeting_num':meeting_num,
                               'plenaries': plenaries, 'ietf':ietf, 'training':training, 'irtf': irtf,
                               'begin_date':begin_date, 'cut_off_date':cut_off_date,
                               'cor_cut_off_date':cor_cut_off_date,'sub_began':sub_began,
                               'cache_version':cache_version},
                              context_instance=RequestContext(request))

def current_materials(request):
    meeting = OldMeeting.objects.exclude(number__startswith='interim-').order_by('-meeting_num')[0]
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
            meeting= OldMeeting.objects.get(meeting_num=n)
            venue  = MeetingVenue.objects.get(meeting_num=n)
            break
        except (MeetingTime.DoesNotExist, Switches.DoesNotExist, OldMeeting.DoesNotExist, MeetingVenue.DoesNotExist):
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
            meeting = OldMeeting.objects.get(number=num)
        else:
            meeting = OldMeeting.objects.all().order_by('-date')[:1].get()
    except OldMeeting.DoesNotExist:
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
    for g in Group.objects.filter(type="area").order_by("acronym"):
        history = find_history_active_at(g, meeting_time)
        if history:
            if history.state_id == "active":
                ads.extend(IESGHistory().from_role(x, meeting_time) for x in history.rolehistory_set.filter(name="ad").select_related())
        else:
            if g.state_id == "active":
                ads.extend(IESGHistory().from_role(x, meeting_time) for x in g.role_set.filter(name="ad").select_related('group', 'person'))
    
    active_agenda = State.objects.get(type='agenda', slug='active')
    plenary_agendas = Document.objects.filter(session__meeting=meeting, session__timeslot__type="plenary", type="agenda", ).distinct()
    plenaryw_agenda = plenaryt_agenda = "The Plenary has not been scheduled"
    for agenda in plenary_agendas:
        if active_agenda in agenda.states.all():
            # we use external_url at the moment, should probably regularize
            # the filenames to match the document name instead
            path = os.path.join(settings.AGENDA_PATH, meeting.number, "agenda", agenda.external_url)
            try:
                f = open(path)
                s = f.read()
                f.close()
            except IOError:
                 s = "THE AGENDA HAS NOT BEEN UPLOADED YET"

            if "tech" in agenda.name.lower():
                plenaryt_agenda = s
            else:
                plenaryw_agenda = s

    return timeslots, update, meeting, venue, ads, plenaryw_agenda, plenaryt_agenda

if settings.USE_DB_REDESIGN_PROXY_CLASSES:
    agenda_info = agenda_infoREDESIGN

@decorator_from_middleware(GZipMiddleware)
def html_agenda(request, num=None):
    if  settings.SERVER_MODE != 'production' and '_testiphone' in request.REQUEST:
        user_agent = "iPhone"
    elif 'user_agent' in request.REQUEST:
        user_agent = request.REQUEST['user_agent']
    elif 'HTTP_USER_AGENT' in request.META:
        user_agent = request.META["HTTP_USER_AGENT"]
    else:
        user_agent = ""
    if "iPhone" in user_agent:
        return iphone_agenda(request, num)

    meeting = get_meeting(num)
    timeslots = TimeSlot.objects.filter(Q(meeting__id = meeting.id)).order_by('time','name')
    modified = timeslots.aggregate(Max('modified'))['modified__max']

    area_list = timeslots.filter(type = 'Session', session__group__parent__isnull = False).order_by('session__group__parent__acronym').distinct('session__group__parent__acronym').values_list('session__group__parent__acronym',flat=True)

    wg_name_list = timeslots.filter(type = 'Session', session__group__isnull = False, session__group__parent__isnull = False).order_by('session__group__acronym').distinct('session__group').values_list('session__group__acronym',flat=True)

    wg_list = Group.objects.filter(acronym__in = set(wg_name_list)).order_by('parent__acronym','acronym')

    return HttpResponse(render_to_string("meeting/agenda.html",
        {"timeslots":timeslots, "modified": modified, "meeting":meeting,
         "area_list": area_list, "wg_list": wg_list ,
         "show_inline": set(["txt","htm","html"]) },
        RequestContext(request)), mimetype="text/html")

def iphone_agenda(request, num):
    timeslots, update, meeting, venue, ads, plenaryw_agenda, plenaryt_agenda = agenda_info(num)

    groups_meeting = [];
    for slot in timeslots:
        for session in slot.sessions():
            groups_meeting.append(session.acronym())
    groups_meeting = set(groups_meeting);

    wgs = IETFWG.objects.filter(status=IETFWG.ACTIVE).filter(group_acronym__acronym__in = groups_meeting).order_by('group_acronym__acronym')
    rgs = IRTF.objects.all().filter(acronym__in = groups_meeting).order_by('acronym')
    areas = Area.objects.filter(status=Area.ACTIVE).order_by('area_acronym__acronym')
    template = "meeting/m_agenda.html"
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
    
def session_agenda(request, num, session):
    d = Document.objects.filter(type="agenda", session__meeting__number=num)
    if session == "plenaryt":
        d = d.filter(session__name__icontains="technical", session__timeslot__type="plenary")
    elif session == "plenaryw":
        d = d.filter(session__name__icontains="admin", session__timeslot__type="plenary")
    else:
        d = d.filter(session__group__acronym=session)

    if d:
        agenda = d[0]
        content = read_agenda_file(num, agenda)
        _, ext = os.path.splitext(agenda.external_url)
        ext = ext.lstrip(".").lower()

        if ext == "txt":
            return HttpResponse(content, mimetype="text/plain")
        elif ext == "pdf":
            return HttpResponse(content, mimetype="application/pdf")
        else:
            return HttpResponse(content)

    raise Http404("No agenda for the %s session of IETF %s is available" % (session, num))

def convert_to_pdf(doc_name):
    inpath = os.path.join(settings.IDSUBMIT_REPOSITORY_PATH, doc_name + ".txt")
    outpath = os.path.join(settings.INTERNET_DRAFT_PDF_PATH, doc_name + ".pdf")

    try:
        infile = open(inpath, "r")
    except IOError:
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

def read_agenda_file(num, doc):
    # XXXX FIXME: the path fragment in the code below should be moved to
    # settings.py.  The *_PATH settings should be generalized to format()
    # style python format, something like this:
    #  DOC_PATH_FORMAT = { "agenda": "/foo/bar/agenda-{meeting.number}/agenda-{meeting-number}-{doc.group}*", }
    path = os.path.join(settings.AGENDA_PATH, "%s/agenda/%s" % (num, doc.external_url))
    if os.path.exists(path):
        with open(path) as f:
            return f.read()
    else:
        return None

def session_draft_list(num, session):
    #extensions = ["html", "htm", "txt", "HTML", "HTM", "TXT", ]
    result = []
    found = False

    drafts = set()

    for agenda in Document.objects.filter(type="agenda", session__meeting__number=num, session__group__acronym=session):
        content = read_agenda_file(num, agenda)
        if content != None:
            found = True
            drafts.update(re.findall('(draft-[-a-z0-9]*)', content))

    if not found:
        raise Http404("No agenda for the %s group of IETF %s is available" % (session, num))
    
    for draft in drafts:
        try:
            if (re.search('-[0-9]{2}$',draft)):
                doc_name = draft
            else:
                id = InternetDraft.objects.get(filename=draft)
                #doc = IdWrapper(id)
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
    except IOError:
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

def get_meeting(num=None):
    if (num == None):
        meeting = Meeting.objects.filter(type="ietf").order_by("-date")[:1].get()
    else:
        meeting = get_object_or_404(Meeting, number=num)
    return meeting

def week_view(request, num=None):
    meeting = get_meeting(num)
    timeslots = TimeSlot.objects.filter(meeting__id = meeting.id)

    template = "meeting/week-view.html"
    return render_to_response(template,
            {"timeslots":timeslots,"render_types":["Session","Other","Break","Plenary"]}, context_instance=RequestContext(request))

def ical_agenda(request, num=None):
    # The timezone situation here remains tragic, but I've burned
    # hours trying to figure out how to get the information I need
    # in python. I can do this trivially in perl with its Ical module,
    # but the icalendar module in python seems staggeringly less
    # capable. There might be a path to success here, but I'm not
    # completely convinced. So I'm going to spend some time
    # working on more urgent matters for now. -Adam

    meeting = get_meeting(num)

    q = request.META.get('QUERY_STRING','') or ""
    filter = q.lower().split(',');
    include = set(filter)
    include_types = ["Plenary","Other"]
    exclude = []

    # Process the special flags.
    for item in include:
        if item:
            if item[0] == '-':
                exclude.append(item[1:])
            if item[0] == '~':
                include_types.append(item[1:2].upper()+item[2:])

    timeslots = TimeSlot.objects.filter(Q(meeting__id = meeting.id),
        Q(type__name__in = include_types) |
        Q(session__group__acronym__in = filter) |
        Q(session__group__parent__acronym__in = filter)
        )#.exclude(Q(session__group__isnull = False),
        #Q(session__group__acronym__in = exclude) | 
        #Q(session__group__parent__acronym__in = exclude))

    if meeting.time_zone:
        tzfn = os.path.join(settings.TZDATA_ICS_PATH, meeting.time_zone + ".ics")
        tzf = open(tzfn)
        icstext = tzf.read()
        debug.show('icstext[:128]')
        vtimezone = re.search("(?sm)(\nBEGIN:VTIMEZONE.*\nEND:VTIMEZONE\n)", icstext).group(1).strip()
        debug.show('vtimezone[:128]')
        tzf.close()
    else:
        vtimezone = None

    return HttpResponse(render_to_string("meeting/agendaREDESIGN.ics",
        {"timeslots":timeslots, "meeting":meeting, "vtimezone": vtimezone },
        RequestContext(request)), mimetype="text/calendar")

def csv_agenda(request, num=None):
    timeslots, update, meeting, venue, ads, plenaryw_agenda, plenaryt_agenda = agenda_info(num)
    #wgs = IETFWG.objects.filter(status=IETFWG.ACTIVE).order_by('group_acronym__acronym')
    #rgs = IRTF.objects.all().order_by('acronym')
    #areas = Area.objects.filter(status=Area.ACTIVE).order_by('area_acronym__acronym')

    # we should really use the Python csv module or something similar
    # rather than a template file which is one big mess

    return HttpResponse(render_to_string("meeting/agenda.csv",
        {"timeslots":timeslots, "update":update, "meeting":meeting, "venue":venue, "ads":ads,
         "plenaryw_agenda":plenaryw_agenda, "plenaryt_agenda":plenaryt_agenda, },
        RequestContext(request)), mimetype="text/csv")

def meeting_requests(request, num=None) :
    meeting = get_meeting(num)
    sessions = Session.objects.filter(meeting__number=meeting.number,group__parent__isnull = False).exclude(requested_by=0).order_by("group__parent__acronym","status__slug","group__acronym")

    groups_not_meeting = Group.objects.filter(state='Active',type__in=['WG','RG','BOF']).exclude(acronym__in = [session.group.acronym for session in sessions]).order_by("parent__acronym","acronym")

    return render_to_response("meeting/requests.html",
        {"meeting": meeting, "sessions":sessions,
         "groups_not_meeting": groups_not_meeting},
        context_instance=RequestContext(request))
