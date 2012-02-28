#coding: utf-8
from django.contrib import admin
from django.conf import settings
from ietf.ipr.models import *
                
class IprContactAdmin(admin.ModelAdmin):
    list_display=('__str__', 'ipr')
admin.site.register(IprContact, IprContactAdmin)

class IprDetailAdmin(admin.ModelAdmin):
    list_display = ['title', 'submitted_date', 'docs', ]
    search_fields = ['title', 'legal_name', ]
admin.site.register(IprDetail, IprDetailAdmin)

class IprLicensingAdmin(admin.ModelAdmin):
    pass
admin.site.register(IprLicensing, IprLicensingAdmin)

class IprNotificationAdmin(admin.ModelAdmin):
    pass
admin.site.register(IprNotification, IprNotificationAdmin)

class IprSelecttypeAdmin(admin.ModelAdmin):
    pass
admin.site.register(IprSelecttype, IprSelecttypeAdmin)

class IprUpdateAdmin(admin.ModelAdmin):
    pass
admin.site.register(IprUpdate, IprUpdateAdmin)

admin.site.register(IprDocAlias)
