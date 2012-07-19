from ietf.utils.proxy import TranslatingManager, proxy_role_email

from models import *

class Acronym(Group):
    class LazyIndividualSubmitter(object):
        def __get__(self, obj, type=None):
            return Group.objects.get(acronym="none").id
    
    INDIVIDUAL_SUBMITTER = LazyIndividualSubmitter()
    
    def from_object(self, base):
        for f in base._meta.fields:
            setattr(self, f.name, getattr(base, f.name))
        return self
    
    #acronym_id = models.AutoField(primary_key=True)
    @property
    def acronym_id(self):
        return self.id
    #acronym = models.CharField(max_length=12) # same name
    #name = models.CharField(max_length=100) # same name
    #name_key = models.CharField(max_length=50, editable=False)
    @property
    def name_key(self):
        return self.name.upper()

    @property
    def ietfwg(self):
        return IETFWG().from_object(self)
    
    def __str__(self):
        return self.acronym

    def __unicode__(self):
        return self.acronym

    class Meta:
        proxy = True

class Area(Group):
    objects = TranslatingManager(dict(area_acronym__acronym="acronym",
                                      area_acronym__name="name",
                                      status=lambda v: ("state", {1: "active", 2: "dormant", 3: "conclude"}[v] )),
                                 always_filter=dict(type="area"))
    
    def from_object(self, base):
        for f in base._meta.fields:
            setattr(self, f.name, getattr(base, f.name))
        return self

    ACTIVE=1
    #area_acronym = models.OneToOneField(Acronym, primary_key=True)
    @property
    def area_acronym(self):
        return Acronym().from_object(self)
    
    #start_date = models.DateField(auto_now_add=True)
    #concluded_date = models.DateField(null=True, blank=True)
    #status = models.ForeignKey(AreaStatus)
    @property
    def status_id(self):
        return { "active": 1, "dormant": 2, "conclude": 3, "proposed": 4 }[self.state_id]
    #comments = models.TextField(blank=True)
    #last_modified_date = models.DateField(auto_now=True)
    @property
    def last_modified_date(self):
        return self.time.date()
    #extra_email_addresses = models.TextField(blank=True,null=True)

    #def additional_urls(self):
    #    return AreaWGURL.objects.filter(name=self.area_acronym.name)
    def active_wgs(self):
        return IETFWG.objects.filter(type="wg", state="active", parent=self).select_related('type', 'state', 'parent').order_by("acronym")

    @property
    def areadirector_set(self):
        return proxied_role_emails(Email.objects.filter(role__group=self, role__name="ad"))
    
    @staticmethod
    def active_areas():
        return Area.objects.filter(type="area", state="active").select_related('type', 'state', 'parent').order_by('acronym')

    def __str__(self):
        return self.acronym
    def __unicode__(self):
        return self.acronym
    
    class Meta:
        proxy = True

def proxied_role_emails(emails):
    for e in emails:
        proxy_role_email(e)
    return emails

