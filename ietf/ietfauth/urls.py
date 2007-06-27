# Copyright The IETF Trust 2007, All Rights Reserved

from django.conf.urls.defaults import patterns
from ietf.my.views import my

urlpatterns = patterns('django.contrib.auth.views',
	(r'^login/$', 'login'),
	# need to provide templates for logout, password_change,
	#  password_change_done
	# right now they use the admin templates, which are not
	# really appropriate.
	(r'^logout/$', 'logout'),
	(r'^password_change/$', 'password_change'),
	(r'^password_change/done/$', 'password_change_done'),
	# Built-in password reset changes before validation
	# so we want to implement a scheme similar to henrik's
	# loginmgr.
	#(r'^password_reset/$', 'password_reset'),
	#(r'^password_reset/done/$', 'password_reset_done'),
)
urlpatterns += patterns('',
	(r'^profile/$', my)
)
