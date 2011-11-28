from django.conf import settings
from django.db import models
from django.shortcuts import get_object_or_404

import datetime
import os
"""
SLIDE_TYPE_CHOICES=(
        ('1', '(converted) HTML'),
        ('2', 'PDF'),
        ('3', 'Text'),
        ('4', 'PowerPoint -2003 (PPT)'),
        ('5', 'Microsoft Word'),
        ('6', 'PowerPoint 2007- (PPTX)'),
    )

def get_group_or_404(id):
    '''
    This function takes an id (integer or string) and returns the appropriate IETFWG, IRTF or 
    Acronym object representing a group, raising 404 if it is not found
    '''
    id = int(id)
    if id > 100:
        group = get_object_or_404(IETFWG, group_acronym=id)
    elif 0 < id < 100:
        group = get_object_or_404(IRTF, irtf_id=id)
    elif id < 0:
        group = get_object_or_404(Acronym, acronym_id=id)
    return group
# ----------------------------------------------------

class Proceeding(models.Model):
    meeting_num = models.ForeignKey(Meeting, db_column='meeting_num', unique=True, primary_key=True)
    dir_name = models.CharField(blank=True, max_length=25)
    sub_begin_date = models.DateField(null=True, blank=True)
    sub_cut_off_date = models.DateField(null=True, blank=True)
    frozen = models.IntegerField(null=True, blank=True)
    c_sub_cut_off_date = models.DateField(null=True, blank=True)
    pr_from_date = models.DateField(null=True, blank=True)
    pr_to_date = models.DateField(null=True, blank=True)
#    def __str__(self):
#        return "%s" % (self.meeting_num)
    def __unicode__(self):
        return "%s" % (self.meeting_num)

    #Custom method for use in template
    def is_frozen(self):
        if self.frozen == 1:
            return True
        else:
            return False
    class Meta:
        db_table = 'proceedings'
        ordering = ['?']        # workaround for FK primary key

class Slide(models.Model):
    id = models.AutoField(primary_key=True)
    meeting = models.ForeignKey(Meeting, db_column='meeting_num')
    group_acronym_id = models.IntegerField(null=True, blank=True)
    slide_num = models.IntegerField(null=True, blank=True)
    slide_type_id = models.IntegerField(choices=SLIDE_TYPE_CHOICES)
    slide_name = models.CharField(blank=True, max_length=255)
    irtf = models.IntegerField()
    interim = models.BooleanField()
    order_num = models.IntegerField(null=True, blank=True)
    in_q = models.IntegerField(null=True, blank=True)
    
    # AMS added -------------------
    SLIDE_TYPES = {1:'htm',2:'pdf',3:'txt',4:'ppt',5:'doc',6:'pptx',7:'wav',8:'avi',9:'mp3'}
    # reverse the slide type mappings to lookup type_id by extension
    REVERSE_SLIDE_TYPES = dict((v,k) for k,v in SLIDE_TYPES.iteritems())
    
    def get_filename(self):
        # would use get_group_or_404 but was causing circular import problem, this will go away
        if self.group_acronym_id > 100:
            group = IETFWG.objects.get(group_acronym=self.group_acronym_id)
        else: 
            group = IRTF.objects.get(irtf_id=self.group_acronym_id)
        return '%s-%s.%s' % (group.acronym, self.slide_num, self.SLIDE_TYPES[self.slide_type_id])
    filename = property(get_filename)
    def get_group_name(self):
        if self.irtf == 0:
            object = Acronym.objects.get(acronym_id=self.group_acronym_id)
        else:
            object = IRTF.objects.get(irtf_id=self.group_acronym_id)
        return object.acronym
    group_name = property(get_group_name)
    def get_file_path(self):
        if self.slide_type_id == 1:
            slide_dir = os.path.splitext(self.filename)[0]
            path = os.path.join(self.meeting.upload_root,'slides',slide_dir)
        else:
            path = os.path.join(self.meeting.upload_root,'slides',self.filename)
        return path
    file_path = property(get_file_path)
    def _get_url(self):
        url = '%s/proceedings/%s/slides/%s' % (settings.MEDIA_URL,self.meeting.meeting_num,self.filename)
        return url
    url = property(_get_url)
    # end AMS ---------------------
    def __unicode__(self):
        return "%d %s %s" % (self.meeting_id, self.group_acronym_id, self.slide_name)
    class Meta:
        db_table = 'slides'

class Minute(models.Model):
    id = models.AutoField(primary_key=True)
    meeting = models.ForeignKey(Meeting, db_column='meeting_num')
    group_acronym_id = models.IntegerField()
    filename = models.CharField(blank=True, max_length=255)
    irtf = models.IntegerField()
    interim = models.BooleanField()
    
    # AMS Added
    def get_file_path(self):
        path = os.path.join(self.meeting.upload_root,'minutes',self.filename)
        return path
    file_path = property(get_file_path)
    def _get_url(self):
        url = '%s/proceedings/%s/minutes/%s' % (settings.MEDIA_URL,self.meeting.meeting_num,self.filename)
        return url
    url = property(_get_url)
    # end AMS Add
    
    def __unicode__(self):
        return "%d %s" % (self.meeting_id, self.group_acronym_id)

    class Meta:
        db_table = 'minutes'

class WgAgenda(models.Model):
    id = models.AutoField(primary_key=True)
    meeting = models.ForeignKey(Meeting, db_column='meeting_num')
    group_acronym_id = models.IntegerField()
    filename = models.CharField(max_length=255)
    irtf = models.IntegerField()
    interim = models.BooleanField()
    
    # AMS Added
    def get_file_path(self):
        path = os.path.join(self.meeting.upload_root,'agenda',self.filename)
        return path
    file_path = property(get_file_path)
    def _get_url(self):
        url = '%s/proceedings/%s/agenda/%s' % (settings.MEDIA_URL,self.meeting.meeting_num,self.filename)
        return url
    url = property(_get_url)
    # end AMS Add
    
    def __unicode__(self):
        return "%d %s" % (self.meeting_id, self.group_acronym_id)

    class Meta:
        db_table = 'wg_agenda'

class WgProceedingsActivity(models.Model):
    #id = models.IntegerField(primary_key=True)
    # group would be foreign key but can refer to many different objects
    group_acronym_id = models.IntegerField()
    meeting_num = models.IntegerField()
    activity = models.TextField(blank=True)
    act_date = models.DateField(auto_now=True)
    act_time = models.TimeField(auto_now=True)
    #act_by = models.IntegerField()
    act_by = models.ForeignKey(PersonOrOrgInfo, db_column='act_by')
    def __str__(self):
        return str(self.pk)
    class Meta:
        db_table = u'wg_proceedings_activities'
# ----------------------------------------------
# Custom Interim Tables
# ----------------------------------------------
class InterimActivity(models.Model):
    #id = models.IntegerField(primary_key=True)
    # group would be foreign key but can refer to many different objects
    group_acronym_id = models.IntegerField()
    meeting_num = models.IntegerField()
    activity = models.TextField(blank=True)
    act_date = models.DateField(auto_now=True)
    act_time = models.TimeField(auto_now=True)
    #act_by = models.IntegerField()
    act_by = models.ForeignKey(PersonOrOrgInfo, db_column='act_by')
    def __str__(self):
        return str(self.pk)
    class Meta:
        db_table = u'interim_activities'
        
class InterimSlide(models.Model):
    id = models.AutoField(primary_key=True)
    meeting = models.ForeignKey(InterimMeeting, db_column='meeting_num')
    group_acronym_id = models.IntegerField(null=True, blank=True)
    slide_num = models.IntegerField(null=True, blank=True)
    slide_type_id = models.IntegerField(choices=SLIDE_TYPE_CHOICES)
    slide_name = models.CharField(blank=True, max_length=255)
    irtf = models.IntegerField()
    interim = models.BooleanField()
    order_num = models.IntegerField(null=True, blank=True)
    in_q = models.IntegerField(null=True, blank=True)
    
    # AMS added -------------------
    SLIDE_TYPES = {1:'htm',2:'pdf',3:'txt',4:'ppt',5:'doc',6:'pptx',7:'wav',8:'avi',9:'mp3'}
    # reverse the slide type mappings to lookup type_id by extension
    REVERSE_SLIDE_TYPES = dict((v,k) for k,v in SLIDE_TYPES.iteritems())
    
    def get_filename(self):
        # would use get_group_or_404 but was causing circular import problem, this will go away
        if self.group_acronym_id > 100:
            group = IETFWG.objects.get(group_acronym=self.group_acronym_id)
        else: 
            group = IRTF.objects.get(irtf_id=self.group_acronym_id)
        return '%s-%s.%s' % (group.acronym, self.slide_num, self.SLIDE_TYPES[self.slide_type_id])
    filename = property(get_filename)
    def get_group_name(self):
        if self.irtf == 0:
            object = Acronym.objects.get(acronym_id=self.group_acronym_id)
        else:
            object = IRTF.objects.get(irtf_id=self.group_acronym_id)
        return object.acronym
    group_name = property(get_group_name)

    def get_file_path(self):
        if self.slide_type_id == 1:
            slide_dir = os.path.splitext(self.filename)[0]
            path = os.path.join(self.meeting.upload_root,'slides',slide_dir)
        else:
            path = os.path.join(self.meeting.upload_root,'slides',self.filename)
        return path
    file_path = property(get_file_path)
    def get_url(self):
        url = "%s/proceedings/interim/%s/%s/%s/%s/slides/%s" % (
            settings.MEDIA_URL,
            self.meeting.start_date.strftime('%Y'),
            self.meeting.start_date.strftime('%m'),
            self.meeting.start_date.strftime('%d'),
            self.get_group_name(),
            self.filename)
        return url
    url = property(get_url)

    # end AMS ---------------------
    def __unicode__(self):
        return "%d %s %s" % (self.meeting_id, self.group_acronym_id, self.slide_name)
    class Meta:
        db_table = 'interim_slides'

class InterimMinute(models.Model):
    id = models.AutoField(primary_key=True)
    meeting = models.ForeignKey(InterimMeeting, db_column='meeting_num')
    group_acronym_id = models.IntegerField()
    filename = models.CharField(blank=True, max_length=255)
    irtf = models.IntegerField()
    interim = models.BooleanField()

    def get_file_path(self):
        path = os.path.join(self.meeting.upload_root,'minutes',self.filename)
        return path
    file_path = property(get_file_path)
    def get_url(self):
        url = "%s/proceedings/interim/%s/%s/%s/%s/minutes/%s" % (
            settings.MEDIA_URL,
            self.meeting.start_date.strftime('%Y'),
            self.meeting.start_date.strftime('%m'),
            self.meeting.start_date.strftime('%d'),
            self.group_acronym,
            self.filename)
        return url
    url = property(get_url)
    def get_group_acronym(self):
        try:
            acronym = Acronym.objects.get(acronym_id=self.group_acronym_id)
        except Acronym.DoesNotExist:
            return ''
        return acronym.acronym
    group_acronym = property(get_group_acronym)
    
    def __unicode__(self):
        return "%d %s" % (self.meeting_id, self.group_acronym_id)
        
    class Meta:
        db_table = 'interim_minutes'

class InterimAgenda(models.Model):
    id = models.AutoField(primary_key=True)
    meeting = models.ForeignKey(InterimMeeting, db_column='meeting_num')
    group_acronym_id = models.IntegerField()
    filename = models.CharField(max_length=255)
    irtf = models.IntegerField()
    interim = models.BooleanField()
    
    def get_file_path(self):
        path = os.path.join(self.meeting.upload_root,'agenda',self.filename)
        return path
    file_path = property(get_file_path)
    def get_url(self):
        url = "%s/proceedings/interim/%s/%s/%s/%s/agenda/%s" % (
            settings.MEDIA_URL,
            self.meeting.start_date.strftime('%Y'),
            self.meeting.start_date.strftime('%m'),
            self.meeting.start_date.strftime('%d'),
            self.group_acronym,
            self.filename)
        return url
    url = property(get_url)
    def get_group_acronym(self):
        try:
            acronym = Acronym.objects.get(acronym_id=self.group_acronym_id)
        except Acronym.DoesNotExist:
            return ''
        return acronym.acronym
    group_acronym = property(get_group_acronym)
    
    def __unicode__(self):
        return "%d %s" % (self.meeting_id, self.group_acronym_id)

    class Meta:
        db_table = 'interim_agenda'
"""

