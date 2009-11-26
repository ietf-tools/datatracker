-- This file holds needed corrections to the database until they have been applied to
-- the live database.  This file is applied after importing a new dump of the live DB.
delete from auth_user;
delete from auth_user_groups;
delete from auth_group;
delete from auth_group_permissions;
drop table ietfauth_usermap;
