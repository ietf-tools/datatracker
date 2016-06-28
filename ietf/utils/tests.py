# -*- coding: utf-8 -*-
import os.path
import types
#import json
#from pathlib import Path

from textwrap import dedent
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart

from django.conf import settings
from django.template import Context
from django.template.defaulttags import URLNode
from django.templatetags.static import StaticNode
from django.template.loaders.filesystem import Loader
from django.test import TestCase

import debug                            # pyflakes:ignore

import ietf.urls
from ietf.utils.management.commands import pyflakes
from ietf.utils.mail import send_mail_text, send_mail_mime, outbox 
from ietf.utils.test_runner import get_template_paths

class PyFlakesTestCase(TestCase):

    def test_pyflakes(self):
        self.maxDiff = None
        path = os.path.join(settings.BASE_DIR)
        warnings = []
        warnings = pyflakes.checkPaths([path], verbosity=0)
        self.assertEqual([str(w) for w in warnings], [])

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
            textpart= MIMEText(dedent(u"""\
                             Sometimes people send mail with things like “smart quotes” in them.
                             Sometimes they have attachments with pictures.
                              """),_charset='utf-8')
            msg.attach(textpart)
            img = MIMEImage('\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x10\x00\x00\x00\x10\x08\x06\x00\x00\x00\x1f\xf3\xffa\x00\x00\x02\x88IDATx\xda\xa5\x93\xcbO\x13Q\x14\xc6\xbf\xb9\xd32}L\x9fZ\x06\x10Q\x90\x10\x85b\x89\xfe\x01\x06BXK"\xd4hB\xdc\xa0\x06q\xe1c% H1l\xd0\x8dbT6\x1a5\x91\x12#K\x891\xf2\x07\x98\xc8[L\x1ay\xa8@\xdb\xd0\xd2\xe9\x83N;\xbdc\x1f\x11\x03\x04\x17zW\'_\xce\xf9\xdd\xef\x9c\x9c\xc3\xe0?\x1f\xb3S\xf8\xfe\xba\xc2Be\xa9]m\xd6\x9e\xe6x\xde\x9e\xd1\xa4HdF\x0e\xc5G\x89\x8a{X\xec\xfc\x1a\xdc\x1307X\xd4$T\nC\xc6\xfc|\x13\x8d\xa6\x00\xe5O\x16\xd1\xb3\x10}\xbe\x90w\xce\xdbZyeed\x17\xc03(4\x15\x9d(s\x13\xca!\x10\xa6\xb0\x1a\xb6\x9b\x0b\x84\x95\xb4F@\x89\x84\xe5O\x0b\xcdG\xaf\xae\x8dl\x01V\x9f\x1d\xb4q\x16\xde\xa33[\x8d\xe3\x93)\xdc\x7f\x9b\xc4\xf3\x1b\x1c,|\xaex#\n\xb4\x0cH\xb8\xd6\xa8F\xad\x83El# \xc6\x83\xb1\xf2\xa2\x0bK\xfe,`y\xd0\xe6*<V\xda\x99\x92\x15\xb8\xdc\x14\xef>\x03\xaes\x0c\xea\xaas.\xc6g\x14t\xbcR\xd0P\x03t;\tX\x15\x83\xd5\xf9\xc5\xbe\x926_W6\xe3\xe7ca\xc2Z,82\xb1\xeb\r\x8b\xb1)\x82\xde\xa6\x14\xea\xec4\x0b\xf88K\xd0\xe5fQ_M\xd1s&\x95k\xe9\x87w\xf2\xc0eoM\x16\xe0\x1b*\xdc4XM\x9aL\xfca\x8e\xc5\xbd1\x0e//\xc6`\xd5\xe7Z\x08\xa6[8\xffT\x87\xeb\r\x12\xea\xabr\x80p \x14\xcfo]\xd5f\x01k\x8fl\x9bF3\xaf\xf9=\xb0X\x82\x81.O\xd96\xc4\x9d\x9a\xb8\x11\x89\x17\xb4\xf9s\x80\xe5\x01\xc3\xc4\xfe}FG\\\x064\xaa\xbf/\x0eM3\x92i\x13\xe1\x908Yr3\x9ck\xe1[\xbf\xd6%X\xf4\x9d\xef=z$(\xc1\xa9\xc3Q\xf0\x1c\xddV(\xa7\x18Ly9L\xafq8{\\D0\x14\xbd{\xe4V\xac3\x0bX\xe8\xd7\xdb\xb4,\xf5\x18\xb4j\xe3\xf8\xa2\x1e/\xa6\xac`\x18\x06\x02\x9f\x84\x8a\xa4\x07\x16c\xb1\xbe\xc9\xa2\xf6P\x04-\x8e\x00\x12\xc9\x84(&\xd9\xf2\x8a\x8e\x88\x7fk[\xbet\xe75\x0bzf\x98cI\xd6\xe6\xfc\xba\x06\xd3~\x1d\x12\xe9\x9fK\xcd\x12N\x16\xc4\xa0UQH)\x8a\x95\x08\x9c\xf6^\xc9\xbdk\x95\xe7o\xab\x9c&\xb5\xf2\x84W3\xa6\x9dG\x92\x19_$\xa9\x84\xd6%r\xc9\xde\x97\x1c\xde\xf3\x98\x96\xee\xb0\x16\x99\xd2v\x15\x94\xc6<\xc2Te\xb4\x04Ufe\x85\x8c2\x84<(\xeb\x91\xf7>\xa6\x7fy\xbf\x00\x96T\xff\x11\xf7\xd8R\xb9\x00\x00\x00\x00IEND\xaeB`\x82')

            msg.attach(img)
            send_mail_mime(request=None, to=to, frm=settings.DEFAULT_FROM_EMAIL, subject=u'это сложно', msg=msg, cc=None, extra=None)

        len_before = len(outbox)
        send_complex_mail('good@example.com')
        self.assertEqual(len(outbox),len_before+1)

        len_before = len(outbox)
        send_complex_mail('good@example.com,poison@example.com')
        self.assertEqual(len(outbox),len_before+2)


def get_callbacks(urllist):
    callbacks = set()
    for entry in urllist:
        if hasattr(entry, 'url_patterns'):
            callbacks.update(get_callbacks(entry.url_patterns))
        else:
            if hasattr(entry, '_callback_str'):
                callbacks.add(unicode(entry._callback_str))
            if (hasattr(entry, 'callback') and entry.callback
                and type(entry.callback) in [types.FunctionType, types.MethodType ]):
                callbacks.add("%s.%s" % (entry.callback.__module__, entry.callback.__name__))
            if hasattr(entry, 'name') and entry.name:
                callbacks.add(unicode(entry.name))
            # There are some entries we don't handle here, mostly clases
            # (such as Feed subclasses)

    return list(callbacks)

class TemplateChecksTestCase(TestCase):

    paths = []
    templates = {}

    def setUp(self):
        self.loader = Loader()
        self.paths = list(get_template_paths())
        self.paths.sort()
        for path in self.paths:
            try:
                self.templates[path], _ = self.loader.load_template(path)
            except Exception:
                pass

    def tearDown(self):
        pass

    def test_parse_templates(self):
        errors = []
        for path in self.paths:
            if not path in self.templates:
                try:
                    self.loader.load_template(path)
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
        def check_that_url_tag_callbacks_exists(node, origin, callbacks):
            """
            Check that an URLNode's callback is in callbacks.
            """
            cb = node.view_name.token.strip("\"'")
            if cb in callbacks:
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
