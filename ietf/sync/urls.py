from django.conf.urls.defaults import patterns, url

urlpatterns = patterns('',
    url(r'^discrepancies/$', 'ietf.sync.views.discrepancies'),
    url(r'^iana/update/$', 'ietf.sync.views.update_iana'),
    url(r'^rfc-editor/update/$', 'ietf.sync.views.update_rfc_editor'),
)

