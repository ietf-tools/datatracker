# django imports
from django.db import IntegrityError
from django.db.models import Q
from django.db import connection
from django.contrib.auth.models import User
from django.contrib.auth.models import Group
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist

# permissions imports
from permissions.exceptions import Unauthorized
from permissions.models import ObjectPermission
from permissions.models import ObjectPermissionInheritanceBlock
from permissions.models import Permission
from permissions.models import PrincipalRoleRelation
from permissions.models import Role


# Roles ######################################################################

def add_role(principal, role):
    """Adds a global role to a principal.

    **Parameters:**

    principal
        The principal (user or group) which gets the role added.

    role
        The role which is assigned.
    """
    if isinstance(principal, User):
        try:
            ppr = PrincipalRoleRelation.objects.get(user=principal, role=role, content_id=None, content_type=None)
        except PrincipalRoleRelation.DoesNotExist:
            PrincipalRoleRelation.objects.create(user=principal, role=role)
            return True
    else:
        try:
            ppr = PrincipalRoleRelation.objects.get(group=principal, role=role, content_id=None, content_type=None)
        except PrincipalRoleRelation.DoesNotExist:
            PrincipalRoleRelation.objects.create(group=principal, role=role)
            return True

    return False

def add_local_role(obj, principal, role):
    """Adds a local role to a principal.

    **Parameters:**

    obj
        The object for which the principal gets the role.

    principal
        The principal (user or group) which gets the role.

    role
        The role which is assigned.
    """
    ctype = ContentType.objects.get_for_model(obj)
    if isinstance(principal, User):
        try:
            ppr = PrincipalRoleRelation.objects.get(user=principal, role=role, content_id=obj.pk, content_type=ctype)
        except PrincipalRoleRelation.DoesNotExist:
            PrincipalRoleRelation.objects.create(user=principal, role=role, content=obj)
            return True
    else:
        try:
            ppr = PrincipalRoleRelation.objects.get(group=principal, role=role, content_id=obj.pk, content_type=ctype)
        except PrincipalRoleRelation.DoesNotExist:
            PrincipalRoleRelation.objects.create(group=principal, role=role, content=obj)
            return True

    return False

def remove_role(principal, role):
    """Removes role from passed principal.

    **Parameters:**

    principal
        The principal (user or group) from which the role is removed.

    role
        The role which is removed.
    """
    try:
        if isinstance(principal, User):
            ppr = PrincipalRoleRelation.objects.get(
                    user=principal, role=role, content_id=None, content_type=None)
        else:
            ppr = PrincipalRoleRelation.objects.get(
                    group=principal, role=role, content_id=None, content_type=None)

    except PrincipalRoleRelation.DoesNotExist:
        return False
    else:
        ppr.delete()

    return True

def remove_local_role(obj, principal, role):
    """Removes role from passed object and principle.

    **Parameters:**

    obj
        The object from which the role is removed.

    principal
        The principal (user or group) from which the role is removed.

    role
        The role which is removed.
    """
    try:
        ctype = ContentType.objects.get_for_model(obj)

        if isinstance(principal, User):
            ppr = PrincipalRoleRelation.objects.get(
                user=principal, role=role, content_id=obj.pk, content_type=ctype)
        else:
            ppr = PrincipalRoleRelation.objects.get(
                group=principal, role=role, content_id=obj.pk, content_type=ctype)

    except PrincipalRoleRelation.DoesNotExist:
        return False
    else:
        ppr.delete()

    return True

def remove_roles(principal):
    """Removes all roles passed principal (user or group).

    **Parameters:**

    principal
        The principal (user or group) from which all roles are removed.
    """
    if isinstance(principal, User):
        ppr = PrincipalRoleRelation.objects.filter(
            user=principal, content_id=None, content_type=None)
    else:
        ppr = PrincipalRoleRelation.objects.filter(
            group=principal, content_id=None, content_type=None)

    if ppr:
        ppr.delete()
        return True
    else:
        return False

