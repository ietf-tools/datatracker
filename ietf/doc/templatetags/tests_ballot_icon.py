from ietf.doc.factories import WgDraftFactory
from ietf.doc.templatetags.ballot_icon import auth48_alert_badge
from ietf.utils.test_utils import TestCase


class BallotIconTests(TestCase):
    def test_auth48_alert_badge_marks_auth48(self):
        draft = WgDraftFactory(states=[
            ('draft','active'),
            ('draft-iesg','rfcqueue'),
            ('draft-rfceditor', 'auth48'),
        ])
        output = auth48_alert_badge(draft)
        self.assertIn('AUTH48', output)

    def test_auth48_alert_badge_ignores_others(self):
        # If the auth48_alert_badge() method becomes more complicated, more
        # sophisticated testing can be added.
        # For now, just test a couple states that should not be marked.
        draft = WgDraftFactory(states=[
            ('draft', 'active'),
            ('draft-iesg', 'approved'),  # not in rfcqueue state
            ('draft-rfceditor', 'auth48'),
        ])
        output = auth48_alert_badge(draft)
        self.assertEqual('', output)

        draft = WgDraftFactory(states=[
            ('draft', 'active'),
            ('draft-iesg', 'rfcqueue'),
            ('draft-rfceditor', 'auth48-done'),   # not in auth48 state
        ])
        output = auth48_alert_badge(draft)
        self.assertEqual('', output)
