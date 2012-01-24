import datetime, os, shutil

from django.conf import settings
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse as urlreverse
import django.test
from StringIO import StringIO
from pyquery import PyQuery

from ietf.utils.test_utils import SimpleUrlTestCase, canonicalize_feed, canonicalize_sitemap, login_testing_unauthorized
from ietf.utils.test_data import make_test_data
from ietf.utils.mail import outbox

class LiaisonsUrlTestCase(SimpleUrlTestCase):
    def testUrls(self):
        self.doTestUrls(__file__)
    def doCanonicalize(self, url, content):
        if url.startswith("/feed/"):
            return canonicalize_feed(content)
        elif url == "/sitemap-liaison.xml":
            return canonicalize_sitemap(content)
        else:
            return content

if settings.USE_DB_REDESIGN_PROXY_CLASSES:
    from ietf.liaisons.models import LiaisonStatement, LiaisonStatementPurposeName
    from ietf.person.models import Person, Email
    from ietf.group.models import Group, Role
        
def make_liaison_models():
    sdo = Group.objects.create(
        name="United League of Marsmen",
        acronym="",
        state_id="active",
        type_id="sdo",
        )

    # liaison manager
    u = User.objects.create(username="zrk")
    p = Person.objects.create(
        name="Zrk Brekkk",
        ascii="Zrk Brekkk",
        user=u)
    manager = email = Email.objects.create(
        address="zrk@ulm.mars",
        person=p)
    Role.objects.create(
        name_id="liaiman",
        group=sdo,
        person=p,
        email=email)

    # authorized individual
    u = User.objects.create(username="rkz")
    p = Person.objects.create(
        name="Rkz Kkkreb",
        ascii="Rkz Kkkreb",
        user=u)
    email = Email.objects.create(
        address="rkz@ulm.mars",
        person=p)
    Role.objects.create(
        name_id="auth",
        group=sdo,
        person=p,
        email=email)

    mars_group = Group.objects.get(acronym="mars")
    
    l = LiaisonStatement.objects.create(
        title="Comment from United League of Marsmen",
        purpose_id="comment",
        body="The recently proposed Martian Standard for Communication Links neglects the special ferro-magnetic conditions of the Martian soil.",
        deadline=datetime.date.today() + datetime.timedelta(days=7),
        related_to=None,
        from_group=sdo,
        from_name=sdo.name,
        from_contact=manager,
        to_group=mars_group,
        to_name=mars_group.name,
        to_contact="%s@ietf.org" % mars_group.acronym,
        reply_to=email.address,
        response_contact="",
        technical_contact="",
        cc="",
        submitted=datetime.datetime.now(),
        modified=datetime.datetime.now(),
        approved=datetime.datetime.now(),
        action_taken=False,
        )
    return l
    

