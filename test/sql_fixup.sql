-- This file holds needed corrections to the database until they have been applied to
-- the live database.  This file is applied after importing a new dump of the live DB.
DROP TABLE idtracker_areaurl;

ALTER TABLE rfc_editor_queue_mirror ADD COLUMN auth48_url VARCHAR(200);
ALTER TABLE rfc_editor_queue_mirror ADD COLUMN rfc_number INTEGER;
ALTER TABLE rfc_index_mirror ADD COLUMN stream VARCHAR(15);
ALTER TABLE rfc_index_mirror ADD COLUMN wg VARCHAR(15);
ALTER TABLE rfc_index_mirror ADD COLUMN file_formats VARCHAR(20);

