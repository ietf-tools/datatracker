from datetime import timedelta
import os, shutil

import django.test
from django.core.urlresolvers import reverse as urlreverse
from django.conf import settings

from pyquery import PyQuery

from ietf.idrfc.models import RfcIndex
from ietf.idtracker.models import *
from ietf.iesg.models import *
from ietf.utils.test_utils import SimpleUrlTestCase, RealDatabaseTest, canonicalize_feed, login_testing_unauthorized

class RescheduleOnAgendaTestCase(django.test.TestCase):
    fixtures = ['base', 'draft']

    def test_reschedule(self):
        draft = InternetDraft.objects.get(filename="draft-ietf-mipshop-pfmipv6")
        draft.idinternal.telechat_date = TelechatDates.objects.all()[0].dates()[0]
        draft.idinternal.agenda = True
        draft.idinternal.returning_item = True
        draft.idinternal.save()

        form_id = draft.idinternal.draft_id
        telechat_date_before = draft.idinternal.telechat_date
        
        url = urlreverse('ietf.idrfc.views_edit.edit_info', kwargs={"name":"draft-ietf-mipshop-pfmipv6",})
        self.client.login(remote_user="klm")

        # normal get
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEquals(len(q('form select[name=telechat_date]')), 1)
        self.assertEquals(len(q('form input[name=returning_item]')), 1)

        # reschedule
        comments_before = draft.idinternal.comments().count()
        d = TelechatDates.objects.all()[0].dates()[2]

        r = self.client.post(url, { 'telechat_date': d.strftime("%Y-%m-%d"),
                                    'returning_item': "0",
                                    'job_owner': "49",
                                    'note': draft.idinternal.note,
                                    'state_change_notice_to': draft.idinternal.state_change_notice_to,
                                    'intended_status': "6", })
        self.assertEquals(r.status_code, 302)

        # check that it moved below the right header in the DOM on the
        # agenda docs page
        url = urlreverse('ietf.iesg.views.agenda_documents')
        r = self.client.get(url)
        d_header_pos = r.content.find("IESG telechat %s" % d.strftime("%Y-%m-%d"))
        draft_pos = r.content.find(draft.filename)
        self.assertTrue(d_header_pos < draft_pos)

        draft = InternetDraft.objects.get(filename="draft-ietf-mipshop-pfmipv6")
        self.assertEquals(draft.idinternal.telechat_date, d)
        self.assertTrue(not draft.idinternal.returning_item)
        self.assertEquals(draft.idinternal.comments().count(), comments_before + 1)
        self.assertTrue("Telechat" in draft.idinternal.comments()[0].comment_text)


class ManageTelechatDatesTestCase(django.test.TestCase):
    fixtures = ['base', 'draft']

    def test_set_dates(self):
        dates = TelechatDates.objects.all()[0]
        url = urlreverse('ietf.iesg.views.telechat_dates')
        login_testing_unauthorized(self, "klm", url)

        # normal get
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEquals(len(q('form input[name=date1]')), 1)

        # post
        new_date = dates.date1 + timedelta(days=7)
        
        r = self.client.post(url, dict(date1=new_date.isoformat(),
                                       date2=new_date.isoformat(),
                                       date3=new_date.isoformat(),
                                       date4=new_date.isoformat(),
                                       ))
        self.assertEquals(r.status_code, 200)

        dates = TelechatDates.objects.all()[0]
        self.assertTrue(dates.date1 == new_date)

    def test_rollup_dates(self):
        dates = TelechatDates.objects.all()[0]
        url = urlreverse('ietf.iesg.views.telechat_dates')
        login_testing_unauthorized(self, "klm", url)

        old_date2 = dates.date2
        new_date = dates.date4 + timedelta(days=14)
        r = self.client.post(url, dict(rollup_dates="1"))
        self.assertEquals(r.status_code, 200)

        dates = TelechatDates.objects.all()[0]
        self.assertTrue(dates.date4 == new_date)
        self.assertTrue(dates.date1 == old_date2)

