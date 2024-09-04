# Copyright The IETF Trust 2024, All Rights Reserved
from django.contrib.admin import apps as admin_apps


class AdminConfig(admin_apps.AdminConfig):
    default_site = "ietf.admin.sites.AdminSite" 
