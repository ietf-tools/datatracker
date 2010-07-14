#coding: utf-8
from django.contrib import admin
from ietf.liaisons.models import (FromBodies, LiaisonDetail, LiaisonPurpose,
                                  SDOs, LiaisonManagers, SDOAuthorizedIndividual)


class FromBodiesAdmin(admin.ModelAdmin):
    pass


class LiaisonDetailAdmin(admin.ModelAdmin):
    pass


class LiaisonPurposeAdmin(admin.ModelAdmin):
    pass


class LiaisonManagersInline(admin.TabularInline):
    model = LiaisonManagers
    raw_id_fields=['person']


class SDOAuthorizedIndividualInline(admin.TabularInline):
    model = SDOAuthorizedIndividual
    raw_id_fields=['person']


class LiaisonManagersAdmin(admin.ModelAdmin):
    raw_id_fields=['person']


class SDOAuthorizedIndividualAdmin(admin.ModelAdmin):
    raw_id_fields=['person']


class SDOsAdmin(admin.ModelAdmin):
    inlines = [LiaisonManagersInline, SDOAuthorizedIndividualInline]


class RelatedAdmin(admin.ModelAdmin):
    pass

admin.site.register(FromBodies, FromBodiesAdmin)
admin.site.register(LiaisonDetail, LiaisonDetailAdmin)
admin.site.register(LiaisonPurpose, LiaisonPurposeAdmin)
admin.site.register(SDOs, SDOsAdmin)
admin.site.register(LiaisonManagers, LiaisonManagersAdmin)
admin.site.register(SDOAuthorizedIndividual, SDOAuthorizedIndividualAdmin)
