from django.conf.urls.defaults import patterns, url


urlpatterns = patterns('ietf.registration.views',
    url(r'^$', 'register_view', name='register_view'),
    url(r'^confirm/(?P<username>[\w.@+-]+)/(?P<date>[\d]+)/(?P<realm>[\w]+)/(?P<registration_hash>[a-f0-9]+)/$', 'confirm_register_view', name='confirm_register_view'),
    url(r'^password_recovery/$', 'password_recovery_view', name='password_recovery_view'),
    url(r'^password_recovery/confirm/(?P<username>[\w.@+-]+)/(?P<date>[\d]+)/(?P<realm>[\w]+)/(?P<recovery_hash>[a-f0-9]+)/$', 'confirm_password_recovery', name='confirm_password_recovery'),
    url(r'^ajax/check_username/$', 'ajax_check_username', name='ajax_check_username'),
)
