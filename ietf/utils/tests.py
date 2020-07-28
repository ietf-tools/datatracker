# Copyright The IETF Trust 2014-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import io
import os.path
import shutil
import sys
import types

from typing import Dict, List       # pyflakes:ignore

from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from fnmatch import fnmatch
from importlib import import_module
from .pipe import pipe
from textwrap import dedent
from unittest import skipIf
from tempfile import mkdtemp

from django.apps import apps
from django.contrib.auth.models import User
from django.conf import settings
from django.core.management import call_command
from django.template import Context
from django.template import Template    # pyflakes:ignore
from django.template.defaulttags import URLNode
from django.template.loader import get_template
from django.templatetags.static import StaticNode
from django.urls import reverse as urlreverse

import debug                            # pyflakes:ignore

from ietf.group.factories import GroupFactory
from ietf.group.models import Group
from ietf.person.name import name_parts, unidecode_name
from ietf.submit.tests import submission_file
from ietf.utils.bower_storage import BowerStorageFinder
from ietf.utils.draft import Draft, getmeta
from ietf.utils.log import unreachable, assertion
from ietf.utils.mail import send_mail_preformatted, send_mail_text, send_mail_mime, outbox, get_payload_text
from ietf.utils.test_runner import get_template_paths, set_coverage_checking
from ietf.utils.test_utils import TestCase

skip_wiki_glue_testing = False
skip_message_svn = ""
skip_message_trac = ""
try:
    import svn                          # pyflakes:ignore
except ImportError as e:
    skip_wiki_glue_testing = True
    skip_message_svn = "Skipping trac tests: %s" % e
    print("     "+skip_message_svn)

if sys.version_info.major==3:
    skip_version_trac = True
    skip_message_trac = "Skipping trac tests: Trac not available for Python3 as of 14 Jul 2019, 04 Jul 2020"
    print("     "+skip_message_trac)

class SendingMail(TestCase):

    def test_send_mail_preformatted(self):
        msg = """To: to1@example.com, to2@example.com
From: from1@ietf.org, from2@ietf.org
Cc: cc1@example.com, cc2@example.com
Bcc: bcc1@example.com, bcc2@example.com
Subject: subject

body
"""
        send_mail_preformatted(None, msg, {}, {})
        recv = outbox[-1]
        self.assertSameEmail(recv['To'], '<to1@example.com>, <to2@example.com>')
        self.assertSameEmail(recv['From'], 'from1@ietf.org, from2@ietf.org')
        self.assertSameEmail(recv['Cc'], 'cc1@example.com, cc2@example.com')
        self.assertSameEmail(recv['Bcc'], None)
        self.assertEqual(recv['Subject'], 'subject')
        self.assertEqual(get_payload_text(recv), 'body\n')

        override = {
            'To': 'oto1@example.net, oto2@example.net',
            'From': 'ofrom1@ietf.org, ofrom2@ietf.org',
            'Cc': 'occ1@example.net, occ2@example.net',
            'Subject': 'osubject',
        }
        send_mail_preformatted(request=None, preformatted=msg, extra={}, override=override)
        recv = outbox[-1]
        self.assertSameEmail(recv['To'], '<oto1@example.net>, <oto2@example.net>')
        self.assertSameEmail(recv['From'], 'ofrom1@ietf.org, ofrom2@ietf.org')
        self.assertSameEmail(recv['Cc'], 'occ1@example.net, occ2@example.net')
        self.assertSameEmail(recv['Bcc'], None)
        self.assertEqual(recv['Subject'], 'osubject')
        self.assertEqual(recv.get_payload(), 'body\n')

        override = {
            'To': ['<oto1@example.net>', 'oto2@example.net'],
            'From': ['<ofrom1@ietf.org>', 'ofrom2@ietf.org'],
            'Cc': ['<occ1@example.net>', 'occ2@example.net'],
            'Subject': 'osubject',
        }
        send_mail_preformatted(request=None, preformatted=msg, extra={}, override=override)
        recv = outbox[-1]
        self.assertSameEmail(recv['To'], '<oto1@example.net>, <oto2@example.net>')
        self.assertSameEmail(recv['From'], '<ofrom1@ietf.org>, ofrom2@ietf.org')
        self.assertSameEmail(recv['Cc'], '<occ1@example.net>, occ2@example.net')
        self.assertSameEmail(recv['Bcc'], None)
        self.assertEqual(recv['Subject'], 'osubject')
        self.assertEqual(get_payload_text(recv), 'body\n')

        extra = {'Fuzz': [ 'bucket' ]}
        send_mail_preformatted(request=None, preformatted=msg, extra=extra, override={})
        recv = outbox[-1]
        self.assertEqual(recv['Fuzz'], 'bucket')

        extra = {'Fuzz': ['bucket','monger']}
        send_mail_preformatted(request=None, preformatted=msg, extra=extra, override={})
        recv = outbox[-1]
        self.assertEqual(recv['Fuzz'], 'bucket, monger')

