from django.conf.urls.defaults import patterns, url

urlpatterns = patterns('',
    url(r'^discrepancies/$', 'ietf.sync.views.discrepancies'),
    url(r'^(?P<org>\w+)/notify/(?P<notification>\w+)/$', 'ietf.sync.views.notify'),
    url(r'^rfceditor/undo/', 'ietf.sync.views.rfceditor_undo')
)

