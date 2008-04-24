-- This file holds needed corrections to the database until they have been applied to
-- the live database.  This file is applied after importing a new dump of the live DB.

-- making author_order mandatory
alter table id_authors change author_order author_order int( 11 ) not null;

-- changing aux. auth table - person_id can be null, and add
-- the htdigest columns
alter table ietfauth_usermap change person_id person_id int( 11 ) null;
alter table ietfauth_usermap add `email_htdigest` varchar(32) NULL, add `rfced_htdigest` varchar(32) NULL;