class TestSMTPServer(TestCase):

    def test_address_rejected(self):

        def send_simple_mail(to):
            send_mail_text(None, to=to, frm=None, subject="Test for rejection", txt="dummy body")

        len_before = len(outbox)
        send_simple_mail('good@example.com,poison@example.com')
        self.assertEqual(len(outbox),len_before+2)
        self.assertTrue('Some recipients were refused' in outbox[-1]['Subject'])

        len_before = len(outbox)
        send_simple_mail('poison@example.com')
        self.assertEqual(len(outbox),len_before+2)
        self.assertTrue('error while sending email' in outbox[-1]['Subject'])
        
    def test_rejecting_complex_mail(self):

        def send_complex_mail(to):
            msg = MIMEMultipart()
            textpart= MIMEText(dedent("""\
                             Sometimes people send mail with things like “smart quotes” in them.
                             Sometimes they have attachments with pictures.
                              """),_charset='utf-8')
            msg.attach(textpart)
            img = MIMEImage(b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x10\x00\x00\x00\x10\x08\x06\x00\x00\x00\x1f\xf3\xffa\x00\x00\x02\x88IDATx\xda\xa5\x93\xcbO\x13Q\x14\xc6\xbf\xb9\xd32}L\x9fZ\x06\x10Q\x90\x10\x85b\x89\xfe\x01\x06BXK"\xd4hB\xdc\xa0\x06q\xe1c% H1l\xd0\x8dbT6\x1a5\x91\x12#K\x891\xf2\x07\x98\xc8[L\x1ay\xa8@\xdb\xd0\xd2\xe9\x83N;\xbdc\x1f\x11\x03\x04\x17zW\'_\xce\xf9\xdd\xef\x9c\x9c\xc3\xe0?\x1f\xb3S\xf8\xfe\xba\xc2Be\xa9]m\xd6\x9e\xe6x\xde\x9e\xd1\xa4HdF\x0e\xc5G\x89\x8a{X\xec\xfc\x1a\xdc\x1307X\xd4$T\nC\xc6\xfc|\x13\x8d\xa6\x00\xe5O\x16\xd1\xb3\x10}\xbe\x90w\xce\xdbZyeed\x17\xc03(4\x15\x9d(s\x13\xca!\x10\xa6\xb0\x1a\xb6\x9b\x0b\x84\x95\xb4F@\x89\x84\xe5O\x0b\xcdG\xaf\xae\x8dl\x01V\x9f\x1d\xb4q\x16\xde\xa33[\x8d\xe3\x93)\xdc\x7f\x9b\xc4\xf3\x1b\x1c,|\xaex#\n\xb4\x0cH\xb8\xd6\xa8F\xad\x83El# \xc6\x83\xb1\xf2\xa2\x0bK\xfe,`y\xd0\xe6*<V\xda\x99\x92\x15\xb8\xdc\x14\xef>\x03\xaes\x0c\xea\xaas.\xc6g\x14t\xbcR\xd0P\x03t;\tX\x15\x83\xd5\xf9\xc5\xbe\x926_W6\xe3\xe7ca\xc2Z,82\xb1\xeb\r\x8b\xb1)\x82\xde\xa6\x14\xea\xec4\x0b\xf88K\xd0\xe5fQ_M\xd1s&\x95k\xe9\x87w\xf2\xc0eoM\x16\xe0\x1b*\xdc4XM\x9aL\xfca\x8e\xc5\xbd1\x0e//\xc6`\xd5\xe7Z\x08\xa6[8\xffT\x87\xeb\r\x12\xea\xabr\x80p \x14\xcfo]\xd5f\x01k\x8fl\x9bF3\xaf\xf9=\xb0X\x82\x81.O\xd96\xc4\x9d\x9a\xb8\x11\x89\x17\xb4\xf9s\x80\xe5\x01\xc3\xc4\xfe}FG\\\x064\xaa\xbf/\x0eM3\x92i\x13\xe1\x908Yr3\x9ck\xe1[\xbf\xd6%X\xf4\x9d\xef=z$(\xc1\xa9\xc3Q\xf0\x1c\xddV(\xa7\x18Ly9L\xafq8{\\D0\x14\xbd{\xe4V\xac3\x0bX\xe8\xd7\xdb\xb4,\xf5\x18\xb4j\xe3\xf8\xa2\x1e/\xa6\xac`\x18\x06\x02\x9f\x84\x8a\xa4\x07\x16c\xb1\xbe\xc9\xa2\xf6P\x04-\x8e\x00\x12\xc9\x84(&\xd9\xf2\x8a\x8e\x88\x7fk[\xbet\xe75\x0bzf\x98cI\xd6\xe6\xfc\xba\x06\xd3~\x1d\x12\xe9\x9fK\xcd\x12N\x16\xc4\xa0UQH)\x8a\x95\x08\x9c\xf6^\xc9\xbdk\x95\xe7o\xab\x9c&\xb5\xf2\x84W3\xa6\x9dG\x92\x19_$\xa9\x84\xd6%r\xc9\xde\x97\x1c\xde\xf3\x98\x96\xee\xb0\x16\x99\xd2v\x15\x94\xc6<\xc2Te\xb4\x04Ufe\x85\x8c2\x84<(\xeb\x91\xf7>\xa6\x7fy\xbf\x00\x96T\xff\x11\xf7\xd8R\xb9\x00\x00\x00\x00IEND\xaeB`\x82')

            msg.attach(img)
            send_mail_mime(request=None, to=to, frm=settings.DEFAULT_FROM_EMAIL, subject='это сложно', msg=msg, cc=None, extra=None)

        len_before = len(outbox)
        send_complex_mail('good@example.com')
        self.assertEqual(len(outbox),len_before+1)

        len_before = len(outbox)
        send_complex_mail('good@example.com,poison@example.com')
        self.assertEqual(len(outbox),len_before+2)


