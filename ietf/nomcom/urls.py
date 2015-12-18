from django.conf.urls import patterns, url

from ietf.nomcom.forms import EditMembersForm, EditMembersFormPreview

urlpatterns = patterns('ietf.nomcom.views',
    url(r'^$', 'index'),
    url(r'^ann/$', 'announcements'),
    url(r'^(?P<year>\d{4})/private/$', 'private_index', name='nomcom_private_index'),
    url(r'^(?P<year>\d{4})/private/key/$', 'private_key', name='nomcom_private_key'),
    url(r'^(?P<year>\d{4})/private/help/$', 'configuration_help', name='nomcom_chair_help'),
    url(r'^(?P<year>\d{4})/private/nominate/$', 'private_nominate', name='nomcom_private_nominate'),
    url(r'^(?P<year>\d{4})/private/nominate/newperson$', 'private_nominate_newperson', name='nomcom_private_nominate_newperson'),
    url(r'^(?P<year>\d{4})/private/feedback/$', 'private_feedback', name='nomcom_private_feedback'),
    url(r'^(?P<year>\d{4})/private/feedback-email/$', 'private_feedback_email', name='nomcom_private_feedback_email'),
    url(r'^(?P<year>\d{4})/private/questionnaire-response/$', 'private_questionnaire', name='nomcom_private_questionnaire'),
    url(r'^(?P<year>\d{4})/private/view-feedback/$', 'view_feedback', name='nomcom_view_feedback'),
    url(r'^(?P<year>\d{4})/private/view-feedback/unrelated/$', 'view_feedback_unrelated', name='nomcom_view_feedback_unrelated'),
    url(r'^(?P<year>\d{4})/private/view-feedback/pending/$', 'view_feedback_pending', name='nomcom_view_feedback_pending'),
    url(r'^(?P<year>\d{4})/private/view-feedback/nominee/(?P<nominee_id>\d+)$', 'view_feedback_nominee', name='nomcom_view_feedback_nominee'),
    url(r'^(?P<year>\d{4})/private/edit/nominee/(?P<nominee_id>\d+)$', 'edit_nominee', name='nomcom_edit_nominee'),
    url(r'^(?P<year>\d{4})/private/merge/$', 'private_merge', name='nomcom_private_merge'),
#    url(r'^(?P<year>\d{4})/private/send-reminder-mail/$', RedirectView.as_view(url=reverse_lazy('nomcom_send_reminder_mail',kwargs={'year':year,'type':'accept'}))),
    url(r'^(?P<year>\d{4})/private/send-reminder-mail/(?P<type>\w+)/$', 'send_reminder_mail', name='nomcom_send_reminder_mail'),
    url(r'^(?P<year>\d{4})/private/edit-members/$', EditMembersFormPreview(EditMembersForm), name='nomcom_edit_members'),
    url(r'^(?P<year>\d{4})/private/edit-nomcom/$', 'edit_nomcom', name='nomcom_edit_nomcom'),
    url(r'^(?P<year>\d{4})/private/chair/templates/$', 'list_templates', name='nomcom_list_templates'),
    url(r'^(?P<year>\d{4})/private/chair/templates/(?P<template_id>\d+)/$', 'edit_template', name='nomcom_edit_template'),
    url(r'^(?P<year>\d{4})/private/chair/position/$', 'list_positions', name='nomcom_list_positions'),
    url(r'^(?P<year>\d{4})/private/chair/position/add/$', 'edit_position', name='nomcom_add_position'),
    url(r'^(?P<year>\d{4})/private/chair/position/(?P<position_id>\d+)/$', 'edit_position', name='nomcom_edit_position'),
    url(r'^(?P<year>\d{4})/private/chair/position/(?P<position_id>\d+)/remove/$', 'remove_position', name='nomcom_remove_position'),

    url(r'^(?P<year>\d{4})/$', 'year_index', name='nomcom_year_index'),
    url(r'^(?P<year>\d{4})/requirements/$', 'requirements', name='nomcom_requirements'),
    url(r'^(?P<year>\d{4})/expertise/$', 'requirements', name='nomcom_requirements'),
    url(r'^(?P<year>\d{4})/questionnaires/$', 'questionnaires', name='nomcom_questionnaires'),
    url(r'^(?P<year>\d{4})/feedback/$', 'public_feedback', name='nomcom_public_feedback'),
    url(r'^(?P<year>\d{4})/nominate/$', 'public_nominate', name='nomcom_public_nominate'),
    url(r'^(?P<year>\d{4})/nominate/newperson$', 'public_nominate_newperson', name='nomcom_public_nominate_newperson'),
    url(r'^(?P<year>\d{4})/process-nomination-status/(?P<nominee_position_id>\d+)/(?P<state>[\w]+)/(?P<date>[\d]+)/(?P<hash>[a-f0-9]+)/$', 'process_nomination_status', name='nomcom_process_nomination_status'),
)

# use the generic view from message
urlpatterns += patterns('',
    url(r'^ann/(?P<message_id>\d+)/$', 'ietf.message.views.message', {'group_type': "nomcom" }, "nomcom_announcement"),
)
