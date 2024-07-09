from django.contrib import admin
from .models import Status

class StatusAdmin(admin.ModelAdmin):
    list_display = ['title', 'body', 'active', 'date', 'by', 'page']
    raw_id_fields = ['by']
    
admin.site.register(Status, StatusAdmin)
