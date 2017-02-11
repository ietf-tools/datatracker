
from ietf.nomcom.forms import EditMembersForm, EditMembersFormPreview
from ietf.nomcom import views
from ietf.message import views as message_views
from ietf.utils.urls import url

urlpatterns = [
    url(r'^$', views.index),
    url(r'^ann/$', views.announcements),
    url(r'^(?P<year>\d{4})/private/$', views.private_index),
    url(r'^(?P<year>\d{4})/private/key/$', views.private_key, name='nomcom_private_key'),
    url(r'^(?P<year>\d{4})/private/help/$', views.configuration_help, name='nomcom_chair_help'),
    url(r'^(?P<year>\d{4})/private/nominate/$', views.private_nominate, name='nomcom_private_nominate'),
    url(r'^(?P<year>\d{4})/private/nominate/newperson$', views.private_nominate_newperson, name='nomcom_private_nominate_newperson'),
    url(r'^(?P<year>\d{4})/private/feedback/$', views.private_feedback, name='nomcom_private_feedback'),
    url(r'^(?P<year>\d{4})/private/feedback-email/$', views.private_feedback_email, name='nomcom_private_feedback_email'),
    url(r'^(?P<year>\d{4})/private/questionnaire-response/$', views.private_questionnaire, name='nomcom_private_questionnaire'),
    url(r'^(?P<year>\d{4})/private/view-feedback/$', views.view_feedback, name='nomcom_view_feedback'),
    url(r'^(?P<year>\d{4})/private/view-feedback/unrelated/$', views.view_feedback_unrelated, name='nomcom_view_feedback_unrelated'),
    url(r'^(?P<year>\d{4})/private/view-feedback/pending/$', views.view_feedback_pending, name='nomcom_view_feedback_pending'),
    url(r'^(?P<year>\d{4})/private/view-feedback/nominee/(?P<nominee_id>\d+)$', views.view_feedback_nominee),
    url(r'^(?P<year>\d{4})/private/edit/nominee/(?P<nominee_id>\d+)$', views.edit_nominee, name='nomcom_edit_nominee'),
    url(r'^(?P<year>\d{4})/private/merge-nominee/?$', views.private_merge_nominee),
    url(r'^(?P<year>\d{4})/private/merge-person/?$', views.private_merge_person),
#    url(r'^(?P<year>\d{4})/private/send-reminder-mail/$', RedirectView.as_view(url=reverse_lazy('nomcom_send_reminder_mail',kwargs={'year':year,'type':'accept'}))),
    url(r'^(?P<year>\d{4})/private/send-reminder-mail/(?P<type>\w+)/$', views.send_reminder_mail, name='nomcom_send_reminder_mail'),
    url(r'^(?P<year>\d{4})/private/edit-members/$', EditMembersFormPreview(EditMembersForm), name='nomcom_edit_members'),
    url(r'^(?P<year>\d{4})/private/edit-nomcom/$', views.edit_nomcom, name='nomcom_edit_nomcom'),
    url(r'^(?P<year>\d{4})/private/chair/templates/$', views.list_templates, name='nomcom_list_templates'),
    url(r'^(?P<year>\d{4})/private/chair/templates/(?P<template_id>\d+)/$', views.edit_template, name='nomcom_edit_template'),
    url(r'^(?P<year>\d{4})/private/chair/position/$', views.list_positions, name='nomcom_list_positions'),
    url(r'^(?P<year>\d{4})/private/chair/position/add/$', views.edit_position, name='nomcom_add_position'),
    url(r'^(?P<year>\d{4})/private/chair/position/(?P<position_id>\d+)/$', views.edit_position, name='nomcom_edit_position'),
    url(r'^(?P<year>\d{4})/private/chair/position/(?P<position_id>\d+)/remove/$', views.remove_position, name='nomcom_remove_position'),

    url(r'^(?P<year>\d{4})/$', views.year_index, name='nomcom_year_index'),
    url(r'^(?P<year>\d{4})/requirements/$', views.requirements, name='nomcom_requirements'),
    url(r'^(?P<year>\d{4})/expertise/$', views.requirements, name='nomcom_requirements'),
    url(r'^(?P<year>\d{4})/questionnaires/$', views.questionnaires, name='nomcom_questionnaires'),
    url(r'^(?P<year>\d{4})/feedback/$', views.public_feedback, name='nomcom_public_feedback'),
    url(r'^(?P<year>\d{4})/nominate/$', views.public_nominate, name='nomcom_public_nominate'),
    url(r'^(?P<year>\d{4})/nominate/newperson$', views.public_nominate_newperson, name='nomcom_public_nominate_newperson'),
    url(r'^(?P<year>\d{4})/process-nomination-status/(?P<nominee_position_id>\d+)/(?P<state>[\w]+)/(?P<date>[\d]+)/(?P<hash>[a-f0-9]+)/$', views.process_nomination_status, name='nomcom_process_nomination_status'),
# use the generic view from message
    url(r'^ann/(?P<message_id>\d+)/$', message_views.message, {'group_type': "nomcom" }),
]
