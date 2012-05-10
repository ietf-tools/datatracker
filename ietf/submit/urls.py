from django.conf.urls.defaults import patterns, url


urlpatterns = patterns('ietf.submit.views',
    url(r'^$', 'submit_index', name='submit_index'),
    url(r'^status/$', 'submit_status', name='submit_status'),
    url(r'^status/(?P<submission_id>\d+)/$', 'draft_status', name='draft_status'),
    url(r'^status/(?P<submission_id>\d+)/edit/$', 'draft_edit', name='draft_edit'),
    url(r'^status/(?P<submission_id>\d+)/confirm/(?P<auth_key>[a-f\d]+)/$', 'draft_confirm', name='draft_confirm'),
    url(r'^status/(?P<submission_id>\d+)/cancel/$', 'draft_cancel', name='draft_cancel'),
    url(r'^status/(?P<submission_id>\d+)/approve/$', 'draft_approve', name='draft_approve'),
    url(r'^status/(?P<submission_id>\d+)/force/$', 'draft_force', name='draft_force'),
    url(r'^status/(?P<submission_id>\d+)/request/$', 'full_url_request', name='full_url_request'),
    url(r'^status/(?P<submission_id>\d+)/(?P<submission_hash>[a-f\d]+)/$', 'draft_status', name='draft_status_by_hash'),
    url(r'^status/(?P<submission_id>\d+)/(?P<submission_hash>[a-f\d]+)/cancel/$', 'draft_cancel', name='draft_cancel_by_hash'),
    url(r'^status/(?P<submission_id>\d+)/(?P<submission_hash>[a-f\d]+)/edit/$', 'draft_edit', name='draft_edit_by_hash'),
    url(r'^approvals/$', 'approvals', name='submit_approvals'),
    url(r'^approvals/addpreapproval/$', 'add_preapproval', name='submit_add_preapproval'),
    url(r'^approvals/cancelpreapproval/(?P<preapproval_id>[a-f\d]+)/$', 'cancel_preapproval', name='submit_cancel_preapproval'),
)

urlpatterns += patterns('django.views.generic.simple',
    url(r'^note-well/$', 'direct_to_template',
        {'template': 'submit/note_well.html',
         'extra_context': {'selected': 'notewell'}
        },
        name='submit_note_well'),
    url(r'^tool-instructions/$', 'direct_to_template',
        {'template': 'submit/tool_instructions.html',
         'extra_context': {'selected': 'instructions'}
        },
        name='submit_tool_instructions'),
)
