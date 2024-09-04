# Copyright The IETF Trust 2021 All Rights Reserved

import datetime
import debug    # pyflakes:ignore
import json
import os

from pathlib import Path
from pyquery import PyQuery
from random import randint
from tempfile import NamedTemporaryFile
from html import unescape

from django.conf import settings
from django.urls import reverse as urlreverse
from django.template.loader import render_to_string
from django.utils import timezone

from ietf.group.factories import RoleFactory
from ietf.doc.factories import BofreqFactory, NewRevisionDocEventFactory
from ietf.doc.models import State, Document, NewRevisionDocEvent
from ietf.doc.utils_bofreq import bofreq_editors, bofreq_responsible
from ietf.ietfauth.utils import has_role
from ietf.person.factories import PersonFactory
from ietf.person.models import Person
from ietf.utils.mail import outbox, empty_outbox
from ietf.utils.test_utils import TestCase, reload_db_objects, unicontent, login_testing_unauthorized
from ietf.utils.text import xslugify


class BofreqTests(TestCase):
    settings_temp_path_overrides = TestCase.settings_temp_path_overrides + ['BOFREQ_PATH']

    def write_bofreq_file(self, bofreq):
        fname = Path(settings.BOFREQ_PATH) / ("%s-%s.md" % (bofreq.name, bofreq.rev))
        with fname.open("w") as f:
            f.write(f"""# This is a test bofreq.
Version: {bofreq.rev}

## A section

This test section has some text.
""")

    def test_show_bof_requests(self):
        url = urlreverse('ietf.doc.views_bofreq.bof_requests')
        r = self.client.get(url)
        self.assertContains(r, 'There are currently no BOF Requests', status_code=200)
        states = State.objects.filter(type_id='bofreq')
        self.assertTrue(states.count()>0)
        for i in range(3*len(states)):
           BofreqFactory(states=[('bofreq',states[i%len(states)].slug)],newrevisiondocevent__time=timezone.now()-datetime.timedelta(days=randint(0,20)))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        for state in states:
            self.assertEqual(len(q(f'#bofreqs-{state.slug}')), 1 if state.slug!="spam" else 0)
            self.assertEqual(len(q(f'#bofreqs-{state.slug} tbody tr')), 3 if state.slug!="spam" else 0)
        self.assertFalse(q('#start_button'))
        PersonFactory(user__username='nobody')
        self.client.login(username='nobody', password='nobody+password')
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(q('#start_button'))
        self.client.logout()
        self.client.login(username='secretary', password='secretary+password')
        r = self.client.get(url)
        q = PyQuery(r.content)
        for state in states:
            self.assertEqual(len(q(f'#bofreqs-{state.slug}')), 1)
            self.assertEqual(len(q(f'#bofreqs-{state.slug} tbody tr')), 3)


    def test_bofreq_main_page(self):
        doc = BofreqFactory()
        doc.save_with_history(doc.docevent_set.all())
        self.write_bofreq_file(doc)
        nr_event = NewRevisionDocEventFactory(doc=doc,rev='01')
        doc.rev='01'
        doc.save_with_history([nr_event])
        self.write_bofreq_file(doc)
        editors = bofreq_editors(doc)
        responsible = bofreq_responsible(doc)
        url = urlreverse('ietf.doc.views_doc.document_main', kwargs=dict(name=doc.name))
        r = self.client.get(url)
        self.assertContains(r,'Version: 01',status_code=200)
        q = PyQuery(r.content)
        self.assertEqual(0, len(q('td.edit>a.btn')))
        self.assertEqual([],q('#change-request'))
        editor_row = q('#editors').html()
        for editor in editors:
            self.assertInHTML(editor.name, editor_row)
        responsible_row = q('#responsible').html()
        for leader in responsible:
            self.assertInHTML(leader.name,responsible_row)
        for user in ('secretary','ad','iab-member'): 
            self.client.login(username=user,password=user+"+password")
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)
            q = PyQuery(r.content)
            self.assertEqual(6, len(q('td.edit>a.btn')))
            self.client.logout()
            self.assertNotEqual([],q('#change-request'))
        editor = editors.first().user.username
        self.client.login(username=editor, password=editor+"+password")
        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        q = PyQuery(r.content)
        self.assertEqual(3, len(q('td.edit>a.btn')))
        self.assertNotEqual([],q('#change-request'))
        self.client.logout()
        url = urlreverse('ietf.doc.views_doc.document_main', kwargs=dict(name=doc,rev='00'))
        r = self.client.get(url)
        self.assertContains(r,'Version: 00',status_code=200)
        self.assertContains(r,'is for an older version')


    def test_edit_title(self):
        doc = BofreqFactory()
        editor = bofreq_editors(doc).first()
        url = urlreverse('ietf.doc.views_bofreq.edit_title', kwargs=dict(name=doc.name))
        title = doc.title
        r = self.client.post(url,dict(title='New title'))
        self.assertEqual(r.status_code, 302)
        doc = reload_db_objects(doc)
        self.assertEqual(title, doc.title)
        nobody = PersonFactory()
        self.client.login(username=nobody.user.username,password=nobody.user.username+'+password')
        r = self.client.post(url,dict(title='New title'))
        self.assertEqual(r.status_code, 403)
        doc = reload_db_objects(doc)
        self.assertEqual(title, doc.title)
        self.client.logout()
        for username in ('secretary', 'ad', 'iab-member', editor.user.username):
            self.client.login(username=username, password=username+'+password')
            r = self.client.get(url)
            self.assertEqual(r.status_code,200)
            docevent_count = doc.docevent_set.count()
            empty_outbox()
            r = self.client.post(url,dict(title=username))
            self.assertEqual(r.status_code,302)
            doc = reload_db_objects(doc)
            self.assertEqual(doc.title, username)
            self.assertEqual(docevent_count+1, doc.docevent_set.count())
            self.assertEqual(1, len(outbox)) 
            self.client.logout()

    def state_pk_as_str(self, type_id, slug):
        return str(State.objects.get(type_id=type_id, slug=slug).pk)

    def test_edit_state(self):
        doc = BofreqFactory()
        editor = bofreq_editors(doc).first()
        url = urlreverse('ietf.doc.views_bofreq.change_state', kwargs=dict(name=doc.name))
        state = doc.get_state('bofreq')
        r = self.client.post(url, dict(new_state=self.state_pk_as_str('bofreq','approved')))
        self.assertEqual(r.status_code, 302)
        doc = reload_db_objects(doc)
        self.assertEqual(state, doc.get_state('bofreq'))
        self.client.login(username=editor.user.username,password=editor.user.username+'+password')
        r = self.client.post(url, dict(new_state=self.state_pk_as_str('bofreq','approved')))
        self.assertEqual(r.status_code, 403)
        doc = reload_db_objects(doc)
        self.assertEqual(state,doc.get_state('bofreq'))
        self.client.logout()
        for username in ('secretary', 'ad', 'iab-member'):
            doc.set_state(state)
            self.client.login(username=username,password=username+'+password')
            r = self.client.get(url)
            self.assertEqual(r.status_code,200)
            docevent_count = doc.docevent_set.count()
            r = self.client.post(url,dict(new_state=self.state_pk_as_str('bofreq','approved' if username=='secretary' else 'declined'),comment=f'{username}-2309hnf'))
            self.assertEqual(r.status_code,302)
            doc = reload_db_objects(doc)
            self.assertEqual('approved' if username=='secretary' else 'declined',doc.get_state_slug('bofreq'))
            self.assertEqual(docevent_count+2, doc.docevent_set.count())
            self.assertIn(f'{username}-2309hnf',doc.latest_event(type='added_comment').desc)
            self.client.logout()

    def test_change_editors(self):
        doc = BofreqFactory()
        previous_editors = list(bofreq_editors(doc))
        acting_editor = previous_editors[0]
        new_editors = set(previous_editors)
        new_editors.discard(acting_editor)
        new_editors.add(PersonFactory())
        url = urlreverse('ietf.doc.views_bofreq.change_editors', kwargs=dict(name=doc.name))
        postdict = dict(editors=[str(p.pk) for p in new_editors])
        r = self.client.post(url, postdict)
        self.assertEqual(r.status_code,302)
        editors = bofreq_editors(doc)
        self.assertEqual(set(previous_editors),set(editors))
        nobody = PersonFactory()
        self.client.login(username=nobody.user.username,password=nobody.user.username+'+password')
        r = self.client.post(url, postdict)
        self.assertEqual(r.status_code,403)
        editors = bofreq_editors(doc)
        self.assertEqual(set(previous_editors),set(editors))
        self.client.logout()
        for username in (previous_editors[0].user.username, 'secretary', 'ad', 'iab-member'):
            empty_outbox()
            self.client.login(username=username,password=username+'+password')
            r = self.client.get(url)
            self.assertEqual(r.status_code,200)
            # Yes, unescape is needed twice, for names like "O'Connor"
            unescaped = unescape(unescape(unicontent(r).encode('utf-8').decode('unicode-escape')))
            for editor in previous_editors:
                self.assertIn(editor.name,unescaped)
            new_editors = set(previous_editors)
            new_editors.discard(acting_editor)
            new_editors.add(PersonFactory())
            postdict = dict(editors=[str(p.pk) for p in new_editors])
            r = self.client.post(url,postdict)
            self.assertEqual(r.status_code, 302)
            updated_editors = bofreq_editors(doc)
            self.assertEqual(new_editors,set(updated_editors))
            previous_editors = new_editors
            self.client.logout()
            self.assertEqual(len(outbox),1)
            self.assertIn('BOF Request editors changed',outbox[0]['Subject'])


    def test_change_responsible(self):
        doc = BofreqFactory()
        previous_responsible = list(bofreq_responsible(doc))
        new_responsible = set(previous_responsible[1:])
        new_responsible.add(RoleFactory(group__type_id='area',name_id='ad').person)
        url = urlreverse('ietf.doc.views_bofreq.change_responsible', kwargs=dict(name=doc.name))
        postdict = dict(responsible=[str(p.pk) for p in new_responsible])
        r = self.client.post(url, postdict)
        self.assertEqual(r.status_code,302)
        responsible = bofreq_responsible(doc)
        self.assertEqual(set(previous_responsible), set(responsible))
        PersonFactory(user__username='nobody')
        self.client.login(username='nobody',password='nobody+password')
        r = self.client.post(url, postdict)
        self.assertEqual(r.status_code,403)
        responsible = bofreq_responsible(doc)
        self.assertEqual(set(previous_responsible), set(responsible))
        self.client.logout()
        for username in ('secretary', 'ad', 'iab-member'):
            empty_outbox()
            self.client.login(username=username,password=username+'+password')
            r = self.client.get(url)
            self.assertEqual(r.status_code,200)
            # Yes, unescape is needed twice, for names like "O'Connor"
            unescaped = unescape(unescape(unicontent(r).encode('utf-8').decode('unicode-escape')))
            for responsible in previous_responsible: 
                self.assertIn(responsible.name, unescaped)
            new_responsible = set(previous_responsible)
            new_responsible.add(RoleFactory(group__type_id='area',name_id='ad').person)
            postdict = dict(responsible=[str(p.pk) for p in new_responsible])
            r = self.client.post(url,postdict)
            self.assertEqual(r.status_code, 302)
            updated_responsible = bofreq_responsible(doc)
            self.assertEqual(new_responsible,set(updated_responsible))
            previous_responsible = new_responsible
            self.client.logout()
            self.assertEqual(len(outbox),1)
            self.assertIn('BOF Request responsible leadership changed',outbox[0]['Subject'])

    def test_change_responsible_validation(self):
        doc = BofreqFactory()
        url = urlreverse('ietf.doc.views_bofreq.change_responsible', kwargs=dict(name=doc.name))
        login_testing_unauthorized(self,'secretary',url)
        bad_batch = PersonFactory.create_batch(3)
        good_batch = list()
        good_batch.append(RoleFactory(group__type_id='area', name_id='ad').person)
        good_batch.append(RoleFactory(group__acronym='iab', name_id='member').person)
        pks = set()
        pks.update([p.pk for p in good_batch])
        pks.update([p.pk for p in bad_batch])
        postdict = dict(responsible=[str(pk) for pk in pks])
        r = self.client.post(url,postdict)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        error_text = q('.invalid-feedback').text()
        for p in good_batch:
            self.assertNotIn(p.plain_name(), error_text)
        for p in bad_batch:
            self.assertIn(p.plain_name(), error_text)

    def test_change_responsible_options(self):
        """Only valid options should be offered for responsible leadership field"""
        doc = BofreqFactory()
        url = urlreverse('ietf.doc.views_bofreq.change_responsible', kwargs={'name': doc.name})
        self.client.login(username='secretary', password='secretary+password')
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        option_ids = [opt['id'] for opt in json.loads(q('#id_responsible').attr('data-pre'))]
        ad_people = [p for p in Person.objects.all() if has_role(p.user, 'Area Director')]
        iab_people = [p for p in Person.objects.all() if has_role(p.user, 'IAB')]
        self.assertGreater(len(ad_people), 0, 'Need at least one AD')
        self.assertGreater(len(iab_people), 0, 'Need at least one IAB member')
        self.assertGreater(Person.objects.count(), len(ad_people) + len(iab_people),
                           'Need at least one Person not an AD nor IAB member')
        # Next line will fail if there's overlap between ad_people and iab_people. This is by design.
        # If the test setup changes and overlap is expected, need to separately check that area directors
        # and IAB members wind up in the options list.
        self.assertCountEqual(option_ids, [p.pk for p in ad_people + iab_people])

    def test_submit(self):
        doc = BofreqFactory()
        url = urlreverse('ietf.doc.views_bofreq.submit', kwargs=dict(name=doc.name))

        rev = doc.rev
        r = self.client.post(url,{'bofreq_submission':'enter','bofreq_content':'# oiwefrase'})
        self.assertEqual(r.status_code, 302)
        doc = reload_db_objects(doc)
        self.assertEqual(rev, doc.rev)

        nobody = PersonFactory()
        self.client.login(username=nobody.user.username, password=nobody.user.username+'+password')
        r = self.client.post(url,{'bofreq_submission':'enter','bofreq_content':'# oiwefrase'})
        self.assertEqual(r.status_code, 403)
        doc = reload_db_objects(doc)
        self.assertEqual(rev, doc.rev)
        self.client.logout()

        editor = bofreq_editors(doc).first()
        for username in ('secretary', 'ad', 'iab-member', editor.user.username):
            self.client.login(username=username, password=username+'+password')
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)
            file = NamedTemporaryFile(delete=False,mode="w+",encoding='utf-8')
            file.write(f'# {username}')
            file.close()
            try:
                with open(file.name, 'rb') as bofreq_fd:
                    for postdict in [
                                {'bofreq_submission':'enter','bofreq_content':f'# {username}'},
                                {'bofreq_submission':'upload','bofreq_file':bofreq_fd},
                            ]:
                        docevent_count = doc.docevent_set.count()
                        empty_outbox()
                        r = self.client.post(url, postdict)
                        self.assertEqual(r.status_code, 302)
                        doc = reload_db_objects(doc)
                        self.assertEqual('%02d'%(int(rev)+1) ,doc.rev)
                        self.assertEqual(f'# {username}', doc.text())
                        self.assertEqual(docevent_count+1, doc.docevent_set.count())
                        self.assertEqual(1, len(outbox))
                        rev = doc.rev
            finally:
                os.unlink(file.name)

            self.client.logout()

    def test_start_new_bofreq(self):
        url = urlreverse('ietf.doc.views_bofreq.new_bof_request')
        nobody = PersonFactory()
        login_testing_unauthorized(self,nobody.user.username,url)
        r = self.client.get(url)
        self.assertContains(r,'Fill in the details below. Keep items in the order they appear here.',status_code=200)
        r = self.client.post(url, dict(title='default', 
                                       bofreq_submission='enter',
                                       bofreq_content=render_to_string('doc/bofreq/bofreq_template.md',{'settings': settings})))
        self.assertContains(r, 'The example content may not be saved.', status_code=200)
        file = NamedTemporaryFile(delete=False,mode="w+",encoding='utf-8')
        file.write('some stuff')
        file.close()
        try:
            with open(file.name,'rb') as bofreq_fd:
                for postdict in [
                                    dict(title='title one', bofreq_submission='enter', bofreq_content='some stuff'),
                                    dict(title='title two', bofreq_submission='upload', bofreq_file=bofreq_fd),
                                ]:
                    empty_outbox()
                    r = self.client.post(url, postdict)
                    self.assertEqual(r.status_code,302)
                    name = f"bofreq-{xslugify(nobody.last_name())[:64]}-{postdict['title']}".replace(' ','-')
                    bofreq = Document.objects.filter(name=name,type_id='bofreq').first()
                    self.assertIsNotNone(bofreq)
                    self.assertEqual(bofreq.title, postdict['title'])
                    self.assertEqual(bofreq.rev, '00')
                    self.assertEqual(bofreq.get_state_slug(), 'proposed')
                    self.assertEqual(list(bofreq_editors(bofreq)), [nobody])
                    self.assertEqual(bofreq.latest_event(NewRevisionDocEvent).rev, '00')
                    self.assertEqual(bofreq.text_or_error(), 'some stuff')
                    self.assertEqual(len(outbox),1)
        finally:
            os.unlink(file.name)
        existing_bofreq = BofreqFactory(requester_lastname=nobody.last_name())
        for postdict in [
                            dict(title='', bofreq_submission='enter', bofreq_content='some stuff'),
                            dict(title='a title', bofreq_submission='enter', bofreq_content=''),
                            dict(title=existing_bofreq.title, bofreq_submission='enter', bofreq_content='some stuff'),
                            dict(title='森川', bofreq_submission='enter', bofreq_content='some stuff'),
                            dict(title='a title', bofreq_submission='', bofreq_content='some stuff'),
                        ]:
            r = self.client.post(url,postdict)
            self.assertEqual(r.status_code, 200, f'Wrong status_code for {postdict}')
            q = PyQuery(r.content)
            self.assertTrue(q('form div.is-invalid'), f'Expected an error for {postdict}')

    def test_post_proposed_restrictions(self):
        states = State.objects.filter(type_id='bofreq').exclude(slug='proposed')
        bofreq = BofreqFactory()
        editor = bofreq_editors(bofreq).first()

        for view in ('submit', 'change_editors', 'edit_title'):
            url = urlreverse(f'ietf.doc.views_bofreq.{view}', kwargs=dict(name=bofreq.name))
            for state in states:
                bofreq.set_state(state)
                for username in ('secretary', 'ad', 'iab-member'):
                    self.client.login(username=username, password=username+'+password')
                    r = self.client.get(url)
                    self.assertEqual(r.status_code,200)
                    self.client.logout()
                self.client.login(username=editor.user.username, password=editor.user.username+'+password')   
                r = self.client.get(url)
                self.assertEqual(r.status_code, 403, f'editor should not be able to use {view} in state {state.slug}')
                self.client.logout()

        url = urlreverse('ietf.doc.views_doc.document_main', kwargs=dict(name=bofreq.name))
        self.client.login(username=editor.user.username, password=editor.user.username+'+password')   
        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        q = PyQuery(r.content)
        self.assertEqual(0, len(q('td.edit>a.btn')))
        self.assertEqual([],q('#change-request'))
