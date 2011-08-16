from django.conf.urls.defaults import patterns, url


urlpatterns = patterns('ietf.community.views',
    url(r'^personal/(?P<username>[\w.@+-]+)/$', 'manage_personal_list', name='manage_personal_list'),
    url(r'^group/(?P<acronym>[\w.@+-]+)/$', 'manage_group_list', name='manage_group_list'),
)
