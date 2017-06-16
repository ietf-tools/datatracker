# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import debug     # pyflakes:ignore

import contextlib
import os
import urllib2

from bs4 import BeautifulSoup
from tqdm import tqdm

from django.db import migrations
from django.conf import settings

def get_filename(doc):
    path = settings.DOCUMENT_PATH_PATTERN.format(doc=doc)
    # ! These files right now are created with no version number?
    #name = '%s-%s.txt' % (doc.name,doc.rev)
    name = '%s.txt' % (doc.name,)
    return os.path.join(path,name)

def forward(apps,schema_editor):
    # for each qualifying document
    Document = apps.get_model('doc','Document')

    for doc in tqdm(Document.objects.filter(type='review',external_url__contains="www.ietf.org/mail-archive/web"),desc="Pointers into Mhonarc"):
        filename = get_filename(doc)
        if not os.path.isfile(filename):
            with contextlib.closing(urllib2.urlopen(doc.external_url)) as infile:
                fullcontents = infile.read().decode('utf-8', 'ignore');
                start = fullcontents.find('<!--X-Body-of-Message-->')
                end = fullcontents.find('<!--X-Body-of-Message-End-->')
                bodyblock=fullcontents[start+len('<!--X-Body-of-Message-->'):end]
                text = BeautifulSoup(bodyblock,"lxml").get_text('\n\n') \
                           .replace('FAQ at <\n\nhttp://wiki.tools','FAQ at <http://wiki.tools') \
                           .replace('wiki/GenArtfaq\n\n>','wiki/GenArtfaq>')
                with contextlib.closing(open(filename,'w')) as outfile:
                    outfile.write(text.encode('utf8'))

    for doc in tqdm(Document.objects.filter(type='review',external_url__contains="mailarchive.ietf.org"),desc="Pointers into Mailarchive"):
        filename = get_filename(doc)
        if not os.path.isfile(filename):
            with contextlib.closing(urllib2.urlopen(doc.external_url)) as infile:
                fullcontents = infile.read().decode('utf-8', 'ignore');
                soup = BeautifulSoup(fullcontents,"lxml")
                divpre = soup.find('div',{"id":"msg-payload"}).find('pre')
                text = divpre.get_text('\n\n')
                with contextlib.closing(open(filename,'w')) as outfile:
                    outfile.write(text.encode('utf8'))

    ## After this migration, we should figure out what to do with these stragglers:
    ## In [29]: Document.objects.filter(type='review').exclude(Q(external_url__contains="mailarchive")|Q(external_url__contains="mail-archive")).values_list('external_url',flat=True)
    ## Out[29]: [u'https://art.tools.ietf.org/tools/art/genart/index.cgi/t=1909/review_edit?reviewid=2300', u'https://art.tools.ietf.org/tools/art/genart/index.cgi/t=8460/review_edit?reviewid=2735', u'https://www.ietf.org/ibin/c5i?mid=6&rid=49&gid=0&k1=933&k2=55337&tid=1296220835', u'https://www.ietf.org/mailman/private/tsv-dir/2012-February/002007.html', u'', u'']

def reverse(apps,schema_editor):
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('doc', '0016_auto_20160927_0713'),
    ]

    operations = [
        migrations.RunPython(forward,reverse)
    ]
