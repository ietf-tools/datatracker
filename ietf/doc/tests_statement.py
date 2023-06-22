# Copyright The IETF Trust 2023, All Rights Reserved

import debug # pyflakes:ignore
from ietf.doc.factories import StatementFactory
from ietf.utils.test_utils import TestCase


class StatementsTestCase(TestCase):
    def test_statement(self):
        stmt = StatementFactory()
        debug.show("stmt")
        debug.show("stmt.states.all()")
