-- This file holds commands which removes stuff which **really** should not be in the
-- database in cleartext, such as passwords...

UPDATE iesg_login SET password = 'deleted';
UPDATE iesg_password SET password = 'deleted';
UPDATE wg_password SET password = 'deleted';
UPDATE web_user_info SET password = 'deleted';
UPDATE idst_users SET password = 'deleted';
UPDATE idst_users SET random_str = 'deleted';
UPDATE users SET password = 'deleted';
DELETE FROM django_session;

-- Information only shown to IESG currently

DELETE FROM document_comments WHERE public_flag=0;
DELETE FROM management_issues;
DELETE FROM templates;

-- Personal information not shown currently

DELETE FROM meeting_attendees;
UPDATE postal_addresses SET person_title='', affiliated_company='Deleted', aff_company_key='DELETED', department = '', staddr1='', staddr2='', mail_stop='', city='', state_or_prov='', postal_code='';
UPDATE phone_numbers SET phone_number='deleted';