class IETFWG(Group):
    objects = TranslatingManager(dict(group_acronym="id",
                                      group_acronym__acronym="acronym",
                                      group_acronym__acronym__in="acronym__in",
                                      group_acronym__acronym__contains="acronym__contains",
                                      email_archive__startswith="list_archive__startswith",
                                      group_type=lambda v: ("type", { 1: "wg" }[int(v)]),
                                      status=lambda v: ("state__in", { 1: ("active", "bof") }[int(v)]),
                                      areagroup__area__status=lambda v: ("parent__state", { 1: "active" }[v]),
                                      start_date__isnull=lambda v: None if v else ("groupevent__changestategroupevent__state__slug", "active"),
                                      ),
                                 always_filter=dict(type__in=("wg", "individ", "area")))

    def from_object(self, base):
        for f in base._meta.fields:
            setattr(self, f.name, getattr(base, f.name))
        return self

    ACTIVE=1
    #group_acronym = models.OneToOneField(Acronym, primary_key=True, editable=False)
    @property
    def group_acronym(self):
        return Acronym().from_object(self)
    
    #group_type = models.ForeignKey(WGType)
    #proposed_date = models.DateField(null=True, blank=True)
    #start_date = models.DateField(null=True, blank=True)
    @property
    def start_date(self):
        e = GroupEvent.objects.filter(group=self, type="changed_state", changestategroupevent__state="active").order_by('time')[:1]
        return e[0].time.date() if e else None
        
    #dormant_date = models.DateField(null=True, blank=True)
    #concluded_date = models.DateField(null=True, blank=True)
    #status = models.ForeignKey(WGStatus)
    @property
    def status_id(self):
        return { "active": 1, "dormant": 2, "conclude": 3, "proposed": 4, "bof": 4, }[self.state_id]
    #area_director = models.ForeignKey(AreaDirector, null=True)
    #meeting_scheduled = models.CharField(blank=True, max_length=3)
    @property
    def meeting_scheduled(self):
        from ietf.meeting.models import Meeting
        latest_meeting = Meeting.objects.order_by('-date')[0]
        return "YES" if self.session_set.filter(meeting=latest_meeting) else "NO"
    #email_address = models.CharField(blank=True, max_length=60)
    @property
    def email_address(self):
        return self.list_email
    #email_subscribe = models.CharField(blank=True, max_length=120)
    @property
    def email_subscribe(self):
        return self.list_subscribe
    #email_keyword = models.CharField(blank=True, max_length=50)
    #email_archive = models.CharField(blank=True, max_length=95)
    @property
    def email_archive(self):
        return self.list_archive
    #comments = models.TextField(blank=True)
    #last_modified_date = models.DateField()
    @property
    def last_modified_date(self):
        return self.time.date()
    #meeting_scheduled_old = models.CharField(blank=True, max_length=3)
    #area = FKAsOneToOne('areagroup', reverse=True)
    @property
    def area(self):
        if self.parent:
            areagroup = AreaGroup().from_object(self)
            return areagroup
        else:
            return None
    
    def __str__(self):
	return self.group_acronym.acronym

    def __unicode__(self):
	return self.group_acronym.acronym

    def active_drafts(self):
        from ietf.doc.proxy import InternetDraft
	return InternetDraft.objects.filter(group=self, states__type="draft", states__slug="active")
    # def choices():
    #     return [(wg.group_acronym_id, wg.group_acronym.acronym) for wg in IETFWG.objects.all().filter(group_type__type='WG').select_related().order_by('acronym.acronym')]
    # choices = staticmethod(choices)
    def area_acronym(self):
        return Area().from_object(self.parent) if self.parent else None
    def area_directors(self):
        if not self.parent:
            return None
        return proxied_role_emails(sorted(Email.objects.filter(role__group=self.parent, role__name="ad"), key=lambda e: e.person.name_parts()[3]))
    def chairs(self): # return a set of WGChair objects for this work group
        return proxied_role_emails(sorted(Email.objects.filter(role__group=self, role__name="chair"), key=lambda e: e.person.name_parts()[3]))
    # def secretaries(self): # return a set of WGSecretary objects for this group
    #     return WGSecretary.objects.filter(group_acronym__exact=self.group_acronym)
    # def milestones(self): # return a set of GoalMilestone objects for this group
    #     return GoalMilestone.objects.filter(group_acronym__exact=self.group_acronym)
    # def rfcs(self): # return a set of Rfc objects for this group
    #     return Rfc.objects.filter(group_acronym__exact=self.group_acronym)
    # def drafts(self): # return a set of Rfc objects for this group
    #     return InternetDraft.objects.filter(group__exact=self.group_acronym)
    def charter_text(self): # return string containing WG description read from file
        from ietf.group.utils import get_charter_text
        return get_charter_text(self)
    def additional_urls(self):
        return self.groupurl_set.all().order_by("name")
    def clean_email_archive(self):
        return self.list_archive
    @property
    def wgchair_set(self):
        # gross hack ...
        class Dummy: pass
        d = Dummy()
        d.all = self.chairs
        return d
    @property
    def wgdelegate_set(self):
        from ietf.wgchairs.models import WGDelegate
        return WGDelegate.objects.filter(group=self, name="delegate")
    
    class Meta:
        proxy = True

class IRTF(Group):
    objects = TranslatingManager(dict(),
                                 always_filter=dict(type="rg"))

    #irtf_id = models.AutoField(primary_key=True)
    @property
    def irtf_id(self):
        return self.pk
    #acronym = models.CharField(blank=True, max_length=25, db_column='irtf_acronym') # same name
    #name = models.CharField(blank=True, max_length=255, db_column='irtf_name') # same name
    #charter_text = models.TextField(blank=True,null=True)
    #meeting_scheduled = models.BooleanField(blank=True)
    def __str__(self):
	return self.acronym
    def __unicode__(self):
	return self.acronym
    #def chairs(self): # return a set of IRTFChair objects for this work group
    #    return IRTFChair.objects.filter(irtf=self)
    class Meta:
        proxy = True

class AreaGroup(Group):
    objects = TranslatingManager(dict(group=lambda v: ("pk", v.pk)),
                                 always_filter=dict(type="wg"))

    def from_object(self, base):
        for f in base._meta.fields:
            setattr(self, f.name, getattr(base, f.name))
        return self

    @property
    def area(self):
        return Area().from_object(self.parent)

    @property
    def group(self):
        return self

    class Meta:
        proxy = True
