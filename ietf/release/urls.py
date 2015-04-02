from django.conf.urls import patterns

urlpatterns = patterns('',
    (r'^$',  'ietf.release.views.release'),
    (r'^(?P<version>[0-9.]+.*)/$',  'ietf.release.views.release'),
)

