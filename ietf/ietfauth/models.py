# Copyright The IETF Trust 2007, All Rights Reserved

from django.db import models
from django.contrib.auth.models import User
from ietf.idtracker.models import PersonOrOrgInfo

class UserMap(models.Model):
    """
    This is a 1:1 mapping of django-user -> IETF user.
    This can't represent the users in the existing tool that
    have multiple accounts with multiple privilege levels: they
    need extra IETF users.

    It also contains a text field for the user's hashed htdigest
    password.  In order to allow logging in with either username
    or email address, we need to store two hashes.  One is in the
    user model's password field, the other is here.  We also store
    a hashed version of just the email address for the RFC Editor.
    """
    user = models.ForeignKey(User)
    # user should have unique=True, but that confuses the
    # admin edit_inline interface.
    person = models.ForeignKey(PersonOrOrgInfo, unique=True, null=True)
    email_htdigest = models.CharField(max_length=32, blank=True, null=True)
    rfced_htdigest = models.CharField(max_length=32, blank=True, null=True)
    def __str__(self):
	return "Mapping django user %s to IETF person %s" % ( self.user, self.person )


######################################################
# legacy per-tool access tables.
# ietf.idtracker.models.IESGLogin is in the same vein.

class LegacyLiaisonUser(models.Model):
    person = models.ForeignKey(PersonOrOrgInfo, db_column='person_or_org_tag', primary_key=True)
    login_name = models.CharField(max_length=255)
    password = models.CharField(max_length=25)
    user_level = models.IntegerField(null=True, blank=True)
    comment = models.TextField(blank=True)
    def __str__(self):
	return self.login_name
    class Meta:
        db_table = 'users'
	ordering = ['login_name']

class LegacyWgPassword(models.Model):
    person = models.ForeignKey(PersonOrOrgInfo, db_column='person_or_org_tag', primary_key=True)
    password = models.CharField(blank=True, max_length=255)
    secrete_question_id = models.IntegerField(null=True, blank=True)
    secrete_answer = models.CharField(blank=True, max_length=255)
    is_tut_resp = models.IntegerField(null=True, blank=True)
    irtf_id = models.IntegerField(null=True, blank=True)
    comment = models.TextField(blank=True)
    login_name = models.CharField(blank=True, max_length=100)
    def __str__(self):
	return self.login_name
    class Meta:
        db_table = 'wg_password'
	ordering = ['login_name']

# changes done by convert-096.py:changed maxlength to max_length
# removed core
# removed edit_inline
# removed max_num_in_admin
# removed num_in_admin
# removed raw_id_admin
