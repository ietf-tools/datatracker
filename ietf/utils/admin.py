# Copyright The IETF Trust 2011-2020, All Rights Reserved
# -*- coding: utf-8 -*-


from django.contrib import admin
from django.utils.encoding import force_text

from ietf.utils.models import VersionInfo

def name(obj):
    if hasattr(obj, 'abbrev'):
        return obj.abbrev()
    elif hasattr(obj, 'name'):
        if callable(obj.name):
            name = obj.name()
        else:
            name = force_text(obj.name)
        if name:
            return name
    return str(obj)
    
def admin_link(field, label=None, ordering="", display=name, suffix=""):
    if not label:
        label = field.capitalize().replace("_", " ").strip()
    if ordering == "":
        ordering = field
    def _link(self):
        obj = self
        for attr in field.split("__"):
            obj = getattr(obj, attr)
            if callable(obj):
                obj = obj()
        if hasattr(obj, "all"):
            objects = obj.all()
        elif callable(obj):
            objects = obj()
            if not hasattr(objects, "__iter__"):
                objects = [ objects ]
        elif hasattr(obj, "__iter__"):
            objects = obj
        else:
            objects = [ obj ]
        chunks = []
        for obj in objects:
            app = obj._meta.app_label
            model = obj.__class__.__name__.lower()
            id = obj.pk
            chunks += [ '<a href="/admin/%(app)s/%(model)s/%(id)s/%(suffix)s">%(display)s</a>' %
                {'app':app, "model": model, "id":id, "display": display(obj), "suffix":suffix, } ]
        return ", ".join(chunks)
    _link.allow_tags = True
    _link.short_description = label
    _link.admin_order_field = ordering
    return _link

from .models import DumpInfo
class DumpInfoAdmin(admin.ModelAdmin):
    list_display = ['date', 'host', 'tz']
    list_filter = ['date']
admin.site.register(DumpInfo, DumpInfoAdmin)

class VersionInfoAdmin(admin.ModelAdmin):
    list_display = ['command', 'switch', 'version', 'time', ]
admin.site.register(VersionInfo, VersionInfoAdmin)

