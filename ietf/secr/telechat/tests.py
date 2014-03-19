import datetime

from django.core.urlresolvers import reverse

from ietf.utils.test_utils import TestCase
from ietf.iesg.models import TelechatDate


SECR_USER='secretary'

def augment_data():
    TelechatDate.objects.create(date=datetime.datetime.today())
    
class MainTestCase(TestCase):
    def test_main(self):
        "Main Test"
        augment_data()
        url = reverse('telechat')
        response = self.client.get(url, REMOTE_USER=SECR_USER)
        self.assertEqual(response.status_code, 200)

    def test_doc(self):
        "View Test"
        augment_data()
        d = TelechatDate.objects.all()[0]
        date = d.date.strftime('%Y-%m-%d')
        url = reverse('telechat_doc', kwargs={'date':date})
        response = self.client.get(url, REMOTE_USER=SECR_USER)
        self.assertEqual(response.status_code, 200)

