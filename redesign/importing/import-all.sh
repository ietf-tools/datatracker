#!/bin/bash

# basic dependencies
set -e
python import-persons.py
python import-states.py
python import-groups.py
python import-roles.py

python import-meetings.py
python import-announcements.py
python import-docs.py
python import-ipr.py # sets up links to drafts/RFCs so needs them
python import-liaison.py
