# permissions imports
import permissions.utils

class ObjectPermissionsBackend(object):
    """Django backend for object permissions. Needs Django 1.2.


    Use it together with the default ModelBackend like so::

        AUTHENTICATION_BACKENDS = (
            'django.contrib.auth.backends.ModelBackend',
            'permissions.backend.ObjectPermissionsBackend',
        )

    Then you can use it like:

        user.has_perm("view", your_object)

    """
    supports_object_permissions = True
    supports_anonymous_user = True

    def authenticate(self, username, password):
        return None

    def has_perm(self, user_obj, perm, obj=None):
        """Checks whether the passed user has passed permission for passed
        object (obj).

        This should be the primary method to check wether a user has a certain
        permission.

        Parameters
        ==========

        perm
            The permission's codename which should be checked.

        user_obj
            The user for which the permission should be checked.

        obj
            The object for which the permission should be checked.
        """
        return permissions.utils.has_permission(obj, user_obj, perm)