# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import datetime
from django.db import migrations

import debug        # pyflakes:ignore

definite_bof_conc = [
    'afic',
    'dnsevolv',
    'fddifs',
    'icp',
    'ietfgrow',
    'ios',
    'ipdecide',
    'mailftp',
    'osiextnd',
    'ramp',
    'skey',
    'termacct',
    'tpcint',
    'usm',
    'vtp',
]

maybe_bof_conc = [
    'ima',
    'nsfnet',
    'resdisc',
    'shr',
    'tadmin',
    'tsess',
    'txwg',
    'x3s3.3',
]

had_no_parent = {
    'acct2':  'ops-old',
    'gisd':   'ops-old',
    'ire':    'ops-old',
    'newdom': 'ops-old',
    'ucp':    'ops-old',
    'dfs':    'usv',
}

make_into_team = [
    'isoc-old',
    'iahc',
]

change_parents = {
    'bgpdepl': {'old':'ops','new':'ops-old'},
    'cidrd': {'old':'ops','new':'ops-old'},
    'eii': {'old':'ops','new':'ops-old'},
    'netstat': {'old':'ops','new':'ops-old'},
    'njm': {'old':'ops','new':'ops-old'},
    'noop': {'old':'osi','new':'ops-old'},
    'opstat': {'old':'ops','new':'ops-old'},
    'thinosi': {'old':'app','new':'osi'},
    'wpkops': {'old':'ops','new':'ops-old'},
    'poised': {'old':'adm','new':'gen'},
    'poised95': {'old':'adm','new':'gen'},
    'ietfgrow': {'old':'adm','new':'gen'},
    'stdguide': {'old':'adm','new':'usv'},
    'inaparch': {'old':'adm','new':'gen'},
    'intprop': {'old':'adm','new':'gen'},
    'iahc': {'old':'adm', 'new':'gen' },
    'newgen': {'old':'adm', 'new':'gen' },

}


def forward(apps, schema_editor):
    Group = apps.get_model('group','Group')
    Document = apps.get_model('doc','Document')


    # Verify assumptions
    for acronym in definite_bof_conc:
        assert Group.objects.filter(acronym=acronym,state_id='conclude').exists(), '%s not found or not concluded'%acronym
    for acronym in maybe_bof_conc:
        assert Group.objects.filter(acronym=acronym,state_id='conclude').exists(), '%s not found or not concluded'%acronym

    for acronym in had_no_parent:
        assert Group.objects.filter(acronym=acronym,parent__isnull=True).exists(), '%s not found or has a parent' % acronym
    for acronym in change_parents:
        assert Group.objects.filter(acronym=acronym,parent__acronym=change_parents[acronym]['old']).exists(),'%s not found or parent is not %s'%(acronym,change_parents[acronym]['old'])

    for acronym in make_into_team:
        assert Group.objects.filter(acronym=acronym,type_id='wg').exists(),'%s not found or is not a WG'%acronym

    Group.objects.filter(acronym__in=definite_bof_conc).update(state_id='bof-conc')
    Group.objects.filter(acronym__in=maybe_bof_conc).update(state_id='bof-conc')

    for acronym in had_no_parent:
        g=Group.objects.get(acronym=acronym)
        g.parent = Group.objects.get(acronym=had_no_parent[acronym])
        g.save()
    
    for acronym in change_parents:
        g=Group.objects.get(acronym=acronym)
        g.parent = Group.objects.get(acronym=change_parents[acronym]['new'])
        g.save()

    for acronym in make_into_team:
        g=Group.objects.get(acronym=acronym)
        g.type_id='team'
        g.save()

    gen = Group.objects.get(acronym='gen')
    Document.objects.filter(name='draft-rescorla-sec-cons').update(group=gen)

    Group.objects.filter(acronym='adm').delete()
    
