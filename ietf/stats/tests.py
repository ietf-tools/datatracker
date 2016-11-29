from pyquery import PyQuery

from django.core.urlresolvers import reverse as urlreverse

from ietf.utils.test_data import make_test_data, make_review_data
from ietf.utils.test_utils import login_testing_unauthorized, TestCase
import ietf.stats.views

class StatisticsTests(TestCase):
    def test_stats_index(self):
        url = urlreverse(ietf.stats.views.stats_index)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

    def test_review_stats(self):
        doc = make_test_data()
        review_req = make_review_data(doc)

        # check redirect
        url = urlreverse(ietf.stats.views.review_stats)

        login_testing_unauthorized(self, "secretary", url)

        completion_url = urlreverse(ietf.stats.views.review_stats, kwargs={ "stats_type": "completion" })

        r = self.client.get(url)
        self.assertEqual(r.status_code, 302)
        self.assertTrue(completion_url in r["Location"])

        self.client.logout()
        self.client.login(username="plain", password="plain+password")
        r = self.client.get(completion_url)
        self.assertEqual(r.status_code, 403)

        # check tabular
        self.client.login(username="secretary", password="secretary+password")
        for stats_type in ["completion", "results", "states"]:
            url = urlreverse(ietf.stats.views.review_stats, kwargs={ "stats_type": stats_type })
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)
            q = PyQuery(r.content)
            if stats_type != "results":
                self.assertTrue(q('.review-stats td:contains("1")'))

        # check chart
        url = urlreverse(ietf.stats.views.review_stats, kwargs={ "stats_type": "time" })
        url += "?team={}".format(review_req.team.acronym)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(q('.stats-time-graph'))

        # check reviewer level
        url = urlreverse(ietf.stats.views.review_stats, kwargs={ "stats_type": "completion", "acronym": review_req.team.acronym })
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(q('.review-stats td:contains("1")'))
