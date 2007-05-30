from django.conf.urls.defaults import *
from ietf.meeting import models, views

urlpatterns = patterns('',
     (r'^$', views.showlist),
     
	 (r'^(?P<meeting_num>\d+)/$', views.show),
	(r'^(?P<meeting_num>\d+)/agenda.(?P<html_or_txt>\S+)$', views.show_html_agenda),
	(r'^(?P<meeting_num>\d+)/materials.html$', views.show_html_materials),


#     (r'^update/(?P<meeting_id>\d+)/$', views.update),
#     (r'^new-(?P<type>(specific|generic|thirdpty))/$', views.new),
)

#queryset = models.IprDetail.objects.all()
#archive = {'queryset':queryset, 'date_field': 'submitted_date', 'allow_empty':True }

#urlpatterns += patterns('django.views.generic.date_based',
#	(r'^(?P<year>\d{4})/$', 'archive_year', archive),
#	(r'^(?P<year>\d{4})/(?P<month>[a-z]{3})/$', 'archive_month', archive),
#)


