CREATE TABLE `interim_slides` (
    `id` integer AUTO_INCREMENT NOT NULL PRIMARY KEY,
    `meeting_num` integer NOT NULL,
    `group_acronym_id` integer,
    `slide_num` integer,
    `slide_type_id` integer NOT NULL,
    `slide_name` varchar(255) NOT NULL,
    `irtf` integer NOT NULL,
    `interim` bool NOT NULL,
    `order_num` integer,
    `in_q` integer
)
;
CREATE TABLE `interim_minutes` (
    `id` integer AUTO_INCREMENT NOT NULL PRIMARY KEY,
    `meeting_num` integer NOT NULL,
    `group_acronym_id` integer NOT NULL,
    `filename` varchar(255) NOT NULL,
    `irtf` integer NOT NULL,
    `interim` bool NOT NULL
)
;
CREATE TABLE `interim_agenda` (
    `id` integer AUTO_INCREMENT NOT NULL PRIMARY KEY,
    `meeting_num` integer NOT NULL,
    `group_acronym_id` integer NOT NULL,
    `filename` varchar(255) NOT NULL,
    `irtf` integer NOT NULL,
    `interim` bool NOT NULL
)
;
CREATE TABLE `interim_meetings` (
    `meeting_num` integer NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `start_date` date ,
    `end_date` date ,
    `city` varchar(255) ,
    `state` varchar(255) ,
    `country` varchar(255) ,
    `time_zone` integer,
    `ack` longtext ,
    `agenda_html` longtext ,
    `agenda_text` longtext ,
    `future_meeting` longtext ,
    `overview1` longtext ,
    `overview2` longtext ,
    `group_acronym_id` integer 
)
;
alter table interim_meetings auto_increment=201;

