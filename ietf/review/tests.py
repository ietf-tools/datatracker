# Copyright The IETF Trust 2019-2020, All Rights Reserved
# -*- coding: utf-8 -*-


from ietf.review.factories import ReviewAssignmentFactory, ReviewRequestFactory
from ietf.utils.test_utils import TestCase, reload_db_objects
from .mailarch import hash_list_message_id

class HashTest(TestCase):

    def test_hash_list_message_id(self):
        for list, msgid, hash in (
                ('ietf', '156182196167.12901.11966487185176024571@ietfa.amsl.com',  'lr6RtZ4TiVMZn1fZbykhkXeKhEk'),
                ('codesprints', 'E1hNffl-0004RM-Dh@zinfandel.tools.ietf.org',       'N1nFHHUXiFWYtdzBgjtqzzILFHI'),
                ('xml2rfc', '3A0F4CD6-451F-44E2-9DA4-28235C638588@rfc-editor.org',  'g6DN4SxJGDrlSuKsubwb6rRSePU'),
                (u'ietf', u'156182196167.12901.11966487185176024571@ietfa.amsl.com','lr6RtZ4TiVMZn1fZbykhkXeKhEk'),
                (u'codesprints', u'E1hNffl-0004RM-Dh@zinfandel.tools.ietf.org',     'N1nFHHUXiFWYtdzBgjtqzzILFHI'),
                (u'xml2rfc', u'3A0F4CD6-451F-44E2-9DA4-28235C638588@rfc-editor.org','g6DN4SxJGDrlSuKsubwb6rRSePU'),
                (b'ietf', b'156182196167.12901.11966487185176024571@ietfa.amsl.com','lr6RtZ4TiVMZn1fZbykhkXeKhEk'),
                (b'codesprints', b'E1hNffl-0004RM-Dh@zinfandel.tools.ietf.org',     'N1nFHHUXiFWYtdzBgjtqzzILFHI'),
                (b'xml2rfc', b'3A0F4CD6-451F-44E2-9DA4-28235C638588@rfc-editor.org','g6DN4SxJGDrlSuKsubwb6rRSePU'),
            ):
            self.assertEqual(hash, hash_list_message_id(list, msgid))
            

class ReviewAssignmentTest(TestCase):
    def do_test_update_review_req_status(self, assignment_state, expected_state):
        review_req = ReviewRequestFactory(state_id='assigned')
        ReviewAssignmentFactory(review_request=review_req, state_id='part-completed')
        assignment = ReviewAssignmentFactory(review_request=review_req)

        assignment.state_id = assignment_state
        assignment.save()
        review_req = reload_db_objects(review_req)
        self.assertEqual(review_req.state_id, expected_state)

    def test_update_review_req_status(self):
        # Test change
        for assignment_state in ['no-response', 'rejected', 'withdrawn', 'overtaken']:
            self.do_test_update_review_req_status(assignment_state, 'requested')
        # Test no-change
        for assignment_state in ['accepted', 'assigned', 'completed', 'part-completed', 'unknown', ]:
            self.do_test_update_review_req_status(assignment_state, 'assigned')

    def test_no_update_review_req_status_when_other_active_assignment(self):
        # If there is another still active assignment, do not update review_req state
        review_req = ReviewRequestFactory(state_id='assigned')
        ReviewAssignmentFactory(review_request=review_req, state_id='assigned')
        assignment = ReviewAssignmentFactory(review_request=review_req)

        assignment.state_id = 'no-response'
        assignment.save()
        review_req = reload_db_objects(review_req)
        self.assertEqual(review_req.state_id, 'assigned')

    def test_no_update_review_req_status_when_review_req_withdrawn(self):
        # review_req state must only be changed to "requested", if old state was "assigned",
        # to prevent reviving dead review requests
        review_req = ReviewRequestFactory(state_id='withdrawn')
        assignment = ReviewAssignmentFactory(review_request=review_req)

        assignment.state_id = 'no-response'
        assignment.save()
        review_req = reload_db_objects(review_req)
        self.assertEqual(review_req.state_id, 'withdrawn')
