from django.conf.urls.defaults import patterns, url
from ietf.nomcom.forms import ManageGroupForm, ManageGroupFormPreview

urlpatterns = patterns('ietf.nomcom.views',

    url(r'^group/(?P<acronym>[\w.@+-]+)/$', ManageGroupFormPreview(ManageGroupForm), name='manage_group'),
)
