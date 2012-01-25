#!/usr/bin/python

from django.core.management import setup_environ
from sec import settings

setup_environ(settings)

from ietf.group.models import *
from ietf.person.models import *
from ietf.name.models import *


'''
This script loads data into the new db.
'''
records = [('IETF Secretariat','ietf-secretariat@ietf.org'),
           ('IESG Secretary', 'iesg-secretary@ietf.org'),
           ('The IESG', 'iesg@ietf.org'),
           ('Internet Drafts Administrator', 'internet-drafts@ietf.org'),
           ('IETF Agenda', 'agenda@ietf.org'),
           ('IETF Chair', 'chair@ietf.org'),
           ('IAB Chair', 'iab-chair@ietf.org'),
           ('NomCom Chair', 'nomcom-chair@ietf.org'),
           ('IETF Registrar', 'ietf-registrar@ietf.org'),
           ('IETF Administrative Director', 'iad@ietf.org'),
           ('IETF Executive Director', 'exec-director@ietf.org'),
           ('RSOC Chair', 'rsoc-chair@iab.org')]
               
def add_emails():
    for item in records:
        p = Person(name=item[0],ascii=item[0])
        p.save()
        print 'created %s' % repr(p)
        e = Email(address=item[1],person=p)
        e.save()
        print 'created %s' % repr(e)

def add_group():
    gt = GroupTypeName(slug='system',name='System')
    gt.save()
    print 'created %s' % repr(gt)
    g = Group(name="Announced From",type_id=gt,acronym="annfrom")
    g.save()
    print 'created %s' % repr(g)
    
def add_roles():
    rn = RoleName(slug='member',name='Member')
    rn.save()
    print 'created %s' % repr(rn)
    
def assign_roles():
    group = Group.objects.get(name="Announced From")
    role_name = RoleName.objects.get(name="Member")
    for item in records:
        email = Email.objects.get(address=item[1])
        r = Role(name=role_name,group=group,email=email)
        r.save()
        print 'created %s' % repr(r)
    
# control        
# add_emails()
# add_group()
# add_roles()
assign_roles()
