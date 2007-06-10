ALTER TABLE  `email_addresses` ADD  `id` INT NOT NULL AUTO_INCREMENT PRIMARY KEY FIRST ;
ALTER TABLE  `postal_addresses` ADD  `id` INT NOT NULL AUTO_INCREMENT PRIMARY KEY FIRST ;
ALTER TABLE  `phone_numbers` ADD  `id` INT NOT NULL AUTO_INCREMENT PRIMARY KEY FIRST ;

ALTER TABLE  `ballots` DROP PRIMARY KEY;
ALTER TABLE  `ballots` ADD  `id` INT NOT NULL AUTO_INCREMENT PRIMARY KEY FIRST ;
ALTER TABLE  `ballots` ADD UNIQUE (`ballot_id` , `ad_id`);

ALTER TABLE  `ballots_comment` DROP PRIMARY KEY;
ALTER TABLE  `ballots_comment` ADD  `id` INT NOT NULL AUTO_INCREMENT PRIMARY KEY FIRST ;
ALTER TABLE  `ballots_comment` ADD UNIQUE (`ballot_id` , `ad_id`);

ALTER TABLE  `ballots_discuss` DROP PRIMARY KEY;
ALTER TABLE  `ballots_discuss` ADD  `id` INT NOT NULL AUTO_INCREMENT PRIMARY KEY FIRST ;
ALTER TABLE  `ballots_discuss` ADD UNIQUE (`ballot_id` , `ad_id`);

ALTER TABLE  `iesg_history` DROP PRIMARY KEY;
ALTER TABLE  `iesg_history` ADD  `id` INT NOT NULL AUTO_INCREMENT PRIMARY KEY FIRST ;

ALTER TABLE  `chairs` DROP PRIMARY KEY;
ALTER TABLE  `chairs` ADD  `id` INT NOT NULL AUTO_INCREMENT
 PRIMARY KEY FIRST ;


INSERT INTO announced_from VALUES (98, 'IETF Executive Director <exec-director@ietf.org>', NULL);
INSERT INTO announced_to VALUES (9, 'Unknown', NULL);
INSERT INTO area_status VALUES (3, 'Unknown');

--
-- Date-based views require all dates to be reasonable.
-- These two rows had bad dates.
UPDATE ipr_detail SET submitted_date="2000-09-15" WHERE ipr_id=170;
UPDATE ipr_detail SET submitted_date="2004-08-30" WHERE ipr_id=418;

--
-- ref_doc_states_new had UTF-8 in the document_desc.
UPDATE ref_doc_states_new SET document_desc='A formal request has been made to advance/publish the document, following the procedures in Section 7.5 of RFC 2418. The request could be from a WG chair, from an individual through the RFC Editor, etc. (The Secretariat (iesg-secretary@ietf.org) is copied on these requests to ensure that the request makes it into the ID tracker.) A document in this state has not (yet) been reviewed by an AD nor has any official action been taken on it yet (other than to note that its publication has been requested.' WHERE document_state_id=10;

--
--
-- django wants FK pointers to nowhere to be NULL;
-- the current schema uses pointers to nonexistent rows.
ALTER TABLE  `id_internal`
 CHANGE  `cur_sub_state_id`  `cur_sub_state_id` INT( 11 ) NULL DEFAULT NULL,
 CHANGE  `prev_sub_state_id` `prev_sub_state_id` INT( 11 ) NULL DEFAULT NULL;

UPDATE id_internal SET cur_sub_state_id=NULL WHERE cur_sub_state_id < 1;
UPDATE id_internal SET prev_sub_state_id=NULL WHERE prev_sub_state_id < 1;

-- need to do announcements (99998 and 0 for person_or_org_tag)

UPDATE imported_mailing_list SET group_acronym_id=NULL WHERE group_acronym_id=0;

ALTER TABLE `area_directors`
 CHANGE `area_acronym_id` `area_acronym_id` INT(11) NULL DEFAULT NULL;

UPDATE area_directors SET area_acronym_id=NULL WHERE area_acronym_id=999999;

ALTER TABLE `groups_ietf`
 CHANGE `area_director_id` `area_director_id` INT(11) NULL DEFAULT NULL;

UPDATE groups_ietf SET area_director_id=NULL WHERE area_director_id=0;
-- inactive groups are at risk of having their area_director rows
-- deleted, so orphaned.  should we fix all of these to NULL?


-- the only missing area is for a sub-ip mailing list, so instead of
-- making the model say that the area is optional, set it here.
UPDATE none_wg_mailing_list SET area_acronym_id=1541 WHERE id=45;

