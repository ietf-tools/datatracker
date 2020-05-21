from django.contrib import admin

import debug                            # pyflakes:ignore

from ietf.doc.models import TelechatDocEvent
from ietf.iesg.models import TelechatDate, TelechatAgendaItem

class TelechatAgendaItemAdmin(admin.ModelAdmin):
    pass
admin.site.register(TelechatAgendaItem, TelechatAgendaItemAdmin)

class TelechatDateAdmin(admin.ModelAdmin):
    def save_model(self, request, obj, form, change):
        '''If changing a Telechat date, change all related TelechatDocEvents, which is how
        documents are related to the Telechat
        '''
        super(TelechatDateAdmin, self).save_model(request, obj, form, change)
        if 'date' in form.changed_data:
            old_date = form.data['initial-date']
            new_date = form.cleaned_data['date']
            TelechatDocEvent.objects.filter(telechat_date=old_date).update(telechat_date=new_date)

admin.site.register(TelechatDate, TelechatDateAdmin)

