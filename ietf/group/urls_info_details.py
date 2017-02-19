from django.views.generic import RedirectView

from ietf.community import views as community_views
from ietf.doc import views_material as material_views
from ietf.group import views, views_edit, views_review, milestones as milestone_views
from ietf.utils.urls import url

urlpatterns = [
    url(r'^$', views.group_home),
    url(r'^documents/txt/$', views.group_documents_txt),
    url(r'^documents/$', views.group_documents),
    url(r'^documents/manage/$', community_views.manage_list),
    url(r'^documents/csv/$', community_views.export_to_csv),
    url(r'^documents/feed/$', community_views.feed),
    url(r'^documents/subscription/$', community_views.subscription),
    url(r'^charter/$', views.group_about),
    url(r'^about/$', views.group_about),
    url(r'^about/status/$', views.group_about_status),
    url(r'^about/status/edit/$', views.group_about_status_edit),
    url(r'^about/status/meeting/(?P<num>\d+)/$', views.group_about_status_meeting),
    url(r'^history/$',views.history),
    url(r'^email/$', views.email),
    url(r'^deps/(?P<output_type>[\w-]+)/$', views.dependencies),
    url(r'^meetings/$', views.meetings),
    url(r'^edit/$', views_edit.edit, {'action': "edit"}),
    url(r'^conclude/$', views_edit.conclude),
    url(r'^milestones/$', milestone_views.edit_milestones, {'milestone_set': "current"}, "group_edit_milestones"),
    url(r'^milestones/charter/$', milestone_views.edit_milestones, {'milestone_set': "charter"}, "group_edit_charter_milestones"),
    url(r'^milestones/charter/reset/$', milestone_views.reset_charter_milestones, None, "group_reset_charter_milestones"),
    url(r'^workflow/$', views_edit.customize_workflow),
    url(r'^materials/$', views.materials),
    url(r'^materials/new/$', material_views.choose_material_type),
    url(r'^materials/new/(?P<doc_type>[\w-]+)/$', material_views.edit_material, { 'action': "new" }, "group_new_material"),
    url(r'^archives/$', views.derived_archives),
    url(r'^photos/$', views.group_photos),
    url(r'^reviews/$', views_review.review_requests),
    url(r'^reviews/manage/(?P<assignment_status>assigned|unassigned)/$', views_review.manage_review_requests),
    url(r'^reviews/email-assignments/$', views_review.email_open_review_assignments),
    url(r'^reviewers/$', views_review.reviewer_overview),
    url(r'^reviewers/(?P<reviewer_email>[\w%+-.@]+)/settings/$', views_review.change_reviewer_settings),
    url(r'^secretarysettings/$', views_review.change_review_secretary_settings),
    url(r'^email-aliases/$', RedirectView.as_view(pattern_name=views.email,permanent=False),name='old_group_email_aliases'),
]
