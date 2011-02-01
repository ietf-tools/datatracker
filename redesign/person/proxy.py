from models import *

class IESGLogin(Email):
    def __init__(self, base):
        for f in base._meta.fields:
            setattr(self, f.name, getattr(base, f.name))
            
    SECRETARIAT_LEVEL = 0
    AD_LEVEL = 1
    INACTIVE_AD_LEVEL = 2

    @property
    def id(self):
        return self.pk # this is not really backwards-compatible
    #login_name = models.CharField(blank=True, max_length=255)
    @property
    def login_name(self): raise NotImplemented
    #password = models.CharField(max_length=25)
    @property
    def password(self): raise NotImplemented
    #user_level = models.IntegerField(choices=USER_LEVEL_CHOICES)
    @property
    def user_level(self): raise NotImplemented
    
    #first_name = models.CharField(blank=True, max_length=25)
    @property
    def first_name(self):
        return self.get_name().split(" ")[0]
    
    #last_name = models.CharField(blank=True, max_length=25)
    @property
    def last_name(self):
        return self.get_name().split(" ")[1]

    # FIXME: person isn't wrapped yet
    #person = BrokenForeignKey(PersonOrOrgInfo, db_column='person_or_org_tag', unique=True, null_values=(0, 888888), null=True)

    # apparently unused
    #pgp_id = models.CharField(blank=True, null=True, max_length=20)
    #default_search = models.NullBooleanField()
    
    def __str__(self):
        return self.get_name()
    def __unicode__(self):
        return self.get_name()
    def is_current_ad(self):
	return self in Email.objects.filter(role__name="ad", role__group__state="active")
    @staticmethod
    def active_iesg():
        raise NotImplemented
	#return IESGLogin.objects.filter(user_level=1,id__gt=1).order_by('last_name')
    
    class Meta:
        proxy = True
