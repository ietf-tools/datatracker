from django.conf.urls.defaults import patterns, url
from ietf.nomcom.forms import EditChairForm, EditChairFormPreview, \
                              EditMembersForm, EditMembersFormPreview, \
                              EditPublicKeyForm, EditPublicKeyFormPreview

urlpatterns = patterns('ietf.nomcom.views',
    url(r'^(?P<year>\d{4})/edit-chair/$', EditChairFormPreview(EditChairForm), name='edit_chair'),
    url(r'^(?P<year>\d{4})/edit-members/$', EditMembersFormPreview(EditMembersForm), name='edit_members'),
    url(r'^(?P<year>\d{4})/edit-publickey/$', EditPublicKeyFormPreview(EditPublicKeyForm), name='edit_publickey'),
)
