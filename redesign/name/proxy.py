from redesign.proxy_utils import TranslatingManager
from models import *

class IDSubStateManager(TranslatingManager):
    def __init__(self, *args):
        super(IDSubStateManager, self).__init__(*args)
        
    def all(self):
        return self.filter(slug__in=['extpty', 'need-rev', 'ad-f-up', 'point'])
        
class IDSubState(DocTagName):
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


class AnnotationTagObjectRelationProxy(DocTagName):
    objects = TranslatingManager(dict(annotation_tag__name="name"))

    @property
    def annotation_tag(self):
        return self

    class Meta:
        proxy = True

class StreamProxy(DocStreamName):
    def get_chairs(self):
        from redesign.group.models import Role
        from redesign.proxy_utils import proxy_personify_role
        return [proxy_personify_role(r) for r in Role.objects.filter(group__acronym=self.slug, name="chair")]

    def get_delegates(self):
        from redesign.group.models import Role
        from redesign.proxy_utils import proxy_personify_role
        return [proxy_personify_role(r) for r in Role.objects.filter(group__acronym=self.slug, name="delegate")]

    class Meta:
        proxy = True
