from django.conf.urls import url

urlpatterns = [
    url(r'^$', 'ietf.secr.drafts.views.search', name='drafts'),
    url(r'^add/$', 'ietf.secr.drafts.views.add', name='drafts_add'),
    url(r'^approvals/$', 'ietf.secr.drafts.views.approvals', name='drafts_approvals'),
    url(r'^dates/$', 'ietf.secr.drafts.views.dates', name='drafts_dates'),
    url(r'^nudge-report/$', 'ietf.secr.drafts.views.nudge_report', name='drafts_nudge_report'),
    url(r'^(?P<id>[A-Za-z0-9._\-\+]+)/$', 'ietf.secr.drafts.views.view', name='drafts_view'),
    url(r'^(?P<id>[A-Za-z0-9._\-\+]+)/abstract/$', 'ietf.secr.drafts.views.abstract', name='drafts_abstract'),
    url(r'^(?P<id>[A-Za-z0-9._\-\+]+)/announce/$', 'ietf.secr.drafts.views.announce', name='drafts_announce'),
    url(r'^(?P<id>[A-Za-z0-9._\-\+]+)/authors/$', 'ietf.secr.drafts.views.authors', name='drafts_authors'),
    url(r'^(?P<id>[A-Za-z0-9._\-\+]+)/author_delete/(?P<oid>\d{1,6})$', 'ietf.secr.drafts.views.author_delete', name='drafts_author_delete'),
    url(r'^(?P<id>[A-Za-z0-9._\-\+]+)/confirm/$', 'ietf.secr.drafts.views.confirm', name='drafts_confirm'),
    url(r'^(?P<id>[A-Za-z0-9._\-\+]+)/edit/$', 'ietf.secr.drafts.views.edit', name='drafts_edit'),
    url(r'^(?P<id>[A-Za-z0-9._\-\+]+)/extend/$', 'ietf.secr.drafts.views.extend', name='drafts_extend'),
    url(r'^(?P<id>[A-Za-z0-9._\-\+]+)/email/$', 'ietf.secr.drafts.views.email', name='drafts_email'),
    url(r'^(?P<id>[A-Za-z0-9._\-\+]+)/makerfc/$', 'ietf.secr.drafts.views.makerfc', name='drafts_makerfc'),
    url(r'^(?P<id>[A-Za-z0-9._\-\+]+)/replace/$', 'ietf.secr.drafts.views.replace', name='drafts_replace'),
    url(r'^(?P<id>[A-Za-z0-9._\-\+]+)/resurrect/$', 'ietf.secr.drafts.views.resurrect', name='drafts_resurrect'),
    url(r'^(?P<id>[A-Za-z0-9._\-\+]+)/revision/$', 'ietf.secr.drafts.views.revision', name='drafts_revision'),
    url(r'^(?P<id>[A-Za-z0-9._\-\+]+)/update/$', 'ietf.secr.drafts.views.update', name='drafts_update'),
    url(r'^(?P<id>[A-Za-z0-9._\-\+]+)/withdraw/$', 'ietf.secr.drafts.views.withdraw', name='drafts_withdraw'),
]