from django.conf.urls.defaults import *
from ietf.iesg.models import TelechatMinutes


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

urlpatterns = patterns('django.views.generic.date_based',
	(r'^telechat/$', 'archive_index', telechat_archive),
	(r'^telechat/(?P<year>\d{4})/$', 'archive_year', telechat_archive),
	(r'^telechat/(?P<year>\d{4})/(?P<month>[a-z]{3})/$', 'archive_month', telechat_archive),
)

urlpatterns += patterns('django.views.generic.list_detail',
	(r'^telechat/detail/(?P<object_id>\d+)/$', 'object_detail', { 'queryset': queryset }),
)
