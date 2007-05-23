from django.db import models
from django.contrib.auth.models import User
from ietf.idtracker.models import PersonOrOrgInfo

class UserMap(models.Model):
    """
    This is effectively a many:1 mapping of django-user -> IETF user.
    It'd ideally be 1:1, but for testing some users have multiple
    accounts with different privilege levels.
    """
    user = models.ForeignKey(User, raw_id_admin=True, core=True, unique=True)
    person = models.ForeignKey(PersonOrOrgInfo, edit_inline=models.STACKED, max_num_in_admin=1)
    def __str__(self):
	return "Mapping django user %s to IETF person %s" % ( self.user, self.person )


######################################################
# legacy per-tool access tables.
# ietf.idtracker.models.IESGLogin is in the same vein.

class LiaisonUser(models.Model):
    person = models.ForeignKey(PersonOrOrgInfo, db_column='person_or_org_tag', primary_key=True, raw_id_admin=True)
    login_name = models.CharField(maxlength=255)
    password = models.CharField(maxlength=25)
    user_level = models.IntegerField(null=True, blank=True)
    comment = models.TextField(blank=True)
    def __str__(self):
	return self.login_name
    class Meta:
        db_table = 'users'
	ordering = ['login_name']
    class Admin:
	pass

class WgPassword(models.Model):
    person = models.ForeignKey(PersonOrOrgInfo, db_column='person_or_org_tag', primary_key=True, raw_id_admin=True)
    password = models.CharField(blank=True, maxlength=255)
    secrete_question_id = models.IntegerField(null=True, blank=True)
    secrete_answer = models.CharField(blank=True, maxlength=255)
    is_tut_resp = models.IntegerField(null=True, blank=True)
    irtf_id = models.IntegerField(null=True, blank=True)
    comment = models.TextField(blank=True)
    login_name = models.CharField(blank=True, maxlength=100)
    def __str__(self):
	return self.login_name
    class Meta:
        db_table = 'wg_password'
	ordering = ['login_name']
    class Admin:
	pass
