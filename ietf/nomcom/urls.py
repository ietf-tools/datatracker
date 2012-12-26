from django.conf.urls.defaults import patterns, url
from ietf.nomcom.forms import EditChairForm, EditChairFormPreview, \
                              EditMembersForm, EditMembersFormPreview

urlpatterns = patterns('ietf.nomcom.views',
    url(r'^(?P<year>\d{4})/$', 'index', name='nomcom_index'),
    url(r'^(?P<year>\d{4})/requirements/$', 'requirements', name='nomcom_requirements'),
    url(r'^(?P<year>\d{4})/questionnaires/$', 'questionnaires', name='nomcom_questionnaires'),
    url(r'^(?P<year>\d{4})/requirement/(?P<name>[^/]+)/$', 'requirement_detail', name='nomcom_requirement_detail'),
    url(r'^(?P<year>\d{4})/questionnaire/(?P<name>[^/]+)/$', 'questionnaire_detail', name='nomcom_questionnaire_detail'),
    url(r'^(?P<year>\d{4})/comments/$', 'comments', name='nomcom_comments'),
    url(r'^(?P<year>\d{4})/nominate/$', 'nominate', name='nomcom_nominate'),
    url(r'^ajax/position-text/(?P<position_id>\d+)/$', 'ajax_position_text', name='nomcom_ajax_position_text'),
    url(r'^(?P<year>\d{4})/edit-chair/$', EditChairFormPreview(EditChairForm), name='edit_chair'),
    url(r'^(?P<year>\d{4})/edit-members/$', EditMembersFormPreview(EditMembersForm), name='edit_members'),
    url(r'^(?P<year>\d{4})/edit-publickey/$', 'edit_publickey', name='edit_publickey'),
)