class LiaisonManagementTestCase(django.test.TestCase):
    fixtures = ['names']

    def setUp(self):
        self.liaison_dir = os.path.abspath("tmp-liaison-dir")
        os.mkdir(self.liaison_dir)
        
        settings.LIAISON_ATTACH_PATH = self.liaison_dir

    def tearDown(self):
        shutil.rmtree(self.liaison_dir)

    def test_taken_care_of(self):
        make_test_data()
        liaison = make_liaison_models()
        
        url = urlreverse('liaison_detail', kwargs=dict(object_id=liaison.pk))
        # normal get
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEquals(len(q('form input[name=do_action_taken]')), 0)
        
        # log in and get
        self.client.login(remote_user="secretary")

        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEquals(len(q('form input[name=do_action_taken]')), 1)
        
        # mark action taken
        r = self.client.post(url, dict(do_action_taken="1"))
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEquals(len(q('form input[name=do_action_taken]')), 0)
        liaison = LiaisonStatement.objects.get(id=liaison.id)
        self.assertTrue(liaison.action_taken)

    def test_approval(self):
        make_test_data()
        liaison = make_liaison_models()
        # has to come from WG to need approval
        liaison.from_group = Group.objects.get(acronym="mars")
        liaison.approved = None
        liaison.save()
        
        url = urlreverse('liaison_approval_detail', kwargs=dict(object_id=liaison.pk))
        # this liaison is for a WG so we need the AD for the area
        login_testing_unauthorized(self, "ad", url)
        
        # normal get
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEquals(len(q('form input[name=do_approval]')), 1)
        
        # approve
        mailbox_before = len(outbox)
        r = self.client.post(url, dict(do_approval="1"))
        self.assertEquals(r.status_code, 302)
        
        liaison = LiaisonStatement.objects.get(id=liaison.id)
        self.assertTrue(liaison.approved)
        self.assertEquals(len(outbox), mailbox_before + 1)
        self.assertTrue("Liaison Statement" in outbox[-1]["Subject"])

    def test_edit_liaison(self):
        make_test_data()
        liaison = make_liaison_models()
        
        url = urlreverse('liaison_edit', kwargs=dict(object_id=liaison.pk))
        login_testing_unauthorized(self, "secretary", url)

        # get
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEquals(len(q('form input[name=from_field]')), 1)

        # edit
        attachments_before = liaison.attachments.count()
        test_file = StringIO("hello world")
        test_file.name = "unnamed"
        r = self.client.post(url,
                             dict(from_field="from",
                                  replyto="replyto@example.com",
                                  organization="org",
                                  to_poc="to_poc@example.com",
                                  response_contact="responce_contact@example.com",
                                  technical_contact="technical_contact@example.com",
                                  cc1="cc@example.com",
                                  purpose="4",
                                  deadline_date=(liaison.deadline + datetime.timedelta(days=1)).strftime("%Y-%m-%d"),
                                  title="title",
                                  submitted_date=(liaison.submitted + datetime.timedelta(days=1)).strftime("%Y-%m-%d"),
                                  body="body",
                                  attach_file_1=test_file,
                                  attach_title_1="attachment",
                                  ))
        self.assertEquals(r.status_code, 302)
        
        new_liaison = LiaisonStatement.objects.get(id=liaison.id)
        self.assertEquals(new_liaison.from_name, "from")
        self.assertEquals(new_liaison.reply_to, "replyto@example.com")
        self.assertEquals(new_liaison.to_name, "org")
        self.assertEquals(new_liaison.to_contact, "to_poc@example.com")
        self.assertEquals(new_liaison.response_contact, "responce_contact@example.com")
        self.assertEquals(new_liaison.technical_contact, "technical_contact@example.com")
        self.assertEquals(new_liaison.cc, "cc@example.com")
        self.assertEquals(new_liaison.purpose, LiaisonStatementPurposeName.objects.get(order=4))
        self.assertEquals(new_liaison.deadline, liaison.deadline + datetime.timedelta(days=1)),
        self.assertEquals(new_liaison.title, "title")
        self.assertEquals(new_liaison.submitted.date(), (liaison.submitted + datetime.timedelta(days=1)).date())
        self.assertEquals(new_liaison.body, "body")
        
        self.assertEquals(new_liaison.attachments.count(), attachments_before + 1)
        attachment = new_liaison.attachments.order_by("-name")[0]
        self.assertEquals(attachment.title, "attachment")
        with open(os.path.join(self.liaison_dir, attachment.external_url)) as f:
            written_content = f.read()

        test_file.seek(0)
        self.assertEquals(written_content, test_file.read())
        
    def test_add_incoming_liaison(self):
        make_test_data()
        liaison = make_liaison_models()
        
        url = urlreverse('add_liaison') + "?incoming=1"
        login_testing_unauthorized(self, "secretary", url)

        # get
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEquals(len(q('form textarea[name=body]')), 1)

        # add new
        mailbox_before = len(outbox)
        test_file = StringIO("hello world")
        test_file.name = "unnamed"
        from_group = Group.objects.filter(type="sdo")[0]
        to_group = Group.objects.get(acronym="mars")
        submitter = Person.objects.get(user__username="marschairman")
        today = datetime.date.today()
        related_liaison = liaison
        r = self.client.post(url,
                             dict(from_field="%s_%s" % (from_group.type_id, from_group.pk),
                                  from_fake_user=str(submitter.pk),
                                  replyto="replyto@example.com",
                                  organization="%s_%s" % (to_group.type_id, to_group.pk),
                                  response_contact="responce_contact@example.com",
                                  technical_contact="technical_contact@example.com",
                                  cc1="cc@example.com",
                                  purpose="4",
                                  deadline_date=(today + datetime.timedelta(days=1)).strftime("%Y-%m-%d"),
                                  related_to=str(related_liaison.pk),
                                  title="title",
                                  submitted_date=today.strftime("%Y-%m-%d"),
                                  body="body",
                                  attach_file_1=test_file,
                                  attach_title_1="attachment",
                                  send="1",
                                  ))
        self.assertEquals(r.status_code, 302)
        
        l = LiaisonStatement.objects.all().order_by("-id")[0]
        self.assertEquals(l.from_group, from_group)
        self.assertEquals(l.from_contact.address, submitter.email_address())
        self.assertEquals(l.reply_to, "replyto@example.com")
        self.assertEquals(l.to_group, to_group)
        self.assertEquals(l.response_contact, "responce_contact@example.com")
        self.assertEquals(l.technical_contact, "technical_contact@example.com")
        self.assertEquals(l.cc, "cc@example.com")
        self.assertEquals(l.purpose, LiaisonStatementPurposeName.objects.get(order=4))
        self.assertEquals(l.deadline, today + datetime.timedelta(days=1)),
        self.assertEquals(l.related_to, liaison),
        self.assertEquals(l.title, "title")
        self.assertEquals(l.submitted.date(), today)
        self.assertEquals(l.body, "body")
        self.assertTrue(l.approved)
        
        self.assertEquals(l.attachments.count(), 1)
        attachment = l.attachments.all()[0]
        self.assertEquals(attachment.title, "attachment")
        with open(os.path.join(self.liaison_dir, attachment.external_url)) as f:
            written_content = f.read()

        test_file.seek(0)
        self.assertEquals(written_content, test_file.read())

        self.assertEquals(len(outbox), mailbox_before + 1)
        self.assertTrue("Liaison Statement" in outbox[-1]["Subject"])
        
    def test_add_outgoing_liaison(self):
        make_test_data()
        liaison = make_liaison_models()
        
        url = urlreverse('add_liaison')
        login_testing_unauthorized(self, "secretary", url)

        # get
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEquals(len(q('form textarea[name=body]')), 1)

        # add new
        mailbox_before = len(outbox)
        test_file = StringIO("hello world")
        test_file.name = "unnamed"
        from_group = Group.objects.get(acronym="mars")
        to_group = Group.objects.filter(type="sdo")[0]
        submitter = Person.objects.get(user__username="marschairman")
        today = datetime.date.today()
        related_liaison = liaison
        r = self.client.post(url,
                             dict(from_field="%s_%s" % (from_group.type_id, from_group.pk),
                                  from_fake_user=str(submitter.pk),
                                  approved="",
                                  replyto="replyto@example.com",
                                  to_poc="to_poc@example.com",
                                  organization="%s_%s" % (to_group.type_id, to_group.pk),
                                  other_organization="",
                                  response_contact="responce_contact@example.com",
                                  technical_contact="technical_contact@example.com",
                                  cc1="cc@example.com",
                                  purpose="4",
                                  deadline_date=(today + datetime.timedelta(days=1)).strftime("%Y-%m-%d"),
                                  related_to=str(related_liaison.pk),
                                  title="title",
                                  submitted_date=today.strftime("%Y-%m-%d"),
                                  body="body",
                                  attach_file_1=test_file,
                                  attach_title_1="attachment",
                                  send="1",
                                  ))
        self.assertEquals(r.status_code, 302)
        
        l = LiaisonStatement.objects.all().order_by("-id")[0]
        self.assertEquals(l.from_group, from_group)
        self.assertEquals(l.from_contact.address, submitter.email_address())
        self.assertEquals(l.reply_to, "replyto@example.com")
        self.assertEquals(l.to_group, to_group)
        self.assertEquals(l.to_contact, "to_poc@example.com")
        self.assertEquals(l.response_contact, "responce_contact@example.com")
        self.assertEquals(l.technical_contact, "technical_contact@example.com")
        self.assertEquals(l.cc, "cc@example.com")
        self.assertEquals(l.purpose, LiaisonStatementPurposeName.objects.get(order=4))
        self.assertEquals(l.deadline, today + datetime.timedelta(days=1)),
        self.assertEquals(l.related_to, liaison),
        self.assertEquals(l.title, "title")
        self.assertEquals(l.submitted.date(), today)
        self.assertEquals(l.body, "body")
        self.assertTrue(not l.approved)
        
        self.assertEquals(l.attachments.count(), 1)
        attachment = l.attachments.all()[0]
        self.assertEquals(attachment.title, "attachment")
        with open(os.path.join(self.liaison_dir, attachment.external_url)) as f:
            written_content = f.read()

        test_file.seek(0)
        self.assertEquals(written_content, test_file.read())

        self.assertEquals(len(outbox), mailbox_before + 1)
        self.assertTrue("Liaison Statement" in outbox[-1]["Subject"])
        
        # try adding statement to non-predefined organization
        r = self.client.post(url,
                             dict(from_field="%s_%s" % (from_group.type_id, from_group.pk),
                                  from_fake_user=str(submitter.pk),
                                  approved="1",
                                  replyto="replyto@example.com",
                                  to_poc="to_poc@example.com",
                                  organization="othersdo",
                                  other_organization="Mars Institute",
                                  response_contact="responce_contact@example.com",
                                  technical_contact="technical_contact@example.com",
                                  cc1="cc@example.com",
                                  purpose="4",
                                  deadline_date=(today + datetime.timedelta(days=1)).strftime("%Y-%m-%d"),
                                  related_to=str(related_liaison.pk),
                                  title="new title",
                                  submitted_date=today.strftime("%Y-%m-%d"),
                                  body="body",
                                  ))
        self.assertEquals(r.status_code, 302)

        l = LiaisonStatement.objects.all().order_by("-id")[0]
        self.assertEquals(l.to_group, None)
        self.assertEquals(l.to_name, "Mars Institute")

    def test_send_sdo_reminder(self):
        make_test_data()
        liaison = make_liaison_models()

        from ietf.liaisons.mails import send_sdo_reminder

        mailbox_before = len(outbox)
        send_sdo_reminder(Group.objects.filter(type="sdo")[0])
        self.assertEquals(len(outbox), mailbox_before + 1)
        self.assertTrue("authorized individuals" in outbox[-1]["Subject"])

    def test_send_liaison_deadline_reminder(self):
        make_test_data()
        liaison = make_liaison_models()

        from ietf.liaisons.mails import possibly_send_deadline_reminder
        from ietf.liaisons.proxy import LiaisonDetailProxy as LiaisonDetail 

        l = LiaisonDetail.objects.all()[0]
        
        mailbox_before = len(outbox)
        possibly_send_deadline_reminder(l)
        self.assertEquals(len(outbox), mailbox_before + 1)
        self.assertTrue("deadline" in outbox[-1]["Subject"])

        # try pushing the deadline
        l.deadline = l.deadline + datetime.timedelta(days=30)
        l.save()
        
        mailbox_before = len(outbox)
        possibly_send_deadline_reminder(l)
        self.assertEquals(len(outbox), mailbox_before)

        
if not settings.USE_DB_REDESIGN_PROXY_CLASSES:
    # the above tests only work with the new schema
    del LiaisonManagementTestCase 
