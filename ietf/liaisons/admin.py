# Copyright The IETF Trust 2010-2020, All Rights Reserved
# -*- coding: utf-8 -*-


from django.contrib import admin
from django.urls import reverse

from ietf.liaisons.models import  ( LiaisonStatement, LiaisonStatementEvent,
    RelatedLiaisonStatement, LiaisonStatementAttachment )


class RelatedLiaisonStatementInline(admin.TabularInline):
    model = RelatedLiaisonStatement
    fk_name = 'source'
    raw_id_fields = ['target']
    extra = 1

class LiaisonStatementAttachmentInline(admin.TabularInline):
    model = LiaisonStatementAttachment
    raw_id_fields = ['document']
    extra = 1

class LiaisonStatementAdmin(admin.ModelAdmin):
    list_display = ['id', 'title', 'submitted', 'from_groups_short_display', 'purpose', 'related_to']
    list_display_links = ['id', 'title']
    ordering = ('title', )
    raw_id_fields = ('from_contact', 'attachments', 'from_groups', 'to_groups')
    #filter_horizontal = ('from_groups', 'to_groups')
    inlines = [ RelatedLiaisonStatementInline, LiaisonStatementAttachmentInline ]

    def related_to(self, obj):
        return '<br>'.join(['<a href="%s">%s</a>' % (reverse('admin:liaisons_liaisonstatement_change', None, (i.target.id, )), str(i.target)) for i in obj.source_of_set.select_related('target').all()])
    related_to.allow_tags = True        # type: ignore # https://github.com/python/mypy/issues/2087

class LiaisonStatementAttachmentAdmin(admin.ModelAdmin):
    list_display = ['id', 'statement', 'document', 'removed']
    list_filter = ['removed']
    raw_id_fields = ['statement', 'document']
admin.site.register(LiaisonStatementAttachment, LiaisonStatementAttachmentAdmin)

class RelatedLiaisonStatementAdmin(admin.ModelAdmin):
    list_display = ['id', 'source', 'target', 'relationship']
    list_filter = ['relationship']
    raw_id_fields = ['source', 'target']
admin.site.register(RelatedLiaisonStatement, RelatedLiaisonStatementAdmin)

class LiaisonStatementEventAdmin(admin.ModelAdmin):
    list_display = ["statement", "type", "by", "time"]
    search_fields = ["statement__title", "by__name"]
    raw_id_fields = ["statement", "by"]

admin.site.register(LiaisonStatement, LiaisonStatementAdmin)
admin.site.register(LiaisonStatementEvent, LiaisonStatementEventAdmin)