def get_callbacks(urllist, namespace=None):
    callbacks = set()
    def qualified(name):
        return '%s:%s' % (namespace, name) if namespace else name
    for entry in urllist:
        if hasattr(entry, 'url_patterns'):
            callbacks.update(get_callbacks(entry.url_patterns, entry.namespace))
        else:
            if hasattr(entry, '_callback_str'):
                callbacks.add(qualified(entry._callback_str))
            if (hasattr(entry, 'callback') and entry.callback and
                type(entry.callback) in [types.FunctionType, types.MethodType ]):
                    callbacks.add(qualified("%s.%s" % (entry.callback.__module__, entry.callback.__name__)))
            if hasattr(entry, 'name') and entry.name:
                callbacks.add(qualified(entry.name))
            if hasattr(entry, 'lookup_str') and entry.lookup_str:
                callbacks.add(qualified(entry.lookup_str))
            # There are some entries we don't handle here, mostly clases
            # (such as Feed subclasses)

    return list(callbacks)

class TemplateChecksTestCase(TestCase):

    paths = []                          # type: List[str]
    templates = {}                      # type: Dict[str, Template]

    def setUp(self):
        set_coverage_checking(False)
        self.paths = list(get_template_paths())
        self.paths.sort()
        for path in self.paths:
            try:
                self.templates[path] = get_template(path).template
            except Exception:
                pass

    def tearDown(self):
        set_coverage_checking(True)
        pass

    def test_parse_templates(self):
        errors = []
        for path in self.paths:
            for pattern in settings.TEST_TEMPLATE_IGNORE:
                if fnmatch(path, pattern):
                    continue
            if not path in self.templates:

                try:
                    get_template(path)
                except Exception as e:
                    errors.append((path, e))
        if errors:
            messages = [ "Parsing template '%s' failed with error: %s" % (path, ex) for (path, ex) in errors ]
            raise self.failureException("Template parsing failed for %s templates:\n  %s" % (len(errors), "\n  ".join(messages)))

    def apply_template_test(self, func, node_type, msg, *args, **kwargs):
        errors = []
        for path, template in self.templates.items():
            origin = str(template.origin).replace(settings.BASE_DIR, '')
            for node in template:
                for child in node.get_nodes_by_type(node_type):
                    errors += func(child, origin, *args, **kwargs)
        if errors:
            errors = list(set(errors))
            errors.sort()
            messages = [ msg % (k, v) for (k, v) in errors ]
            raise self.failureException("Found %s errors when trying to %s:\n  %s" %(len(errors), func.__name__.replace('_',' '), "\n  ".join(messages)))

    def test_template_url_lookup(self):
        """
        This test doesn't do full url resolving, using the appropriate contexts, as it
        simply doesn't have any context to use.  It only looks if there exists a URL
        pattern with the appropriate callback, callback string, or name.  If no matching
        urlconf can be found, a full resolution would also fail.
        """
        #
        import ietf.urls

        def check_that_url_tag_callbacks_exists(node, origin, callbacks):
            """
            Check that an URLNode's callback is in callbacks.
            """
            cb = node.view_name.token.strip("\"'")
            if cb in callbacks or cb.startswith("admin:"):
                return []
            else:
                return [ (origin, cb), ]
        #

        callbacks = get_callbacks(ietf.urls.urlpatterns)
        self.apply_template_test(check_that_url_tag_callbacks_exists, URLNode, 'In %s: Could not find urlpattern for "%s"', callbacks)

    def test_template_statics_exists(self):
        """
        This test checks that every static template tag found in the template files found
        by utils.test_runner.get_template_paths() actually resolves to a file that can be
        served.  If collectstatic is correctly set up and used, the results should apply
        to both development and production mode.
        """
        #
        def check_that_static_tags_resolve(node, origin, checked):
            """
            Check that a StaticNode resolves to an url that can be served.
            """
            url = node.render(Context((), {}))
            if url in checked:
                return []
            else:
                r = self.client.get(url)
                if r.status_code == 200:
                    checked[url] = origin
                    return []
                else:
                    return [(origin, url), ]
        #
        checked = {}
        # the test client will only return static files when settings.DEBUG is True:
        saved_debug = settings.DEBUG
        settings.DEBUG = True
        self.apply_template_test(check_that_static_tags_resolve, StaticNode, 'In %s: Could not find static file for "%s"', checked)
        settings.DEBUG = saved_debug

    def test_500_page(self):
        url = urlreverse('django.views.defaults.server_error')
        r = self.client.get(url)        
        self.assertTemplateUsed(r, '500.html')

