# Copyright The IETF Trust 2012-2020, All Rights Reserved
# -*- coding: utf-8 -*-


from django.contrib import admin

from ietf.nomcom.models import ( ReminderDates, NomCom, Nomination, Nominee, NomineePosition, 
                               Position, Feedback, FeedbackLastSeen, TopicFeedbackLastSeen)


class ReminderDatesAdmin(admin.ModelAdmin):
    list_display = ['id', 'date', 'nomcom']
    list_filter = ['date', 'nomcom']
admin.site.register(ReminderDates, ReminderDatesAdmin)

class NomComAdmin(admin.ModelAdmin):
    list_display = ['id', 'group', 'send_questionnaire', 'reminder_interval', 'initial_text', 'show_nominee_pictures']
    list_filter = ['send_questionnaire', 'show_nominee_pictures']
    raw_id_fields = ['group']
admin.site.register(NomCom, NomComAdmin)

class NominationAdmin(admin.ModelAdmin):
    list_display = ['id', 'position', 'candidate_name', 'candidate_email', 'candidate_phone', 'nominee', 'comments', 'nominator_email', 'user', 'time', 'share_nominator']
    list_filter = ['time', 'share_nominator']
    raw_id_fields = ['nominee', 'comments', 'user']
admin.site.register(Nomination, NominationAdmin)

class NomineeAdmin(admin.ModelAdmin):
    list_display = ('email', 'person', 'duplicated', 'nomcom')
    search_fields = ('email__address', 'person__name', )
    list_filter = ('nomcom', )
    raw_id_fields = ['nominee_position', 'email', 'person', 'duplicated']
admin.site.register(Nominee, NomineeAdmin)

class NomineePositionAdmin(admin.ModelAdmin):
    list_display = ['id', 'position', 'nominee', 'state', 'time']
    list_filter = ['state', 'position', 'time']
    raw_id_fields = ['nominee']
admin.site.register(NomineePosition, NomineePositionAdmin)

class PositionAdmin(admin.ModelAdmin):
    list_display = ('name', 'nomcom', 'is_open', 'accepting_nominations', 'accepting_feedback')
    list_filter = ['nomcom', 'is_open', 'accepting_nominations', 'accepting_feedback']
    raw_id_fields = ['requirement', 'questionnaire']
    search_fields = ['name']
admin.site.register(Position, PositionAdmin)

class FeedbackAdmin(admin.ModelAdmin):
    def nominee(self, obj):
        return ", ".join(n.person.ascii for n in obj.nominees.all())
    nominee.admin_order_field = 'nominees__person__ascii' # type: ignore # https://github.com/python/mypy/issues/2087

    list_display = ['id', 'nomcom', 'author', 'nominee', 'subject', 'type', 'user', 'time']
    list_filter = ['nomcom', 'type', 'time', ]
    raw_id_fields = ['positions', 'topics', 'user']
admin.site.register(Feedback, FeedbackAdmin)


class FeedbackLastSeenAdmin(admin.ModelAdmin):
    list_display = ['id', 'reviewer', 'nominee', 'time']
    list_filter = ['time']
    raw_id_fields = ['reviewer', 'nominee']
admin.site.register(FeedbackLastSeen, FeedbackLastSeenAdmin)

class TopicFeedbackLastSeenAdmin(admin.ModelAdmin):
    list_display = ['id', 'reviewer', 'topic', 'time']
    list_filter = ['topic', 'time']
    raw_id_fields = ['reviewer']
admin.site.register(TopicFeedbackLastSeen, TopicFeedbackLastSeenAdmin)


