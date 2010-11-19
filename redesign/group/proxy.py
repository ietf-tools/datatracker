from models import *

class Acronym(Group):
    def __init__(self, base):
        for f in base._meta.fields:
            setattr(self, f.name, getattr(base, f.name))
    
    #acronym_id = models.AutoField(primary_key=True)
    @property
    def acronym_id(self):
        raise NotImplemented
    #acronym = models.CharField(max_length=12) # same name
    #name = models.CharField(max_length=100) # same name
    #name_key = models.CharField(max_length=50, editable=False)
    @property
    def name_key(self):
        return self.name.upper()
    
    class Meta:
        proxy = True

class Area(Group):
    ACTIVE=1
    #area_acronym = models.OneToOneField(Acronym, primary_key=True)
    @property
    def area_acronym(self):
        return Acronym(self)
    
    #start_date = models.DateField(auto_now_add=True)
    #concluded_date = models.DateField(null=True, blank=True)
    #status = models.ForeignKey(AreaStatus)
    #comments = models.TextField(blank=True)
    #last_modified_date = models.DateField(auto_now=True)
    #extra_email_addresses = models.TextField(blank=True,null=True)

    #def additional_urls(self):
    #    return AreaWGURL.objects.filter(name=self.area_acronym.name)
    #def active_wgs(self):
    #    return IETFWG.objects.filter(group_type=1,status=IETFWG.ACTIVE,areagroup__area=self).order_by('group_acronym__acronym')
    
    @staticmethod
    def active_areas():
        return Area.objects.filter(type="area", state="active")
    
    class Meta:
        proxy = True
