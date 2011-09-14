from redesign.proxy_utils import TranslatingManager

from models import *

class IESGLogin(Person):
    objects = TranslatingManager(dict(user_level__in=None,
                                      first_name="name"
                                      ))

    def from_object(self, base):
        for f in base._meta.fields:
            setattr(self, f.name, getattr(base, f.name))
        return self
            
    SECRETARIAT_LEVEL = 0
    AD_LEVEL = 1
    INACTIVE_AD_LEVEL = 2

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
        return self.name_parts()[1]
    
    #last_name = models.CharField(blank=True, max_length=25)
    @property
    def last_name(self):
        return self.name_parts()[3]

    # FIXME: person isn't wrapped yet
    #person = BrokenForeignKey(PersonOrOrgInfo, db_column='person_or_org_tag', unique=True, null_values=(0, 888888), null=True)

    # apparently unused
    #pgp_id = models.CharField(blank=True, null=True, max_length=20)
    #default_search = models.NullBooleanField()
    
    def __str__(self):
        return self.name
    def __unicode__(self):
        return self.name
    def is_current_ad(self):
	return self in Person.objects.filter(role__name="ad", role__group__state="active").distinct()
    @staticmethod
    def active_iesg():
	return IESGLogin.objects.filter(role__name="ad", role__group__state="active").distinct().order_by('name')
    
    class Meta:
        proxy = True
