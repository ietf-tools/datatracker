# Copyright The IETF Trust 2024, All Rights Reserved
from django.contrib.admin import AdminSite as _AdminSite
from django.conf import settings
from django.utils.safestring import mark_safe


class AdminSite(_AdminSite):
    site_title = "Datatracker admin"
    
    @staticmethod
    def site_header():
        if settings.SERVER_MODE == "production":
            return "Datatracker administration"
        else:
            return mark_safe('Datatracker administration <span class="text-danger">&delta;</span>')
