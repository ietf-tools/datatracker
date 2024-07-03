# Copyright The IETF Trust 2024, All Rights Reserved
from django.contrib.admin import AdminSite as _AdminSite


class AdminSite(_AdminSite):
    site_title = "Datatracker admin"
    site_header = "Datatracker administration"
