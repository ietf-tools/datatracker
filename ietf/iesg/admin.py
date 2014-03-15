from django.contrib import admin

from ietf.iesg.models import TelechatDate, TelechatAgendaItem

class TelechatAgendaItemAdmin(admin.ModelAdmin):
    pass
admin.site.register(TelechatAgendaItem, TelechatAgendaItemAdmin)

admin.site.register(TelechatDate)

