# Copyright The IETF Trust 2015-2019, All Rights Reserved
from django.contrib import admin

from ietf.mailtrigger.models import MailTrigger, Recipient

class RecipientAdmin(admin.ModelAdmin):
    list_display = [ 'slug', 'desc', 'template', 'has_code', ]
    def has_code(self, obj):
        return hasattr(obj,'gather_%s'%obj.slug) 
    has_code.boolean = True             # type: ignore # https://github.com/python/mypy/issues/2087
admin.site.register(Recipient, RecipientAdmin)


class MailTriggerAdmin(admin.ModelAdmin):
    list_display = [ 'slug', 'desc',  ]
    filter_horizontal = [ 'to', 'cc',  ]
admin.site.register(MailTrigger, MailTriggerAdmin)

