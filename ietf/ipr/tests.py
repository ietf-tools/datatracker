import os, datetime, shutil

import urllib

from pyquery import PyQuery

from django.conf import settings
from django.core.urlresolvers import reverse as urlreverse

from ietf.utils.test_utils import TestCase, login_testing_unauthorized
from ietf.utils.test_data import make_test_data
from ietf.utils.mail import outbox
from ietf.ipr.models import *


class IprTests(TestCase):
    def setUp(self):
        # for patent number search
        self.ipr_dir = os.path.abspath("tmp-ipr-dir")
        if not os.path.exists(self.ipr_dir):
            os.mkdir(self.ipr_dir)
        settings.IPR_DOCUMENT_PATH = self.ipr_dir

    def tearDown(self):
        shutil.rmtree(self.ipr_dir)
    
    def test_overview(self):
        make_test_data()
        ipr = IprDetail.objects.get(title="Statement regarding rights")

        r = self.client.get(urlreverse("ipr_showlist"))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(ipr.title in r.content)

    def test_iprs_for_drafts(self):
        draft = make_test_data()
        ipr = IprDetail.objects.get(title="Statement regarding rights")

        r = self.client.get(urlreverse("ietf.ipr.views.iprs_for_drafts_txt"))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(draft.name in r.content)
        self.assertTrue(str(ipr.pk) in r.content)

    def test_about(self):
        r = self.client.get(urlreverse("ietf.ipr.views.about"))
        self.assertEqual(r.status_code, 200)
        self.assertTrue("File a disclosure" in r.content)

    def test_search(self):
        draft = make_test_data()
        ipr = IprDetail.objects.get(title="Statement regarding rights")

        url = urlreverse("ipr_search")

        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(q("form input[name=document_search]"))

        # find by id
        r = self.client.get(url + "?option=document_search&id=%s" % draft.name)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(ipr.title in r.content)

        # find draft
        r = self.client.get(url + "?option=document_search&document_search=%s" % draft.name)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(ipr.title in r.content)

        # search + select document
        r = self.client.get(url + "?option=document_search&document_search=draft")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(draft.name in r.content)
        self.assertTrue(ipr.title not in r.content)

        DocAlias.objects.create(name="rfc321", document=draft)

        # find RFC
        r = self.client.get(url + "?option=rfc_search&rfc_search=321")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(ipr.title in r.content)

        # find by patent owner
        r = self.client.get(url + "?option=patent_search&patent_search=%s" % ipr.legal_name)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(ipr.title in r.content)
        
        # find by patent info
        r = self.client.get(url + "?option=patent_info_search&patent_info_search=%s" % ipr.patents)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(ipr.title in r.content)

        # find by patent info in file
        filename = "ipr1.txt"
        with open(os.path.join(self.ipr_dir, filename), "w") as f:
            f.write("Hello world\nPTO9876")
        ipr.legacy_url_0 = "/hello/world/%s" % filename
        ipr.save()

        r = self.client.get(url + "?option=patent_info_search&patent_info_search=PTO9876")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(ipr.title in r.content)

        # must search for at least 3 characters with digit
        r = self.client.get(url + "?option=patent_info_search&patent_info_search=a")
        self.assertTrue("ipr search result error" in r.content.lower())

        r = self.client.get(url + "?option=patent_info_search&patent_info_search=aaa")
        self.assertTrue("ipr search result error" in r.content.lower())
        
        # find by group acronym
        r = self.client.get(url + "?option=wg_search&wg_search=%s" % draft.group.acronym)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(ipr.title in r.content)

        # find by doc title
        r = self.client.get(url + "?option=title_search&title_search=%s" % urllib.quote(draft.title))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(ipr.title in r.content)

        # find by ipr title
        r = self.client.get(url + "?option=ipr_title_search&ipr_title_search=%s" % urllib.quote(ipr.title))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(ipr.title in r.content)

    def test_feed(self):
        make_test_data()
        ipr = IprDetail.objects.get(title="Statement regarding rights")

        r = self.client.get("/feed/ipr/")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(ipr.title in r.content)

    def test_sitemap(self):
        make_test_data()
        ipr = IprDetail.objects.get(title="Statement regarding rights")

        r = self.client.get("/sitemap-ipr.xml")
        self.assertEqual(r.status_code, 200)
        self.assertTrue("/ipr/%s/" % ipr.pk in r.content)

    def test_new_generic(self):
        draft = make_test_data()

        url = urlreverse("ietf.ipr.new.new", kwargs={ "type": "generic" })

        # faulty post
        r = self.client.post(url, {
            "legal_name": "Test Legal",
            })
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(len(q("ul.errorlist")) > 0)

        # succesfull post
        r = self.client.post(url, {
            "legal_name": "Test Legal",
            "hold_name": "Test Holder",
            "hold_telephone": "555-555-0100",
            "hold_email": "test.holder@example.com",
            "ietf_name": "Test Participant",
            "ietf_telephone": "555-555-0101",
            "ietf_email": "test.participant@example.com",
            "patents": "none",
            "date_applied": "never",
            "country": "nowhere",
            "licensing_option": "5",
            "subm_name": "Test Submitter",
            "subm_telephone": "555-555-0102",
            "subm_email": "test.submitter@example.com"
            })
        self.assertEqual(r.status_code, 200)
        self.assertTrue("Your IPR disclosure has been submitted" in r.content)

        iprs = IprDetail.objects.filter(title__icontains="General License Statement")
        self.assertEqual(len(iprs), 1)
        ipr = iprs[0]
        self.assertEqual(ipr.legal_name, "Test Legal")
        self.assertEqual(ipr.status, 0)

    def test_new_specific(self):
        draft = make_test_data()

        url = urlreverse("ietf.ipr.new.new", kwargs={ "type": "specific" })

        # succesfull post
        r = self.client.post(url, {
            "legal_name": "Test Legal",
            "hold_name": "Test Holder",
            "hold_telephone": "555-555-0100",
            "hold_email": "test.holder@example.com",
            "ietf_name": "Test Participant",
            "ietf_telephone": "555-555-0101",
            "ietf_email": "test.participant@example.com",
            "rfclist": DocAlias.objects.filter(name__startswith="rfc")[0].name[3:],
            "draftlist": "%s-%s" % (draft.name, draft.rev),
            "patents": "none",
            "date_applied": "never",
            "country": "nowhere",
            "licensing_option": "5",
            "subm_name": "Test Submitter",
            "subm_telephone": "555-555-0102",
            "subm_email": "test.submitter@example.com"
            })
        self.assertEqual(r.status_code, 200)
        self.assertTrue("Your IPR disclosure has been submitted" in r.content)

        iprs = IprDetail.objects.filter(title__icontains=draft.name)
        self.assertEqual(len(iprs), 1)
        ipr = iprs[0]
        self.assertEqual(ipr.legal_name, "Test Legal")
        self.assertEqual(ipr.status, 0)

    def test_new_thirdparty(self):
        draft = make_test_data()

        url = urlreverse("ietf.ipr.new.new", kwargs={ "type": "third-party" })

        # succesfull post
        r = self.client.post(url, {
            "legal_name": "Test Legal",
            "hold_name": "Test Holder",
            "hold_telephone": "555-555-0100",
            "hold_email": "test.holder@example.com",
            "ietf_name": "Test Participant",
            "ietf_telephone": "555-555-0101",
            "ietf_email": "test.participant@example.com",
            "rfclist": "",
            "draftlist": "%s-%s" % (draft.name, draft.rev),
            "patents": "none",
            "date_applied": "never",
            "country": "nowhere",
            "licensing_option": "5",
            "subm_name": "Test Submitter",
            "subm_telephone": "555-555-0102",
            "subm_email": "test.submitter@example.com"
            })
        self.assertEqual(r.status_code, 200)
        self.assertTrue("Your IPR disclosure has been submitted" in r.content)

        iprs = IprDetail.objects.filter(title__icontains="belonging to Test Legal")
        self.assertEqual(len(iprs), 1)
        ipr = iprs[0]
        self.assertEqual(ipr.legal_name, "Test Legal")
        self.assertEqual(ipr.status, 0)

    def test_update(self):
        draft = make_test_data()
        original_ipr = IprDetail.objects.get(title="Statement regarding rights")

        url = urlreverse("ietf.ipr.new.update", kwargs={ "ipr_id": original_ipr.pk })

        # succesfull post
        r = self.client.post(url, {
            "legal_name": "Test Legal",
            "hold_name": "Test Holder",
            "hold_telephone": "555-555-0100",
            "hold_email": "test.holder@example.com",
            "ietf_name": "Test Participant",
            "ietf_telephone": "555-555-0101",
            "ietf_email": "test.participant@example.com",
            "rfclist": "",
            "draftlist": "%s-%s" % (draft.name, draft.rev),
            "patents": "none",
            "date_applied": "never",
            "country": "nowhere",
            "licensing_option": "5",
            "subm_name": "Test Submitter",
            "subm_telephone": "555-555-0102",
            "subm_email": "test.submitter@example.com"
            })
        self.assertEqual(r.status_code, 200)
        self.assertTrue("Your IPR disclosure has been submitted" in r.content)

        iprs = IprDetail.objects.filter(title__icontains=draft.name)
        self.assertEqual(len(iprs), 1)
        ipr = iprs[0]
        self.assertEqual(ipr.legal_name, "Test Legal")
        self.assertEqual(ipr.status, 0)

        self.assertTrue(ipr.updates.filter(updated=original_ipr))
