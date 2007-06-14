from django.conf.urls.defaults import patterns
from ietf.ipr import models, views

urlpatterns = patterns('',
     (r'^$', views.showlist),
     (r'^about/?$', views.default),
     (r'^ipr-(?P<ipr_id>\d+)/$', views.show),
     (r'^update/$', views.updatelist),
     (r'^update/(?P<ipr_id>\d+)/$', views.update),
     (r'^new-(?P<type>(specific|generic|third-party))/$', views.new),
     (r'^search/$', views.search),     
     (r'^search/\?((option=(?P<option>[^&]*)|.*search=(?P<search>[^&]*)|submit=(?P<submit>[^&]*))&?)+/$', views.search),
)

queryset = models.IprDetail.objects.all()
archive = {'queryset':queryset, 'date_field': 'submitted_date', 'allow_empty':True }

urlpatterns += patterns('django.views.generic.date_based',
	(r'^by-date/$', 'archive_index', archive),
	(r'^(?P<year>\d{4})/$', 'archive_year', archive),
	(r'^(?P<year>\d{4})/(?P<month>[a-z]{3})/$', 'archive_month', archive),
)


