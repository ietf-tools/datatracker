#coding: utf-8
from django.contrib import admin
from ietf.idrfc.models import *
                
class DraftVersionsAdmin(admin.ModelAdmin):
    pass
admin.site.register(DraftVersions, DraftVersionsAdmin)

class RfcEditorQueueAdmin(admin.ModelAdmin):
    pass
admin.site.register(RfcEditorQueue, RfcEditorQueueAdmin)

class RfcEditorQueueRefAdmin(admin.ModelAdmin):
    list_display = ["id", "source", "destination", "in_queue", "direct"]
    pass
admin.site.register(RfcEditorQueueRef, RfcEditorQueueRefAdmin)

class RfcIndexAdmin(admin.ModelAdmin):
    pass
admin.site.register(RfcIndex, RfcIndexAdmin)