@skipIf(skip_version_trac, skip_message_trac)
@skipIf(skip_wiki_glue_testing, skip_message_svn)
class TestWikiGlueManagementCommand(TestCase):

    def setUp(self):
        # We create temporary wiki and svn directories, and provide them to the management
        # command through command line switches.  We have to do it this way because the
        # management command reads in its own copy of settings.py in its own python
        # environment, so we can't modify it here.
        set_coverage_checking(False)
        self.wiki_dir_pattern = os.path.abspath('tmp-wiki-dir-root/%s')
        if not os.path.exists(os.path.dirname(self.wiki_dir_pattern)):
            os.mkdir(os.path.dirname(self.wiki_dir_pattern))
        self.svn_dir_pattern = os.path.abspath('tmp-svn-dir-root/%s')
        if not os.path.exists(os.path.dirname(self.svn_dir_pattern)):
            os.mkdir(os.path.dirname(self.svn_dir_pattern))

    def tearDown(self):
        shutil.rmtree(os.path.dirname(self.wiki_dir_pattern))
        shutil.rmtree(os.path.dirname(self.svn_dir_pattern))
        set_coverage_checking(True)

    def test_wiki_create_output(self):
        for group_type in ['wg','rg','ag','area','rag']:
            GroupFactory(type_id=group_type)
        groups = Group.objects.filter(
                        type__slug__in=['wg','rg','ag','area','rag'],
                        state__slug='active'
                    ).order_by('acronym')
        out = io.StringIO()
        err = io.StringIO()
        call_command('create_group_wikis', stdout=out, stderr=err, verbosity=2,
            wiki_dir_pattern=self.wiki_dir_pattern,
            svn_dir_pattern=self.svn_dir_pattern,
        )
        command_output = out.getvalue()
        command_errors = err.getvalue()
        self.assertEqual("", command_errors)
        for group in groups:
            self.assertIn("Processing group '%s'" % group.acronym, command_output)
            # Do a bit of verification using trac-admin, too
            admin_code, admin_output, admin_error = pipe(
                'trac-admin %s permission list' % (self.wiki_dir_pattern % group.acronym))
            self.assertEqual(admin_code, 0)
            roles = group.role_set.filter(name_id__in=['chair', 'secr', 'ad'])
            for role in roles:
                user = role.email.address.lower()
                self.assertIn("Granting admin permission for %s" % user, command_output)
                self.assertIn(user, admin_output)
            docs = group.document_set.filter(states__slug='active', type_id='draft')
            for doc in docs:
                name = doc.name
                name = name.replace('draft-','')
                name = name.replace(doc.stream_id+'-', '')
                name = name.replace(group.acronym+'-', '')
                self.assertIn("Adding component %s"%name, command_output)
        for page in settings.TRAC_WIKI_PAGES_TEMPLATES:
            self.assertIn("Adding page %s" % os.path.basename(page), command_output)
        self.assertIn("Indexing default repository", command_output)

