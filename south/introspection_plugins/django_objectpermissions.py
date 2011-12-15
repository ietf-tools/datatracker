"""
South introspection rules for django-objectpermissions
"""

from south.modelsinspector import add_ignored_fields

try:
    from objectpermissions.models import UserPermissionRelation, GroupPermissionRelation
except ImportError:
    pass
else:
    add_ignored_fields(["^objectpermissions\.models\.UserPermissionRelation",
                        "^objectpermissions\.models\.GroupPermissionRelation"])

