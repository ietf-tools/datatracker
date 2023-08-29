# Copyright The IETF Trust 2023, All Rights Reserved
# -*- coding: utf-8 -*-
from django.contrib import admin

from .models import RpcPerson


@admin.register(RpcPerson)
class RpcPersonAdmin(admin.ModelAdmin):
    list_display = ["person", "hours_per_week", "manager"]
    raw_id_fields = ["person"]