OMITTED_APPS = [
    'ietf.secr.meetings',
    'ietf.secr.proceedings',
    'ietf.redirects',
]

class AdminTestCase(TestCase):
    def __init__(self, *args, **kwargs):
        self.apps = {}
        for app_name in settings.INSTALLED_APPS:
            if app_name.startswith('ietf') and not app_name in OMITTED_APPS:
                app = import_module(app_name)
                name = app_name.split('.',1)[-1]
                models_path = os.path.join(os.path.dirname(app.__file__), "models.py")
                if os.path.exists(models_path):
                    self.apps[name] = app_name
        super(AdminTestCase, self).__init__(*args, **kwargs)

    def test_all_model_admins_exist(self):

        User.objects.create_superuser('admin', 'admin@example.org', 'admin+password')
        self.client.login(username='admin', password='admin+password')
        rtop = self.client.get("/admin/")
        self.assertContains(rtop, 'Django administration')
        for name in self.apps:
            app_name = self.apps[name]
            self.assertContains(rtop, name)
            app = import_module(app_name)
            r = self.client.get('/admin/%s/'%name)
            #
            model_list = apps.get_app_config(name).get_models()
            for model in model_list:
                if model.__name__.startswith('Historical') and hasattr(model, "get_history_type_display"):
                    continue
                else:
                    self.assertContains(r, model._meta.model_name,
                        msg_prefix="There doesn't seem to be any admin API for model %s.models.%s"%(app.__name__,model.__name__,))

## One might think that the code below would work, but it doesn't ...

# def list_static_files(path):
#     r = Path(settings.STATIC_ROOT)
#     p = r / path
#     files =  list(p.glob('**/*'))
#     relfn = [ str(file.relative_to(r)) for file in files ] 
#     return relfn
# 
# class TestBowerStaticFiles(TestCase):
# 
#     def test_bower_static_file_finder(self):
#         from django.templatetags.static import static
#         bower_json = os.path.join(settings.BASE_DIR, 'bower.json')
#         with open(bower_json) as file:
#             bower_info = json.load(file)
#         for asset in bower_info["dependencies"]:
#             files = list_static_files(asset)
#             self.assertGreater(len(files), 0)
#             for file in files:
#                 url = static(file)
#                 debug.show('url')
#                 r = self.client.get(url)
#                 self.assertEqual(r.status_code, 200)

