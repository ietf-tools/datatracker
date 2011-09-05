import datetime, os, shutil

from django.conf import settings
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse as urlreverse
import django.test
from StringIO import StringIO
from pyquery import PyQuery

from ietf.utils.test_utils import login_testing_unauthorized
from ietf.utils.test_runner import mail_outbox
from ietf.utils.test_data import make_test_data

if settings.USE_DB_REDESIGN_PROXY_CLASSES:
    from redesign.person.models import Person, Email
    from redesign.group.models import Group, Role
    from redesign.doc.models import Document
        
class SubmitTestCase(django.test.TestCase):
    fixtures = ['names']

    def setUp(self):
        self.staging_dir = os.path.abspath("tmp-submit-staging-dir")
        os.mkdir(self.staging_dir)
        
        settings.IDSUBMIT_STAGING_PATH = self.staging_dir

    def tearDown(self):
        shutil.rmtree(self.staging_dir)

    def test_submit(self):
        # break early in case of missing configuration
        self.assertTrue(os.path.exists(settings.IDSUBMIT_IDNITS_BINARY))

        draft = make_test_data()

        url = urlreverse('submit_index')

        # get
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEquals(len(q('input[type=file][name=txt]')), 1)

        # submit text draft
        filename = "draft-mars-testing-tests-00"

        # construct appropriate text file
        f = open(os.path.join(settings.BASE_DIR, "submit", "test_submission.txt"))
        template = f.read()
        f.close()
        submission_text = template % dict(
            date=datetime.date.today().strftime("%Y-%m-%d"),
            expire=(datetime.date.today() + datetime.timedelta(days=100)).strftime("%Y-%m-%d"),
            year=datetime.date.today().strftime("%Y"),
            month_year=datetime.date.today().strftime("%B, %Y"),
            filename=filename,
            )
        
        test_file = StringIO(submission_text)
        test_file.name = "somename.txt"

        r = self.client.post(url,
                             dict(txt=test_file))
        self.assertEquals(r.status_code, 302)
        self.assertTrue(os.path.exists(os.path.join(self.staging_dir, filename + ".txt")))


if not settings.USE_DB_REDESIGN_PROXY_CLASSES:
    # the above tests only work with the new schema
    del SubmitTestCase 
