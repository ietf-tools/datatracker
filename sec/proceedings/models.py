from django.conf import settings
from django.db import models
from django.shortcuts import get_object_or_404

from ietf.meeting.models import Meeting
from sec.utils.meeting import get_upload_root

import datetime
import os

class InterimManager(models.Manager):
    '''A custom manager to limit objects to type=interim'''
    def get_query_set(self):
        return super(InterimManager, self).get_query_set().filter(type='interim')
        
class InterimMeeting(Meeting):
    '''
    This class is a proxy of Meeting.  It's purpose is to provide extra methods that are 
    useful for an interim meeting, to help in templates.  Most information is derived from 
    the session associated with this meeting.  We are assuming there is only one.
    '''
    class Meta:
        proxy = True
        
    objects = InterimManager()
    
    def group(self):
        return self.session_set.all()[0].group

    def agenda(self):
        session = self.session_set.all()[0]
        agendas = session.materials.exclude(states__slug='deleted').filter(type='agenda')
        if agendas:
            return agendas[0]
        else:
            return None
            
    def minutes(self):
        session = self.session_set.all()[0]
        minutes = session.materials.exclude(states__slug='deleted').filter(type='minutes')
        if minutes:
            return minutes[0]
        else:
            return None
        
    def get_proceedings_path(self, group=None):
        path = os.path.join(get_upload_root(self),'proceedings.html')
        return path
    
    def get_proceedings_url(self, group=None):
        '''
        If the proceedings file doesn't exist return empty string.  For use in templates.
        '''
        if os.path.exists(self.get_proceedings_path()):
            url = "%s/proceedings/interim/%s/%s/proceedings.html" % (
                settings.MEDIA_URL,
                self.date.strftime('%Y/%m/%d'),
                self.group().acronym)
            return url
        else:
            return ''

class Registration(models.Model):
    rsn = models.AutoField(primary_key=True)
    fname = models.CharField(max_length=255)
    lname = models.CharField(max_length=255)
    company = models.CharField(max_length=255)
    country = models.CharField(max_length=2)
    
    def __unicode__(self):
        return "%s %s" % (fname, lname)
    class Meta:
        db_table = 'registrations'