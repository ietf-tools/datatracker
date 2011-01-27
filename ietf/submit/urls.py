from django.conf.urls.defaults import patterns, url
from django.db.models import Q
from ietf.liaisons.models import LiaisonDetail


urlpatterns = patterns('ietf.submit.views',
    url(r'^$', 'submit_index', name='submit_index'),
    url(r'^status/$', 'submit_status', name='submit_status'),
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
