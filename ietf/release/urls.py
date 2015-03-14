from django.conf.urls import patterns

urlpatterns = patterns('',
    (r'^$',                 'ietf.release.views.release'),
    (r'^(?P<version>.+)/$', 'ietf.release.views.release'),
    (r'^coverage/code/$',   'ietf.release.views.code_coverage')
)

