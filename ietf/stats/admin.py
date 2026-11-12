from django.contrib import admin

from ietf.stats.models import AffiliationAlias, AffiliationIgnoredEnding, AffiliationMainName, CountryAlias, MeetingRegistration


class AffiliationAliasAdmin(admin.ModelAdmin):
    list_filter = ["name"]
    list_display = ["alias", "name"]
    search_fields = ["alias", "name"]
admin.site.register(AffiliationAlias, AffiliationAliasAdmin)

class AffiliationIgnoredEndingAdmin(admin.ModelAdmin):
    list_display = ["ending"]
    search_fields = ["ending"]
admin.site.register(AffiliationIgnoredEnding, AffiliationIgnoredEndingAdmin)

class AffiliationMainNameAdmin(admin.ModelAdmin):
    list_display = ('main_name',)
    search_fields = ('main_name',)
admin.site.register(AffiliationMainName, AffiliationMainNameAdmin)

class CountryAliasAdmin(admin.ModelAdmin):
    list_filter = ["country"]
    list_display = ["alias", "country"]
    search_fields = ["alias", "country__name"]
admin.site.register(CountryAlias, CountryAliasAdmin)

class MeetingRegistrationAdmin(admin.ModelAdmin):
    list_filter = ['meeting', ]
    list_display = ['meeting', 'first_name', 'last_name', 'affiliation', 'country_code', 'person', 'email', ]
    search_fields = ['meeting__number', 'first_name', 'last_name', 'affiliation', 'country_code', 'email', ]
    raw_id_fields = ['person']
admin.site.register(MeetingRegistration, MeetingRegistrationAdmin)
