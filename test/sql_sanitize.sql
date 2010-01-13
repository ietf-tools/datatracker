-- This file holds commands which removes stuff which **really** should not be in the
-- database in cleartext, such as passwords...

UPDATE iesg_login SET password = 'deleted';
UPDATE iesg_password SET password = 'deleted';
UPDATE wg_password SET password = 'deleted';
UPDATE web_user_info SET password = 'deleted';
UPDATE idst_users SET password = 'deleted';
UPDATE idst_users SET random_str = 'deleted';
UPDATE iesg_login SET password = 'deleted';



