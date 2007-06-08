ALTER TABLE  `email_addresses` ADD  `id` INT NOT NULL AUTO_INCREMENT
 PRIMARY KEY FIRST ;
ALTER TABLE  `postal_addresses` ADD  `id` INT NOT NULL AUTO_INCREMENT
 PRIMARY KEY FIRST ;
ALTER TABLE  `phone_numbers` ADD  `id` INT NOT NULL AUTO_INCREMENT
 PRIMARY KEY FIRST ;

ALTER TABLE  `ballots` DROP PRIMARY KEY;
ALTER TABLE  `ballots` ADD  `id` INT NOT NULL AUTO_INCREMENT
 PRIMARY KEY FIRST ;
ALTER TABLE  `ballots` ADD UNIQUE (`ballot_id` , `ad_id`);
ALTER TABLE  `ballots_comment` DROP PRIMARY KEY;
ALTER TABLE  `ballots_comment` ADD  `id` INT NOT NULL AUTO_INCREMENT
 PRIMARY KEY FIRST ;
ALTER TABLE  `ballots_comment` ADD UNIQUE (`ballot_id` , `ad_id`);
ALTER TABLE  `ballots_discuss` DROP PRIMARY KEY;
ALTER TABLE  `ballots_discuss` ADD  `id` INT NOT NULL AUTO_INCREMENT
 PRIMARY KEY FIRST ;
ALTER TABLE  `ballots_discuss` ADD UNIQUE (`ballot_id` , `ad_id`);
ALTER TABLE  `iesg_history` DROP PRIMARY KEY;
ALTER TABLE  `iesg_history` ADD  `id` INT NOT NULL AUTO_INCREMENT
 PRIMARY KEY FIRST ;


INSERT INTO announced_from VALUES (98, 'IETF Executive Director <exec-director@ietf.org>', NULL);
INSERT INTO announced_to VALUES (9, 'Unknown', NULL);
INSERT INTO area_status VALUES (3, 'Unknown');

UPDATE ipr_detail SET submitted_date=2000-09-15 WHERE ipr_id=170;
UPDATE ipr_detail SET submitted_date=2004-08-30 WHERE ipr_id=418;
