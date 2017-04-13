import datetime
from pyquery import PyQuery

from django.urls import reverse

from ietf.doc.models import Document, State, BallotDocEvent, BallotType
from ietf.doc.utils import update_telechat
from ietf.utils.test_utils import TestCase
from ietf.iesg.models import TelechatDate
from ietf.person.models import Person
from ietf.secr.telechat.views import get_next_telechat_date
from ietf.utils.test_data import make_test_data

SECR_USER='secretary'

def augment_data():
    TelechatDate.objects.create(date=datetime.datetime.today())
    
class SecrTelechatTestCase(TestCase):
    def test_main(self):
        "Main Test"
        augment_data()
        url = reverse('ietf.secr.telechat.views.main')
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_doc(self):
        "View Test"
        augment_data()
        d = TelechatDate.objects.all()[0]
        date = d.date.strftime('%Y-%m-%d')
        url = reverse('ietf.secr.telechat.views.doc', kwargs={'date':date})
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_doc_detail_draft(self):
        draft = make_test_data()
        d = get_next_telechat_date()
        date = d.strftime('%Y-%m-%d')
        by=Person.objects.get(name="(System)")
        update_telechat(None, draft, by, date)
        url = reverse('ietf.secr.telechat.views.doc_detail', kwargs={'date':date, 'name':draft.name})
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        q = PyQuery(response.content)
        self.assertEqual(q("#telechat-positions-table").find("th:contains('Yes')").length,1)
        self.assertEqual(q("#telechat-positions-table").find("th:contains('No Objection')").length,1)
        self.assertEqual(q("#telechat-positions-table").find("th:contains('Discuss')").length,1)
        self.assertEqual(q("#telechat-positions-table").find("th:contains('Abstain')").length,1)
        self.assertEqual(q("#telechat-positions-table").find("th:contains('Recuse')").length,1)
        self.assertEqual(q("#telechat-positions-table").find("th:contains('No Record')").length,1)

    def test_doc_detail_charter(self):
        make_test_data()
        by=Person.objects.get(name="(System)")
        charter = Document.objects.filter(type='charter').first()
        charter.set_state(State.objects.get(used=True, slug="intrev", type="charter"))
        last_week = datetime.date.today()-datetime.timedelta(days=7)
        BallotDocEvent.objects.create(type='created_ballot',by=by,doc=charter, rev=charter.rev,
                                      ballot_type=BallotType.objects.get(doc_type=charter.type,slug='r-extrev'),
                                      time=last_week)
        d = get_next_telechat_date()
        date = d.strftime('%Y-%m-%d')
        update_telechat(None, charter, by, date)
        url = reverse('ietf.secr.telechat.views.doc_detail', kwargs={'date':date, 'name':charter.name})
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        q = PyQuery(response.content)
        self.assertEqual(q("#telechat-positions-table").find("th:contains('Yes')").length,1)
        self.assertEqual(q("#telechat-positions-table").find("th:contains('No Objection')").length,1)
        self.assertEqual(q("#telechat-positions-table").find("th:contains('Block')").length,1)
        self.assertEqual(q("#telechat-positions-table").find("th:contains('Abstain')").length,1)
        self.assertEqual(q("#telechat-positions-table").find("th:contains('No Record')").length,1)
