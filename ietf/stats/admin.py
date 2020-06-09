from django.contrib import admin

from ietf.stats.models import AffiliationAlias, AffiliationIgnoredEnding, CountryAlias, MeetingRegistration


class AffiliationAliasAdmin(admin.ModelAdmin):
    list_filter = ["name"]
    list_display = ["alias", "name"]
    search_fields = ["alias", "name"]
admin.site.register(AffiliationAlias, AffiliationAliasAdmin)

class AffiliationIgnoredEndingAdmin(admin.ModelAdmin):
    list_display = ["ending"]
    search_fields = ["ending"]
admin.site.register(AffiliationIgnoredEnding, AffiliationIgnoredEndingAdmin)

class CountryAliasAdmin(admin.ModelAdmin):
    list_filter = ["country"]
    list_display = ["alias", "country"]
    search_fields = ["alias", "country__name"]
admin.site.register(CountryAlias, CountryAliasAdmin)

class MeetingRegistrationAdmin(admin.ModelAdmin):
    list_filter = ['meeting', ]
    list_display = ['meeting', 'first_name', 'last_name', 'affiliation', 'country_code', 'person', 'email', ]
    search_fields = ['meeting__number', 'first_name', 'last_name', 'affiliation', 'country_code', 'email', ]
admin.site.register(MeetingRegistration, MeetingRegistrationAdmin)
