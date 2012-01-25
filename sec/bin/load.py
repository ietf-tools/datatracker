#!/usr/bin/python

from django.core.management import setup_environ
from django.contrib.auth.models import User
from sec import settings

setup_environ(settings)

from ietf.group.models import *
from ietf.person.models import *
from ietf.name.models import *


'''
This script loads data into the new db.
to run first do
export DJANGO_SETTINGS_MODULE=sec.settings
'''
records = [('IETF Announcement List','ietf-announce@ietf.org'),
           ('I-D Announcement List', 'i-d-announce@ietf.org'),
           ('The IESG', 'iesg@ietf.org'),
           ('Working Group Chairs', 'wgchairs@ietf.org'),
           ('BoF Chairs', 'bofchairs@ietf.org')]
               
def add_user():
    try:
        user = User.objects.get(username='test-chair')
    except User.DoesNotExist:
	user = User.objects.create_user('test-chair',email='testchair@amsl.com')
    person,x = Person.objects.get_or_create(name='Test Chair',user=user)
    email,x = Email.objects.get_or_create(address='testchair@amsl.com',person=person)
    group = Group.objects.get(acronym="ancp")
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
