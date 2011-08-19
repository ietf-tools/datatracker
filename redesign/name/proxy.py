from redesign.proxy_utils import TranslatingManager
from models import *

class IDStatus(DocStateName):
    def from_object(self, base):
        for f in base._meta.fields:
            setattr(self, f.name, getattr(base, f.name))
        return self
                
    #status_id = models.AutoField(primary_key=True)
    
    #status = models.CharField(max_length=25, db_column='status_value')
    @property
    def status(self):
        return self.name

    def __unicode__(self):
        return super(self.__class__, self).__unicode__()
    
    class Meta:
        proxy = True

class IDState(IesgDocStateName):
    PUBLICATION_REQUESTED = 10
    LAST_CALL_REQUESTED = 15
    IN_LAST_CALL = 16
    WAITING_FOR_WRITEUP = 18
    WAITING_FOR_AD_GO_AHEAD = 19
    IESG_EVALUATION = 20
    IESG_EVALUATION_DEFER = 21
    APPROVED_ANNOUNCEMENT_SENT = 30
    AD_WATCHING = 42
    DEAD = 99
    DO_NOT_PUBLISH_STATES = (33, 34)
    
    objects = TranslatingManager(dict(pk="order"))
    
    def from_object(self, base):
        for f in base._meta.fields:
            setattr(self, f.name, getattr(base, f.name))
        return self
                
    #document_state_id = models.AutoField(primary_key=True)
    @property
    def document_state_id(self):
        return self.order
        
    #state = models.CharField(max_length=50, db_column='document_state_val')
    @property
    def state(self):
        return self.name
    
    #equiv_group_flag = models.IntegerField(null=True, blank=True) # unused
    #description = models.TextField(blank=True, db_column='document_desc')
    @property
    def description(self):
        return self.desc

    @property
    def nextstate(self):
        # simulate related queryset
        from name.models import get_next_iesg_states
        return IDState.objects.filter(pk__in=[x.pk for x in get_next_iesg_states(self)])
    
    @property
    def next_state(self):
        # simulate IDNextState
        return self

    def __str__(self):
        return self.state

    @staticmethod
    def choices():
	return [(state.slug, state.name) for state in IDState.objects.all()]
    
    class Meta:
        proxy = True
        

class IDSubStateManager(TranslatingManager):
    def __init__(self, *args):
        super(IDSubStateManager, self).__init__(*args)
        
    def all(self):
        return self.filter(slug__in=['extpty', 'need-rev', 'ad-f-up', 'point'])
        
class IDSubState(DocInfoTagName):
    objects = IDSubStateManager(dict(pk="order"))
    
    def from_object(self, base):
        for f in base._meta.fields:
            setattr(self, f.name, getattr(base, f.name))
        return self
                 
    #sub_state_id = models.AutoField(primary_key=True)
    @property
    def sub_state_id(self):
        return self.order
    
    #sub_state = models.CharField(max_length=55, db_column='sub_state_val')
    @property
    def sub_state(self):
        return self.name
    
    #description = models.TextField(blank=True, db_column='sub_state_desc')
    @property
    def description(self):
        return self.desc
    
    def __str__(self):
        return self.sub_state
    
    class Meta:
        proxy = True

