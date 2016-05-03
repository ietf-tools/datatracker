import datetime

from django.template.loader import render_to_string

from ietf.meeting.models import Meeting
from ietf.doc.models import DocEvent, Document
from ietf.secr.proceedings.proc_utils import get_progress_stats

def report_id_activity(start,end):

    # get previous meeting
    meeting = Meeting.objects.filter(date__lt=datetime.datetime.now(),type='ietf').order_by('-date')[0]
    syear,smonth,sday = start.split('-')
    eyear,emonth,eday = end.split('-')
    sdate = datetime.datetime(int(syear),int(smonth),int(sday))
    edate = datetime.datetime(int(eyear),int(emonth),int(eday))
    
    #queryset = Document.objects.filter(type='draft').annotate(start_date=Min('docevent__time'))
    new_docs = Document.objects.filter(type='draft').filter(docevent__type='new_revision',
                                                            docevent__newrevisiondocevent__rev='00',
                                                            docevent__time__gte=sdate,
                                                            docevent__time__lte=edate)
    new = new_docs.count()
    updated = 0
    updated_more = 0
    for d in new_docs:
        updates = d.docevent_set.filter(type='new_revision',time__gte=sdate,time__lte=edate).count()
        if updates > 1:
            updated += 1
        if updates > 2:
            updated_more +=1
    
    # calculate total documents updated, not counting new, rev=00
    result = set()
    events = DocEvent.objects.filter(doc__type='draft',time__gte=sdate,time__lte=edate)
    for e in events.filter(type='new_revision').exclude(newrevisiondocevent__rev='00'):
        result.add(e.doc)
    total_updated = len(result)
    
    # calculate sent last call
    last_call = events.filter(type='sent_last_call').count()
    
    # calculate approved
    approved = events.filter(type='iesg_approved').count()
    
    # get 4 weeks
    monday = Meeting.get_ietf_monday()
    cutoff = monday + datetime.timedelta(days=3)
    ff1_date = cutoff - datetime.timedelta(days=28)
    #ff2_date = cutoff - datetime.timedelta(days=21)
    #ff3_date = cutoff - datetime.timedelta(days=14)
    #ff4_date = cutoff - datetime.timedelta(days=7)
    
    ff_docs = Document.objects.filter(type='draft').filter(docevent__type='new_revision',
                                                           docevent__newrevisiondocevent__rev='00',
                                                           docevent__time__gte=ff1_date,
                                                           docevent__time__lte=cutoff)
    ff_new_count = ff_docs.count()
    ff_new_percent = format(ff_new_count / float(new),'.0%')
    
    # calculate total documents updated in final four weeks, not counting new, rev=00
    result = set()
    events = DocEvent.objects.filter(doc__type='draft',time__gte=ff1_date,time__lte=cutoff)
    for e in events.filter(type='new_revision').exclude(newrevisiondocevent__rev='00'):
        result.add(e.doc)
    ff_update_count = len(result)
    ff_update_percent = format(ff_update_count / float(total_updated),'.0%')
    
    #aug_docs = augment_with_start_time(new_docs)
    '''
    ff1_new = aug_docs.filter(start_date__gte=ff1_date,start_date__lt=ff2_date)
    ff2_new = aug_docs.filter(start_date__gte=ff2_date,start_date__lt=ff3_date)
    ff3_new = aug_docs.filter(start_date__gte=ff3_date,start_date__lt=ff4_date)
    ff4_new = aug_docs.filter(start_date__gte=ff4_date,start_date__lt=edate)
    ff_new_iD = ff1_new + ff2_new + ff3_new + ff4_new
    '''
    context = {'meeting':meeting,
               'new':new,
               'updated':updated,
               'updated_more':updated_more,
               'total_updated':total_updated,
               'last_call':last_call,
               'approved':approved,
               'ff_new_count':ff_new_count,
               'ff_new_percent':ff_new_percent,
               'ff_update_count':ff_update_count,
               'ff_update_percent':ff_update_percent}
    
    report = render_to_string('drafts/report_id_activity.txt', context)
    
    return report
    
def report_progress_report(start_date,end_date):
    syear,smonth,sday = start_date.split('-')
    eyear,emonth,eday = end_date.split('-')
    sdate = datetime.datetime(int(syear),int(smonth),int(sday))
    edate = datetime.datetime(int(eyear),int(emonth),int(eday))
    
    context = get_progress_stats(sdate,edate)
    
    report = render_to_string('drafts/report_progress_report.txt', context)
    
    return report