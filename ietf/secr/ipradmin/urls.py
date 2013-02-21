from django.conf.urls.defaults import *
from django.views.generic.simple import redirect_to

urlpatterns = patterns('ietf.secr.ipradmin.views',
    url(r'^$', redirect_to, {'url': 'admin/'}, name="ipradmin"),
    url(r'^admin/?$', 'admin_list', name="ipradmin_admin_list"),
    url(r'^admin/detail/(?P<ipr_id>\d+)/?$', 'admin_detail', name="ipradmin_admin_detail"),
    url(r'^admin/create/?$', 'admin_create', name="ipradmin_admin_create"),
    url(r'^admin/update/(?P<ipr_id>\d+)/?$', 'admin_update', name="ipradmin_admin_update"),
    url(r'^admin/notify/(?P<ipr_id>\d+)/?$', 'admin_notify', name="ipradmin_admin_notify"),
    url(r'^admin/old_submitter_notify/(?P<ipr_id>\d+)/?$', 'old_submitter_notify', name="ipradmin_old_submitter_notify"),
    url(r'^admin/post/(?P<ipr_id>\d+)/?$', 'admin_post', name="ipradmin_admin_post"),
    url(r'^admin/delete/(?P<ipr_id>\d+)/?$', 'admin_delete', name="ipradmin_admin_delete"),
    url(r'^ajax/rfc_num/?$', 'ajax_rfc_num', name="ipradmin_ajax_rfc_num"),
    url(r'^ajax/internet_draft/?$', 'ajax_internet_draft', name="ipradmin_ajax_internet_draft"),
   
)








