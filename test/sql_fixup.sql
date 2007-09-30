-- This file holds needed corrections to the database until they have been applied to
-- the live database.  This file is applied after importing a new dump of the live DB.

ALTER TABLE `MailingList` ADD `require_tmda` INT( 10 ) NOT NULL AFTER `domain_name` ;

