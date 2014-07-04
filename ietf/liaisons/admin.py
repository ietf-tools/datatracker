from django.contrib import admin
from django.core.urlresolvers import reverse

from ietf.liaisons.models import LiaisonStatement


class LiaisonStatementAdmin(admin.ModelAdmin):
    list_display = ['id', 'title', 'from_name', 'to_name', 'submitted', 'purpose', 'related_to']
    list_display_links = ['id', 'title']
    ordering = ('title', )
    raw_id_fields = ('from_contact', 'attachments')
    filter_horizontal = ('from_groups', 'to_groups')

    def related_to(self, obj):
        return '<br />'.join(['<a href="%s">%s</a>' % (reverse('admin:liaisons_liaisonstatement_change', None, (i.target.id, )), str(i.target)) for i in obj.source_of_set.select_related('target').all()])
    related_to.allow_tags = True


admin.site.register(LiaisonStatement, LiaisonStatementAdmin)
