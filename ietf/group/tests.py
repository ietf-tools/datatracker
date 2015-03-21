from django.core.urlresolvers import reverse as urlreverse

from django.db.models import Q
from django.test import Client

from ietf.group.models import Role, Group
from ietf.utils.test_data import make_test_data
from ietf.utils.test_utils import login_testing_unauthorized, TestCase

class StreamTests(TestCase):
    def test_streams(self):
        make_test_data()
        r = self.client.get(urlreverse("ietf.group.views_stream.streams"))
        self.assertEqual(r.status_code, 200)
        self.assertTrue("Independent Submission Editor" in r.content)

    def test_stream_documents(self):
        draft = make_test_data()
        draft.stream_id = "iab"
        draft.save()

        r = self.client.get(urlreverse("ietf.group.views_stream.stream_documents", kwargs=dict(acronym="iab")))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(draft.name in r.content)

    def test_stream_edit(self):
        make_test_data()

        stream_acronym = "ietf"

        url = urlreverse("ietf.group.views_stream.stream_edit", kwargs=dict(acronym=stream_acronym))
        login_testing_unauthorized(self, "secretary", url)

        # get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        r = self.client.post(url, dict(delegates="ad2@ietf.org"))
        self.assertEqual(r.status_code, 302)
        self.assertTrue(Role.objects.filter(name="delegate", group__acronym=stream_acronym, email__address="ad2@ietf.org"))

class GroupTests(TestCase):
    def test_dep_urls(self):
        make_test_data()
        for group in Group.objects.filter(Q(type="wg") | Q(type="rg")):
            client = Client(Accept='application/pdf')
            r = client.get(urlreverse("ietf.group.info.dependencies_dot",
                kwargs=dict(acronym=group.acronym)))
            self.assertTrue(r.status_code == 200, "Failted to request "
                "a dot dependency graph for group: %s"%group.acronym)
            self.assertTrue(len(r.content), "Dot dependency graph for group "
                "%s has no content"%group.acronym)
            r = client.get(urlreverse("ietf.group.info.dependencies_pdf",
                kwargs=dict(acronym=group.acronym)))
            self.assertTrue(r.status_code == 200, "Failted to request "
                "a pdf dependency graph for group: %s"%group.acronym)
            self.assertTrue(len(r.content), "Pdf dependency graph for group "
                "%s has no content"%group.acronym)
