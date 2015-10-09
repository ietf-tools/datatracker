from django.contrib import admin

from ietf.mailtrigger.models import MailTrigger, Recipient

class RecipientAdmin(admin.ModelAdmin):
    list_display = [ 'slug', 'desc', 'template', 'has_code', ]
    def has_code(self, obj):
        return hasattr(obj,'gather_%s'%obj.slug) 
    has_code.boolean = True
admin.site.register(Recipient, RecipientAdmin)


class MailTriggerAdmin(admin.ModelAdmin):
    list_display = [ 'slug', 'desc',  ]
    filter_horizontal = [ 'to', 'cc',  ]
admin.site.register(MailTrigger, MailTriggerAdmin)

