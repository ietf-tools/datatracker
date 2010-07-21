#coding: utf-8
from django.contrib import admin
from ietf.ipr.models import *
                
class IprContactAdmin(admin.ModelAdmin):
    list_display=('__str__', 'ipr')
admin.site.register(IprContact, IprContactAdmin)

class IprDetailAdmin(admin.ModelAdmin):
    pass
admin.site.register(IprDetail, IprDetailAdmin)

class IprDraftAdmin(admin.ModelAdmin):
    pass
admin.site.register(IprDraft, IprDraftAdmin)

class IprLicensingAdmin(admin.ModelAdmin):
    pass
admin.site.register(IprLicensing, IprLicensingAdmin)

class IprNotificationAdmin(admin.ModelAdmin):
    pass
admin.site.register(IprNotification, IprNotificationAdmin)

class IprRfcAdmin(admin.ModelAdmin):
    pass
admin.site.register(IprRfc, IprRfcAdmin)

class IprSelecttypeAdmin(admin.ModelAdmin):
    pass
admin.site.register(IprSelecttype, IprSelecttypeAdmin)

class IprUpdateAdmin(admin.ModelAdmin):
    pass
admin.site.register(IprUpdate, IprUpdateAdmin)

