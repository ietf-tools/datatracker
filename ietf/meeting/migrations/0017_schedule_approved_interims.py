# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations
from collections import Counter

affected = ['interim-2010-drinks-1','interim-2010-core-1','interim-2010-behave-1','interim-2010-siprec-1','interim-2010-cuss-1','interim-2010-iri-1','interim-2010-pcp-1','interim-2010-geopriv-1','interim-2010-soc-1','interim-2010-precis-1','interim-2010-mptcp-1','interim-2010-roll-1','interim-2011-sipclf-1','interim-2011-ipsecme-1','interim-2011-siprec-1','interim-2011-alto-1','interim-2011-xmpp-1','interim-2011-precis-1','interim-2011-nfsv4-1','interim-2011-pcp-1','interim-2011-clue-1','interim-2011-oauth-1','interim-2011-rtcweb-1','interim-2011-drinks-1','interim-2011-atoca-1','interim-2011-cuss-1','interim-2011-softwire-1','interim-2011-ppsp-1','interim-2011-homenet-1','interim-2011-mptcp-1','interim-2012-rtcweb-1','interim-2012-drinks-1','interim-2012-sidr-1','interim-2012-clue-1','interim-2012-krb-wg-1','interim-2012-behave-1','interim-2012-bfcpbis-1','interim-2012-mboned-1']

def forward(apps, schema_editor):
    Session = apps.get_model('meeting','Session')
    assert( Counter(Session.objects.filter(meeting__number__in=affected).values_list('status',flat=True)) == Counter({u'appr':38}) )
    Session.objects.filter(meeting__number__in=affected).update(status_id='sched')

def reverse(apps, schema_editor):
    Session = apps.get_model('meeting','Session')
    Session.objects.filter(meeting__number__in=affected).update(status_id='appr')


class Migration(migrations.Migration):

    dependencies = [
        ('meeting', '0016_schedule_ietf88_and_89'),
    ]

    operations = [
        migrations.RunPython(forward,reverse),
    ]
