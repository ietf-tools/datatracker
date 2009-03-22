# Copyright The IETF Trust 2007, 2009, All Rights Reserved

from django.conf.urls.defaults import patterns
from ietf.ietfauth import views
from ietf.my.views import my

urlpatterns = patterns('django.contrib.auth.views',
	(r'^login/$', 'login'),
	(r'^logout/$', 'logout'),
	(r'^password_change/$', 'password_change'),
	(r'^password_change/done/$', 'password_change_done'),
)
urlpatterns += patterns('',
        (r'^$', 'django.views.generic.simple.direct_to_template', {'template': 'registration/account_info.html'}),
	(r'^request/$', views.password_request),
	(r'^return/$', views.password_return),
	(r'^return/(?P<action>\w+)/$', 'django.views.generic.simple.direct_to_template', {'template': 'registration/action_done.html'}),
	(r'^profile/$', my)
)
