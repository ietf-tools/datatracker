from django.conf.urls import patterns, url
from django.conf import settings
from ietf.meeting.views import OldUploadRedirect

urlpatterns = patterns('ietf.secr.proceedings.views',
    url(r'^$', 'main', name='proceedings'),
    url(r'^ajax/generate-proceedings/(?P<meeting_num>\d{1,3})/$', 'ajax_generate_proceedings', name='proceedings_ajax_generate_proceedings'),
    # special offline URL for testing proceedings build
    url(r'^process-pdfs/(?P<meeting_num>\d{1,3})/$', 'process_pdfs', name='proceedings_process_pdfs'),
    url(r'^progress-report/(?P<meeting_num>\d{1,3})/$', 'progress_report', name='proceedings_progress_report'),
    url(r'^(?P<meeting_num>\d{1,3})/$', 'select', name='proceedings_select'),
    url(r'^(?P<meeting_num>\d{1,3})/recording/$', 'recording', name='proceedings_recording'),
    url(r'^(?P<meeting_num>\d{1,3})/recording/edit/(?P<name>[A-Za-z0-9_\-\+]+)$', 'recording_edit', name='proceedings_recording_edit'),
    url(r'^(?P<num>\d{1,3}|interim-\d{4}-[A-Za-z0-9_\-\+]+)/%(acronym)s/$' % settings.URL_REGEXPS,
         OldUploadRedirect.as_view(permanent=True)),
)
