# Copyright The IETF Trust 2012-2025, All Rights Reserved
from django.contrib import admin, messages
from django.db.models import QuerySet
from rangefilter.filters import DateRangeQuickSelectListFilterBuilder

from ietf.message.models import Message, MessageAttachment, SendQueue, AnnouncementFrom
from ietf.message.tasks import retry_send_messages_by_pk_task


class MessageSentStatusListFilter(admin.SimpleListFilter):
    """Filter Messages by whether or not they were sent"""

    title = "status"
    parameter_name = "status"

    def lookups(self, request, model_admin):
        return [
            ("sent", "Sent"),
            ("unsent", "Not sent"),
        ]

    def queryset(self, request, queryset):
        if self.value() == "unsent":
            return queryset.filter(sent__isnull=True)
        elif self.value() == "sent":
            return queryset.filter(sent__isnull=False)


class MessageAdmin(admin.ModelAdmin):
    list_display = ["sent_status", "subject", "by", "time", "groups"]
    search_fields = ["subject", "body"]
    raw_id_fields = ["by", "related_groups", "related_docs"]
    list_filter = [
        MessageSentStatusListFilter,
        ("time", DateRangeQuickSelectListFilterBuilder()),
    ]
    ordering = ["-time"]
    actions = ["retry_send"]

    def groups(self, instance):
        return ", ".join(g.acronym for g in instance.related_groups.all())

    @admin.display(description="Sent", boolean=True)
    def sent_status(self, instance):
        return instance.sent is not None

    @admin.action(description="Send selected messages if unsent")
    def retry_send(self, request, queryset: QuerySet[Message]):
        try:
            retry_send_messages_by_pk_task.delay(
                message_pks=list(queryset.values_list("pk", flat=True)),
                resend=False,
            )
        except Exception as err:
            self.message_user(
                request,
                f"Error: {repr(err)}",
                messages.ERROR,
            )
        else:
            self.message_user(request, "Messages queued for delivery", messages.SUCCESS)


admin.site.register(Message, MessageAdmin)


class MessageAttachmentAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "message",
        "filename",
        "removed",
    ]
    raw_id_fields = ["message"]


admin.site.register(MessageAttachment, MessageAttachmentAdmin)


class SendQueueAdmin(admin.ModelAdmin):
    list_display = ["time", "by", "message", "send_at", "sent_at"]
    list_filter = ["time", "send_at", "sent_at"]
    search_fields = ["message__body"]
    raw_id_fields = ["by", "message"]
    ordering = ["-time"]


admin.site.register(SendQueue, SendQueueAdmin)


class AnnouncementFromAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "group",
        "address",
    ]


admin.site.register(AnnouncementFrom, AnnouncementFromAdmin)
