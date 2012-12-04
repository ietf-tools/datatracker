from django.conf.urls.defaults import patterns, url
from ietf.nomcom.forms import EditChairForm, EditChairFormPreview, \
                              EditMembersForm, EditMembersFormPreview

urlpatterns = patterns('ietf.nomcom.views',
    url(r'^(?P<year>\d{4})/edit-chair/$', EditChairFormPreview(EditChairForm), name='edit_chair'),
    url(r'^(?P<year>\d{4})/edit-members/$', EditMembersFormPreview(EditMembersForm), name='edit_members'),
    url(r'^(?P<year>\d{4})/edit-publickey/$', 'edit_publickey', name='edit_publickey'),
)