def remove_local_roles(obj, principal):
    """Removes all local roles from passed object and principal (user or
    group).

    **Parameters:**

    obj
        The object from which the roles are removed.

    principal
        The principal (user or group) from which the roles are removed.
    """
    ctype = ContentType.objects.get_for_model(obj)

    if isinstance(principal, User):
        ppr = PrincipalRoleRelation.objects.filter(
            user=principal, content_id=obj.pk, content_type=ctype)
    else:
        ppr = PrincipalRoleRelation.objects.filter(
            group=principal, content_id=obj.pk, content_type=ctype)

    if ppr:
        ppr.delete()
        return True
    else:
        return False

def get_roles(user, obj=None):
    """Returns *all* roles of the passed user.

    This takes direct roles and roles via the user's groups into account.

    If an object is passed local roles will also added. Then all local roles
    from all ancestors and all user's groups are also taken into account.

    This is the method to use if one want to know whether the passed user
    has a role in general (for the passed object).

    **Parameters:**

    user
        The user for which the roles are returned.

    obj
        The object for which local roles will returned.

    """
    roles = []
    groups = user.groups.all()
    groups_ids_str = ", ".join([str(g.id) for g in groups])

    # Gobal roles for user and the user's groups
    cursor = connection.cursor()
    cursor.execute("""SELECT role_id
                      FROM permissions_principalrolerelation
                      WHERE (user_id=%s OR group_id IN (%s))
                      AND content_id is Null""" % (user.id, groups_ids_str))

    for row in cursor.fetchall():
        roles.append(row[0])

    # Local roles for user and the user's groups and all ancestors of the
    # passed object.
    while obj:
        ctype = ContentType.objects.get_for_model(obj)
        cursor.execute("""SELECT role_id
                          FROM permissions_principalrolerelation
                          WHERE (user_id='%s' OR group_id IN (%s))
                          AND content_id='%s'
                          AND content_type_id='%s'""" % (user.id, groups_ids_str, obj.pk, ctype.id))

        for row in cursor.fetchall():
            roles.append(row[0])

        try:
            obj = obj.get_parent_for_permissions()
        except AttributeError:
            obj = None

    return roles

def get_global_roles(principal):
    """Returns *direct* global roles of passed principal (user or group).
    """
    if isinstance(principal, User):
        return [prr.role for prr in PrincipalRoleRelation.objects.filter(
            user=principal, content_id=None, content_type=None)]
    else:
        if isinstance(principal, Group):
            principal = (principal,)
        return [prr.role for prr in PrincipalRoleRelation.objects.filter(
            group__in=principal, content_id=None, content_type=None)]

def get_local_roles(obj, principal):
    """Returns *direct* local roles for passed principal and content object.    
    """
    ctype = ContentType.objects.get_for_model(obj)

    if isinstance(principal, User):
        return [prr.role for prr in PrincipalRoleRelation.objects.filter(
            user=principal, content_id=obj.pk, content_type=ctype)]
    else:
        return [prr.role for prr in PrincipalRoleRelation.objects.filter(
            group=principal, content_id=obj.pk, content_type=ctype)]

# Permissions ################################################################

def check_permission(obj, user, codename, roles=None):
    """Checks whether passed user has passed permission for passed obj.

    **Parameters:**

    obj
        The object for which the permission should be checked.

    codename
        The permission's codename which should be checked.

    user
        The user for which the permission should be checked.

    roles
        If given these roles will be assigned to the user temporarily before
        the permissions are checked.
    """
    if not has_permission(obj, user, codename):
        raise Unauthorized("User '%s' doesn't have permission '%s' for object '%s' (%s)"
            % (user, codename, obj.slug, obj.__class__.__name__))

def grant_permission(obj, role, permission):
    """Grants passed permission to passed role. Returns True if the permission
    was able to be added, otherwise False.

    **Parameters:**

    obj
        The content object for which the permission should be granted.

    role
        The role for which the permission should be granted.

    permission
        The permission which should be granted. Either a permission
        object or the codename of a permission.
    """
    if not isinstance(permission, Permission):
        try:
            permission = Permission.objects.get(codename = permission)
        except Permission.DoesNotExist:
            return False

    ct = ContentType.objects.get_for_model(obj)
    try:
        ObjectPermission.objects.get(role=role, content_type = ct, content_id=obj.pk, permission=permission)
    except ObjectPermission.DoesNotExist:
        ObjectPermission.objects.create(role=role, content=obj, permission=permission)

    return True

