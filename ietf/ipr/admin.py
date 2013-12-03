#coding: utf-8
from django.contrib import admin
from django.conf import settings
from ietf.ipr.models import *
                
class IprContactAdmin(admin.ModelAdmin):
    list_display=('__str__', 'ipr')
admin.site.register(IprContact, IprContactAdmin)

class IprDetailAdmin(admin.ModelAdmin):
    list_display = ['title', 'submitted_date', 'docs', 'status']
    search_fields = ['title', 'legal_name']

    def docs(self, ipr):
        res = []
        for iprdocalias in IprDocAlias.objects.filter(ipr=ipr).order_by("id").select_related("doc_alias"):
            if iprdocalias.doc_alias.name.startswith("rfc"):
                n = iprdocalias.doc_alias.name.upper()
            elif iprdocalias.rev:
                n = iprdocalias.doc_alias.name + iprdocalias.rev
            else:
                n = iprdocalias.doc_alias.name
            res.append(n)
        return u", ".join(res)
admin.site.register(IprDetail, IprDetailAdmin)

class IprNotificationAdmin(admin.ModelAdmin):
    pass
admin.site.register(IprNotification, IprNotificationAdmin)

class IprUpdateAdmin(admin.ModelAdmin):
    pass
admin.site.register(IprUpdate, IprUpdateAdmin)

admin.site.register(IprDocAlias)
