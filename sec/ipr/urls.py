from django.conf.urls.defaults import *
from django.views.generic.simple import redirect_to
import sec.ipr.views


urlpatterns = patterns('sec.ipr.views',
    url(r'^$', redirect_to, {'url': 'admin/'}, name="ipr"),
    url(r'^admin/?$', 'admin_list', name="ipr_admin_list"),
    url(r'^admin/detail/(?P<ipr_id>\d+)/?$', 'admin_detail', name="ipr_admin_detail"),
    url(r'^admin/create/?$', 'admin_create', name="ipr_admin_create"),
    url(r'^admin/update/(?P<ipr_id>\d+)/?$', 'admin_update', name="ipr_admin_update"),
    url(r'^admin/notify/(?P<ipr_id>\d+)/?$', 'admin_notify', name="ipr_admin_notify"),
    url(r'^admin/old_submitter_notify/(?P<ipr_id>\d+)/?$', 'old_submitter_notify', name="ipr_old_submitter_notify"),
    url(r'^admin/post/(?P<ipr_id>\d+)/?$', 'admin_post', name="ipr_admin_post"),
    url(r'^admin/delete/(?P<ipr_id>\d+)/?$', 'admin_delete', name="ipr_admin_delete"),
    url(r'^ajax/rfc_num/?$', 'ajax_rfc_num', name="ipr_ajax_rfc_num"),
    url(r'^ajax/internet_draft/?$', 'ajax_internet_draft', name="ipr_ajax_internet_draft"),
   
)








