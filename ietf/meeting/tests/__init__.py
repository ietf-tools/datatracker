# Copyright The IETF Trust 2012, All Rights Reserved

"""
The test cases are split into multiple files.
"""

# actual tests are distributed among a set of files in subdir tests/
from ietf.meeting.tests.meetingurls   import MeetingUrlTestCase
from ietf.meeting.tests.agenda        import AgendaInfoTestCase
from ietf.meeting.tests.api           import ApiTestCase
from ietf.meeting.tests.edit          import EditTestCase
from ietf.meeting.tests.auths         import AuthDataTestCase
from ietf.meeting.tests.view          import ViewTestCase
from ietf.meeting.tests.urlgen        import UrlGenTestCase


