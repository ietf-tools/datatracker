# Copyright The IETF Trust 2024, All Rights Reserved
#
from rest_framework import permissions
from ietf.api.ietf_utils import is_valid_token


class HasApiKey(permissions.BasePermission):
    """Permissions class that validates a token using is_valid_token
    
    The view class must indicate the relevant endpoint by setting `api_key_endpoint`.
    Must be used with an Authentication class that puts a token in request.auth.
    """
    def has_permission(self, request, view):
        endpoint = getattr(view, "api_key_endpoint", None)
        auth_token = getattr(request, "auth", None)
        if endpoint is not None and auth_token is not None:
            return is_valid_token(endpoint, auth_token)
        return False


class IsOwnPerson(permissions.BasePermission):
    """Permission to access own Person object"""
    def has_object_permission(self, request, view, obj):
        if not (request.user.is_authenticated and hasattr(request.user, "person")):
            return False
        return obj == request.user.person


class BelongsToOwnPerson(permissions.BasePermission):
    """Permission to access objects associated with own Person
    
    Requires that the object have a "person" field that indicates ownership.
    """
    def has_object_permission(self, request, view, obj):
        if not (request.user.is_authenticated and hasattr(request.user, "person")):
            return False
        return (
            hasattr(obj, "person") and obj.person == request.user.person
        )