class TestBowerStaticFiles(TestCase):

    def test_bower_storage_finder(self):
        bfs = BowerStorageFinder()
        files = bfs.find('.')
        self.assertNotEqual(files,[])


class DraftTests(TestCase):

    def setUp(self):
        file,_ = submission_file(name='draft-test-draft-class',rev='00',format='txt',templatename='test_submission.txt',group=None)
        self.draft = Draft(text=file.getvalue(),source='draft-test-draft-class-00.txt',name_from_source=False)

    def test_get_status(self):
        self.assertEqual(self.draft.get_status(),'Informational')
    
    def test_get_authors(self):
        self.assertTrue(all([u'@' in author for author in self.draft.get_authors()]))

    def test_get_authors_with_firm(self):
        self.assertTrue(all([u'@' in author for author in self.draft.get_authors_with_firm()]))
        
    def test_old_get_refs(self):
        self.assertEqual(self.draft.old_get_refs()[1][0],u'rfc2119')

    def test_get_meta(self):
        tempdir = mkdtemp()
        filename = os.path.join(tempdir,self.draft.source)
        with io.open(filename,'w') as file:
            file.write(self.draft.text)
        self.assertEqual(getmeta(filename)['docdeststatus'],'Informational')
        shutil.rmtree(tempdir)


class NameTests(TestCase):

    def test_name_parts(self):
        names = (
            #name,                          (prefix, first, middle, last, suffix)
            ("Mart van Oostendorp",         ('', 'Mart', '', 'van Oostendorp', '')),
            ("Lina Heribert van Laon",      ('', 'Lina', 'Heribert', 'van Laon', '')),
            ("Daniél van Luin",             ('', 'Daniél', '', 'van Luin', '')),
            ("Dylano van 't Riet",          ('', 'Dylano', '', 'van \'t Riet', '')),
            ("Pedro de la Rosa",            ('', 'Pedro', '', 'de la Rosa', '')),
            ("Jim Bruijne van der Veen",    ('', 'Jim', 'Bruijne', 'van der Veen', '')),
            ("Mr. Fix Hollister",           ('Mr.', 'Fix', '', 'Hollister', '')),
            ("Donald E. Eastlake 3rd",      ('', 'Donald', 'E.', 'Eastlake', '3rd')),
            ("Professor André Danthine",    ('Professor', 'André', '', 'Danthine', '')),
            ("DENG Hui",                    ('', 'Hui', '', 'Deng', '')),
            ("ዳዊት በቀለ (Dawit Bekele)",      ('', 'ዳዊት', '', 'በቀለ', '')),
            ("",  ('', '', '', '', '')),
            ("",  ('', '', '', '', '')),
            ("",  ('', '', '', '', '')),
            ("",  ('', '', '', '', '')),
            )

        for name, parts in names:
            if name:
                self.assertEqual(parts, name_parts(name))


    def test_unidecode(self):
        names = (
            ("ዳዊት በቀለ",         ("Daawite Baqala", )),
            ("丽 郜",             ("Li Gao", )),
            ("कम्बोज डार",      ("Kmboj Ddaar", )),
            ("Ηράκλεια Λιόντη", ("Erakleia Lionte", )),
            ("ישראל רוזנפלד",   ("Yshrl Rvznpld", "Yshral Rvznpld", )),
            ("丽华 皇",            ("Li Hua Huang", )),
            ("نرگس پویان",      ("Nrgs Pwyn", )),
            ("موسوی سينا زمانی",("Mwswy Syn Zmny", )),
            ("Iñigo Sanç Ibáñez de la Peña",    ("Inigo Sanc Ibanez de La Pena", )),
            ("",    ("", )),
            )

        for name, ascii in names:
            if name:
                self.assertIn(unidecode_name(name), ascii)
            
class LogUtilTests(TestCase):
    def test_unreachable(self):
        with self.assertRaises(AssertionError):
            unreachable()
        settings.SERVER_MODE = 'development'
        unreachable()
        settings.SERVER_MODE = 'test'

    def test_assertion(self):
        with self.assertRaises(AssertionError):
            assertion('False')
        settings.DEBUG = False
        settings.SERVER_MODE = 'development'
        assertion('False')
        settings.SERVER_MODE = 'test'