def remove_permission(obj, role, permission):
    """Removes passed permission from passed role and object. Returns True if
    the permission has been removed.

    **Parameters:**

    obj
        The content object for which a permission should be removed.

    role
        The role for which a permission should be removed.

    permission
        The permission which should be removed. Either a permission object
        or the codename of a permission.
    """
    if not isinstance(permission, Permission):
        try:
            permission = Permission.objects.get(codename = permission)
        except Permission.DoesNotExist:
            return False

    ct = ContentType.objects.get_for_model(obj)

    try:
        op = ObjectPermission.objects.get(role=role, content_type = ct, content_id=obj.pk, permission = permission)
    except ObjectPermission.DoesNotExist:
        return False

    op.delete()
    return True

def has_permission(obj, user, codename, roles=None):
    """Checks whether the passed user has passed permission for passed object.

    **Parameters:**

    obj
        The object for which the permission should be checked.

    codename
        The permission's codename which should be checked.

    request
        The current request.

    roles
        If given these roles will be assigned to the user temporarily before
        the permissions are checked.
    """
    cache_key = "%s-%s-%s" % (obj.content_type, obj.pk, codename)
    result = _get_cached_permission(user, cache_key)
    if result is not None:
        return result

    if roles is None:
        roles = []

    if user.is_superuser:
        return True

    if not user.is_anonymous():
        roles.extend(get_roles(user, obj))

    ct = ContentType.objects.get_for_model(obj)

    result = False
    while obj is not None:
        p = ObjectPermission.objects.filter(
            content_type=ct, content_id=obj.pk, role__in=roles, permission__codename = codename).values("id")

        if len(p) > 0:
            result = True
            break

        if is_inherited(obj, codename) == False:
            result = False
            break

        try:
            obj = obj.get_parent_for_permissions()
            ct = ContentType.objects.get_for_model(obj)
        except AttributeError:
            result = False
            break

    _cache_permission(user, cache_key, result)
    return result

# Inheritance ################################################################

def add_inheritance_block(obj, permission):
    """Adds an inheritance for the passed permission on the passed obj.

    **Parameters:**

        permission
            The permission for which an inheritance block should be added.
            Either a permission object or the codename of a permission.
        obj
            The content object for which an inheritance block should be added.
    """
    if not isinstance(permission, Permission):
        try:
            permission = Permission.objects.get(codename = permission)
        except Permission.DoesNotExist:
            return False

    ct = ContentType.objects.get_for_model(obj)
    try:
        ObjectPermissionInheritanceBlock.objects.get(content_type = ct, content_id=obj.pk, permission=permission)
    except ObjectPermissionInheritanceBlock.DoesNotExist:
        try:
            result = ObjectPermissionInheritanceBlock.objects.create(content=obj, permission=permission)
        except IntegrityError:
            return False
    return True

def remove_inheritance_block(obj, permission):
    """Removes a inheritance block for the passed permission from the passed
    object.

    **Parameters:**

        obj
            The content object for which an inheritance block should be added.

        permission
            The permission for which an inheritance block should be removed.
            Either a permission object or the codename of a permission.
    """
    if not isinstance(permission, Permission):
        try:
            permission = Permission.objects.get(codename = permission)
        except Permission.DoesNotExist:
            return False

    ct = ContentType.objects.get_for_model(obj)
    try:
        opi = ObjectPermissionInheritanceBlock.objects.get(content_type = ct, content_id=obj.pk, permission=permission)
    except ObjectPermissionInheritanceBlock.DoesNotExist:
        return False

    opi.delete()
    return True

def is_inherited(obj, codename):
    """Returns True if the passed permission is inherited for passed object.

    **Parameters:**

        obj
            The content object for which the permission should be checked.

        codename
            The permission which should be checked. Must be the codename of
            the permission.
    """
    ct = ContentType.objects.get_for_model(obj)
    try:
        ObjectPermissionInheritanceBlock.objects.get(
            content_type=ct, content_id=obj.pk, permission__codename = codename)
    except ObjectDoesNotExist:
        return True
    else:
        return False

