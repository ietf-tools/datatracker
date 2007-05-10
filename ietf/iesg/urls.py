from django.conf.urls.defaults import *
from ietf.iesg.models import TelechatMinutes
from ietf.idtracker.models import BallotInfo, IDInternal, InternetDraft
import datetime

date_threshold = datetime.datetime.now().date() - datetime.timedelta(days=185)

#urlpatterns = patterns('django.views.generic.list_detail',
#     (r'^lastcall/$', 'object_list', {
#	     'queryset': InternetDraft.objects.all() }),
#)

queryset = TelechatMinutes.objects.all()
telechat_detail = {
    'queryset': queryset,
    'date_field': 'telechat_date',
}
telechat_archive = dict(telechat_detail, allow_empty=True)

queryset_ann = BallotInfo.objects.all()

queryset_list = InternetDraft.objects.filter(b_approve_date__gte = date_threshold, intended_status__in=[1,2,6,7],idinternal__via_rfc_editor=0).order_by("-b_approve_date")

queryset_list_doc = InternetDraft.objects.filter(b_approve_date__gte = date_threshold, intended_status__in=[3,5],idinternal__via_rfc_editor=0).order_by("-b_approve_date")

queryset_list_old = InternetDraft.objects.filter(b_approve_date__lt = date_threshold, b_approve_date__gte = '1995-1-1', intended_status__in=[1,2,6,7]).order_by("-b_approve_date")

queryset_list_old_doc = InternetDraft.objects.filter(b_approve_date__lt = date_threshold, b_approve_date__gte = '1995-1-1', intended_status__in=[3,5]).order_by("-b_approve_date")

queryset_list_ind = IDInternal.objects.filter(via_rfc_editor = 1,rfc_flag=0,noproblem=1, dnp=0).select_related().order_by('-internet_drafts.b_approve_date')

queryset_list_ind_dnp = IDInternal.objects.filter(via_rfc_editor = 1,rfc_flag=0,dnp=1).order_by('-dnp_date')

urlpatterns = patterns('django.views.generic.date_based',
	(r'^telechat/$', 'archive_index', telechat_archive),
	(r'^telechat/(?P<year>\d{4})/$', 'archive_year', telechat_archive),
	(r'^telechat/(?P<year>\d{4})/(?P<month>[a-z]{3})/$', 'archive_month', telechat_archive),
)

urlpatterns += patterns('django.views.generic.list_detail',
	(r'^telechat/detail/(?P<object_id>\d+)/$', 'object_detail', { 'queryset': queryset }),
	(r'^ann/detail/(?P<object_id>\d+)/$', 'object_detail', { 'queryset': queryset_ann }),
        (r'^ann/ietf-doc/$', 'object_list', { 'queryset':queryset_list, 'template_name': 'iesg/ietf_doc.html', 'extra_context': { 'object_list_doc':queryset_list_doc, 'is_recent':1 } }),
        (r'^ann/ietf-doc/recent/$', 'object_list', { 'queryset':queryset_list, 'template_name': 'iesg/ietf_doc.html', 'extra_context': { 'object_list_doc':queryset_list_doc, 'is_recent':1 } }),
        (r'^ann/ietf-doc/previous/$', 'object_list', { 'queryset':queryset_list_old, 'template_name': 'iesg/ietf_doc.html', 'extra_context': { 'object_list_doc':queryset_list_old_doc } }),
        (r'^ann/independent/$', 'object_list', { 'queryset':queryset_list_ind, 'template_name': 'iesg/independent_doc.html', 'extra_context': { 'object_list_dnp':queryset_list_ind_dnp } }),
)