class WorkingGroupActionsTestCase(django.test.TestCase):
    fixtures = ['base', 'wgactions']

    def setUp(self):
        super(self.__class__, self).setUp()

        curdir = os.path.dirname(os.path.abspath(__file__))
        self.evaldir = os.path.join(curdir, "testdir")
        os.mkdir(self.evaldir)
        
        src = os.path.join(curdir, "fixtures", "sieve-charter.txt")
        shutil.copy(src, self.evaldir)
        
        settings.IESG_WG_EVALUATION_DIR = self.evaldir

    def tearDown(self):
        super(self.__class__, self).tearDown()
        shutil.rmtree(self.evaldir)
        
    
    def test_working_group_actions(self):
        url = urlreverse('iesg_working_group_actions')
        login_testing_unauthorized(self, "klm", url)

        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        for wga in WGAction.objects.all():
            self.assertTrue(wga.group_acronym.name in r.content)

        self.assertTrue('(sieve)' in r.content)

    def test_delete_wgaction(self):
        wga = WGAction.objects.all()[0]
        url = urlreverse('iesg_edit_working_group_action', kwargs=dict(wga_id=wga.pk))
        login_testing_unauthorized(self, "klm", url)

        r = self.client.post(url, dict(delete="1"))
        self.assertEquals(r.status_code, 302)
        self.assertTrue(not WGAction.objects.filter(pk=wga.pk))

    def test_edit_wgaction(self):
        wga = WGAction.objects.all()[0]
        url = urlreverse('iesg_edit_working_group_action', kwargs=dict(wga_id=wga.pk))
        login_testing_unauthorized(self, "klm", url)

        # normal get
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEquals(len(q('form select[name=token_name]')), 1)
        self.assertEquals(len(q('form select[name=telechat_date]')), 1)

        # change
        dates = TelechatDates.objects.all()[0]
        token_name = IESGLogin.active_iesg().exclude(first_name=wga.token_name)[0].first_name
        old = wga.pk
        r = self.client.post(url, dict(status_date=dates.date1.isoformat(),
                                       token_name=token_name,
                                       category="23",
                                       note="Testing.",
                                       telechat_date=dates.date4.isoformat()))
        self.assertEquals(r.status_code, 302)

        wga = WGAction.objects.get(pk=old)
        self.assertEquals(wga.status_date, dates.date1)
        self.assertEquals(wga.token_name, token_name)
        self.assertEquals(wga.category, 23)
        self.assertEquals(wga.note, "Testing.")
        self.assertEquals(wga.telechat_date, dates.date4)
        
    def test_add_possible_wg(self):
        url = urlreverse('iesg_working_group_actions')
        login_testing_unauthorized(self, "klm", url)
        
        r = self.client.post(url, dict(add="1",
                                       filename='sieve-charter.txt'))
        self.assertEquals(r.status_code, 302)

        add_url = r['Location']
        r = self.client.get(add_url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue('(sieve)' in r.content)
        self.assertEquals(len(q('form select[name=token_name]')), 1)
        self.assertEquals(q('form input[name=status_date]')[0].get("value"), "2010-05-07")
        self.assertEquals(len(q('form select[name=telechat_date]')), 1)

        wgas_before = WGAction.objects.all().count()
        dates = TelechatDates.objects.all()[0]
        token_name = IESGLogin.active_iesg()[0].first_name
        r = self.client.post(add_url,
                             dict(status_date=dates.date1.isoformat(),
                                  token_name=token_name,
                                  category="23",
                                  note="Testing.",
                                  telechat_date=dates.date4.isoformat()))
        self.assertEquals(r.status_code, 302)
        self.assertEquals(wgas_before + 1, WGAction.objects.all().count())
        
    def test_delete_possible_wg(self):
        url = urlreverse('iesg_working_group_actions')
        login_testing_unauthorized(self, "klm", url)
        
        r = self.client.post(url, dict(delete="1",
                                       filename='sieve-charter.txt'))
        self.assertEquals(r.status_code, 200)

        self.assertTrue('(sieve)' not in r.content)
        


class IesgUrlTestCase(SimpleUrlTestCase):
    def testUrls(self):
        self.doTestUrls(__file__)
    def doCanonicalize(self, url, content):
        if url.startswith("/feed/"):
            return canonicalize_feed(content)
        else:
            return content

