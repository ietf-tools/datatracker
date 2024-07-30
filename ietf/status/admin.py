# Copyright The IETF Trust 2024, All Rights Reserved
# -*- coding: utf-8 -*-

from datetime import datetime
from django.contrib import admin
from django.template.defaultfilters import slugify
from .models import Status

class StatusAdmin(admin.ModelAdmin):
    list_display = ['title', 'body', 'active', 'date', 'by', 'page']
    raw_id_fields = ['by']

    def get_changeform_initial_data(self, request):
        date = datetime.now()
        return {
            "slug": slugify(f"{date.year}-{date.month}-{date.day}-"),
        }
    
admin.site.register(Status, StatusAdmin)
