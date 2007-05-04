from django.conf.urls.defaults import *
from ietf.ipr import models, views

urlpatterns = patterns('',
     (r'^$', views.showlist),
     (r'^about/?$', views.default),
     (r'^ipr-(?P<ipr_id>\d+)/$', views.show),
     (r'^update/$', views.updatelist),
     (r'^update/(?P<ipr_id>\d+)/$', views.update),
     (r'^new-(?P<type>(specific|generic|thirdpty))/$', views.new),
)

queryset = models.IprDetail.objects.all()
archive = {'queryset':queryset, 'date_field': 'submitted_date', 'allow_empty':True }

urlpatterns += patterns('django.views.generic.date_based',
	(r'^(?P<year>\d{4})/$', 'archive_year', archive),
	(r'^(?P<year>\d{4})/(?P<month>[a-z]{3})/$', 'archive_month', archive),
)