def reverse(apps, schema_editor):
    Group = apps.get_model('group','Group')
    ChangeStateGroupEvent = apps.get_model('group','ChangeStateGroupEvent')
    Person = apps.get_model('person','Person')
    Document = apps.get_model('doc','Document')

    # Reconstitute the adm area
        
    adm = Group.objects.create(acronym='adm',
                               type_id='area',
                               name='ops',
                               state_id='unknown',
                               parent = Group.objects.get(acronym='iesg'),
                              )

    Group.objects.filter(acronym__in=definite_bof_conc).update(state_id='conclude')
    Group.objects.filter(acronym__in=maybe_bof_conc).update(state_id='conclude')

    for acronym in had_no_parent:
        g=Group.objects.get(acronym=acronym)
        g.parent_id = None
        g.save()
    
    for acronym in change_parents:
        g=Group.objects.get(acronym=acronym)
        g.parent = Group.objects.get(acronym=change_parents[acronym]['old'])
        g.save()

    for acronym in make_into_team:
        g=Group.objects.get(acronym=acronym)
        g.type_id = 'wg'
        g.save()

    adm.communitylist_set.create()

    create_time = datetime.datetime(2011,12,9,12,0,0)
    event_time = datetime.datetime(1997,1,1,12, 0,0)
    system = Person.objects.get(name='(System)')
    names = [
            'Dr. Borka Jerman-Blazic',
            'Stephen J. Coya',
            'Piet Bovenga',
            'Bernhard Stockman',
            'Paul-Andre Pays',
            'Brian Gilmore',
            'Jill Foster',
            'Dr. Klaus Truoel',
            'Jean-Paul Le Guigner',
            'Urs Eppenberger',
            'Christian Tschudin',
            'David Oran',
    ]
    persons = dict()
    for name in names:
        persons[name] = Person.objects.get(name=name)

    adm.role_set.create(name_id='ad',person=persons['Stephen J. Coya'],email=persons['Stephen J. Coya'].email_set.first())
    adm.role_set.create(name_id='ad',person=persons['David Oran'],email=persons['David Oran'].email_set.first())

    g = Group.objects.create(name='Working Group on International Character Sets',
                             acronym='wg-char',
                             time=create_time,
                             parent=adm,
                             type_id='wg',
                             state_id='conclude')
    ChangeStateGroupEvent.objects.create(group=g,time=event_time,by=system,desc='Concluded group',state_id='conclude')
    g.role_set.create(name_id='chair',person=persons['Dr. Borka Jerman-Blazic'],email=persons['Dr. Borka Jerman-Blazic'].email_set.first())
    g.role_set.create(name_id='ad',person=persons['Stephen J. Coya'],email=persons['Stephen J. Coya'].email_set.first())
    g = Group.objects.create(name='Informational Services and User Support',
                             acronym='wg-isus',
                             time=create_time,
                             parent=adm,
                             type_id='wg',
                             state_id='conclude')
    ChangeStateGroupEvent.objects.create(group=g,time=event_time,by=system,desc='Concluded group',state_id='conclude')
    g.role_set.create(name_id='chair',person=persons['Jill Foster'],email=persons['Jill Foster'].email_set.first())
    g.role_set.create(name_id='ad',person=persons['Stephen J. Coya'],email=persons['Stephen J. Coya'].email_set.first())
    g = Group.objects.create(name='Lower Layers Technology',
                             acronym='wg-llt',
                             time=create_time,
                             parent=adm,
                             type_id='wg',
                             state_id='conclude')
    ChangeStateGroupEvent.objects.create(group=g,time=event_time,by=system,desc='Concluded group',state_id='conclude')
    g.role_set.create(name_id='chair',person=persons['Piet Bovenga'],email=persons['Piet Bovenga'].email_set.first())
    g.role_set.create(name_id='ad',person=persons['Stephen J. Coya'],email=persons['Stephen J. Coya'].email_set.first())
    g = Group.objects.create(name='Network Applications Support',
                             acronym='wg-nap',
                             time=create_time,
                             parent=adm,
                             type_id='wg',
                             state_id='conclude')
    ChangeStateGroupEvent.objects.create(group=g,time=event_time,by=system,desc='Concluded group',state_id='conclude')
    g.role_set.create(name_id='chair',person=persons['Paul-Andre Pays'],email=persons['Paul-Andre Pays'].email_set.first())
    g.role_set.create(name_id='ad',person=persons['Stephen J. Coya'],email=persons['Stephen J. Coya'].email_set.first())
    g = Group.objects.create(name='Network Operations',
                             acronym='wg-nop',
                             time=create_time,
                             parent=adm,
                             type_id='wg',
                             state_id='conclude')
    ChangeStateGroupEvent.objects.create(group=g,time=event_time,by=system,desc='Concluded group',state_id='conclude')
    g.role_set.create(name_id='chair',person=persons['Bernhard Stockman'],email=persons['Bernhard Stockman'].email_set.first())
    g.role_set.create(name_id='ad',person=persons['Stephen J. Coya'],email=persons['Stephen J. Coya'].email_set.first())
    g = Group.objects.create(name='Security Technology',
                             acronym='wg-sec',
                             time=create_time,
                             parent=adm,
                             type_id='wg',
                             state_id='conclude')
    ChangeStateGroupEvent.objects.create(group=g,time=event_time,by=system,desc='Concluded group',state_id='conclude')
    g.role_set.create(name_id='chair',person=persons['Dr. Klaus Truoel'],email=persons['Dr. Klaus Truoel'].email_set.first())
    g.role_set.create(name_id='ad',person=persons['Stephen J. Coya'],email=persons['Stephen J. Coya'].email_set.first())
    g = Group.objects.create(name='Message Handeling Systems',
                             acronym='wg1',
                             time=create_time,
                             parent=adm,
                             type_id='wg',
                             state_id='conclude')
    ChangeStateGroupEvent.objects.create(group=g,time=event_time,by=system,desc='Concluded group',state_id='conclude')
    g.role_set.create(name_id='chair',person=persons['Urs Eppenberger'],email=persons['Urs Eppenberger'].email_set.first())
    g.role_set.create(name_id='ad',person=persons['Stephen J. Coya'],email=persons['Stephen J. Coya'].email_set.first())
    g = Group.objects.create(name='File Transfer, Access and Management',
                             acronym='wg2',
                             time=create_time,
                             parent=adm,
                             type_id='wg',
                             state_id='conclude')
    ChangeStateGroupEvent.objects.create(group=g,time=event_time,by=system,desc='Concluded group',state_id='conclude')
    g.role_set.create(name_id='chair',person=persons['Jean-Paul Le Guigner'],email=persons['Jean-Paul Le Guigner'].email_set.first())
    g.role_set.create(name_id='ad',person=persons['Stephen J. Coya'],email=persons['Stephen J. Coya'].email_set.first())
    g = Group.objects.create(name='Network Operations and X.25',
                             acronym='wg4',
                             time=create_time,
                             parent=adm,
                             type_id='wg',
                             state_id='conclude')
    ChangeStateGroupEvent.objects.create(group=g,time=event_time,by=system,desc='Concluded group',state_id='conclude')
    g.role_set.create(name_id='chair',person=persons['Piet Bovenga'],email=persons['Piet Bovenga'].email_set.first())
    g.role_set.create(name_id='ad',person=persons['Stephen J. Coya'],email=persons['Stephen J. Coya'].email_set.first())
    g = Group.objects.create(name='Full Screen Services',
                             acronym='wg5',
                             time=create_time,
                             parent=adm,
                             type_id='wg',
                             state_id='conclude')
    ChangeStateGroupEvent.objects.create(group=g,time=event_time,by=system,desc='Concluded group',state_id='conclude')
    g.role_set.create(name_id='chair',person=persons['Brian Gilmore'],email=persons['Brian Gilmore'].email_set.first())
    g.role_set.create(name_id='ad',person=persons['Stephen J. Coya'],email=persons['Stephen J. Coya'].email_set.first())
    g = Group.objects.create(name='Management of Network Application Services',
                             acronym='wg8',
                             time=create_time,
                             parent=adm,
                             type_id='wg',
                             state_id='conclude')
    ChangeStateGroupEvent.objects.create(group=g,time=event_time,by=system,desc='Concluded group',state_id='conclude')
    g.role_set.create(name_id='chair',person=persons['Christian Tschudin'],email=persons['Christian Tschudin'].email_set.first())
    g.role_set.create(name_id='ad',person=persons['Stephen J. Coya'],email=persons['Stephen J. Coya'].email_set.first())
    
    Document.objects.filter(name='draft-rescorla-sec-cons').update(group=adm)

class Migration(migrations.Migration):

    dependencies = [
        ('group', '0006_auto_20150718_0509'),
        ('doc', '0012_auto_20160207_0537'),
        ('person', '0005_deactivate_unknown_email'),
        ('community','0002_auto_20141222_1749'),
    ]

    operations = [
        migrations.RunPython(forward, reverse)
    ]
