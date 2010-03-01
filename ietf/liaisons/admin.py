#coding: utf-8
from django.contrib import admin
from ietf.liaisons.models import *
                
class FromBodiesAdmin(admin.ModelAdmin):
    pass
admin.site.register(FromBodies, FromBodiesAdmin)

class LiaisonDetailAdmin(admin.ModelAdmin):
    pass
admin.site.register(LiaisonDetail, LiaisonDetailAdmin)

class LiaisonPurposeAdmin(admin.ModelAdmin):
    pass
admin.site.register(LiaisonPurpose, LiaisonPurposeAdmin)

