import datetime

from django.conf import settings
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse as urlreverse
import django.test
from pyquery import PyQuery

from ietf.utils.test_utils import SimpleUrlTestCase, canonicalize_feed, canonicalize_sitemap, login_testing_unauthorized
from ietf.utils.test_runner import mail_outbox
from ietf.utils.test_data import make_test_data

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
    from redesign.person.models import Person, Email
    from redesign.group.models import Group, Role
        
def make_liaison_models():
    sdo = Group.objects.create(
        name="United League of Marsmen",
        acronym="",
        state_id="active",
        type_id="sdo",
        )

    u = User.objects.create(username="zrk")
    p = Person.objects.create(
        name="Zrk Brekkk",
        ascii="Zrk Brekkk",
        user=u)
    email = Email.objects.create(
        address="zrk@ulm.mars",
        person=p)
    Role.objects.create(
        name_id="liaiman",
        group=sdo,
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
        from_contact=email,
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
        r = self.client.post(url, dict(do_action_taken=1))
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEquals(len(q('form input[name=do_action_taken]')), 0)
        liaison = LiaisonStatement.objects.get(id=liaison.id)
        self.assertTrue(liaison.action_taken)

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
        r = self.client.post(url,
                             dict(from_field="from",
                                  replyto="replyto@example.com",
                                  organization="org",
                                  to_poc="to_poc@example.com",
                                  response_contact="responce_contact@example.com",
                                  technical_contact="technical_contact@example.com",
                                  cc1="cc1@example.com",
                                  purpose="4",
                                  deadline_date=(liaison.deadline + datetime.timedelta(days=1)).strftime("%Y-%m-%d"),
                                  title="title",
                                  submitted_date=(liaison.submitted + datetime.timedelta(days=1)).strftime("%Y-%m-%d"),
                                  body="body",
                                  ))
        self.assertEquals(r.status_code, 302)
        new_liaison = LiaisonStatement.objects.get(id=liaison.id)
        self.assertEquals(new_liaison.from_name, "from")
        self.assertEquals(new_liaison.reply_to, "replyto@example.com")
        self.assertEquals(new_liaison.to_name, "org")
        self.assertEquals(new_liaison.to_contact, "to_poc@example.com")
        self.assertEquals(new_liaison.response_contact, "responce_contact@example.com")
        self.assertEquals(new_liaison.technical_contact, "technical_contact@example.com")
        self.assertEquals(new_liaison.cc, "cc1@example.com")
        self.assertEquals(new_liaison.purpose, LiaisonStatementPurposeName.objects.get(order=4))
        self.assertEquals(new_liaison.deadline, liaison.deadline + datetime.timedelta(days=1)),
        self.assertEquals(new_liaison.title, "title")
        self.assertEquals(new_liaison.submitted.date(), (liaison.submitted + datetime.timedelta(days=1)).date())
        self.assertEquals(new_liaison.body, "body")
        self.assertTrue(new_liaison.modified > liaison.modified)
        
    # test links and edit button
        
if not settings.USE_DB_REDESIGN_PROXY_CLASSES:
    # the above tests only work with the new schema
    del LiaisonManagementTestCase 
