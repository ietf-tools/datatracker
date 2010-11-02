import permissions.utils

class PermissionBase(object):
    """Mix-in class for permissions.
    """
    def grant_permission(self, role, permission):
        """Grants passed permission to passed role. Returns True if the
        permission was able to be added, otherwise False.

        **Parameters:**

        role
            The role for which the permission should be granted.

        permission
            The permission which should be granted. Either a permission
            object or the codename of a permission.
        """
        return permissions.utils.grant_permission(self, role, permission)

    def remove_permission(self, role, permission):
        """Removes passed permission from passed role. Returns True if the
        permission has been removed.

        **Parameters:**

        role
            The role for which a permission should be removed.

        permission
            The permission which should be removed. Either a permission object
            or the codename of a permission.
        """
        return permissions.utils.remove_permission(self, role, permission)

    def has_permission(self, user, permission, roles=[]):
        """Returns True if the passed user has passed permission for this
        instance. Otherwise False.

        **Parameters:**

        permission
            The permission's codename which should be checked. Must be a
            string with a valid codename.

        user
            The user for which the permission should be checked.

        roles
            If passed, these roles will be assigned to the user temporarily
            before the permissions are checked.
        """
        return permissions.utils.has_permission(self, user, permission, roles)

    def check_permission(self, user, permission, roles=[]):
        """Raise Unauthorized if the the passed user hasn't passed permission 
        for this instance.

        **Parameters:**

        permission
            The permission's codename which should be checked. Must be a
            string with a valid codename.

        user
            The user for which the permission should be checked.

        roles
            If passed, these roles will be assigned to the user temporarily
            before the permissions are checked.
        """
        if not self.has_permission(user, permission, roles):
            raise Unauthorized("User %s doesn't have permission %s for object %s" % (user, permission, obj.slug))

    def add_inheritance_block(self, permission):
        """Adds an inheritance block for the passed permission.

        **Parameters:**

        permission
            The permission for which an inheritance block should be added.
            Either a permission object or the codename of a permission.
        """
        return permissions.utils.add_inheritance_block(self, permission)

    def remove_inheritance_block(self, permission):
        """Removes a inheritance block for the passed permission.

        **Parameters:**

        permission
            The permission for which an inheritance block should be removed.
            Either a permission object or the codename of a permission.
        """
        return permissions.utils.remove_inheritance_block(self, permission)

    def is_inherited(self, codename):
        """Returns True if the passed permission is inherited.

        **Parameters:**

        codename
            The permission which should be checked. Must be the codename of
            the permission.
        """
        return permissions.utils.is_inherited(self, codename)

    def add_role(self, principal, role):
        """Adds a local role for the principal.

        **Parameters:**

        principal
            The principal (user or group) which gets the role.

        role
            The role which is assigned.
        """
        return permissions.utils.add_local_role(self, principal, role)

    def get_roles(self, principal):
        """Returns *direct* local roles for passed principal (user or group).
        """
        return permissions.utils.get_local_roles(self, principal)

    def remove_role(self, principal, role):
        """Adds a local role for the principal to the object.

        **Parameters:**

        principal
            The principal (user or group) from which the role is removed.

        role
            The role which is removed.
        """
        return permissions.utils.remove_local_role(self, principal, role)

    def remove_roles(self, principal):
        """Removes all local roles for the passed principal from the object.

        **Parameters:**

        principal
            The principal (user or group) from which all local roles are
            removed.
        """
        return permissions.utils.remove_local_roles(self, principal)