def get_group(id):
    """Returns the group with passed id or None.
    """
    try:
        return Group.objects.get(pk=id)
    except Group.DoesNotExist:
        return None

def get_role(id):
    """Returns the role with passed id or None.
    """
    try:
        return Role.objects.get(pk=id)
    except Role.DoesNotExist:
        return None

def get_user(id):
    """Returns the user with passed id or None.
    """
    try:
        return User.objects.get(pk=id)
    except User.DoesNotExist:
        return None

def has_group(user, group):
    """Returns True if passed user has passed group.
    """
    if isinstance(group, str):
        group = Group.objects.get(name=group)

    return group in user.groups.all()

def reset(obj):
    """Resets all permissions and inheritance blocks of passed object.
    """
    ctype = ContentType.objects.get_for_model(obj)
    ObjectPermissionInheritanceBlock.objects.filter(content_id=obj.pk, content_type=ctype).delete()
    ObjectPermission.objects.filter(content_id=obj.pk, content_type=ctype).delete()

# Registering ################################################################

def register_permission(name, codename, ctypes=[]):
    """Registers a permission to the framework. Returns the permission if the
    registration was successfully, otherwise False.

    **Parameters:**

        name
            The unique name of the permission. This is displayed to the
            customer.
        codename
            The unique codename of the permission. This is used internally to
            identify the permission.
        content_types
            The content type for which the permission is active. This can be
            used to display only reasonable permissions for an object. This
            must be a Django ContentType
    """
    try:
        p = Permission.objects.create(name=name, codename=codename)

        ctypes = [ContentType.objects.get_for_model(ctype) for ctype in ctypes]
        if ctypes:
            p.content_types = ctypes
            p.save()
    except IntegrityError:
        return False
    return p

def unregister_permission(codename):
    """Unregisters a permission from the framework

    **Parameters:**

        codename
            The unique codename of the permission.
    """
    try:
        permission = Permission.objects.get(codename=codename)
    except Permission.DoesNotExist:
        return False
    permission.delete()
    return True

def register_role(name):
    """Registers a role with passed name to the framework. Returns the new
    role if the registration was successfully, otherwise False.

    **Parameters:**

    name
        The unique role name.
    """
    try:
        role = Role.objects.create(name=name)
    except IntegrityError:
        return False
    return role

def unregister_role(name):
    """Unregisters the role with passed name.

    **Parameters:**

    name
        The unique role name.
    """
    try:
        role = Role.objects.get(name=name)
    except Role.DoesNotExist:
        return False

    role.delete()
    return True

def register_group(name):
    """Registers a group with passed name to the framework. Returns the new
    group if the registration was successfully, otherwise False.

    Actually this creates just a default Django Group.

    **Parameters:**

    name
        The unique group name.
    """
    try:
        group = Group.objects.create(name=name)
    except IntegrityError:
        return False
    return group

def unregister_group(name):
    """Unregisters the group with passed name. Returns True if the
    unregistration was succesfull otherwise False.

    Actually this deletes just a default Django Group.

    **Parameters:**

    name
        The unique role name.
    """
    try:
        group = Group.objects.get(name=name)
    except Group.DoesNotExist:
        return False

    group.delete()
    return True

def _cache_permission(user, cache_key, data):
    """Stores the passed data on the passed user object.

    **Parameters:**

    user
        The user on which the data is stored.

    cache_key
        The key under which the data is stored.

    data
        The data which is stored.
    """
    if not getattr(user, "permissions", None):
        user.permissions = {}
    user.permissions[cache_key] = data

def _get_cached_permission(user, cache_key):
    """Returns the stored data from passed user object for passed cache_key.

    **Parameters:**

    user
        The user from which the data is retrieved.

    cache_key
        The key under which the data is stored.

    """
    permissions = getattr(user, "permissions", None)
    if permissions:
        return user.permissions.get(cache_key, None)
