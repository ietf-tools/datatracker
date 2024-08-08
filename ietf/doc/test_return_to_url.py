# Copyright The IETF Trust 2013-2024, All Rights Reserved
# -*- coding: utf-8 -*-

import debug                            # pyflakes:ignore

from ietf.utils.test_utils import TestCase
from .return_to_url import parse_ballot_edit_return_point


class ReturnToUrlTests(TestCase):
    def test_invalid_return_to_url(self):
        self.assertRaises(
            Exception,
            lambda: parse_ballot_edit_return_point('/doc/', 'draft-ietf-opsawg-ipfix-tcpo-v6eh', '998718'),
        )
        self.assertRaises(
            Exception,
            lambda: parse_ballot_edit_return_point('/a-route-that-does-not-exist/', 'draft-ietf-opsawg-ipfix-tcpo-v6eh', '998718'),
        )
        self.assertRaises(
            Exception,
            lambda: parse_ballot_edit_return_point('https://example.com/phishing', 'draft-ietf-opsawg-ipfix-tcpo-v6eh', '998718'),
        )

    def test_valid_default_return_to_url(self):
        self.assertEqual(parse_ballot_edit_return_point(
            None,
            'draft-ietf-opsawg-ipfix-tcpo-v6eh',
            '998718'
        ), '/doc/draft-ietf-opsawg-ipfix-tcpo-v6eh/ballot/998718/')
        
    def test_valid_return_to_url(self):
        self.assertEqual(parse_ballot_edit_return_point(
            '/doc/draft-ietf-opsawg-ipfix-tcpo-v6eh/ballot/998718/',
            'draft-ietf-opsawg-ipfix-tcpo-v6eh',
            '998718'
        ), '/doc/draft-ietf-opsawg-ipfix-tcpo-v6eh/ballot/998718/')
