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

INSERT INTO announced_from VALUES (98, 'IETF Executive Director <exec-director@ietf.org>', NULL);
INSERT INTO announced_to VALUES (9, 'Unknown', NULL);
INSERT INTO area_status VALUES (3, 'Unknown');

UPDATE ipr_detail SET submitted_date="2000-09-15" WHERE ipr_id=170;
UPDATE ipr_detail SET submitted_date="2004-08-30" WHERE ipr_id=418;

UPDATE ref_doc_states_new SET document_desc='A formal request has been made to advance/publish the document, following the procedures in Section 7.5 of RFC 2418. The request could be from a WG chair, from an individual through the RFC Editor, etc. (The Secretariat (iesg-secretary@ietf.org) is copied on these requests to ensure that the request makes it into the ID tracker.) A document in this state has not (yet) been reviewed by an AD nor has any official action been taken on it yet (other than to note that its publication has been requested.' WHERE document_state_id=10;

