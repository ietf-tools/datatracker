import json

from django.core.urlresolvers import reverse as urlreverse

from ietf.community.models import CommunityList
from ietf.utils.test_data import make_test_data
from ietf.utils.test_utils import login_testing_unauthorized, TestCase

class CommunityListTests(TestCase):
    def test_track_untrack_document_for_personal_list_through_ajax(self):
        draft = make_test_data()

        url = urlreverse("community_personal_track_document", kwargs={ "name": draft.name })
        login_testing_unauthorized(self, "plain", url)

        # track
        r = self.client.post(url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(json.loads(r.content)["success"], True)
        clist = CommunityList.objects.get(user__username="plain")
        self.assertEqual(list(clist.added_ids.all()), [draft])

        # untrack
        url = urlreverse("community_personal_untrack_document", kwargs={ "name": draft.name })
        r = self.client.post(url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(json.loads(r.content)["success"], True)
        clist = CommunityList.objects.get(user__username="plain")
        self.assertEqual(list(clist.added_ids.all()), [])

    def test_track_untrack_document_for_group_list(self):
        draft = make_test_data()

        url = urlreverse("community_group_track_document", kwargs={ "name": draft.name, "acronym": draft.group.acronym })
        login_testing_unauthorized(self, "marschairman", url)

        # track
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        r = self.client.post(url)
        self.assertEqual(r.status_code, 302)
        clist = CommunityList.objects.get(group__acronym=draft.group.acronym)
        self.assertEqual(list(clist.added_ids.all()), [draft])

        # untrack
        url = urlreverse("community_group_untrack_document", kwargs={ "name": draft.name, "acronym": draft.group.acronym })
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        r = self.client.post(url)
        self.assertEqual(r.status_code, 302)
        clist = CommunityList.objects.get(group__acronym=draft.group.acronym)
        self.assertEqual(list(clist.added_ids.all()), [])
        
