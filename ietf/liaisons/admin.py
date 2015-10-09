from django.contrib import admin
from django.core.urlresolvers import reverse

from ietf.liaisons.models import  ( LiaisonStatement, LiaisonStatementEvent,
    LiaisonStatementGroupContacts, RelatedLiaisonStatement, LiaisonStatementAttachment )


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
        return '<br />'.join(['<a href="%s">%s</a>' % (reverse('admin:liaisons_liaisonstatement_change', None, (i.target.id, )), str(i.target)) for i in obj.source_of_set.select_related('target').all()])
    related_to.allow_tags = True

class LiaisonStatementEventAdmin(admin.ModelAdmin):
    list_display = ["statement", "type", "by", "time"]
    search_fields = ["statement__title", "by__name"]
    raw_id_fields = ["statement", "by"]

class LiaisonStatementGroupContactsAdmin(admin.ModelAdmin):
    list_display = ["group", "contacts"]
    raw_id_fields = ["group"]
    search_fields = ["group__acronym", "contacts"]
    ordering = ["group__name"]

admin.site.register(LiaisonStatement, LiaisonStatementAdmin)
admin.site.register(LiaisonStatementEvent, LiaisonStatementEventAdmin)
admin.site.register(LiaisonStatementGroupContacts, LiaisonStatementGroupContactsAdmin)
