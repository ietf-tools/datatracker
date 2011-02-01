from models import *

class Acronym(Group):
    class LazyIndividualSubmitter(object):
        def __get__(self, obj, type=None):
            return Group.objects.get(acronym="none").id
    
    INDIVIDUAL_SUBMITTER = LazyIndividualSubmitter()
    
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

    def __str__(self):
        return self.acronym

    def __unicode__(self):
        return self.acronym
    
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
    def active_wgs(self):
        return IETFWG.objects.filter(type="wg", state="active", parent=self).select_related('type', 'state', 'parent').order_by("acronym")
    
    @staticmethod
    def active_areas():
        return Area.objects.filter(type="area", state="active").select_related('type', 'state', 'parent').order_by('acronym')
    
    class Meta:
        proxy = True


class IETFWG(Group):
    ACTIVE=1
    #group_acronym = models.OneToOneField(Acronym, primary_key=True, editable=False)
    @property
    def group_acronym(self):
        return Acronym(self)
    
    #group_type = models.ForeignKey(WGType)
    #proposed_date = models.DateField(null=True, blank=True)
    #start_date = models.DateField(null=True, blank=True)
    #dormant_date = models.DateField(null=True, blank=True)
    #concluded_date = models.DateField(null=True, blank=True)
    #status = models.ForeignKey(WGStatus)
    #area_director = models.ForeignKey(AreaDirector, null=True)
    #meeting_scheduled = models.CharField(blank=True, max_length=3)
    #email_address = models.CharField(blank=True, max_length=60)
    #email_subscribe = models.CharField(blank=True, max_length=120)
    #email_keyword = models.CharField(blank=True, max_length=50)
    #email_archive = models.CharField(blank=True, max_length=95)
    #comments = models.TextField(blank=True)
    #last_modified_date = models.DateField()
    #meeting_scheduled_old = models.CharField(blank=True, max_length=3)
    #area = FKAsOneToOne('areagroup', reverse=True)
    def __str__(self):
	return self.group_acronym.acronym

    def __unicode__(self):
	return self.group_acronym.acronym

    # everything below here is not fixed yet
    def active_drafts(self):
	return self.group_acronym.internetdraft_set.all().filter(status__status="Active")
    def choices():
	return [(wg.group_acronym_id, wg.group_acronym.acronym) for wg in IETFWG.objects.all().filter(group_type__type='WG').select_related().order_by('acronym.acronym')]
    choices = staticmethod(choices)
    def area_acronym(self):
        areas = AreaGroup.objects.filter(group__exact=self.group_acronym)
        if areas:
            return areas[areas.count()-1].area.area_acronym
        else:
            return None
    def area_directors(self):
        areas = AreaGroup.objects.filter(group__exact=self.group_acronym)
        if areas:
            return areas[areas.count()-1].area.areadirector_set.all()
        else:
            return None
    def chairs(self): # return a set of WGChair objects for this work group
        return WGChair.objects.filter(group_acronym__exact=self.group_acronym)
    def secretaries(self): # return a set of WGSecretary objects for this group
        return WGSecretary.objects.filter(group_acronym__exact=self.group_acronym)
    def milestones(self): # return a set of GoalMilestone objects for this group
        return GoalMilestone.objects.filter(group_acronym__exact=self.group_acronym)
    def rfcs(self): # return a set of Rfc objects for this group
        return Rfc.objects.filter(group_acronym__exact=self.group_acronym)
    def drafts(self): # return a set of Rfc objects for this group
        return InternetDraft.objects.filter(group__exact=self.group_acronym)
    def charter_text(self): # return string containing WG description read from file
        # get file path from settings. Syntesize file name from path, acronym, and suffix
        try:
            filename = os.path.join(settings.IETFWG_DESCRIPTIONS_PATH, self.group_acronym.acronym) + ".desc.txt"
            desc_file = open(filename)
            desc = desc_file.read()
        except BaseException:    
            desc =  'Error Loading Work Group Description'
        return desc

    def additional_urls(self):
        return AreaWGURL.objects.filter(name=self.group_acronym.acronym)        
    def clean_email_archive(self):
        x = self.email_archive
        # remove "current/" and "maillist.html"
        x = re.sub("^(http://www\.ietf\.org/mail-archive/web/)([^/]+/)(current/)?([a-z]+\.html)?$", "\\1\\2", x)
        return x
    
    class Meta:
        proxy = True
