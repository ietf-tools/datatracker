#!/bin/bash
set -e

# Adding the extension to the default template is needed to allow the test-suite
# to be run on postgres (see ietf.settings_test). The test runner always
# makes a fresh test database instance, and since we are bypassing the migration
# framework and using a fixture to set the database structure, there's no reaonable
# way to install the extension as part of the test run.
psql -U django -d template1 -v ON_ERROR_STOP=1 -c 'CREATE EXTENSION IF NOT EXISTS citext;'

