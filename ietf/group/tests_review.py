import datetime

#from pyquery import PyQuery

from django.core.urlresolvers import reverse as urlreverse

from ietf.utils.test_data import make_test_data, make_review_data
from ietf.utils.test_utils import login_testing_unauthorized, TestCase, unicontent, reload_db_objects
from ietf.review.models import ReviewRequest
from ietf.person.models import Email, Person
import ietf.group.views_review

class ReviewTests(TestCase):
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
            deadline=datetime.datetime.combine(datetime.date.today() + datetime.timedelta(days=30), datetime.time(23, 59, 59)),
            state_id="accepted",
            reviewer=review_req1.reviewer,
            requested_by=Person.objects.get(user__username="plain"),
        )

        review_req3 = ReviewRequest.objects.create(
            doc=review_req1.doc,
            team=review_req1.team,
            type_id="early",
            deadline=datetime.datetime.combine(datetime.date.today() + datetime.timedelta(days=30), datetime.time(23, 59, 59)),
            state_id="requested",
            requested_by=Person.objects.get(user__username="plain"),
        )

        # get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(review_req1.doc.name in unicontent(r))

        # close and assign
        new_reviewer = Email.objects.get(role__name="reviewer", role__group=group, person__user__username="marschairman")
        r = self.client.post(url, {
            # close
            "r{}-action".format(review_req1.pk): "close",
            "r{}-close".format(review_req1.pk): "no-response",

            # assign
            "r{}-action".format(review_req2.pk): "assign",
            "r{}-reviewer".format(review_req2.pk): new_reviewer.pk,

            # no change
            "r{}-action".format(review_req3.pk): "",
            "r{}-close".format(review_req3.pk): "no-response",
            "r{}-reviewer".format(review_req3.pk): "",
        })
        self.assertEqual(r.status_code, 302)

        review_req1, review_req2, review_req3 = reload_db_objects(review_req1, review_req2, review_req3)
        self.assertEqual(review_req1.state_id, "no-response")
        self.assertEqual(review_req2.state_id, "requested")
        self.assertEqual(review_req2.reviewer, new_reviewer)
        self.assertEqual(review_req3.state_id, "requested")

        # FIXME: test suggested


