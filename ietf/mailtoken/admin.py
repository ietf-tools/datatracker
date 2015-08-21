from django.contrib import admin

from ietf.mailtoken.models import MailToken, Recipient

class RecipientAdmin(admin.ModelAdmin):
    list_display = [ 'slug', 'desc', 'template', 'has_code', ]
    def has_code(self, obj):
        return hasattr(obj,'gather_%s'%obj.slug) 
    has_code.boolean = True
admin.site.register(Recipient, RecipientAdmin)


class MailTokenAdmin(admin.ModelAdmin):
    list_display = [ 'slug', 'desc',  ]
    filter_horizontal = [ 'to', 'cc',  ]
admin.site.register(MailToken, MailTokenAdmin)

