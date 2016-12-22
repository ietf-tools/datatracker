from django.conf.urls import url

from ietf.nomcom.forms import EditMembersForm, EditMembersFormPreview
from ietf.nomcom import views

urlpatterns = [
    url(r'^$', 'ietf.nomcom.views.index'),
    url(r'^ann/$', 'ietf.nomcom.views.announcements'),
    url(r'^(?P<year>\d{4})/private/$', 'ietf.nomcom.views.private_index', name='nomcom_private_index'),
    url(r'^(?P<year>\d{4})/private/key/$', 'ietf.nomcom.views.private_key', name='nomcom_private_key'),
    url(r'^(?P<year>\d{4})/private/help/$', 'ietf.nomcom.views.configuration_help', name='nomcom_chair_help'),
    url(r'^(?P<year>\d{4})/private/nominate/$', 'ietf.nomcom.views.private_nominate', name='nomcom_private_nominate'),
    url(r'^(?P<year>\d{4})/private/nominate/newperson$', 'ietf.nomcom.views.private_nominate_newperson', name='nomcom_private_nominate_newperson'),
    url(r'^(?P<year>\d{4})/private/feedback/$', 'ietf.nomcom.views.private_feedback', name='nomcom_private_feedback'),
    url(r'^(?P<year>\d{4})/private/feedback-email/$', 'ietf.nomcom.views.private_feedback_email', name='nomcom_private_feedback_email'),
    url(r'^(?P<year>\d{4})/private/questionnaire-response/$', 'ietf.nomcom.views.private_questionnaire', name='nomcom_private_questionnaire'),
    url(r'^(?P<year>\d{4})/private/view-feedback/$', 'ietf.nomcom.views.view_feedback', name='nomcom_view_feedback'),
    url(r'^(?P<year>\d{4})/private/view-feedback/unrelated/$', 'ietf.nomcom.views.view_feedback_unrelated', name='nomcom_view_feedback_unrelated'),
    url(r'^(?P<year>\d{4})/private/view-feedback/pending/$', 'ietf.nomcom.views.view_feedback_pending', name='nomcom_view_feedback_pending'),
    url(r'^(?P<year>\d{4})/private/view-feedback/nominee/(?P<nominee_id>\d+)$', 'ietf.nomcom.views.view_feedback_nominee', name='nomcom_view_feedback_nominee'),
    url(r'^(?P<year>\d{4})/private/edit/nominee/(?P<nominee_id>\d+)$', 'ietf.nomcom.views.edit_nominee', name='nomcom_edit_nominee'),
    url(r'^(?P<year>\d{4})/private/merge-nominee/?$', views.private_merge_nominee),
    url(r'^(?P<year>\d{4})/private/merge-person/?$', views.private_merge_person),
#    url(r'^(?P<year>\d{4})/private/send-reminder-mail/$', RedirectView.as_view(url=reverse_lazy('nomcom_send_reminder_mail',kwargs={'year':year,'type':'accept'}))),
    url(r'^(?P<year>\d{4})/private/send-reminder-mail/(?P<type>\w+)/$', 'ietf.nomcom.views.send_reminder_mail', name='nomcom_send_reminder_mail'),
    url(r'^(?P<year>\d{4})/private/edit-members/$', EditMembersFormPreview(EditMembersForm), name='nomcom_edit_members'),
    url(r'^(?P<year>\d{4})/private/edit-nomcom/$', 'ietf.nomcom.views.edit_nomcom', name='nomcom_edit_nomcom'),
    url(r'^(?P<year>\d{4})/private/chair/templates/$', 'ietf.nomcom.views.list_templates', name='nomcom_list_templates'),
    url(r'^(?P<year>\d{4})/private/chair/templates/(?P<template_id>\d+)/$', 'ietf.nomcom.views.edit_template', name='nomcom_edit_template'),
    url(r'^(?P<year>\d{4})/private/chair/position/$', 'ietf.nomcom.views.list_positions', name='nomcom_list_positions'),
    url(r'^(?P<year>\d{4})/private/chair/position/add/$', 'ietf.nomcom.views.edit_position', name='nomcom_add_position'),
    url(r'^(?P<year>\d{4})/private/chair/position/(?P<position_id>\d+)/$', 'ietf.nomcom.views.edit_position', name='nomcom_edit_position'),
    url(r'^(?P<year>\d{4})/private/chair/position/(?P<position_id>\d+)/remove/$', 'ietf.nomcom.views.remove_position', name='nomcom_remove_position'),

    url(r'^(?P<year>\d{4})/$', 'ietf.nomcom.views.year_index', name='nomcom_year_index'),
    url(r'^(?P<year>\d{4})/requirements/$', 'ietf.nomcom.views.requirements', name='nomcom_requirements'),
    url(r'^(?P<year>\d{4})/expertise/$', 'ietf.nomcom.views.requirements', name='nomcom_requirements'),
    url(r'^(?P<year>\d{4})/questionnaires/$', 'ietf.nomcom.views.questionnaires', name='nomcom_questionnaires'),
    url(r'^(?P<year>\d{4})/feedback/$', 'ietf.nomcom.views.public_feedback', name='nomcom_public_feedback'),
    url(r'^(?P<year>\d{4})/nominate/$', 'ietf.nomcom.views.public_nominate', name='nomcom_public_nominate'),
    url(r'^(?P<year>\d{4})/nominate/newperson$', 'ietf.nomcom.views.public_nominate_newperson', name='nomcom_public_nominate_newperson'),
    url(r'^(?P<year>\d{4})/process-nomination-status/(?P<nominee_position_id>\d+)/(?P<state>[\w]+)/(?P<date>[\d]+)/(?P<hash>[a-f0-9]+)/$', 'ietf.nomcom.views.process_nomination_status', name='nomcom_process_nomination_status'),
# use the generic view from message
    url(r'^ann/(?P<message_id>\d+)/$', 'ietf.message.views.message', {'group_type': "nomcom" }, "nomcom_announcement"),
]
