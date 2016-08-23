import datetime

#from pyquery import PyQuery

from django.core.urlresolvers import reverse as urlreverse

from ietf.utils.test_data import make_test_data, make_review_data
from ietf.utils.test_utils import login_testing_unauthorized, TestCase, unicontent, reload_db_objects
from ietf.review.models import ReviewRequest, ReviewRequestStateName
from ietf.doc.models import TelechatDocEvent
from ietf.iesg.models import TelechatDate
from ietf.person.models import Email, Person
from ietf.review.utils import suggested_review_requests_for_team
import ietf.group.views_review

class ReviewTests(TestCase):
    def test_suggested_review_requests(self):
        doc = make_test_data()
        review_req = make_review_data(doc)
        team = review_req.team

        # put on telechat
        TelechatDocEvent.objects.create(
            type="scheduled_for_telechat",
            by=Person.objects.get(name="(System)"),
            doc=doc,
            telechat_date=TelechatDate.objects.all().first().date,
        )
        doc.rev = "10"
        doc.save()

        prev_rev = "{:02}".format(int(doc.rev) - 1)

        # blocked by existing request
        review_req.requested_rev = ""
        review_req.save()

        self.assertEqual(len(suggested_review_requests_for_team(team)), 0)

        # ... but not to previous version
        review_req.requested_rev = prev_rev
        review_req.save()
        suggestions = suggested_review_requests_for_team(team)
        self.assertEqual(len(suggestions), 1)
        self.assertEqual(suggestions[0].doc, doc)
        self.assertEqual(suggestions[0].team, team)

        # blocked by non-versioned refusal
        review_req.requested_rev = ""
        review_req.state = ReviewRequestStateName.objects.get(slug="no-review-document")
        review_req.save()

        self.assertEqual(list(suggested_review_requests_for_team(team)), [])

        # blocked by versioned refusal
        review_req.reviewed_rev = doc.rev
        review_req.state = ReviewRequestStateName.objects.get(slug="no-review-document")
        review_req.save()

        self.assertEqual(list(suggested_review_requests_for_team(team)), [])

        # blocked by completion
        review_req.state = ReviewRequestStateName.objects.get(slug="completed")
        review_req.save()

        self.assertEqual(list(suggested_review_requests_for_team(team)), [])

        # ... but not to previous version
        review_req.reviewed_rev = prev_rev
        review_req.state = ReviewRequestStateName.objects.get(slug="completed")
        review_req.save()

        self.assertEqual(len(suggested_review_requests_for_team(team)), 1)
        

    def test_manage_review_requests(self):
        doc = make_test_data()
        review_req1 = make_review_data(doc)

        group = review_req1.team

        url = urlreverse(ietf.group.views_review.manage_review_requests, kwargs={ 'acronym': group.acronym })

        login_testing_unauthorized(self, "secretary", url)

        review_req2 = ReviewRequest.objects.create(
            doc=review_req1.doc,
            team=review_req1.team,
            type_id="early",
            deadline=datetime.date.today() + datetime.timedelta(days=30),
            state_id="accepted",
            reviewer=review_req1.reviewer,
            requested_by=Person.objects.get(user__username="plain"),
        )

        review_req3 = ReviewRequest.objects.create(
            doc=review_req1.doc,
            team=review_req1.team,
            type_id="early",
            deadline=datetime.date.today() + datetime.timedelta(days=30),
            state_id="requested",
            requested_by=Person.objects.get(user__username="plain"),
        )

        # get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(review_req1.doc.name in unicontent(r))

        # can't save: conflict
        new_reviewer = Email.objects.get(role__name="reviewer", role__group=group, person__user__username="marschairman")
        # provoke conflict by posting bogus data
        r = self.client.post(url, {
            "reviewrequest": [str(review_req1.pk), str(review_req2.pk), str(123456)],

            # close
            "r{}-existing_reviewer".format(review_req1.pk): "123456",
            "r{}-action".format(review_req1.pk): "close",
            "r{}-close".format(review_req1.pk): "no-response",

            # assign
            "r{}-existing_reviewer".format(review_req2.pk): "123456",
            "r{}-action".format(review_req2.pk): "assign",
            "r{}-reviewer".format(review_req2.pk): new_reviewer.pk,

            "action": "save-continue",
        })
        self.assertEqual(r.status_code, 200)
        content = unicontent(r).lower()
        self.assertTrue("1 request closed" in content)
        self.assertTrue("1 request opened" in content)
        self.assertTrue("2 requests changed assignment" in content)

        # close and assign
        new_reviewer = Email.objects.get(role__name="reviewer", role__group=group, person__user__username="marschairman")
        r = self.client.post(url, {
            "reviewrequest": [str(review_req1.pk), str(review_req2.pk), str(review_req3.pk)],

            # close
            "r{}-existing_reviewer".format(review_req1.pk): review_req1.reviewer_id or "",
            "r{}-action".format(review_req1.pk): "close",
            "r{}-close".format(review_req1.pk): "no-response",

            # assign
            "r{}-existing_reviewer".format(review_req2.pk): review_req2.reviewer_id or "",
            "r{}-action".format(review_req2.pk): "assign",
            "r{}-reviewer".format(review_req2.pk): new_reviewer.pk,

            # no change
            "r{}-existing_reviewer".format(review_req3.pk): review_req3.reviewer_id or "",
            "r{}-action".format(review_req3.pk): "",
            "r{}-close".format(review_req3.pk): "no-response",
            "r{}-reviewer".format(review_req3.pk): "",

            "action": "save",
        })
        self.assertEqual(r.status_code, 302)

        review_req1, review_req2, review_req3 = reload_db_objects(review_req1, review_req2, review_req3)
        self.assertEqual(review_req1.state_id, "no-response")
        self.assertEqual(review_req2.state_id, "requested")
        self.assertEqual(review_req2.reviewer, new_reviewer)
        self.assertEqual(review_req3.state_id, "requested")
