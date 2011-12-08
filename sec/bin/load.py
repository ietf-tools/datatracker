#!/usr/bin/python

from django.core.management import setup_environ
from django.contrib.auth.models import User
from sec import settings

setup_environ(settings)

from redesign.group.models import *
from redesign.person.models import *
from redesign.name.models import *


'''
This script loads data into the new db.
'''
records = [('IETF Announcement List','ietf-announce@ietf.org'),
           ('I-D Announcement List', 'i-d-announce@ietf.org'),
           ('The IESG', 'iesg@ietf.org'),
           ('Working Group Chairs', 'wgchairs@ietf.org'),
           ('BoF Chairs', 'bofchairs@ietf.org')]
               
def add_user():
    user = User.objects.create_user('test-chair')
    person = Person(name='Test Chair',user=user)
    person.save()
    email = Email(address='testchair@amsl.com',person=person)
    email.save()
    group = Group.objects.get(name="ancp")
    role_name = RoleName.objects.get(slug='chair')
    r = Role(name=role_name,group=group,email=email,person=email.person)
    r.save()

def add_emails():
    for item in records:
        p = Person(name=item[0],ascii=item[0])
        p.save()
        print 'created %s' % repr(p)
        e = Email(address=item[1],person=p)
        e.save()
        print 'created %s' % repr(e)

def add_roles():
    rn = RoleName(slug='announce',name='Announce')
    rn.save()
    print 'created %s' % repr(rn)
    
def assign_roles():
    group = Group.objects.get(name="IETF")
    role_name = RoleName.objects.get(name="Announce")
    for item in records:
        email = Email.objects.get(address=item[1])
        r = Role(name=role_name,group=group,email=email,person=email.person)
        r.save()
        print 'created %s' % repr(r)
    
# control        
add_user()
add_emails()
add_roles()
assign_roles()
